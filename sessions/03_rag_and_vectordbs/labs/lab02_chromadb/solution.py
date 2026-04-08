#!/usr/bin/env python3
"""Lab 02: ChromaDB — SOLUTION"""

import sys
import chromadb
from sentence_transformers import SentenceTransformer

RUNBOOKS = [
    {"id": "RB-001", "title": "CrashLoopBackOff", "team": "platform", "severity": "P1",
     "content": "Pod repeatedly starting and crashing. Check kubectl logs --previous for crash reason. Common causes: application error, missing ConfigMap/Secret, or OOMKilled. Fix the error or increase memory limits."},
    {"id": "RB-002", "title": "OOMKilled — Container Out of Memory", "team": "platform", "severity": "P1",
     "content": "Container exceeded memory limit and killed by kernel (exit code 137). kubectl describe pod for OOMKilled status. Increase memory limit. Long-term: profile for memory leaks. Alert at 80% utilisation."},
    {"id": "RB-003", "title": "Nginx 502 Bad Gateway", "team": "platform", "severity": "P2",
     "content": "Nginx cannot reach upstream backend. Verify backend pods Running and passing readiness probes. Check nginx error logs. Verify Service selector matches pod labels."},
    {"id": "RB-004", "title": "Terraform State Lock", "team": "infra", "severity": "P2",
     "content": "Terraform state locked by previous run. Verify no CI/CD pipeline running. If stale: terraform force-unlock <LOCK_ID>. Prevention: DynamoDB locking and pipeline timeouts."},
    {"id": "RB-005", "title": "Node NotReady", "team": "platform", "severity": "P1",
     "content": "Kubernetes node not scheduling pods. SSH to node: systemctl status kubelet, df -h, free -m. Common causes: kubelet crash, disk full, network partition."},
    {"id": "RB-006", "title": "ImagePullBackOff", "team": "platform", "severity": "P2",
     "content": "Cannot pull container image. Check image name/tag correct. Verify imagePullSecrets credentials. Test: docker pull <image>."},
    {"id": "RB-007", "title": "High CPU Throttling", "team": "platform", "severity": "P2",
     "content": "Container hitting CPU limit. Check container_cpu_throttled_seconds_total. Increase CPU limit or scale horizontally."},
    {"id": "RB-008", "title": "AWS S3 Access Denied", "team": "infra", "severity": "P2",
     "content": "IAM permissions insufficient for S3. Check IAM role on EC2/EKS pod. Verify bucket policy. Use aws sts get-caller-identity to confirm identity."},
    {"id": "RB-009", "title": "Database Connection Pool Exhausted", "team": "backend", "severity": "P1",
     "content": "Cannot acquire database connection. Check pg_stat_activity. Increase max_connections or pool size. Add PgBouncer connection pooler."},
    {"id": "RB-010", "title": "TLS Certificate Expired", "team": "platform", "severity": "P1",
     "content": "TLS certificate expired. Check cert-manager logs. Inspect: openssl s_client -connect host:443. Renew and update Kubernetes Secret."},
    {"id": "RB-011", "title": "Persistent Volume Claim Pending", "team": "platform", "severity": "P2",
     "content": "PVC stuck in Pending. kubectl describe pvc for events. Check StorageClass exists. Verify CSI driver is running."},
    {"id": "RB-012", "title": "HPA Not Scaling", "team": "platform", "severity": "P2",
     "content": "HPA not triggering. kubectl describe hpa for events. Check metrics-server running. Verify CPU requests set on pods."},
]

DB_PATH = "./chroma_lab_db"
COLLECTION_NAME = "runbooks"
EMBED_MODEL = "all-MiniLM-L6-v2"


def load_embedding_model() -> SentenceTransformer:
    print(f"Loading embedding model '{EMBED_MODEL}'...")
    return SentenceTransformer(EMBED_MODEL)


def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=DB_PATH)


def get_or_create_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def index_runbooks(collection: chromadb.Collection, model: SentenceTransformer) -> int:
    texts = [f"{rb['title']}. {rb['content']}" for rb in RUNBOOKS]
    embeddings = model.encode(texts).tolist()
    collection.upsert(
        ids=[rb["id"] for rb in RUNBOOKS],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {"title": rb["title"], "team": rb["team"], "severity": rb["severity"]}
            for rb in RUNBOOKS
        ],
    )
    return len(RUNBOOKS)


def search(collection, model, query, n_results=3, where=None) -> list[dict]:
    query_vec = model.encode([query]).tolist()
    kwargs: dict = {
        "query_embeddings": query_vec,
        "n_results": min(n_results, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "id":      results["ids"][0][i],
            "title":   results["metadatas"][0][i]["title"],
            "score":   1 - results["distances"][0][i],
            "snippet": results["documents"][0][i][:100],
        })
    return output


def exercise1_build_index(collection, model) -> None:
    print("=" * 60)
    print("Exercise 1: Index Runbooks")
    print("=" * 60)
    count = index_runbooks(collection, model)
    print(f"\n  Indexed {count} runbooks")
    print(f"  Total in collection: {collection.count()}")


def exercise2_basic_search(collection, model) -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Basic Semantic Search")
    print("=" * 60)
    for query in [
        "pod keeps dying and restarting",
        "cannot connect to the database",
        "website returning server errors",
        "Terraform pipeline is blocked",
        "disk is running out of space on the node",
    ]:
        results = search(collection, model, query, n_results=2)
        print(f"\nQuery: '{query}'")
        for r in results:
            print(f"  [{r['id']}] {r['title']}  (score: {r['score']:.3f})")


def exercise3_metadata_filter(collection, model) -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Metadata Filtering")
    print("=" * 60)
    query = "service is completely down"
    print(f"\nQuery: '{query}'")
    for label, where in [
        ("No filter", None),
        ("P1 only", {"severity": "P1"}),
        ("Platform team only", {"team": "platform"}),
    ]:
        results = search(collection, model, query, n_results=3, where=where)
        print(f"\n  {label}:")
        for r in results:
            print(f"    [{r['id']}] {r['title']}  (score: {r['score']:.3f})")


def exercise4_collection_ops(collection, model) -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Collection Operations")
    print("=" * 60)

    new_rb = {
        "id": "RB-NEW",
        "title": "Redis OOM",
        "team": "backend",
        "severity": "P2",
        "content": "Redis out of memory — maxmemory limit reached. Check INFO memory. Set maxmemory-policy to allkeys-lru. Increase maxmemory config. Check for keys without TTL.",
    }
    text = f"{new_rb['title']}. {new_rb['content']}"
    vec = model.encode([text]).tolist()

    print(f"\n  Before add: {collection.count()} runbooks")
    collection.upsert(
        ids=[new_rb["id"]],
        embeddings=vec,
        documents=[text],
        metadatas=[{"title": new_rb["title"], "team": new_rb["team"], "severity": new_rb["severity"]}],
    )
    print(f"  After add:  {collection.count()} runbooks")

    results = search(collection, model, "redis out of memory", n_results=2)
    print(f"\n  Search 'redis out of memory':")
    for r in results:
        print(f"    [{r['id']}] {r['title']}  (score: {r['score']:.3f})")

    collection.delete(ids=[new_rb["id"]])
    print(f"\n  After delete: {collection.count()} runbooks")

    results = search(collection, model, "redis out of memory", n_results=2)
    print(f"  Search again (RB-NEW should be gone):")
    for r in results:
        print(f"    [{r['id']}] {r['title']}  (score: {r['score']:.3f})")


def main() -> None:
    print("\nLab 02: ChromaDB (Solution)\n")
    model = load_embedding_model()
    client = get_chroma_client()
    collection = get_or_create_collection(client)
    exercise1_build_index(collection, model)
    exercise2_basic_search(collection, model)
    exercise3_metadata_filter(collection, model)
    exercise4_collection_ops(collection, model)
    print(f"\n  DB stored at: {DB_PATH}/")


if __name__ == "__main__":
    main()
