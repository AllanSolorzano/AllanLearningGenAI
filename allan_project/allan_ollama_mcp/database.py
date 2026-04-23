"""Async SQLite persistence for chat sessions and messages."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def database_path() -> Path:
    raw = os.environ.get("MCP_DATABASE_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "data" / "app.db"


DB_PATH = database_path()

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, id);
CREATE TABLE IF NOT EXISTS durable_memory_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    rel_path TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_durable_memory_session ON durable_memory_index(session_id, id);
CREATE TABLE IF NOT EXISTS agent_turn_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_agent_turn_session ON agent_turn_log(session_id, id);
CREATE TABLE IF NOT EXISTS agent_step_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    state TEXT NOT NULL,
    tool_name TEXT,
    detail_json TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_agent_step_corr ON agent_step_events(session_id, correlation_id, id);
"""


async def _migrate_chat_messages(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(chat_messages)")
    rows = await cur.fetchall()
    cols = {str(r[1]) for r in rows}
    if "tool_name" not in cols:
        await db.execute("ALTER TABLE chat_messages ADD COLUMN tool_name TEXT")
    if "tool_calls_json" not in cols:
        await db.execute("ALTER TABLE chat_messages ADD COLUMN tool_calls_json TEXT")


async def _migrate_fts_memory(db: aiosqlite.Connection) -> None:
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='durable_memory_fts'"
    )
    row = await cur.fetchone()
    if row is not None:
        return
    try:
        await db.execute(
            """
            CREATE VIRTUAL TABLE durable_memory_fts USING fts5(
                memory_id UNINDEXED,
                session_id UNINDEXED,
                rel_path UNINDEXED,
                title,
                content,
                tokenize = 'porter unicode61'
            )
            """
        )
    except Exception:
        # Extremely old SQLite builds without FTS5 — skip search index.
        pass


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await _migrate_chat_messages(db)
        await _migrate_fts_memory(db)
        await db.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_session(session_id: str) -> tuple[str, str, str] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            "SELECT id, COALESCE(title, ''), created_at FROM chat_sessions WHERE id = ?",
            (session_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return str(row[0]), str(row[1]), str(row[2])


async def session_exists(session_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            "SELECT 1 FROM chat_sessions WHERE id = ? LIMIT 1",
            (session_id,),
        )
        row = await cur.fetchone()
        return row is not None


async def create_session(title: str | None = None) -> str:
    sid = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            "INSERT INTO chat_sessions (id, title, created_at) VALUES (?, ?, ?)",
            (sid, (title or "").strip(), _utc_now()),
        )
        await db.commit()
    return sid


async def append_message(
    session_id: str,
    role: str,
    content: str,
    model: str | None = None,
    *,
    tool_name: str | None = None,
    tool_calls_json: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """INSERT INTO chat_messages
               (session_id, role, content, model, created_at, tool_name, tool_calls_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, model, _utc_now(), tool_name, tool_calls_json),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def fetch_messages_for_model(
    session_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Latest ``limit`` messages, oldest-first, shaped for Ollama (incl. tool / tool_calls)."""
    limit = max(1, min(limit, 500))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """WITH recent AS (
                   SELECT id, role, content, tool_name, tool_calls_json FROM chat_messages
                   WHERE session_id = ?
                   ORDER BY id DESC
                   LIMIT ?
               )
               SELECT role, content, tool_name, tool_calls_json FROM recent ORDER BY id ASC""",
            (session_id, limit),
        )
        rows = await cur.fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        role = str(r["role"])
        content = str(r["content"] or "")
        tool_name = r["tool_name"]
        tc_raw = r["tool_calls_json"]
        if role == "tool" and tool_name:
            out.append(
                {"role": "tool", "tool_name": str(tool_name), "content": content}
            )
            continue
        if role == "assistant" and tc_raw:
            try:
                tc = json.loads(str(tc_raw))
            except json.JSONDecodeError:
                tc = None
            msg: dict[str, Any] = {"role": "assistant", "content": content}
            if isinstance(tc, list) and tc:
                msg["tool_calls"] = tc
            out.append(msg)
            continue
        out.append({"role": role, "content": content})
    return out


async def list_sessions(limit: int) -> list[tuple[str, str, str]]:
    limit = max(1, min(limit, 200))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """SELECT id, COALESCE(title, ''), created_at FROM chat_sessions
               ORDER BY datetime(created_at) DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
    return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]


async def get_messages_display(
    session_id: str,
    limit: int,
) -> list[tuple[int, str, str, str, str | None, str | None, str | None]]:
    """Latest ``limit`` messages: id, role, content, created_at, model, tool_name, tool_calls_json."""
    limit = max(1, min(limit, 500))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """WITH recent AS (
                   SELECT id, role, content, created_at, model, tool_name, tool_calls_json
                   FROM chat_messages
                   WHERE session_id = ?
                   ORDER BY id DESC
                   LIMIT ?
               )
               SELECT id, role, content, created_at, model, tool_name, tool_calls_json
               FROM recent ORDER BY id ASC""",
            (session_id, limit),
        )
        rows = await cur.fetchall()
    out: list[tuple[int, str, str, str, str | None, str | None, str | None]] = []
    for r in rows:
        out.append(
            (
                int(r[0]),
                str(r[1]),
                str(r[2]),
                str(r[3]),
                r[4],
                r[5],
                r[6],
            )
        )
    return out


async def insert_durable_memory_meta(
    session_id: str | None,
    rel_path: str,
    title: str | None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """INSERT INTO durable_memory_index (session_id, rel_path, title, created_at)
               VALUES (?, ?, ?, ?)""",
            (session_id, rel_path, (title or "").strip(), _utc_now()),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def insert_durable_memory_fts(
    memory_id: int,
    session_id: str | None,
    rel_path: str,
    title: str,
    content: str,
) -> None:
    sid = session_id if session_id else ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='durable_memory_fts'"
        )
        if await cur.fetchone() is None:
            return
        await db.execute(
            """INSERT INTO durable_memory_fts
               (memory_id, session_id, rel_path, title, content)
               VALUES (?, ?, ?, ?, ?)""",
            (memory_id, sid, rel_path, title, content),
        )
        await db.commit()


async def search_durable_memory_fts(
    session_id: str,
    fts_match_clause: str,
    *,
    limit: int = 8,
) -> list[tuple[int, str, str, str, str]]:
    """Return rows: memory_id, rel_path, title, snippet, session_scope."""
    limit = max(1, min(limit, 50))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='durable_memory_fts'"
        )
        if await cur.fetchone() is None:
            return []
        try:
            qcur = await db.execute(
                """SELECT memory_id, rel_path, title,
                          snippet(durable_memory_fts, 4, '[', ']', '…', 24),
                          session_id
                   FROM durable_memory_fts
                   WHERE durable_memory_fts MATCH ?
                     AND (session_id = '' OR session_id = ?)
                   LIMIT ?""",
                (fts_match_clause, session_id, limit),
            )
            rows = await qcur.fetchall()
        except Exception:
            return []
    return [
        (int(r[0]), str(r[1]), str(r[2] or ""), str(r[3] or ""), str(r[4] or ""))
        for r in rows
    ]


async def append_agent_turn_log(
    session_id: str,
    phase: str,
    payload: dict[str, Any],
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """INSERT INTO agent_turn_log (session_id, phase, payload_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (session_id, phase, json.dumps(payload, default=str), _utc_now()),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def append_agent_step_event(
    session_id: str,
    correlation_id: str,
    step_id: str,
    state: str,
    *,
    tool_name: str | None = None,
    detail: dict[str, Any] | None = None,
    latency_ms: int | None = None,
) -> int:
    """Append a lifecycle row: queued | running | succeeded | failed | waiting | deferred."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """INSERT INTO agent_step_events
               (session_id, correlation_id, step_id, state, tool_name, detail_json, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                correlation_id,
                step_id,
                state,
                tool_name,
                json.dumps(detail or {}, default=str),
                latency_ms,
                _utc_now(),
            ),
        )
        await db.commit()
        return int(cur.lastrowid or 0)
