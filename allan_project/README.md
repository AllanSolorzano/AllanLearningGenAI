# Allan Ollama MCP

Local agent stack: FastAPI chat UI, Ollama, SQLite sessions, durable memory, MCP tools.

## Session 07 — RAG integration

Durable memory uses SQLite **FTS** by default. Enable **hybrid RAG** (BM25 + embeddings + RRF fused with FTS):

```bash
cd allan_project
uv sync --extra rag
export ALLAN_RAG_HYBRID=1
# optional: export ALLAN_RAG_EMBED_MODEL=all-MiniLM-L6-v2
uv run allan-api
```

Course material: `../sessions/07_retrieval_augmented_generation/`

| Env | Effect |
|-----|--------|
| `ALLAN_RAG_HYBRID=1` | Fuse vector+keyword retrieval with FTS in `kb_connector` |
| `ALLAN_RAG_EMBED_MODEL` | Sentence-transformers model name (default `all-MiniLM-L6-v2`) |

After writing new memory files, restart the API or call `rag.hybrid_search.invalidate_chunk_cache()` to refresh the in-memory chunk index.

## Quick start

```bash
uv sync
uv run allan-api
```
