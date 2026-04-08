#!/usr/bin/env python3
"""
Lab 02: ChromaDB — Build a Searchable Runbook Index
=====================================================
Index a corpus of runbooks into ChromaDB and search it with semantic queries.
This is the indexing phase of a RAG system — once this index is built,
Lab 03 will wire a generation step on top.

No API key required. No Ollama required. Runs entirely offline.

Prerequisites:
    pip install chromadb sentence-transformers

Run:
    python lab.py

When stuck: check solution.py
"""

import re
import sys
from pathlib import Path

try:
    import chromadb
except ImportError:
    print("ERROR: pip install chromadb")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: pip install sentence-transformers")
    sys.exit(1)


# ── Runbook corpus ─────────────────────────────────────────────────────────────
# 12 runbooks covering common K8s, networking, AWS, and database issues.

RUNBOOKS = [
    {"id": "RB-001", "title": "CrashLoopBackOff", "team": "platform", "severity": "P1",
     "content": "Pod repeatedly starting and crashing. Check kubectl logs --previous for crash reason. Common causes: application error, missing ConfigMap/Secret, or OOMKilled. Fix the error or increase memory limits. Check events: kubectl describe pod <name>."},
    {"id": "RB-002", "title": "OOMKilled — Container Out of Memory", "team": "platform", "severity": "P1",
     "content": "Container exceeded memory limit and was killed by kernel (exit code 137). Check kubectl describe pod for OOMKilled status. Short term: increase memory limit in pod spec. Long term: profile the application for memory leaks. Alert at 80% memory utilisation."},
    {"id": "RB-003", "title": "Nginx 502 Bad Gateway", "team": "platform", "severity": "P2",
     "content": "Nginx cannot reach the upstream backend service. Verify backend pods are Running and passing readiness probes. Check nginx error logs and upstream service logs. Verify Service selector matches pod labels. Check if upstream is listening on the correct port."},
    {"id": "RB-004", "title": "Terraform State Lock", "team": "infra", "severity": "P2",
     "content": "Terraform state is locked by a previous run. Get the lock ID from the error message. Verify no other Terraform process is running in CI/CD. If stale: terraform force-unlock <LOCK_ID>. Prevention: configure DynamoDB locking and pipeline timeouts."},
    {"id": "RB-005", "title": "Node NotReady", "team": "platform", "severity": "P1",
     "content": "Kubernetes node not scheduling pods. SSH to node, check: systemctl status kubelet, journalctl -u kubelet, df -h (disk pressure), free -m (memory). Common causes: kubelet crash, disk full, network partition, certificate expiry."},
    {"id": "RB-006", "title": "ImagePullBackOff", "team": "platform", "severity": "P2",
     "content": "Kubernetes cannot pull the container image. Check image name and tag are correct. Verify registry credentials in imagePullSecrets. Test: docker pull <image>. Check registry is accessible from the cluster. Ensure image exists in the registry."},
    {"id": "RB-007", "title": "High CPU Throttling", "team": "platform", "severity": "P2",
     "content": "Container hitting CPU limit, causing throttled_time to grow. Check container_cpu_throttled_seconds_total in Prometheus. Options: increase CPU limit, optimise application code, or scale horizontally. Check for blocking synchronous calls that should be async."},
    {"id": "RB-008", "title": "AWS S3 Access Denied", "team": "infra", "severity": "P2",
     "content": "IAM permissions insufficient to access S3 bucket. Check IAM role on EC2 or EKS pod service account. Verify bucket policy does not explicitly deny. Use aws sts get-caller-identity to confirm identity. Check S3 bucket region matches request region."},
    {"id": "RB-009", "title": "Database Connection Pool Exhausted", "team": "backend", "severity": "P1",
     "content": "Application cannot acquire database connection. Check pg_stat_activity for active connections. Immediate: increase max_connections or pool size. Long-term: add PgBouncer connection pooler. Monitor: connection pool utilisation alert at 70%."},
    {"id": "RB-010", "title": "TLS Certificate Expired", "team": "platform", "severity": "P1",
     "content": "TLS certificate expired causing HTTPS failures. Check cert-manager logs if using cert-manager. Inspect certificate: openssl s_client -connect host:443. Renew via Let's Encrypt or CA, update Kubernetes Secret. Prevention: certificate expiry alert 30 days before expiry."},
    {"id": "RB-011", "title": "Persistent Volume Claim Pending", "team": "platform", "severity": "P2",
     "content": "PVC stuck in Pending state. Check kubectl describe pvc for events. Common causes: StorageClass not found, no available PV, quota exceeded. For dynamic provisioning: check CSI driver is running. Verify storage class exists: kubectl get storageclass."},
    {"id": "RB-012", "title": "HPA Not Scaling", "team": "platform", "severity": "P2",
     "content": "Horizontal Pod Autoscaler not triggering scale-up. Check kubectl describe hpa for events. Common causes: metrics-server not running, no CPU requests set on pods, wrong metric selector. Verify: kubectl top pods is working. Check HPA target CPU threshold."},
]

DB_PATH = "./chroma_lab_db"
COLLECTION_NAME = "runbooks"
EMBED_MODEL = "all-MiniLM-L6-v2"


# ── Setup ──────────────────────────────────────────────────────────────────────

def load_embedding_model() -> SentenceTransformer:
    print(f"Loading embedding model '{EMBED_MODEL}'...")
    return SentenceTransformer(EMBED_MODEL)


def get_chroma_client() -> chromadb.PersistentClient:
    # TODO 1: Create and return a ChromaDB PersistentClient.
    # Use path=DB_PATH so data persists between runs.
    # Hint: chromadb.PersistentClient(path=DB_PATH)
    pass


def get_or_create_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    # TODO 2: Get or create a collection named COLLECTION_NAME.
    # Use cosine similarity: metadata={"hnsw:space": "cosine"}
    # Hint: client.get_or_create_collection(name=..., metadata=...)
    pass


# ── Indexing ───────────────────────────────────────────────────────────────────

def index_runbooks(
    collection: chromadb.Collection,
    model: SentenceTransformer,
) -> int:
    """Embed and index all runbooks. Returns number of docs indexed."""
    # TODO 3: Embed and upsert all runbooks into the collection.
    #
    # Steps:
    #   1. Build a list of texts to embed:
    #      texts = [f"{rb['title']}. {rb['content']}" for rb in RUNBOOKS]
    #   2. Embed all texts at once:
    #      embeddings = model.encode(texts).tolist()
    #   3. Upsert into collection:
    #      collection.upsert(
    #          ids=[rb["id"] for rb in RUNBOOKS],
    #          embeddings=embeddings,
    #          documents=texts,
    #          metadatas=[{"title": rb["title"], "team": rb["team"],
    #                      "severity": rb["severity"]} for rb in RUNBOOKS],
    #      )
    #   4. Return len(RUNBOOKS)
    pass


# ── Querying ───────────────────────────────────────────────────────────────────

def search(
    collection: chromadb.Collection,
    model: SentenceTransformer,
    query: str,
    n_results: int = 3,
    where: dict | None = None,
) -> list[dict]:
    """Search the collection and return top results.

    Returns a list of dicts with: id, title, score, text snippet.
    """
    # TODO 4: Implement semantic search.
    #
    # Steps:
    #   1. Embed the query: query_vec = model.encode([query]).tolist()
    #   2. Query the collection:
    #      results = collection.query(
    #          query_embeddings=query_vec,
    #          n_results=n_results,
    #          where=where,        # pass through for metadata filtering
    #          include=["documents", "metadatas", "distances"],
    #      )
    #   3. Unpack results and return list of dicts:
    #      For each result: {"id": ..., "title": ..., "score": 1-distance, "snippet": doc[:100]}
    pass


# ── Exercises ──────────────────────────────────────────────────────────────────

def exercise1_build_index(collection: chromadb.Collection, model: SentenceTransformer) -> None:
    print("=" * 60)
    print("Exercise 1: Index Runbooks")
    print("=" * 60)

    count = index_runbooks(collection, model)
    if count:
        print(f"\n  Indexed {count} runbooks")
        total = collection.count()
        print(f"  Total in collection: {total}")
    else:
        print("  (complete TODO 3)")


def exercise2_basic_search(collection: chromadb.Collection, model: SentenceTransformer) -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Basic Semantic Search")
    print("=" * 60)

    queries = [
        "pod keeps dying and restarting",
        "cannot connect to the database",
        "website returning server errors",
        "Terraform pipeline is blocked",
        "disk is running out of space on the node",
    ]

    for query in queries:
        results = search(collection, model, query, n_results=2)
        print(f"\nQuery: '{query}'")
        if results is None:
            print("  (complete TODO 4)")
            continue
        for r in results:
            print(f"  [{r['id']}] {r['title']}  (score: {r['score']:.3f})")


def exercise3_metadata_filter(collection: chromadb.Collection, model: SentenceTransformer) -> None:
    """Exercise 3: Filter search results by metadata.

    Show the power of metadata filtering — search only within specific teams
    or severity levels without post-processing the results.
    """
    print("\n" + "=" * 60)
    print("Exercise 3: Metadata Filtering")
    print("=" * 60)

    query = "service is completely down"

    print(f"\nQuery: '{query}'")

    # TODO 5: Run the same query three ways:
    #   a) No filter (top 3)
    #   b) Only P1 severity: where={"severity": "P1"}
    #   c) Only "platform" team: where={"team": "platform"}
    # Print and compare the results for each.

    for label, where in [
        ("No filter", None),
        ("P1 only",   {"severity": "P1"}),
        ("Platform team only", {"team": "platform"}),
    ]:
        results = search(collection, model, query, n_results=3, where=where)
        print(f"\n  {label}:")
        if results is None:
            print("    (complete TODO 4)")
        else:
            for r in results:
                print(f"    [{r['id']}] {r['title']}  (score: {r['score']:.3f})")


def exercise4_collection_ops(collection: chromadb.Collection, model: SentenceTransformer) -> None:
    """Exercise 4: Collection operations — add, update, delete."""
    print("\n" + "=" * 60)
    print("Exercise 4: Collection Operations")
    print("=" * 60)

    # TODO 6: Add a new runbook, search for it, then delete it.
    # Steps:
    #   a) Define a new runbook dict with id="RB-NEW", title="Redis OOM",
    #      content about Redis running out of memory
    #   b) Embed and upsert it into the collection
    #   c) Search "redis out of memory" and verify RB-NEW appears in results
    #   d) Delete it: collection.delete(ids=["RB-NEW"])
    #   e) Search again and verify it's gone

    print("\n  Before add:", collection.count(), "runbooks")
    # your code here
    print("\n  (complete TODO 6 to see add/delete operations)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 02: ChromaDB Vector Store\n")

    model = load_embedding_model()
    client = get_chroma_client()
    if client is None:
        print("ERROR: get_chroma_client() returned None. Complete TODO 1.")
        return

    collection = get_or_create_collection(client)
    if collection is None:
        print("ERROR: get_or_create_collection() returned None. Complete TODO 2.")
        return

    exercise1_build_index(collection, model)
    exercise2_basic_search(collection, model)
    exercise3_metadata_filter(collection, model)
    exercise4_collection_ops(collection, model)

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. ChromaDB: zero config, persists to disk, cosine similarity built-in.")
    print("  2. Upsert = insert-or-update — safe to re-index without duplicates.")
    print("  3. Metadata filtering runs before similarity search — fast and powerful.")
    print(f"\n  DB stored at: {DB_PATH}/  (safe to delete to reset)")
    print("=" * 60)


if __name__ == "__main__":
    main()
