"""Load persisted policies and merge evaluation hints into planner input (approval gates, locality)."""

from __future__ import annotations

import re
from typing import Any

from .orch_store import list_policies_enabled


def _hints(planner_input: dict[str, Any]) -> set[str]:
    raw = (planner_input.get("deterministic_parse") or {}).get("source_hints") or []
    if isinstance(raw, (list, tuple, set)):
        return {str(x) for x in raw if str(x).strip()}
    return set()


async def augment_planner_input(planner_input: dict[str, Any], cap: dict[str, Any]) -> dict[str, Any]:
    """Attach ``registered_policies`` and ``approval_gates`` for the planner LLM."""
    policies = await list_policies_enabled()
    gates: list[dict[str, Any]] = []
    locality_notes: list[str] = []
    hints = _hints(planner_input)
    exec_ctx = planner_input.get("execution_context") if isinstance(planner_input.get("execution_context"), dict) else {}
    env = str((exec_ctx or {}).get("environment") or "").lower()
    out = dict(planner_input)
    mem_policies: list[dict[str, Any]] = []
    for p in policies:
        pt = str(p.get("policy_type") or "")
        cond = p.get("condition") if isinstance(p.get("condition"), dict) else {}
        if pt == "memory_write_guardrail":
            mem_policies.append({"policy_name": p.get("policy_name"), "action": p.get("action")})
            continue
        if pt == "approval_gate":
            want_env = str(cond.get("environment") or "").lower()
            want_mode = str(cond.get("mode") or "").lower()
            if want_env and want_env in env and want_mode == "write":
                gates.append({"policy_name": p.get("policy_name"), "action": p.get("action")})
            continue
        if pt == "data_locality":
            need = str(cond.get("hints_contain") or "")
            if need and need in hints:
                act = p.get("action") or {}
                if act.get("prefer_local_mcp"):
                    locality_notes.append("prefer_local_mcp")
    if mem_policies:
        out["memory_write_policies"] = mem_policies
    out["registered_policies"] = [
        {"policy_name": x.get("policy_name"), "type": x.get("policy_type")} for x in policies
    ]
    if gates:
        out["approval_gates"] = gates
    if locality_notes:
        out["data_locality_hints"] = locality_notes
    return out


def memory_write_blocked(summary_text: str, policies: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Return (blocked, reason) if summary matches secret patterns from memory guardrail policies."""
    low = summary_text.lower()
    for p in policies:
        if p.get("policy_type") != "memory_write_guardrail":
            continue
        cond = p.get("condition") or {}
        needles = cond.get("memory_candidate_contains") or []
        if not isinstance(needles, list):
            continue
        for n in needles:
            token = str(n).lower().strip()
            if len(token) >= 3 and re.search(rf"\b{re.escape(token)}\b", low):
                return True, str(p.get("policy_name"))
    return False, None
