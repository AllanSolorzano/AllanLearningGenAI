# 03 — Ingestion, Cleaning, and Metadata

> **TL;DR:** Treat ingestion like an ETL pipeline. Clean text once, preserve provenance, and attach metadata you will filter and cite later.

## Ingestion Pipeline

```
source file -> extract text per page -> clean -> page record + metadata
```

For PDFs use `pypdf` or `pdfplumber` in production; Session 07 uses pre-extracted page lists to stay terminal-friendly.

## Cleaning Rules

- Collapse whitespace; remove null bytes
- Keep headings and lists readable
- Do **not** strip version numbers or error codes
- Store `source`, `doc_id`, `page`, `heading` for citations

## Metadata Schema (Example)

| Field | Purpose |
|-------|---------|
| `doc_id` | Stable document identifier |
| `source` | File path or URI |
| `service` | Filter (`kubernetes`, `postgresql`) |
| `environment` | `production` vs `staging` |
| `owner` | Team accountability |
| `version` | Freshness and change tracking |
| `page` / `heading` | Citation line in answers |

## Stable Chunk IDs

Hash `(doc_id, page, heading, chunk_index)` so re-indexing does not shuffle citations.

## Access Control

Filter at retrieval time: `environment=production` AND `team=platform-sre`. Never rely on the LLM to ignore forbidden chunks.

Next: [04_chunking_strategies.md](./04_chunking_strategies.md)
