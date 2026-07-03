# 06 — Retrieval Strategies

> **TL;DR:** Use vector search for paraphrases, keyword/BM25 for exact tokens, hybrid + metadata filters in production.

## Vector Retrieval

Embed the query; cosine similarity against chunk embeddings; return top-N.

## Keyword / BM25

Scores term overlap with length normalization. Strong for `OOMKilled`, `INC-1234`, `terraform force-unlock`.

## Hybrid (Recommended)

1. Run vector top-20 and BM25 top-20
2. Fuse with **RRF**
3. Apply metadata filters **before** or **after** fusion (before saves compute)

## Metadata-Filtered Retrieval

```python
filters = {"service": "kubernetes", "environment": "production"}
```

Equivalent to label selectors: narrow the search space before ranking.

## Allan Project Note

`allan_ollama_mcp` uses SQLite FTS for durable memory. With `ALLAN_RAG_HYBRID=1`, vector search over indexed memory chunks is fused with FTS via RRF in `kb_connector`.

Next: [07_reranking_context_assembly.md](./07_reranking_context_assembly.md)
