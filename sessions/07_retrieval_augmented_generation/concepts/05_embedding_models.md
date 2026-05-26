# 05 — Embedding Models

> **TL;DR:** Pick embeddings for your latency, language, and dimension budget. Normalize vectors for cosine search; same model for index and query.

## Local Learning Stack

| Model | Dims | Notes |
|-------|------|-------|
| `all-MiniLM-L6-v2` | 384 | Fast, good for labs |
| `all-mpnet-base-v2` | 768 | Better quality, slower |

## Production Considerations

- **Multilingual** runbooks need multilingual embeddings
- **Domain**: code/logs may need a code-aware model
- **Versioning**: re-embed entire corpus when the model changes
- **Batching**: embed offline in the ingestion job, not per request

## Vector Stores

Chroma, pgvector, OpenSearch k-NN, Pinecone—all store `(chunk_id, vector, metadata)`. Session 07 uses in-memory numpy for labs and optional Chroma in `demo_chroma_rag_pipeline.py`.

Next: [06_retrieval_strategies.md](./06_retrieval_strategies.md)
