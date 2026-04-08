#!/usr/bin/env python3
"""
Lab 03: Full RAG Pipeline — Retrieve, Augment, Generate
=========================================================
Wire everything together: vector search + LLM generation.
The LLM is answered ONLY from retrieved runbook content — not its training data.

Backend auto-selection:
  - If ANTHROPIC_API_KEY is set → uses Claude (fast, high quality)
  - Otherwise → uses Ollama (local, free, no data leaves your machine)

Prerequisites:
    pip install chromadb sentence-transformers
    # One of:
    pip install anthropic          # + add ANTHROPIC_API_KEY to .env
    ollama pull llama3.2           # OR install Ollama and pull a model

Run:
    python lab.py

When stuck: check solution.py
"""

import json
import os
import re
import sys
from pathlib import Path

# Add parent dir to path so we can import utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")
except ImportError:
    pass

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"ERROR: Missing package — {e}\npip install chromadb sentence-transformers")
    sys.exit(1)

from utils.llm import get_llm, ask, describe, LLMConfig


# ── Runbook corpus ─────────────────────────────────────────────────────────────
# Richer content than Lab 02 — more context for the LLM to work with.

RUNBOOKS = [
    {"id": "RB-001", "title": "CrashLoopBackOff", "severity": "P1",
     "content": """Pod repeatedly starting and crashing in a loop.

Diagnosis:
- kubectl logs <pod> --previous  # logs from the crashed container
- kubectl describe pod <pod>     # check Events section for crash reason
- Common causes: application panic/crash, missing ConfigMap or Secret,
  failed health checks, OOMKilled on startup

Remediation:
- Fix the application error shown in --previous logs
- If missing config: kubectl get configmap/secret -n <namespace>
- If OOMKilled on startup: increase memory limit
- Roll back recent deployment: kubectl rollout undo deployment/<name>"""},

    {"id": "RB-002", "title": "OOMKilled — Container Out of Memory", "severity": "P1",
     "content": """Container killed by kernel for exceeding memory limit (exit code 137).

Diagnosis:
- kubectl describe pod <pod> | grep -A5 "Last State"  # shows OOMKilled
- kubectl top pod <pod>                                 # current memory usage
- Check memory limit: kubectl get pod <pod> -o jsonpath='{.spec.containers[*].resources}'

Remediation (short term):
- Increase memory limit:
  kubectl set resources deployment <name> -c=<container> --limits=memory=512Mi
- Or edit deployment YAML: resources.limits.memory: "512Mi"

Remediation (long term):
- Profile for memory leaks: heap profiler for your language/runtime
- Check for unclosed connections, unbounded queues, growing caches
- Add Prometheus alert: container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85"""},

    {"id": "RB-003", "title": "Nginx 502 Bad Gateway", "severity": "P2",
     "content": """Nginx returns 502 when it cannot reach the upstream backend service.

Diagnosis:
- Check backend pod status: kubectl get pods -n <namespace>
- Check backend pod readiness: kubectl describe pod <backend-pod>
- Check nginx error logs: kubectl logs <nginx-pod> | grep error
- Verify Service exists: kubectl get svc -n <namespace>
- Verify Service selector: kubectl describe svc <service-name>
  (selector labels must match pod labels)

Common causes:
- Backend pods in CrashLoopBackOff or OOMKilled
- Backend failing readiness probe (not yet ready, excluded from Service)
- Service selector typo (wrong label key/value)
- Backend listening on wrong port

Remediation:
- Fix the backend pod issue first (see CrashLoopBackOff or OOMKilled runbooks)
- If selector mismatch: kubectl edit svc <name> to fix labels"""},

    {"id": "RB-004", "title": "Terraform State Lock", "severity": "P2",
     "content": """Terraform state is locked, preventing plan/apply.

Diagnosis:
- Error message contains the Lock ID and the process that created it
- Check: is another CI/CD pipeline running with this Terraform workspace?
- Check lock age: if > 30 minutes, likely stale

Remediation:
1. Safe path: Wait for the locking process to complete
2. Force unlock (ONLY if certain no other process is running):
   terraform force-unlock <LOCK_ID>
   WARNING: Force-unlocking while another process writes state corrupts state.

Verify no pipeline is running before force-unlock:
- Check GitLab/GitHub Actions for running pipelines
- Check Terraform Cloud/Atlantis for active runs

Prevention:
- Set pipeline timeouts: jobs should fail after 30 minutes max
- Use Terraform Cloud or Atlantis for managed state locking
- Monitor: alert if lock held > 20 minutes"""},

    {"id": "RB-005", "title": "Node NotReady", "severity": "P1",
     "content": """Kubernetes node stopped reporting to the control plane.

Diagnosis (from control plane):
- kubectl describe node <node-name>  # check Conditions and Events
- kubectl get events --field-selector involvedObject.name=<node>

Diagnosis (SSH to node):
- systemctl status kubelet           # is kubelet running?
- journalctl -u kubelet -n 50       # kubelet logs
- df -h                              # disk pressure?
- free -m                            # memory pressure?
- ping <control-plane-ip>            # network reachable?

Common causes:
- Kubelet crashed: systemctl restart kubelet
- Disk full: clear old container images: crictl rmi --prune
- Memory exhaustion: check for memory-hungry pods
- Certificate expiry: kubelet client cert expired
- Network partition: check node network config, security groups"""},

    {"id": "RB-009", "title": "Database Connection Pool Exhausted", "severity": "P1",
     "content": """Application cannot acquire a database connection; pool is full.

Diagnosis:
- Check active connections: SELECT count(*), state FROM pg_stat_activity GROUP BY state;
- Identify idle connections holding slots: SELECT pid, now()-query_start, query FROM pg_stat_activity WHERE state='idle in transaction' ORDER BY 2 DESC;
- Check application pool config: usually in DATABASE_POOL_SIZE env var or config file

Remediation (immediate):
1. Kill idle-in-transaction connections (use with care):
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle in transaction' AND now()-query_start > interval '5 minutes';
2. Increase pool size in application config (requires restart)
3. Scale application replicas DOWN temporarily to reduce total connections

Remediation (long term):
- Add PgBouncer connection pooler (recommended for production)
- Set application connection pool to max_connections / (num_replicas * 2)
- Add alert: connections > 80% of max_connections"""},
]

DB_PATH = "./chroma_rag_db"
EMBED_MODEL = "all-MiniLM-L6-v2"


# ── Pipeline components ────────────────────────────────────────────────────────

def build_index(
    model: SentenceTransformer,
    client: chromadb.PersistentClient,
) -> chromadb.Collection:
    """Build the vector index from RUNBOOKS. Returns the collection."""
    collection = client.get_or_create_collection(
        name="runbooks_rag",
        metadata={"hnsw:space": "cosine"},
    )

    # Only re-index if collection is empty
    if collection.count() > 0:
        print(f"  Index already exists ({collection.count()} docs). Skipping re-index.")
        return collection

    texts = [f"{rb['title']}\n\n{rb['content']}" for rb in RUNBOOKS]
    embeddings = model.encode(texts).tolist()
    collection.upsert(
        ids=[rb["id"] for rb in RUNBOOKS],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"title": rb["title"], "severity": rb["severity"]} for rb in RUNBOOKS],
    )
    print(f"  Indexed {len(RUNBOOKS)} runbooks.")
    return collection


def retrieve(
    query: str,
    collection: chromadb.Collection,
    model: SentenceTransformer,
    n_results: int = 3,
) -> list[dict]:
    """Retrieve top-n relevant chunks for a query.

    Returns list of {"id", "title", "score", "content"} dicts.
    """
    # TODO 1: Embed the query and search the collection.
    # Steps:
    #   1. Embed: query_vec = model.encode([query]).tolist()
    #   2. Query: collection.query(query_embeddings=query_vec, n_results=n_results,
    #                              include=["documents", "metadatas", "distances"])
    #   3. Return list of dicts: {"id", "title", "score": 1-distance, "content": document}
    pass


def build_prompt(query: str, retrieved_docs: list[dict]) -> tuple[str, str]:
    """Build system + user message for the RAG generation step.

    Returns (system_prompt, user_message).
    The system prompt grounds the model in the retrieved context.
    """
    # TODO 2: Build the augmented prompt.
    #
    # system_prompt:
    #   - Role: SRE assistant
    #   - Instruction: answer ONLY using the provided runbooks
    #   - If info not in runbooks: say "I don't have a runbook for this"
    #   - Output format: brief answer + specific commands
    #
    # user_message:
    #   - Include the retrieved runbook content clearly labeled
    #   - Then the question
    #
    # Format:
    #   RUNBOOK 1: [RB-001] CrashLoopBackOff
    #   ---
    #   <content>
    #   ===
    #   RUNBOOK 2: ...
    #   ===
    #
    #   Question: <query>
    pass


def generate_answer(
    system: str,
    user: str,
    llm: LLMConfig,
) -> str:
    """Call the LLM and return the answer text."""
    # TODO 3: Call ask(llm, user=user, system=system, max_tokens=512)
    # Return the response string.
    pass


def rag_query(
    query: str,
    collection: chromadb.Collection,
    model: SentenceTransformer,
    llm: LLMConfig,
    n_results: int = 2,
    verbose: bool = True,
) -> dict:
    """Full RAG pipeline: retrieve → augment → generate.

    Returns {"query", "retrieved", "answer"}
    """
    # Retrieve
    retrieved = retrieve(query, collection, model, n_results)

    if retrieved is None:
        return {"query": query, "retrieved": [], "answer": "(TODO 1 not complete)"}

    # Build augmented prompt
    system, user = build_prompt(query, retrieved)

    if system is None:
        return {"query": query, "retrieved": retrieved, "answer": "(TODO 2 not complete)"}

    # Generate
    answer = generate_answer(system, user, llm)

    if verbose:
        print(f"\n  Query: {query}")
        print(f"  Retrieved: {[r['id'] for r in retrieved]}")
        print(f"\n  Answer:\n  {answer}")

    return {"query": query, "retrieved": retrieved, "answer": answer}


# ── Exercises ──────────────────────────────────────────────────────────────────

def exercise1_basic_rag(collection, model, llm) -> None:
    print("=" * 60)
    print("Exercise 1: Basic RAG Queries")
    print("=" * 60)

    queries = [
        "My pod keeps restarting after every deploy. How do I fix it?",
        "The container was killed and I see exit code 137. What does that mean and what should I do?",
        "Terraform says the state file is locked. Can I force it?",
        "The node is showing NotReady. What are the first steps?",
    ]

    for query in queries:
        print("\n" + "─" * 55)
        rag_query(query, collection, model, llm)


def exercise2_no_hallucination(collection, model, llm) -> None:
    """Exercise 2: Ask about something NOT in the runbooks.

    The model should say it doesn't have a runbook — not hallucinate an answer.
    """
    print("\n" + "=" * 60)
    print("Exercise 2: Grounding Prevents Hallucination")
    print("=" * 60)

    # These topics are NOT in our runbook corpus
    out_of_scope = [
        "How do I configure ArgoCD for GitOps deployments?",
        "What is the difference between Istio and Linkerd?",
    ]

    for query in out_of_scope:
        print("\n" + "─" * 55)
        result = rag_query(query, collection, model, llm)

    print("\n  Observation: The model should say it has no runbook for these topics.")
    print("  Without RAG grounding, it would invent an answer from training data.")


def exercise3_compare_with_without_rag(collection, model, llm) -> None:
    """Exercise 3: Compare RAG answer vs non-RAG (vanilla LLM) answer.

    The RAG answer should be more specific (exact kubectl commands from our runbooks).
    The vanilla LLM answer may be accurate but generic.
    """
    print("\n" + "=" * 60)
    print("Exercise 3: RAG vs Vanilla LLM")
    print("=" * 60)

    query = "My database application can't connect — connection pool exhausted. Immediate fix?"

    print(f"\nQuery: {query}")

    # RAG answer
    print("\n  [RAG answer — grounded in our runbooks]")
    result = rag_query(query, collection, model, llm, verbose=True)

    # Vanilla LLM answer (no context)
    print("\n  [Vanilla LLM — from training data only]")
    vanilla_system = "You are a helpful SRE assistant. Answer questions about infrastructure."
    vanilla_answer = ask(llm, user=query, system=vanilla_system, max_tokens=300)
    print(f"  {vanilla_answer}")

    print("\n  Observe: RAG answer references your specific runbook's exact SQL commands.")
    print("  Vanilla answer is generic — no organisation-specific procedures.")


def exercise4_source_attribution(collection, model, llm) -> None:
    """Exercise 4: Return source citations with the answer."""
    print("\n" + "=" * 60)
    print("Exercise 4: Source Attribution")
    print("=" * 60)

    # TODO 4: Modify the build_prompt function (or create a variant)
    # to instruct the model to end its answer with:
    # "Source: [RB-XXX] Title"
    # Then run a query and verify the source citation appears.

    query = "A pod is in CrashLoopBackOff. Walk me through diagnosing it."
    print(f"\nQuery: {query}")

    # For now, just show retrieved sources manually
    retrieved = retrieve(query, collection, model, n_results=2)
    if retrieved:
        print("\n  Retrieved sources:")
        for r in retrieved:
            print(f"    [{r['id']}] {r['title']}  (relevance: {r['score']:.3f})")

    system_with_citation = """\
You are an SRE assistant. Answer questions using ONLY the provided runbook content.
At the end of your answer, add: "Source: [RB-XXX] Runbook Title" for each runbook you used.
If the answer is not in the runbooks, say "I don't have a runbook for this." """

    if retrieved:
        _, user = build_prompt(query, retrieved) if build_prompt(query, retrieved) else (None, None)
        if user:
            answer = ask(llm, user=user, system=system_with_citation, max_tokens=512)
            print(f"\n  Answer with citations:\n  {answer}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 03: Full RAG Pipeline\n")

    # Detect available LLM backend
    try:
        llm = get_llm()
        print(f"  LLM backend: {describe(llm)}\n")
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Setup vector store
    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=DB_PATH)
    print("Building index...")
    collection = build_index(model, client)

    exercise1_basic_rag(collection, model, llm)
    exercise2_no_hallucination(collection, model, llm)
    exercise3_compare_with_without_rag(collection, model, llm)
    exercise4_source_attribution(collection, model, llm)

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. Retrieve → Augment → Generate: the three steps of RAG.")
    print("  2. Grounding prevents hallucination — model only uses what you give it.")
    print("  3. Source attribution builds trust and enables post-mortem review.")
    print("  4. Same code, swappable backend: Anthropic or Ollama via utils/llm.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
