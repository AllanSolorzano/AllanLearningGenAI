#!/usr/bin/env python3
"""
Lab 02: Embeddings — SOLUTION
================================
Reference implementation. Try to complete lab.py yourself before reading this.
"""

import numpy as np
from sentence_transformers import SentenceTransformer


RUNBOOKS: list[dict] = [
    {"id": "RB-001", "title": "CrashLoopBackOff",
     "content": ("A pod in CrashLoopBackOff is repeatedly starting and crashing. "
                 "Check logs with kubectl logs <pod> --previous. Common causes: "
                 "application crash, missing ConfigMap or Secret, or OOMKilled. "
                 "Fix the application error or increase memory limits.")},
    {"id": "RB-002", "title": "OOMKilled — Container Out of Memory",
     "content": ("The container was killed by the kernel because it exceeded its memory limit. "
                 "Check kubectl describe pod for 'OOMKilled' exit code 137. "
                 "Increase the memory limit in the pod spec or fix memory leaks in the application.")},
    {"id": "RB-003", "title": "Nginx 502 Bad Gateway",
     "content": ("502 Bad Gateway means nginx cannot reach the upstream service. "
                 "Verify backend pods are running and passing health checks. "
                 "Check nginx error logs and upstream service logs for connection errors.")},
    {"id": "RB-004", "title": "Terraform State Lock",
     "content": ("Terraform state is locked by a previous run. "
                 "Get the lock ID from the error message, then run: "
                 "terraform force-unlock <LOCK_ID>. "
                 "Only do this if you're certain no other Terraform process is running.")},
    {"id": "RB-005", "title": "Node NotReady",
     "content": ("A Kubernetes node is not ready to schedule pods. "
                 "SSH to the node and check: systemctl status kubelet, "
                 "journalctl -u kubelet, and df -h for disk pressure. "
                 "Common causes: kubelet crash, disk full, or network partition.")},
    {"id": "RB-006", "title": "ImagePullBackOff — Cannot Pull Container Image",
     "content": ("Kubernetes cannot pull the container image. "
                 "Check the image name and tag are correct. "
                 "Verify registry credentials in imagePullSecrets. "
                 "Test manually: docker pull <image> or crane pull <image>.")},
    {"id": "RB-007", "title": "High CPU Throttling",
     "content": ("Container CPU is being throttled — it's hitting its CPU limit. "
                 "Check container_cpu_throttled_seconds_total in Prometheus. "
                 "Increase the CPU limit or optimize the application. "
                 "Consider horizontal scaling instead of vertical.")},
    {"id": "RB-008", "title": "AWS S3 Access Denied",
     "content": ("IAM permissions are insufficient to access the S3 bucket. "
                 "Check the IAM role attached to the EC2 instance or EKS pod service account. "
                 "Verify the bucket policy does not explicitly deny access. "
                 "Use aws sts get-caller-identity to confirm the active identity.")},
    {"id": "RB-009", "title": "Database Connection Pool Exhausted",
     "content": ("The application cannot acquire a database connection. "
                 "Check pg_stat_activity for active connections. "
                 "Short term: increase max_connections or pool size. "
                 "Long term: add a connection pooler like PgBouncer or implement connection limits per service.")},
    {"id": "RB-010", "title": "Certificate Expired",
     "content": ("A TLS certificate has expired, causing HTTPS failures. "
                 "Check cert-manager logs if using cert-manager. "
                 "For manual certs: openssl s_client -connect host:443 to inspect expiry. "
                 "Renew via Let's Encrypt or your CA, then update the Kubernetes Secret.")},
]


# ── Core functions ─────────────────────────────────────────────────────────────

def load_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    print(f"Loading model '{model_name}' (downloads ~80MB on first run)...")
    return SentenceTransformer(model_name)


def embed(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    return model.encode(texts)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def find_most_similar(
    query: str,
    corpus: list[str],
    corpus_embeddings: np.ndarray,
    model: SentenceTransformer,
    top_k: int = 3,
) -> list[tuple[int, float]]:
    query_vec = embed(model, [query])[0]
    scores = [
        (i, cosine_similarity(query_vec, corpus_embeddings[i]))
        for i in range(len(corpus))
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# ── Exercises ──────────────────────────────────────────────────────────────────

def exercise1_inspect_embeddings(model: SentenceTransformer) -> None:
    print("=" * 60)
    print("Exercise 1: Inspect an Embedding")
    print("=" * 60)

    text = "kubectl get pods --namespace production"
    embedding = embed(model, [text])[0]

    print(f"\nText:            {text}")
    print(f"Embedding shape: {embedding.shape}")
    print(f"First 8 values:  {embedding[:8].round(4).tolist()}")
    print(f"Min: {embedding.min():.4f}  Max: {embedding.max():.4f}  Mean: {embedding.mean():.4f}")
    print("\nNote: individual values mean nothing — only relative distances matter.")


def exercise2_similarity_pairs(model: SentenceTransformer) -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Similarity Between Pairs")
    print("=" * 60)

    pairs = [
        ("container killed due to memory limit",   "OOMKilled: process exceeded memory limit"),
        ("pod keeps restarting",                   "CrashLoopBackOff: container restarting repeatedly"),
        ("nginx returning 502 errors",             "upstream service is not responding"),
        ("Terraform state is locked",              "IaC state file lock prevents concurrent runs"),
        ("container killed due to memory limit",   "Terraform state is locked"),
        ("nginx returning 502 errors",             "AWS S3 bucket access denied"),
        ("pod keeps restarting",                   "gradient descent optimization algorithm"),
    ]

    all_texts = list({t for pair in pairs for t in pair})
    all_embeddings = {t: embed(model, [t])[0] for t in all_texts}

    print(f"\n{'Pair':<65} {'Similarity':>10}")
    print("─" * 78)
    for text_a, text_b in pairs:
        sim = cosine_similarity(all_embeddings[text_a], all_embeddings[text_b])
        short_a = text_a[:32] + "..." if len(text_a) > 35 else text_a
        short_b = text_b[:32] + "..." if len(text_b) > 35 else text_b
        print(f"{short_a:<35} ↔ {short_b:<25} {sim:>10.4f}")


def exercise3_semantic_search(
    model: SentenceTransformer,
    runbook_embeddings: np.ndarray,
) -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Semantic Runbook Search")
    print("=" * 60)

    runbook_texts = [f"{rb['title']}. {rb['content']}" for rb in RUNBOOKS]

    queries = [
        "my app is using too much RAM and getting killed",
        "container image won't download from registry",
        "website returning bad gateway errors",
        "IaC tool says state file is in use",
        "AWS storage bucket returning permission denied",
        "postgres ran out of connections",
        "SSL certificate is no longer valid",
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        results = find_most_similar(query, runbook_texts, runbook_embeddings, model, top_k=2)
        for idx, score in results:
            rb = RUNBOOKS[idx]
            print(f"  [{rb['id']}] {rb['title']} (score: {score:.4f})")


def exercise4_semantic_vs_keyword(
    model: SentenceTransformer,
    runbook_embeddings: np.ndarray,
) -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Semantic vs Keyword Search")
    print("=" * 60)

    runbook_texts = [f"{rb['title']}. {rb['content']}" for rb in RUNBOOKS]

    def keyword_search(query: str, top_k: int = 2) -> list[tuple[int, int]]:
        query_words = set(query.lower().split())
        scores = []
        for i, text in enumerate(runbook_texts):
            text_words = set(text.lower().split())
            overlap = len(query_words & text_words)
            scores.append((i, overlap))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in scores[:top_k] if s > 0]

    tricky_queries = [
        "my service keeps dying because it consumes all available memory",
        "docker hub authentication is broken",
        "the load balancer upstream is unhealthy",
        "slow response times due to CPU being capped",
    ]

    for query in tricky_queries:
        print(f"\nQuery: '{query}'")

        sem_results = find_most_similar(query, runbook_texts, runbook_embeddings, model, top_k=2)
        kw_results = keyword_search(query, top_k=2)

        print("  Semantic: ", end="")
        for idx, score in sem_results:
            print(f"[{RUNBOOKS[idx]['id']}] {RUNBOOKS[idx]['title']} ({score:.3f})", end="  ")
        print()

        print("  Keyword:  ", end="")
        if kw_results:
            for idx, overlap in kw_results:
                print(f"[{RUNBOOKS[idx]['id']}] {RUNBOOKS[idx]['title']} ({overlap} words)", end="  ")
        else:
            print("(no keyword matches)")
        print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 02: Embeddings (Solution)\n")

    model = load_model()
    print("Computing runbook embeddings...")
    runbook_texts = [f"{rb['title']}. {rb['content']}" for rb in RUNBOOKS]
    runbook_embeddings = embed(model, runbook_texts)
    print(f"  {len(RUNBOOKS)} runbooks → embeddings shape: {runbook_embeddings.shape}")
    print(f"  Each runbook = {runbook_embeddings.shape[1]}-dimensional vector\n")

    exercise1_inspect_embeddings(model)
    exercise2_similarity_pairs(model)
    exercise3_semantic_search(model, runbook_embeddings)
    exercise4_semantic_vs_keyword(model, runbook_embeddings)

    print("\n" + "=" * 60)
    print("Lab complete! Key takeaways:")
    print("  1. Embeddings encode meaning as vectors — similar meaning = close vectors.")
    print("  2. Cosine similarity measures direction, not magnitude.")
    print("  3. Semantic search finds meaning; keyword search finds characters.")
    print("=" * 60)


if __name__ == "__main__":
    main()
