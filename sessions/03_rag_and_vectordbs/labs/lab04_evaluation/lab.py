#!/usr/bin/env python3
"""
Lab 04: Retrieval Evaluation — Measure Before You Optimise
===========================================================
You can't improve what you don't measure. In this lab you'll:
- Build a golden dataset (query → expected docs)
- Implement Precision@k, Recall@k, and MRR metrics
- Evaluate two retrieval strategies (semantic vs hybrid)
- Use LLM-as-judge to evaluate end-to-end answer quality

No API key required for the retrieval evaluation.
API key or Ollama required for the LLM-as-judge section.

Run:
    python lab.py

When stuck: check solution.py
"""

import json
import sys
from pathlib import Path

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
    print(f"ERROR: pip install chromadb sentence-transformers")
    sys.exit(1)

from utils.llm import get_llm, ask, describe


# ── Golden dataset ─────────────────────────────────────────────────────────────
# These are the ground-truth query → relevant document mappings.
# In production: derive these from real user queries + manual labelling.

GOLDEN_DATASET = [
    {"query": "container keeps restarting after each deploy",
     "relevant_ids": {"RB-001", "RB-002"}},      # CrashLoopBackOff and OOMKilled
    {"query": "pod was killed because it used too much memory",
     "relevant_ids": {"RB-002"}},                 # OOMKilled specifically
    {"query": "nginx returning 502 errors from load balancer",
     "relevant_ids": {"RB-003"}},                 # Nginx 502
    {"query": "Terraform pipeline is stuck, says state is locked",
     "relevant_ids": {"RB-004"}},                 # Terraform lock
    {"query": "kubernetes node not ready, pods won't schedule",
     "relevant_ids": {"RB-005"}},                 # Node NotReady
    {"query": "cannot pull docker image from registry",
     "relevant_ids": {"RB-006"}},                 # ImagePullBackOff
    {"query": "CPU is being throttled, service is slow",
     "relevant_ids": {"RB-007"}},                 # CPU throttling
    {"query": "AWS S3 access denied, IAM issue",
     "relevant_ids": {"RB-008"}},                 # S3 access
    {"query": "database connections exhausted, application failing",
     "relevant_ids": {"RB-009"}},                 # DB pool
    {"query": "HTTPS broken, certificate error",
     "relevant_ids": {"RB-010"}},                 # Cert expired
    # Hard queries — phrased differently from runbook vocabulary
    {"query": "process killed with exit code 137",
     "relevant_ids": {"RB-002"}},                 # OOMKilled (technical phrase)
    {"query": "infrastructure as code tool can't write to state",
     "relevant_ids": {"RB-004"}},                 # Terraform (generic phrasing)
    {"query": "worker not joining cluster",
     "relevant_ids": {"RB-005"}},                 # Node NotReady (vague)
]

# Runbooks corpus (same as Lab 02 for consistency)
RUNBOOKS = [
    {"id": "RB-001", "title": "CrashLoopBackOff", "severity": "P1",
     "content": "Pod repeatedly starting and crashing. Check kubectl logs --previous. Fix application error or missing ConfigMap/Secret. Rollback with kubectl rollout undo."},
    {"id": "RB-002", "title": "OOMKilled — Container Out of Memory", "severity": "P1",
     "content": "Container killed by kernel (exit code 137) for exceeding memory limit. kubectl describe pod shows OOMKilled. Increase memory limit: kubectl set resources. Profile for memory leaks."},
    {"id": "RB-003", "title": "Nginx 502 Bad Gateway", "severity": "P2",
     "content": "Nginx cannot reach upstream backend. Check backend pods, readiness probes, and Service selector labels. Common cause: backend crashing or failing health checks."},
    {"id": "RB-004", "title": "Terraform State Lock", "severity": "P2",
     "content": "Terraform state locked by previous run. Check for running CI/CD pipelines. If stale: terraform force-unlock. Only force-unlock if certain no other process is running."},
    {"id": "RB-005", "title": "Node NotReady", "severity": "P1",
     "content": "Kubernetes node not scheduling pods. SSH and check: systemctl status kubelet, df -h, free -m. Common causes: kubelet crash, disk full, network partition."},
    {"id": "RB-006", "title": "ImagePullBackOff", "severity": "P2",
     "content": "Cannot pull container image. Check image name, tag, registry credentials in imagePullSecrets. Test: docker pull <image>."},
    {"id": "RB-007", "title": "High CPU Throttling", "severity": "P2",
     "content": "Container hitting CPU limit. container_cpu_throttled_seconds_total growing. Increase CPU limit or scale horizontally."},
    {"id": "RB-008", "title": "AWS S3 Access Denied", "severity": "P2",
     "content": "IAM permissions insufficient for S3 access. Check IAM role, bucket policy. Use aws sts get-caller-identity to confirm identity."},
    {"id": "RB-009", "title": "Database Connection Pool Exhausted", "severity": "P1",
     "content": "Application cannot acquire database connection. Check pg_stat_activity. Increase pool size or add PgBouncer connection pooler."},
    {"id": "RB-010", "title": "TLS Certificate Expired", "severity": "P1",
     "content": "TLS certificate expired causing HTTPS failures. Check cert-manager logs. Renew via Let's Encrypt or CA. Update Kubernetes Secret."},
    {"id": "RB-011", "title": "Persistent Volume Claim Pending", "severity": "P2",
     "content": "PVC stuck in Pending. Check StorageClass exists. Verify CSI driver running. kubectl describe pvc for events."},
    {"id": "RB-012", "title": "HPA Not Scaling", "severity": "P2",
     "content": "HPA not triggering scale-up. Check metrics-server running. Verify CPU requests set on pods. kubectl describe hpa for events."},
]

DB_PATH = "./chroma_eval_db"
EMBED_MODEL = "all-MiniLM-L6-v2"


# ── Retrieval metrics ──────────────────────────────────────────────────────────

def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of top-k retrieved docs that are relevant."""
    # TODO 1: Implement precision@k.
    # top_k = retrieved_ids[:k]
    # return (number of top_k docs in relevant_ids) / k
    pass


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of all relevant docs that appear in top-k."""
    # TODO 2: Implement recall@k.
    # If relevant_ids is empty, return 1.0
    # top_k = set(retrieved_ids[:k])
    # return len(top_k & relevant_ids) / len(relevant_ids)
    pass


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """1/rank of the first relevant result (0 if none found)."""
    # TODO 3: Implement reciprocal rank.
    # For i, doc_id in enumerate(retrieved_ids, start=1):
    #     if doc_id in relevant_ids: return 1.0 / i
    # return 0.0
    pass


# ── Retrieval systems ──────────────────────────────────────────────────────────

def build_vector_index(model: SentenceTransformer) -> chromadb.Collection:
    """Build ChromaDB index for evaluation."""
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_or_create_collection(
        name="eval_runbooks",
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() == 0:
        texts = [f"{rb['title']}. {rb['content']}" for rb in RUNBOOKS]
        embeddings = model.encode(texts).tolist()
        collection.upsert(
            ids=[rb["id"] for rb in RUNBOOKS],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"title": rb["title"]} for rb in RUNBOOKS],
        )
    return collection


def semantic_search(
    query: str,
    collection: chromadb.Collection,
    model: SentenceTransformer,
    k: int = 5,
) -> list[str]:
    """Pure semantic (embedding) search. Returns list of doc IDs, best first."""
    query_vec = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_vec,
        n_results=min(k, collection.count()),
        include=["metadatas"],
    )
    return results["ids"][0]


def keyword_search(query: str, k: int = 5) -> list[str]:
    """BM25-like keyword overlap search. Returns list of doc IDs, best first."""
    query_words = set(query.lower().split())
    scored = []
    for rb in RUNBOOKS:
        text = f"{rb['title']} {rb['content']}".lower()
        words = set(text.split())
        overlap = len(query_words & words)
        if overlap > 0:
            scored.append((overlap, rb["id"]))
    scored.sort(reverse=True)
    return [doc_id for _, doc_id in scored[:k]]


def hybrid_search(
    query: str,
    collection: chromadb.Collection,
    model: SentenceTransformer,
    k: int = 5,
    alpha: float = 0.7,
) -> list[str]:
    """Hybrid search: combine semantic score (alpha) + keyword score (1-alpha).

    alpha=1.0 → pure semantic, alpha=0.0 → pure keyword
    Returns list of doc IDs, best first.
    """
    # TODO 4: Implement hybrid search.
    # Steps:
    #   1. Get semantic scores from ChromaDB for all docs (n_results = len(RUNBOOKS))
    #   2. Get keyword overlap counts for all docs
    #   3. Normalise both scores to [0,1]
    #   4. Combine: score = alpha * semantic_score + (1-alpha) * keyword_score
    #   5. Return top-k doc IDs sorted by combined score
    pass


# ── Evaluation harness ─────────────────────────────────────────────────────────

def evaluate_retrieval(
    name: str,
    search_fn,
    k: int = 3,
) -> dict:
    """Evaluate a retrieval function against the golden dataset.

    Returns dict with average precision@k, recall@k, and MRR.
    """
    # TODO 5: For each entry in GOLDEN_DATASET:
    #   1. Call search_fn(entry["query"]) to get retrieved_ids
    #   2. Compute precision_at_k, recall_at_k, reciprocal_rank
    #   3. Average all metrics across the dataset
    # Return {"name": ..., "precision_at_k": ..., "recall_at_k": ..., "mrr": ..., "k": k}
    pass


# ── LLM-as-judge ──────────────────────────────────────────────────────────────

def llm_judge_answer(
    question: str,
    context: str,
    answer: str,
    llm,
) -> dict:
    """Use LLM to evaluate a RAG-generated answer.

    Returns {"faithfulness": 0-3, "relevance": 0-3, "completeness": 0-3}
    """
    # TODO 6: Implement LLM-as-judge.
    # Prompt the LLM to rate the answer on 3 dimensions (each 0-3):
    #   - faithfulness: is the answer grounded in the context?
    #   - relevance: does it answer the question?
    #   - completeness: does it cover the key info?
    # Output JSON. Parse and return the dict.
    # If JSON parse fails, return {"faithfulness": -1, "relevance": -1, "completeness": -1}
    pass


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 04: Retrieval Evaluation\n")

    model = SentenceTransformer(EMBED_MODEL)
    collection = build_vector_index(model)
    print(f"  Index: {collection.count()} runbooks\n")

    k = 3

    # ── Retrieval evaluation ──────────────────────────────────────────────────
    print("=" * 60)
    print(f"Retrieval Evaluation (k={k})")
    print("=" * 60)

    # Semantic search
    sem_results = evaluate_retrieval(
        "Semantic",
        lambda q: semantic_search(q, collection, model, k=k),
        k=k,
    )

    # Keyword search
    kw_results = evaluate_retrieval(
        "Keyword",
        lambda q: keyword_search(q, k=k),
        k=k,
    )

    # Hybrid search (if TODO 4 complete)
    hybrid_results = evaluate_retrieval(
        "Hybrid (α=0.7)",
        lambda q: hybrid_search(q, collection, model, k=k, alpha=0.7) or semantic_search(q, collection, model, k=k),
        k=k,
    )

    # Print results table
    if all(r is not None for r in [sem_results, kw_results]):
        print(f"\n{'Strategy':<20} {'Precision@' + str(k):>13} {'Recall@' + str(k):>10} {'MRR':>8}")
        print("─" * 55)
        for r in [sem_results, kw_results, hybrid_results]:
            if r:
                print(f"{r['name']:<20} {r['precision_at_k']:>13.3f} {r['recall_at_k']:>10.3f} {r['mrr']:>8.3f}")
    else:
        print("  Complete TODO 5 to see evaluation results.")

    # ── Hard query analysis ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Hard Queries Analysis")
    print("=" * 60)

    hard_queries = [
        {"query": "process killed with exit code 137", "relevant_ids": {"RB-002"}},
        {"query": "infrastructure as code tool can't write to state", "relevant_ids": {"RB-004"}},
        {"query": "worker not joining cluster", "relevant_ids": {"RB-005"}},
    ]

    for item in hard_queries:
        q = item["query"]
        rel = item["relevant_ids"]
        sem = semantic_search(q, collection, model, k=k)
        kw = keyword_search(q, k=k)

        sem_p = precision_at_k(sem, rel, k) if precision_at_k else None
        kw_p = precision_at_k(kw, rel, k) if precision_at_k else None

        print(f"\n  Query: '{q}'")
        print(f"  Expected: {rel}")
        print(f"  Semantic top-3: {sem[:3]}  P@3={sem_p:.2f}" if sem_p is not None else f"  Semantic top-3: {sem[:3]}")
        print(f"  Keyword  top-3: {kw[:3]}  P@3={kw_p:.2f}" if kw_p is not None else f"  Keyword  top-3: {kw[:3]}")

    # ── LLM-as-judge ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("LLM-as-Judge Evaluation")
    print("=" * 60)

    try:
        llm = get_llm()
        print(f"  Using: {describe(llm)}")
    except RuntimeError:
        print("  No LLM available — skipping LLM-as-judge section.")
        print("  (Add ANTHROPIC_API_KEY to .env or start Ollama)")
        return

    # Test cases: (question, context, answer to evaluate)
    test_evaluations = [
        {
            "question": "How do I fix a pod in CrashLoopBackOff?",
            "context": "Check kubectl logs --previous. Fix application error. Roll back with kubectl rollout undo.",
            "good_answer": "Run kubectl logs <pod> --previous to see the crash reason. Fix the application error shown, or roll back with kubectl rollout undo deployment/<name>.",
            "bad_answer": "The pod is probably out of memory. Increase RAM on the server.",
        },
    ]

    for test in test_evaluations:
        print(f"\n  Question: {test['question']}")
        for label, answer in [("Good answer", test["good_answer"]), ("Bad answer", test["bad_answer"])]:
            scores = llm_judge_answer(test["question"], test["context"], answer, llm)
            if scores and scores.get("faithfulness", -1) >= 0:
                total = sum(scores[k] for k in ["faithfulness", "relevance", "completeness"])
                print(f"\n  {label}: (total={total}/9)")
                print(f"    Faithfulness: {scores['faithfulness']}/3  Relevance: {scores['relevance']}/3  Completeness: {scores['completeness']}/3")
            else:
                print(f"  {label}: (complete TODO 6 to see scores)")

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. Semantic beats keyword on paraphrased queries.")
    print("  2. Hybrid search wins overall — precision of semantic + recall of keyword.")
    print("  3. LLM-as-judge catches hallucinations that retrieval metrics miss.")
    print("=" * 60)


if __name__ == "__main__":
    main()
