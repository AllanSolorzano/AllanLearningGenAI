# 08 — Evaluation and Production

> **TL;DR:** Measure retrieval and answers separately. Ship observability: query, filters, chunk IDs, scores, latency.

## Retrieval Metrics

| Metric | Meaning |
|--------|---------|
| Recall@k | Correct doc in top-k |
| MRR | Rank of first correct hit |
| nDCG | Graded relevance across ranks |

## Answer Metrics

| Metric | Meaning |
|--------|---------|
| Faithfulness | Claims supported by chunks |
| Citation accuracy | `[n]` maps to real passage |
| Abstention rate | Correct "not found" when KB lacks answer |

## Production Checklist

- [ ] Versioned embedding model and index build ID
- [ ] Hybrid retrieval + reranker
- [ ] Metadata ACL filters
- [ ] PII redaction at ingest
- [ ] Trace: `retrieval_id`, chunk IDs, scores, prompt token count
- [ ] Re-index job when runbooks change
- [ ] Load test embed batch separately from online query path

## Observability (DevOps Parallel)

Like tracing an incident tool chain: log each stage latency (ingest, embed, retrieve, rerank, generate) the same way you log `kubectl` → `metrics` → `ticketing`.
