"""Knowledge connector: local durable memory (FTS) as primary KB for orchestration (§6 connectors, §18)."""

from __future__ import annotations

from typing import Any

from . import database
from .orch_store import insert_kb_query, log_memory_access


async def query_local_kb(
    session_id: str,
    query_text: str,
    *,
    correlation_id: str,
    filters: dict[str, Any] | None = None,
    task_step_id: str | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Run FTS over durable memory; persist ``orchestration_kb_queries`` + memory access audit."""
    flt = dict(filters or {})
    from .memory_store import fts_clause_from_user_text

    match = fts_clause_from_user_text(query_text)
    chunks: list[dict[str, Any]] = []
    if match:
        rows = await database.search_durable_memory_fts(session_id, match, limit=limit)
        for memory_id, rel_path, title, snippet, scope in rows:
            chunks.append(
                {
                    "memory_id": str(memory_id),
                    "path": rel_path,
                    "title": title,
                    "snippet": snippet,
                    "scope": scope,
                }
            )
    await insert_kb_query(
        session_id,
        correlation_id,
        "local_fts_memory",
        query_text[:8000],
        flt,
        chunks,
        task_step_id=task_step_id,
    )
    await log_memory_access(
        session_id,
        "kb_query",
        correlation_id=correlation_id,
        task_step_id=task_step_id,
        payload={"connector": "local_fts_memory", "hits": len(chunks)},
    )
    return {
        "connector": "local_fts_memory",
        "query": query_text,
        "chunks": chunks,
        "count": len(chunks),
    }
