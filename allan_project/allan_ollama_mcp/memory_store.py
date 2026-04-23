"""Durable memory: markdown files on disk + SQLite FTS index references."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from . import database


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def memory_dir() -> Path:
    raw = os.environ.get("ALLAN_MEMORY_DIR")
    base = Path(raw).expanduser().resolve() if raw else _project_root() / "data" / "memory"
    base.mkdir(parents=True, exist_ok=True)
    return base


def traces_dir(session_id: str) -> Path:
    d = _project_root() / "data" / "traces" / session_id.strip()
    d.mkdir(parents=True, exist_ok=True)
    return d


def fts_clause_from_user_text(text: str, *, max_tokens: int = 8) -> str | None:
    """Build a conservative FTS5 OR query from user text (no raw user MATCH syntax)."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,48}", text)
    if not tokens:
        return None
    parts: list[str] = []
    for t in tokens[:max_tokens]:
        safe = t.replace('"', "")
        if safe:
            parts.append(f'"{safe}"')
    if not parts:
        return None
    return " OR ".join(parts)


async def search_relevant_memory(
    session_id: str,
    query: str,
    *,
    limit: int = 8,
) -> list[dict[str, str]]:
    clause = fts_clause_from_user_text(query)
    if not clause:
        return []
    rows = await database.search_durable_memory_fts(session_id, clause, limit=limit)
    out: list[dict[str, str]] = []
    for memory_id, rel_path, title, snippet, scope in rows:
        out.append(
            {
                "memory_id": str(memory_id),
                "path": rel_path,
                "title": title,
                "snippet": snippet,
                "scope": scope or "global",
            }
        )
    return out


def enrich_memory_hits_with_previews(hits: list[dict[str, str]], *, max_files: int = 3) -> None:
    """Attach ``body_preview`` from disk for the first ``max_files`` hits (mutates in place)."""
    for h in hits[: max(0, max_files)]:
        path = h.get("path") or ""
        if h.get("body_preview") or not path:
            continue
        body = read_memory_file(path)
        if body:
            h["body_preview"] = body[:4000]


async def write_memory_markdown(
    session_id: str | None,
    title: str,
    body: str,
) -> str:
    """Write ``data/memory/<session|global>/<uuid>.md``, index in SQLite + FTS."""
    sid_folder = session_id.strip() if session_id else "global"
    folder = memory_dir() / sid_folder
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.md"
    path = folder / name
    header = f"# {title.strip() or 'Note'}\n\n" if title.strip() else ""
    full = header + body.strip()
    path.write_text(full, encoding="utf-8")
    rel = f"{sid_folder}/{name}"
    mid = await database.insert_durable_memory_meta(session_id, rel, title.strip() or None)
    await database.insert_durable_memory_fts(
        mid,
        session_id,
        rel,
        title.strip() or name,
        full,
    )
    return rel


async def append_trace_markdown(session_id: str, title: str, body: str) -> str | None:
    if os.environ.get("ALLAN_AGENT_TRACE_MD", "1").strip().lower() in ("0", "false", "no"):
        return None
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = traces_dir(session_id) / f"turn_{ts}.md"
    p.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")
    return str(p.relative_to(_project_root()))


def read_memory_file(rel_path: str) -> str | None:
    root = memory_dir().resolve()
    raw = (rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not raw or any(part == ".." for part in raw.split("/")):
        return None
    p = (root / raw).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return None
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")[:50_000]
    except OSError:
        return None
