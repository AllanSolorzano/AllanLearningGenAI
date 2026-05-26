# 02 — RAG Math

> **TL;DR:** Retrieval is scoring and ranking. Embeddings use cosine similarity; keyword search uses BM25; hybrid systems fuse ranks with reciprocal rank fusion (RRF).

## Cosine Similarity

For embedding vectors **a** and **b**:

```
cos(a, b) = (a · b) / (||a|| × ||b||)
```

Values near **1** mean similar meaning. Normalize vectors when comparing many chunks to one query.

## BM25 (Keyword Relevance)

BM25 rewards term frequency but saturates (unlike raw TF). It penalizes long documents and uses inverse document frequency (IDF) so rare terms matter more.

Good for: exact error codes (`CrashLoopBackOff`), service names, ticket IDs.

## Reciprocal Rank Fusion (RRF)

When vector and keyword lists disagree, fuse by rank position:

```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```

Typical `k = 60`. A document ranked #1 in both lists rises to the top without normalizing incomparable scores.

## Reranking

First-stage retrieval optimizes **recall** (top 20). A reranker optimizes **precision** (top 5). Cross-encoders score (query, passage) jointly; lighter proxies combine vector score + token overlap for labs.

## Grounded Generation

The LLM sees only retrieved context. Citation format in the prompt reduces unsupported claims:

```
Answer using ONLY the passages below. Cite as [1], [2].
If nothing applies, say "not found in knowledge base."
```

Next: [03_ingestion_cleaning_metadata.md](./03_ingestion_cleaning_metadata.md)
