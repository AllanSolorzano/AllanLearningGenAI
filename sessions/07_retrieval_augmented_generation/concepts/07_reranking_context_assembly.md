# 07 — Reranking and Context Assembly

> **TL;DR:** Retrieve wide, rerank narrow, assemble a bounded context block with numbered citations.

## Two-Stage Retrieval

| Stage | Count | Goal |
|-------|-------|------|
| Retrieve | ~20 | High recall |
| Rerank | ~5 | High precision |

Cross-encoders (e.g. `ms-marco-MiniLM`) are standard in production. Labs use a lightweight overlap reranker to teach the pattern without extra downloads.

## Context Assembly

- Number passages `[1]`, `[2]` in the prompt
- Cap total characters/tokens (fit model context minus answer budget)
- Include `doc_id`, page, heading in each block for traceability

## Grounded Answer Template

```
System: Answer only from CONTEXT. Cite [n]. If insufficient, say not found.

CONTEXT:
[1] RB-K8S-001 p2 — OOMKilled
...

User: {question}
```

## Not-Found Behavior

If top rerank score is below threshold, return a safe refusal instead of hallucinating. Log retrieval scores for debugging.

Next: [08_evaluation_and_production.md](./08_evaluation_and_production.md)
