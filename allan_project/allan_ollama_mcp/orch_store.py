"""Normalized orchestration persistence (SQLite) — intents, plans, tasks, events, tool calls, KB, memory audit, policies."""

from __future__ import annotations

import json
import uuid
from typing import Any

import aiosqlite

from .database import DB_PATH, _utc_now


_ORCH_DDL = """
CREATE TABLE IF NOT EXISTS orchestration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    correlation_id TEXT,
    task_step_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orch_events_session ON orchestration_events(session_id, id);
CREATE INDEX IF NOT EXISTS idx_orch_events_corr ON orchestration_events(correlation_id, id);

CREATE TABLE IF NOT EXISTS orchestration_intents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id INTEGER,
    correlation_id TEXT NOT NULL,
    intent_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    priority_score REAL,
    selected INTEGER NOT NULL DEFAULT 0,
    entities_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    features_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orch_intents_session ON orchestration_intents(session_id, correlation_id);

CREATE TABLE IF NOT EXISTS orchestration_plans (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    message_id INTEGER,
    plan_version INTEGER NOT NULL DEFAULT 1,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    plan_json TEXT NOT NULL,
    supersedes_plan_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orch_plans_session ON orchestration_plans(session_id, correlation_id);

CREATE TABLE IF NOT EXISTS orchestration_tasks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    task_type TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    priority REAL DEFAULT 0,
    input_json TEXT,
    output_json TEXT,
    constraints_json TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES orchestration_plans(id)
);
CREATE INDEX IF NOT EXISTS idx_orch_tasks_plan ON orchestration_tasks(plan_id, step_id);

CREATE TABLE IF NOT EXISTS orchestration_task_deps (
    plan_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    depends_on_step_id TEXT NOT NULL,
    PRIMARY KEY (plan_id, step_id, depends_on_step_id),
    FOREIGN KEY (plan_id) REFERENCES orchestration_plans(id)
);

CREATE TABLE IF NOT EXISTS orchestration_tool_calls (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    plan_id TEXT,
    correlation_id TEXT NOT NULL,
    task_step_id TEXT,
    mcp_server_id TEXT,
    tool_name TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT,
    status TEXT NOT NULL,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orch_tool_session ON orchestration_tool_calls(session_id, correlation_id);

CREATE TABLE IF NOT EXISTS orchestration_kb_queries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    task_step_id TEXT,
    connector_name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    filters_json TEXT NOT NULL,
    retrieved_chunks_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orchestration_memory_refs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    correlation_id TEXT,
    task_step_id TEXT,
    memory_type TEXT NOT NULL,
    key_path TEXT NOT NULL,
    value_json TEXT NOT NULL,
    confidence REAL DEFAULT 0.7,
    privacy_scope TEXT DEFAULT 'session',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orchestration_memory_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_ref_id TEXT,
    session_id TEXT NOT NULL,
    correlation_id TEXT,
    task_step_id TEXT,
    access_type TEXT NOT NULL,
    reason TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orch_memacc_session ON orchestration_memory_access_log(session_id, id);

CREATE TABLE IF NOT EXISTS orchestration_policies (
    id TEXT PRIMARY KEY,
    policy_name TEXT NOT NULL UNIQUE,
    policy_type TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    action_json TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""


def _guid() -> str:
    return uuid.uuid4().hex


def _priority_score_from_features(confidence: float, registry_score: float) -> float:
    """§7.2-style compact scalar (stores interpretable features in features_json separately)."""
    urgency = 0.5
    dep_nec = 0.5
    business = 0.55
    cost = min(1.0, max(0.0, 1.0 - registry_score))
    risk = 0.2
    return round(
        0.30 * confidence
        + 0.20 * urgency
        + 0.20 * dep_nec
        + 0.20 * business
        - 0.05 * cost
        - 0.05 * risk,
        4,
    )


async def ensure_orch_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(_ORCH_DDL)


async def seed_default_policies() -> None:
    defaults: list[tuple[str, str, str, str, int]] = [
        (
            _guid(),
            "block_secret_memory_storage",
            "memory_write_guardrail",
            json.dumps(
                {
                    "memory_candidate_contains": ["api_key", "password", "private_key", "token"],
                    "memory_type": ["long_term_semantic", "episodic", "reflective"],
                }
            ),
            json.dumps({"store": False, "redact": True, "emit_event": "memory_write_blocked"}),
            200,
        ),
        (
            _guid(),
            "require_approval_for_prod_mutation",
            "approval_gate",
            json.dumps({"environment": "prod", "mode": "write"}),
            json.dumps({"approval_required": True, "approver_role": "human_operator"}),
            100,
        ),
        (
            _guid(),
            "local_first_observability",
            "data_locality",
            json.dumps({"hints_contain": "local_first"}),
            json.dumps({"prefer_local_mcp": True, "downrank_cloud_tools": 0.55}),
            50,
        ),
    ]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            "SELECT COUNT(*) FROM orchestration_policies WHERE policy_name IN (?, ?, ?)",
            ("block_secret_memory_storage", "require_approval_for_prod_mutation", "local_first_observability"),
        )
        row = await cur.fetchone()
        if row and int(row[0] or 0) >= 3:
            return
        for pid, name, ptype, cond, action, prio in defaults:
            await db.execute(
                """INSERT OR IGNORE INTO orchestration_policies
                   (id, policy_name, policy_type, condition_json, action_json, priority, enabled, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (pid, name, ptype, cond, action, prio, _utc_now()),
            )
        await db.commit()


async def emit_event(
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
    task_step_id: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """INSERT INTO orchestration_events
               (session_id, correlation_id, task_step_id, event_type, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                session_id.strip(),
                correlation_id,
                task_step_id,
                event_type,
                json.dumps(payload, default=str),
                _utc_now(),
            ),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def insert_intents_from_ranked(
    session_id: str,
    correlation_id: str,
    message_id: int | None,
    ranked_rows: list[dict[str, Any]],
    selected_intent_name: str | None,
) -> None:
    if not ranked_rows:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        for r in ranked_rows:
            if not isinstance(r, dict):
                continue
            name = str(r.get("intent") or "").strip() or "compose"
            conf = float(r.get("confidence") or 0.5)
            rs = float(r.get("registry_best_score") or 0.0)
            features = {
                "confidence": conf,
                "registry_best_score": rs,
                "policy_adjusted_score": r.get("policy_adjusted_score"),
                "final_intent_score": r.get("final_intent_score"),
                "urgency": 0.5,
                "dependency_necessity": 0.5,
                "business_value": 0.55,
                "cost_score": round(1.0 - min(1.0, rs), 4),
                "risk_score": 0.2,
                "formula_note": "0.30*c + 0.20*u + 0.20*d + 0.20*b - 0.05*cost - 0.05*risk (compact)",
            }
            prio = _priority_score_from_features(conf, rs)
            sel = 1 if selected_intent_name and name == selected_intent_name else 0
            await db.execute(
                """INSERT INTO orchestration_intents
                   (id, session_id, message_id, correlation_id, intent_name, confidence, priority_score,
                    selected, entities_json, constraints_json, features_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _guid(),
                    session_id.strip(),
                    message_id,
                    correlation_id,
                    name,
                    conf,
                    prio,
                    sel,
                    json.dumps(r.get("entities") or {}, default=str),
                    json.dumps(r.get("constraints") or {}, default=str),
                    json.dumps(features, default=str),
                    _utc_now(),
                ),
            )
        await db.commit()


async def insert_plan(
    session_id: str,
    correlation_id: str,
    message_id: int | None,
    plan_version: int,
    goal: str,
    plan: dict[str, Any],
    *,
    status: str = "active",
    supersedes_plan_id: str | None = None,
) -> str:
    pid = _guid()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO orchestration_plans
               (id, session_id, correlation_id, message_id, plan_version, goal, status, plan_json, supersedes_plan_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pid,
                session_id.strip(),
                correlation_id,
                message_id,
                plan_version,
                goal[:4000],
                status,
                json.dumps(plan, default=str),
                supersedes_plan_id,
                _utc_now(),
            ),
        )
        await db.commit()
    return pid


async def insert_tasks_for_plan(
    plan_id: str,
    session_id: str,
    correlation_id: str,
    steps: list[dict[str, Any]],
) -> None:
    if not steps:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        now = _utc_now()
        for s in steps:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id") or "").strip() or "step"
            tt = str(s.get("type") or s.get("kind") or "tool")
            title = str(s.get("title") or "")[:500]
            inp = json.dumps(s.get("args") or {}, default=str)[:8000]
            cons = json.dumps(s.get("constraints") or s.get("execution_constraints") or {}, default=str)[:4000]
            tid = _guid()
            max_r = int(s.get("max_retries") or 0)
            await db.execute(
                """INSERT INTO orchestration_tasks
                   (id, plan_id, session_id, correlation_id, step_id, task_type, title, status, priority,
                    input_json, output_json, constraints_json, retry_count, max_retries, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, NULL, ?, 0, ?, ?, ?)""",
                (
                    tid,
                    plan_id,
                    session_id.strip(),
                    correlation_id,
                    sid,
                    tt[:80],
                    title,
                    float(s.get("priority") or 0),
                    inp,
                    cons,
                    max_r,
                    now,
                    now,
                ),
            )
            deps = s.get("depends_on") or []
            if isinstance(deps, list):
                for d in deps:
                    ds = str(d).strip()
                    if ds:
                        await db.execute(
                            """INSERT OR IGNORE INTO orchestration_task_deps (plan_id, step_id, depends_on_step_id)
                               VALUES (?, ?, ?)""",
                            (plan_id, sid, ds),
                        )
        await db.commit()


async def update_task_status(
    plan_id: str,
    step_id: str,
    status: str,
    *,
    output_json: dict[str, Any] | None = None,
) -> None:
    out = json.dumps(output_json, default=str)[:12000] if output_json is not None else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        if out is not None:
            await db.execute(
                """UPDATE orchestration_tasks SET status = ?, output_json = ?, updated_at = ?
                   WHERE plan_id = ? AND step_id = ?""",
                (status, out, _utc_now(), plan_id, step_id),
            )
        else:
            await db.execute(
                """UPDATE orchestration_tasks SET status = ?, updated_at = ?
                   WHERE plan_id = ? AND step_id = ?""",
                (status, _utc_now(), plan_id, step_id),
            )
        await db.commit()


async def insert_tool_call_row(
    session_id: str,
    correlation_id: str,
    plan_id: str | None,
    task_step_id: str | None,
    tool_name: str,
    request: dict[str, Any],
    response_excerpt: str | None,
    status: str,
    latency_ms: int | None,
) -> str:
    tid = _guid()
    mcp_id = ""
    if "__" in tool_name:
        mcp_id = tool_name.split("__", 1)[0]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO orchestration_tool_calls
               (id, session_id, plan_id, correlation_id, task_step_id, mcp_server_id, tool_name,
                request_json, response_json, status, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tid,
                session_id.strip(),
                plan_id,
                correlation_id,
                task_step_id,
                mcp_id or None,
                tool_name[:500],
                json.dumps(request, default=str)[:8000],
                (response_excerpt or "")[:16000] if response_excerpt is not None else None,
                status,
                latency_ms,
                _utc_now(),
            ),
        )
        await db.commit()
    return tid


async def insert_kb_query(
    session_id: str,
    correlation_id: str,
    connector_name: str,
    query_text: str,
    filters: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    task_step_id: str | None = None,
) -> str:
    kid = _guid()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO orchestration_kb_queries
               (id, session_id, correlation_id, task_step_id, connector_name, query_text, filters_json, retrieved_chunks_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                kid,
                session_id.strip(),
                correlation_id,
                task_step_id,
                connector_name[:120],
                query_text[:8000],
                json.dumps(filters, default=str),
                json.dumps(chunks, default=str)[:24000],
                _utc_now(),
            ),
        )
        await db.commit()
    return kid


async def log_memory_access(
    session_id: str,
    access_type: str,
    *,
    correlation_id: str | None = None,
    task_step_id: str | None = None,
    memory_ref_id: str | None = None,
    reason: str | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cur = await db.execute(
            """INSERT INTO orchestration_memory_access_log
               (memory_ref_id, session_id, correlation_id, task_step_id, access_type, reason, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory_ref_id,
                session_id.strip(),
                correlation_id,
                task_step_id,
                access_type,
                reason,
                json.dumps(payload or {}, default=str)[:8000],
                _utc_now(),
            ),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def insert_memory_ref(
    session_id: str,
    memory_type: str,
    key_path: str,
    value: dict[str, Any],
    *,
    correlation_id: str | None = None,
    task_step_id: str | None = None,
    confidence: float = 0.7,
    privacy_scope: str = "session",
) -> str:
    rid = _guid()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO orchestration_memory_refs
               (id, session_id, correlation_id, task_step_id, memory_type, key_path, value_json, confidence, privacy_scope, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rid,
                session_id.strip(),
                correlation_id,
                task_step_id,
                memory_type[:80],
                key_path[:500],
                json.dumps(value, default=str)[:12000],
                confidence,
                privacy_scope[:80],
                _utc_now(),
            ),
        )
        await db.commit()
    return rid


async def list_policies_enabled() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT policy_name, policy_type, condition_json, action_json, priority
               FROM orchestration_policies WHERE enabled = 1 ORDER BY priority DESC"""
        )
        rows = await cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            cond = json.loads(str(r["condition_json"] or "{}"))
        except json.JSONDecodeError:
            cond = {}
        try:
            act = json.loads(str(r["action_json"] or "{}"))
        except json.JSONDecodeError:
            act = {}
        out.append(
            {
                "policy_name": str(r["policy_name"]),
                "policy_type": str(r["policy_type"]),
                "condition": cond,
                "action": act,
                "priority": int(r["priority"] or 0),
            }
        )
    return out


async def list_orchestration_summary(session_id: str, *, limit: int = 40) -> dict[str, Any]:
    """Lightweight counts for API / debugging."""
    sid = session_id.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        async def cnt(sql: str) -> int:
            c = await db.execute(sql, (sid,))
            r = await c.fetchone()
            return int(r[0] or 0) if r else 0

        n_int = await cnt(
            "SELECT COUNT(*) FROM orchestration_intents WHERE session_id = ?"
        )
        n_plans = await cnt("SELECT COUNT(*) FROM orchestration_plans WHERE session_id = ?")
        n_tasks = await cnt("SELECT COUNT(*) FROM orchestration_tasks WHERE session_id = ?")
        n_tools = await cnt(
            "SELECT COUNT(*) FROM orchestration_tool_calls WHERE session_id = ?"
        )
        n_kb = await cnt("SELECT COUNT(*) FROM orchestration_kb_queries WHERE session_id = ?")
        n_ev = await cnt("SELECT COUNT(*) FROM orchestration_events WHERE session_id = ?")
        n_mem = await cnt(
            "SELECT COUNT(*) FROM orchestration_memory_access_log WHERE session_id = ?"
        )
    return {
        "session_id": sid,
        "orchestration_intents": n_int,
        "orchestration_plans": n_plans,
        "orchestration_tasks": n_tasks,
        "orchestration_tool_calls": n_tools,
        "orchestration_kb_queries": n_kb,
        "orchestration_events": n_ev,
        "orchestration_memory_access_log": n_mem,
    }
