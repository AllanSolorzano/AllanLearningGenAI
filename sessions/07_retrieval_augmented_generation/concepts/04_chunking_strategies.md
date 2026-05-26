# 04 — Chunking Strategies

> **TL;DR:** Chunk size trades context vs precision. Use heading-aware splits, token limits, overlap, and merge tiny fragments.

## Strategies Compared

| Strategy | Pros | Cons |
|----------|------|------|
| Fixed character size | Simple | Splits mid-sentence |
| Fixed token size | Matches model limits | May ignore structure |
| Heading-aware | Preserves sections | Needs structure in source |
| Semantic | Coherent topics | Slower, extra model |
| Parent-child | Small search, large context | More storage |
| Sliding window | Better recall | Duplicate content |

## Session 07 Default

Heading-aware **token** chunks (`tiktoken`), ~120 tokens, ~20 overlap, then **merge** chunks under 40 tokens on the same page.

## DevOps Guidance

- One chunk ≈ one procedure step or one failure mode
- Prefix chunk text with `## Heading` so embeddings retain section context
- Keep error codes intact in the same chunk as remediation steps

## Overlap

Overlap reduces boundary misses when the answer spans two chunks. Cost: more storage and duplicate hits—dedupe by `chunk_id` after retrieval.

Next: [05_embedding_models.md](./05_embedding_models.md)
