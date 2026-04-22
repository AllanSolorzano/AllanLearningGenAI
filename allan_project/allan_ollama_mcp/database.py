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
"""


async def _migrate_chat_messages(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(chat_messages)")
    rows = await cur.fetchall()
    cols = {str(r[1]) for r in rows}
    if "tool_name" not in cols:
        await db.execute("ALTER TABLE chat_messages ADD COLUMN tool_name TEXT")
    if "tool_calls_json" not in cols:
        await db.execute("ALTER TABLE chat_messages ADD COLUMN tool_calls_json TEXT")


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await _migrate_chat_messages(db)
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
