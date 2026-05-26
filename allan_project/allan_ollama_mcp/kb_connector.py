"""Knowledge connector: local durable memory (FTS) as primary KB for orchestration (§6 connectors, §18)."""

from __future__ import annotations

import os
from typing import Any

from . import database
from .orch_store import insert_kb_query, log_memory_access


def _rrf_merge_chunks(
    lists: list[list[dict[str, Any]]],
    *,
    key_fn,
    k: int = 60,
    limit: int = 8,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    by_key: dict[str, dict[str, Any]] = {}
    for lst in lists:
        for rank, ch in enumerate(lst, start=1):
            key = key_fn(ch)
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            by_key.setdefault(key, ch)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [by_key[key] for key, _ in ordered[:limit] if key in by_key]


async def query_local_kb(
    session_id: str,
    query_text: str,
    *,
    correlation_id: str,
    filters: dict[str, Any] | None = None,
    task_step_id: str | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Run FTS over durable memory; optional hybrid RAG when ``ALLAN_RAG_HYBRID=1``."""
    flt = dict(filters or {})
    from .memory_store import fts_clause_from_user_text

    match = fts_clause_from_user_text(query_text)
    fts_chunks: list[dict[str, Any]] = []
    if match:
        rows = await database.search_durable_memory_fts(session_id, match, limit=limit)
        for memory_id, rel_path, title, snippet, scope in rows:
            fts_chunks.append(
                {
                    "memory_id": str(memory_id),
                    "path": rel_path,
                    "title": title,
                    "snippet": snippet,
                    "scope": scope,
                    "source": "local_fts_memory",
                }
            )

    rag_chunks: list[dict[str, Any]] = []
    connector = "local_fts_memory"
    if os.environ.get("ALLAN_RAG_HYBRID", "").strip().lower() in ("1", "true", "yes"):
        from .rag.hybrid_search import hybrid_memory_search

        connector = "local_fts_memory+rag_hybrid"
        try:
            rag_chunks = await hybrid_memory_search(session_id, query_text, limit=limit)
        except Exception as exc:  # noqa: BLE001 — degrade to FTS only
            flt["rag_error"] = str(exc)[:200]

    if rag_chunks and fts_chunks:
        chunks = _rrf_merge_chunks(
            [fts_chunks, rag_chunks],
            key_fn=lambda c: c.get("path") or c.get("memory_id") or "",
            limit=limit,
        )
    elif rag_chunks:
        chunks = rag_chunks[:limit]
    else:
        chunks = fts_chunks

    await insert_kb_query(
        session_id,
        correlation_id,
        connector,
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
        payload={
            "connector": connector,
            "hits": len(chunks),
            "fts_hits": len(fts_chunks),
            "rag_hits": len(rag_chunks),
        },
    )
    return {
        "connector": connector,
        "query": query_text,
        "chunks": chunks,
        "count": len(chunks),
    }
