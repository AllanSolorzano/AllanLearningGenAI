# 01 — What Is RAG?

> **TL;DR:** RAG retrieves relevant documents at query time, then asks the LLM to answer using that evidence. It grounds responses in your data without retraining the model.

## DevOps Analogy

During an incident you do not memorize every runbook. You **search** the knowledge base, pull the top matches, and respond using those pages. RAG automates that search-then-synthesize loop for an LLM.

## What Problem Does RAG Solve?

| Challenge | RAG approach |
|-----------|--------------|
| Model knowledge is stale | Retrieve current docs at query time |
| Company-specific facts | Inject internal runbooks and tickets |
| Hallucination on facts | Require citations from retrieved chunks |
| Fine-tuning cost/latency | No weight updates; swap the corpus instead |

## RAG vs Fine-Tuning

| | RAG | Fine-tuning |
|---|-----|-------------|
| Updates | Re-index documents | Retrain or adapter refresh |
| Cost | Index + inference | Training pipeline |
| Citations | Natural (chunk IDs) | Harder to attribute |
| Best for | Changing KB, Q&A over docs | Style, format, domain fluency |

Use RAG when answers must cite **your** operational knowledge. Use fine-tuning when behavior or tone must change globally.

## End-to-End Flow

1. **Ingest** PDFs, markdown, tickets
2. **Clean** and attach metadata (service, env, owner)
3. **Chunk** with provenance (doc, page, heading)
4. **Embed** and store in a vector index (and often a keyword index)
5. **Retrieve** top-N candidates (hybrid search common in production)
6. **Rerank** to top-K highest-precision passages
7. **Generate** an answer that quotes or cites those passages
8. **Refuse** when retrieval confidence is low ("not found")

## When RAG Fails

- Chunks too large (diluted relevance) or too small (missing context)
- Missing metadata filters (wrong environment's runbook)
- No hybrid search (keyword-only misses paraphrases; vector-only misses exact IDs)
- No reranking (right doc ranked #14)
- Prompt does not require citations

Next: [02_rag_math.md](./02_rag_math.md)
