#!/usr/bin/env python3
"""Lab 03: Full RAG Pipeline — SOLUTION"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")
except ImportError:
    pass

import chromadb
from sentence_transformers import SentenceTransformer
from utils.llm import get_llm, ask, describe, LLMConfig

RUNBOOKS = [
    {"id": "RB-001", "title": "CrashLoopBackOff", "severity": "P1",
     "content": """Pod repeatedly starting and crashing in a loop.

Diagnosis:
- kubectl logs <pod> --previous
- kubectl describe pod <pod>
- Common causes: application crash, missing ConfigMap/Secret, OOMKilled on startup

Remediation:
- Fix application error shown in --previous logs
- If missing config: kubectl get configmap/secret -n <namespace>
- Roll back: kubectl rollout undo deployment/<name>"""},

    {"id": "RB-002", "title": "OOMKilled — Container Out of Memory", "severity": "P1",
     "content": """Container killed by kernel for exceeding memory limit (exit code 137).

Diagnosis:
- kubectl describe pod <pod> | grep -A5 "Last State"
- kubectl top pod <pod>

Remediation:
- kubectl set resources deployment <name> -c=<container> --limits=memory=512Mi
- Long term: profile for memory leaks, add Prometheus alert at 85% utilisation"""},

    {"id": "RB-003", "title": "Nginx 502 Bad Gateway", "severity": "P2",
     "content": """Nginx returns 502 when it cannot reach upstream backend.

Diagnosis:
- kubectl get pods -n <namespace>
- kubectl describe pod <backend-pod>
- kubectl describe svc <service-name>  # check selector labels

Common causes: backend pods crashing, readiness probe failing, Service selector typo"""},

    {"id": "RB-004", "title": "Terraform State Lock", "severity": "P2",
     "content": """Terraform state is locked. Check if another pipeline is running.
If stale (> 30 min): terraform force-unlock <LOCK_ID>
WARNING: Only force-unlock if CERTAIN no other process is running — can corrupt state."""},

    {"id": "RB-005", "title": "Node NotReady", "severity": "P1",
     "content": """Node stopped reporting to control plane.

Diagnosis from node (SSH):
- systemctl status kubelet
- journalctl -u kubelet -n 50
- df -h  (disk pressure)
- free -m (memory pressure)

Fix: systemctl restart kubelet, or clear disk: crictl rmi --prune"""},

    {"id": "RB-009", "title": "Database Connection Pool Exhausted", "severity": "P1",
     "content": """Application cannot acquire database connection.

Diagnosis:
- SELECT count(*), state FROM pg_stat_activity GROUP BY state;
- SELECT pid, now()-query_start, query FROM pg_stat_activity WHERE state='idle in transaction' ORDER BY 2 DESC;

Remediation:
1. Kill stale connections: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle in transaction' AND now()-query_start > interval '5 minutes';
2. Increase pool size in application config
3. Long-term: add PgBouncer connection pooler"""},
]

DB_PATH = "./chroma_rag_db"
EMBED_MODEL = "all-MiniLM-L6-v2"


def build_index(model, client) -> chromadb.Collection:
    collection = client.get_or_create_collection(
        name="runbooks_rag",
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() > 0:
        print(f"  Index already exists ({collection.count()} docs). Skipping.")
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


def retrieve(query, collection, model, n_results=3) -> list[dict]:
    query_vec = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_vec,
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "id":      results["ids"][0][i],
            "title":   results["metadatas"][0][i]["title"],
            "score":   1 - results["distances"][0][i],
            "content": results["documents"][0][i],
        }
        for i in range(len(results["ids"][0]))
    ]


def build_prompt(query: str, retrieved_docs: list[dict]) -> tuple[str, str]:
    system = """\
You are an SRE assistant. Answer questions using ONLY the provided runbook content.
Include specific commands from the runbooks in your answer.
If the answer is not covered in the provided runbooks, say:
"I don't have a runbook for this — please check the internal wiki or escalate to the platform team."
Do not use knowledge outside of the provided runbooks."""

    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        context_parts.append(
            f"RUNBOOK {i}: [{doc['id']}] {doc['title']}\n---\n{doc['content']}\n==="
        )
    context = "\n\n".join(context_parts)

    user = f"{context}\n\nQuestion: {query}"
    return system, user


def generate_answer(system, user, llm) -> str:
    return ask(llm, user=user, system=system, max_tokens=512)


def rag_query(query, collection, model, llm, n_results=2, verbose=True) -> dict:
    retrieved = retrieve(query, collection, model, n_results)
    system, user = build_prompt(query, retrieved)
    answer = generate_answer(system, user, llm)
    if verbose:
        print(f"\n  Query: {query}")
        print(f"  Retrieved: {[r['id'] for r in retrieved]}")
        print(f"\n  Answer:\n  {answer}")
    return {"query": query, "retrieved": retrieved, "answer": answer}


def exercise1_basic_rag(collection, model, llm) -> None:
    print("=" * 60)
    print("Exercise 1: Basic RAG Queries")
    print("=" * 60)
    for query in [
        "My pod keeps restarting after every deploy. How do I fix it?",
        "The container was killed with exit code 137. What does that mean?",
        "Terraform says the state file is locked. Can I force it?",
        "The node is showing NotReady. What are the first steps?",
    ]:
        print("\n" + "─" * 55)
        rag_query(query, collection, model, llm)


def exercise2_no_hallucination(collection, model, llm) -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Grounding Prevents Hallucination")
    print("=" * 60)
    for query in [
        "How do I configure ArgoCD for GitOps deployments?",
        "What is the difference between Istio and Linkerd?",
    ]:
        print("\n" + "─" * 55)
        rag_query(query, collection, model, llm)
    print("\n  Observation: Model correctly declines instead of hallucinating.")


def exercise3_compare_with_without_rag(collection, model, llm) -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: RAG vs Vanilla LLM")
    print("=" * 60)
    query = "My database application can't connect — connection pool exhausted. Immediate fix?"
    print(f"\nQuery: {query}")
    print("\n  [RAG answer]")
    rag_query(query, collection, model, llm, verbose=True)
    print("\n  [Vanilla LLM — no context]")
    vanilla = ask(llm, user=query, system="You are a helpful SRE assistant.", max_tokens=300)
    print(f"  {vanilla}")


def exercise4_source_attribution(collection, model, llm) -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Source Attribution")
    print("=" * 60)
    query = "A pod is in CrashLoopBackOff. Walk me through diagnosing it."
    retrieved = retrieve(query, collection, model, n_results=2)
    print(f"\nRetrieved sources:")
    for r in retrieved:
        print(f"  [{r['id']}] {r['title']}  (score: {r['score']:.3f})")

    system_with_citation = """\
You are an SRE assistant. Answer ONLY from the provided runbook content.
End your answer with: "Source: [RB-XXX] Title" for each runbook used."""

    _, user = build_prompt(query, retrieved)
    answer = ask(llm, user=user, system=system_with_citation, max_tokens=512)
    print(f"\n  Answer:\n  {answer}")


def main() -> None:
    print("\nLab 03: Full RAG Pipeline (Solution)\n")
    try:
        llm = get_llm()
        print(f"  LLM backend: {describe(llm)}\n")
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

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
    print("  1. Retrieve → Augment → Generate.")
    print("  2. Grounding prevents hallucination.")
    print("  3. Source attribution builds trust.")
    print("  4. Swappable backends: Anthropic or Ollama.")
    print("=" * 60)


if __name__ == "__main__":
    main()
