"""Application settings persisted in SQLite (``app_settings`` table)."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from . import database

DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "provider": "ollama",
    "ollama_host": "http://127.0.0.1:11434",
    "model": "",
    "temperature": 0.3,
    "history_limit": 40,
    "use_agent_pipeline": False,
    "intent_planning": False,
    "plan_execution": True,
    "use_mcp_tools": False,
    "web_search": False,
    "synthetic_demo_tools": False,
    "max_tool_rounds": 12,
    "session_memory_write": True,
    "episodic_retrieval": True,
    "kb_retrieval": True,
    "reflective_memory": True,
    "memory_retention_days": 90,
}


def _env_from_bool(enabled: bool) -> str:
    return "1" if enabled else "0"


def _coerce_settings(raw: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(DEFAULT_APP_SETTINGS)
    if not raw:
        return out
    if isinstance(raw.get("provider"), str) and raw["provider"].strip():
        out["provider"] = raw["provider"].strip().lower()
    if isinstance(raw.get("ollama_host"), str) and raw["ollama_host"].strip():
        out["ollama_host"] = raw["ollama_host"].strip().rstrip("/")
    if isinstance(raw.get("model"), str):
        out["model"] = raw["model"].strip()
    try:
        out["temperature"] = float(raw.get("temperature", out["temperature"]))
    except (TypeError, ValueError):
        pass
    try:
        out["history_limit"] = int(raw.get("history_limit", out["history_limit"]))
    except (TypeError, ValueError):
        pass
    out["history_limit"] = max(1, min(500, int(out["history_limit"])))
    bool_keys = (
        "use_agent_pipeline",
        "intent_planning",
        "plan_execution",
        "use_mcp_tools",
        "web_search",
        "synthetic_demo_tools",
        "session_memory_write",
        "episodic_retrieval",
        "kb_retrieval",
        "reflective_memory",
    )
    for key in bool_keys:
        if key in raw:
            out[key] = bool(raw[key])
    if "intent_planning" in raw:
        out["use_agent_pipeline"] = bool(raw["intent_planning"])
    elif "use_agent_pipeline" in raw:
        out["intent_planning"] = bool(raw["use_agent_pipeline"])
    try:
        out["max_tool_rounds"] = int(raw.get("max_tool_rounds", out["max_tool_rounds"]))
    except (TypeError, ValueError):
        pass
    out["max_tool_rounds"] = max(1, min(50, int(out["max_tool_rounds"])))
    try:
        out["memory_retention_days"] = int(
            raw.get("memory_retention_days", out["memory_retention_days"])
        )
    except (TypeError, ValueError):
        pass
    out["memory_retention_days"] = max(1, min(3650, int(out["memory_retention_days"])))
    return out


async def load_app_settings() -> dict[str, Any]:
    return await database.get_app_settings()


async def save_app_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = await load_app_settings()
    merged = _coerce_settings({**current, **patch})
    await database.set_app_settings(merged)
    apply_runtime_settings(merged)
    return merged


def apply_runtime_settings(settings: dict[str, Any]) -> None:
    """Push persisted values into process env for Ollama client code."""
    host = str(settings.get("ollama_host") or "").strip()
    if host:
        os.environ["OLLAMA_HOST"] = host.rstrip("/")
    rounds = settings.get("max_tool_rounds")
    if rounds is not None:
        os.environ["OLLAMA_TOOLS_MAX_ROUNDS"] = str(int(rounds))
    os.environ["ALLAN_AGENT_MEMORY_WRITE"] = _env_from_bool(
        bool(settings.get("session_memory_write", True))
    )
    os.environ["ALLAN_EPISODIC_RETRIEVAL"] = _env_from_bool(
        bool(settings.get("episodic_retrieval", True))
    )
    os.environ["ALLAN_KB_RETRIEVAL"] = _env_from_bool(bool(settings.get("kb_retrieval", True)))
    os.environ["ALLAN_REFLECTIVE_MEMORY"] = _env_from_bool(
        bool(settings.get("reflective_memory", True))
    )
    os.environ["ALLAN_MEMORY_RETENTION_DAYS"] = str(
        int(settings.get("memory_retention_days", 90))
    )
