"""SQLite catalog for discovered MCP tools (per-server enable toggles)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from .database import DB_PATH, _utc_now

_DDL = """
CREATE TABLE IF NOT EXISTS mcp_tool_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    prefixed_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    parameters_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    UNIQUE(server_id, tool_name)
);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_catalog_server ON mcp_tool_catalog(server_id);
"""


async def ensure_mcp_tool_schema() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_DDL)


async def upsert_discovered_tools(
    server_id: str,
    tools: list[dict[str, Any]],
) -> int:
    """Insert or refresh tools from a discover run. Preserves ``enabled`` on existing rows."""
    sid = server_id.strip()
    if not sid:
        return 0
    await ensure_mcp_tool_schema()
    now = _utc_now()
    n = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for t in tools:
            name = str(t.get("tool_name") or "").strip()
            if not name:
                continue
            prefixed = str(t.get("prefixed_name") or f"{sid}__{name}")
            desc = str(t.get("description") or "")
            params = t.get("parameters") or {}
            if not isinstance(params, dict):
                params = {}
            cur = await db.execute(
                """INSERT INTO mcp_tool_catalog
                   (server_id, tool_name, prefixed_name, description, parameters_json, enabled, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)
                   ON CONFLICT(server_id, tool_name) DO UPDATE SET
                     prefixed_name = excluded.prefixed_name,
                     description = excluded.description,
                     parameters_json = excluded.parameters_json,
                     updated_at = excluded.updated_at""",
                (
                    sid,
                    name,
                    prefixed,
                    desc[:4000],
                    json.dumps(params, default=str)[:12000],
                    now,
                ),
            )
            n += int(cur.rowcount or 0)
        await db.commit()
    return n


async def list_tools_for_server(server_id: str) -> list[dict[str, Any]]:
    sid = server_id.strip()
    await ensure_mcp_tool_schema()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT tool_name, prefixed_name, description, parameters_json, enabled, updated_at
               FROM mcp_tool_catalog
               WHERE server_id = ?
               ORDER BY tool_name ASC""",
            (sid,),
        )
        rows = await cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            params = json.loads(str(r["parameters_json"] or "{}"))
        except json.JSONDecodeError:
            params = {}
        out.append(
            {
                "tool_name": str(r["tool_name"]),
                "prefixed_name": str(r["prefixed_name"]),
                "description": str(r["description"] or ""),
                "parameters": params,
                "enabled": bool(int(r["enabled"] or 0)),
                "updated_at": str(r["updated_at"]),
            }
        )
    return out


async def set_tool_enabled(server_id: str, tool_name: str, enabled: bool) -> bool:
    sid = server_id.strip()
    tn = tool_name.strip()
    await ensure_mcp_tool_schema()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE mcp_tool_catalog SET enabled = ?, updated_at = ?
               WHERE server_id = ? AND tool_name = ?""",
            (1 if enabled else 0, _utc_now(), sid, tn),
        )
        await db.commit()
        return int(cur.rowcount or 0) > 0


async def enabled_tool_filter(server_id: str) -> dict[str, bool] | None:
    """Return tool_name -> enabled for server. None if catalog empty (no filter)."""
    rows = await list_tools_for_server(server_id)
    if not rows:
        return None
    return {str(r["tool_name"]): bool(r["enabled"]) for r in rows}


async def delete_tools_for_server(server_id: str) -> None:
    sid = server_id.strip()
    await ensure_mcp_tool_schema()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM mcp_tool_catalog WHERE server_id = ?", (sid,))
        await db.commit()
