# 03 — Vector Stores: Storing and Searching Embeddings

> **TL;DR:** A vector store is a database optimised for similarity search over high-dimensional vectors.
> ChromaDB runs locally with no setup. pgvector adds vector search to existing Postgres.
> Qdrant and Pinecone are managed options for production scale.

---

## DevOps Analogy

A vector store is a **specialised index**, just like a database index — except instead of B-tree lookups (equality, range), it answers: "give me the 5 most similar vectors to this query vector."

Your existing knowledge of database indexing applies directly:

| Concept | Traditional DB | Vector Store |
|---------|---------------|--------------|
| Index type | B-tree, Hash | HNSW, IVF |
| Query type | `WHERE x = ?` | `ORDER BY cosine_similarity DESC` |
| Insert | `INSERT INTO docs` | `collection.add(embeddings, ids)` |
| Query | `SELECT WHERE` | `collection.query(query_embeddings, n_results=5)` |
| Persistence | Disk | Disk (ChromaDB) or dedicated service |
| Scaling | Vertical / sharding | Dedicated servers (Qdrant, Pinecone) |

---

## ChromaDB: Local Vector Store

ChromaDB is the easiest way to get started. It runs embedded in your Python process (no server) and persists to disk.

```python
import chromadb

# Persistent client — data saved to disk
client = chromadb.PersistentClient(path="./chroma_db")

# Create a collection (like a table)
collection = client.get_or_create_collection(
    name="runbooks",
    metadata={"hnsw:space": "cosine"},  # use cosine similarity
)

# Add documents
collection.add(
    ids=["rb-001", "rb-002"],
    embeddings=[[0.1, 0.2, ...], [0.3, 0.1, ...]],  # your pre-computed embeddings
    documents=["OOMKilled runbook text...", "CrashLoop runbook text..."],
    metadatas=[{"source": "rb-001", "severity": "P1"}, {"source": "rb-002", "severity": "P2"}],
)

# Query
results = collection.query(
    query_embeddings=[[0.15, 0.18, ...]],  # query vector
    n_results=3,
    where={"severity": "P1"},  # metadata filter
)
```

### ChromaDB Key Concepts

**Collection:** A named group of documents (like a table). Separate collections for different document types.

**`add()` vs `upsert()`:** Use `upsert()` to handle re-indexing — it updates if the ID exists, inserts if not.

**Metadata filtering:** The `where` parameter filters by metadata before similarity search. Extremely useful for multi-tenant systems ("only search docs for team X") or filtering by date.

**Persistent vs in-memory:**
```python
# In-memory (lost on restart) — for testing
client = chromadb.Client()

# Persistent (survives restarts) — for production
client = chromadb.PersistentClient(path="./chroma_db")
```

---

## Vector Store Comparison

| Store | Setup | Scale | Best for |
|-------|-------|-------|----------|
| ChromaDB | Embedded Python lib, zero config | Millions of docs | Learning, prototyping, small production |
| pgvector | Postgres extension | Millions of docs | Teams already running Postgres |
| Qdrant | Docker or managed cloud | Billions of docs | Production, multi-tenant |
| Pinecone | Managed cloud only | Billions of docs | Production, no ops overhead |
| Weaviate | Docker or managed cloud | Billions of docs | Production, rich filtering |

**Rule for DevOps teams:** If you're already running Postgres, add `pgvector`. If you're starting fresh and want simplicity, start with ChromaDB and migrate to Qdrant when you outgrow it.

---

## HNSW: The Index Algorithm

Most vector stores use **HNSW (Hierarchical Navigable Small World)** for approximate nearest neighbour search. You don't need to understand the algorithm, but the key property matters:

- **Exact search** (brute force): compare query to every vector → 100% recall, O(n) time
- **HNSW**: traverse a hierarchical graph → ~95-99% recall, O(log n) time

For 10,000 documents: exact search is fine. For 10 million: HNSW is necessary. ChromaDB uses HNSW by default.

**Recall vs Latency trade-off** — you can tune HNSW parameters:
- `ef_construction` (build quality): higher = better recall, slower indexing
- `ef_search` (query quality): higher = better recall, slower queries
- Default ChromaDB settings are good for most use cases.

---

## Embedding Consistency: The Critical Constraint

**You must use the same embedding model for indexing and querying.**

If you index with `all-MiniLM-L6-v2` (384 dimensions) and query with `text-embedding-ada-002` (1536 dimensions), the similarity scores are meaningless — the dimensions don't correspond.

In production: store the embedding model name as collection metadata:
```python
collection = client.get_or_create_collection(
    name="runbooks",
    metadata={
        "hnsw:space": "cosine",
        "embedding_model": "all-MiniLM-L6-v2",  # enforce consistency
    },
)
```

---

## Key Takeaways

1. **ChromaDB = zero config, runs locally.** Start here, migrate later if needed.
2. **Metadata filtering is powerful** — tag your chunks and filter at query time rather than post-processing.
3. **Embedding model must match** between indexing and querying. Store the model name as metadata.

---

## Hands-On

→ [Lab 02: ChromaDB Vector Store](../labs/lab02_chromadb/lab.py)
