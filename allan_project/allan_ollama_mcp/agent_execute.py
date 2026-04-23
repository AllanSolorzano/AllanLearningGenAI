"""Plan execution: supports §6.8 plan shape (kind, tool, on_failure) + legacy type/reason steps."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from typing import Any

from . import agent_llm
from . import database
from .mcp_hub import McpHub
from .ollama_service import _coerce_tool_arguments


def _toposort_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for s in steps:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if sid:
            by_id[sid] = s
    preds: dict[str, set[str]] = defaultdict(set)
    for sid, s in by_id.items():
        d = s.get("depends_on") or []
        if isinstance(d, list):
            for x in d:
                xs = str(x).strip()
                if xs in by_id:
                    preds[sid].add(xs)

    in_deg = {sid: len(preds[sid]) for sid in by_id}
    q = deque([sid for sid in by_id if in_deg[sid] == 0])
    out: list[dict[str, Any]] = []
    while q:
        n = q.popleft()
        out.append(by_id[n])
        for sid in by_id:
            if n in preds[sid]:
                in_deg[sid] -= 1
                if in_deg[sid] == 0:
                    q.append(sid)
    if len(out) != len(by_id):
        return list(by_id.values())
    return out


def _step_is_tool_invocation(step: dict[str, Any]) -> tuple[bool, str]:
    """Returns (should_invoke_tool, tool_name)."""
    tool = str(step.get("tool") or "").strip()
    kind = str(step.get("kind") or "").lower()
    legacy = str(step.get("type") or "").lower()
    if legacy == "tool":
        return bool(tool), tool
    if kind in ("action", "inspection", "verification", "fallback"):
        return bool(tool), tool
    if tool and legacy != "reason":
        return True, tool
    return False, tool


async def execute_plan_graph(
    hub: McpHub,
    *,
    session_id: str,
    correlation_id: str,
    plan: dict[str, Any],
    has_remote_tools: bool,
) -> list[dict[str, Any]]:
    ps = str(plan.get("plan_status") or "ready").lower()
    if ps in ("blocked", "needs_clarification"):
        detail = {
            "plan_status": ps,
            "goal": plan.get("goal"),
            "strategy": plan.get("strategy"),
        }
        await database.append_agent_step_event(
            session_id,
            correlation_id,
            "_plan",
            "failed" if ps == "blocked" else "waiting",
            detail=detail,
        )
        return [
            {
                "step_id": "_plan",
                "type": "plan",
                "kind": "blocked" if ps == "blocked" else "needs_clarification",
                "status": ps,
                "result_excerpt": json.dumps(detail, indent=2)[:8000],
            }
        ]

    steps_in = plan.get("steps")
    if not isinstance(steps_in, list) or not steps_in:
        await database.append_agent_step_event(
            session_id,
            correlation_id,
            "_plan",
            "failed",
            detail={"reason": "empty_plan"},
        )
        return [
            {
                "step_id": "noop",
                "type": "reason",
                "status": "skipped",
                "detail": "empty plan",
            }
        ]
    steps = _toposort_steps([s for s in steps_in if isinstance(s, dict)])
    evidence: list[dict[str, Any]] = []

    for step in steps:
        sid = str(step.get("id") or "").strip() or "step"
        do_tool, tool = _step_is_tool_invocation(step)
        typ = str(step.get("type") or "tool").lower()
        kind = str(step.get("kind") or "").lower()
        args_raw = step.get("args")
        args = _coerce_tool_arguments(args_raw)

        await database.append_agent_step_event(
            session_id,
            correlation_id,
            sid,
            "queued",
            tool_name=tool or None,
            detail={"type": typ, "kind": kind, "tool": tool or None},
        )

        if do_tool and tool and has_remote_tools:
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "running",
                tool_name=tool,
                detail={"args_keys": list(args.keys()) if isinstance(args, dict) else []},
            )
            t0 = time.perf_counter()
            try:
                body = await hub.invoke_tool(tool, args if isinstance(args, dict) else {})
                ms = int((time.perf_counter() - t0) * 1000)
                excerpt = body[:8000]
                evidence.append(
                    {
                        "step_id": sid,
                        "type": "tool",
                        "kind": kind or typ,
                        "title": str(step.get("title") or ""),
                        "tool": tool,
                        "status": "ok",
                        "result_excerpt": excerpt,
                        "latency_ms": ms,
                        "success_condition": step.get("success_condition"),
                    },
                )
                await database.append_agent_step_event(
                    session_id,
                    correlation_id,
                    sid,
                    "succeeded",
                    tool_name=tool,
                    detail={"response_chars": len(body)},
                    latency_ms=ms,
                )
            except Exception as exc:
                ms = int((time.perf_counter() - t0) * 1000)
                err = str(exc)[:4000]
                evidence.append(
                    {
                        "step_id": sid,
                        "type": "tool",
                        "kind": kind or typ,
                        "title": str(step.get("title") or ""),
                        "tool": tool,
                        "status": "error",
                        "result_excerpt": err,
                        "latency_ms": ms,
                        "on_failure": step.get("on_failure"),
                    },
                )
                await database.append_agent_step_event(
                    session_id,
                    correlation_id,
                    sid,
                    "failed",
                    tool_name=tool,
                    detail={"error": err[:1200]},
                    latency_ms=ms,
                )
        elif do_tool and tool and not has_remote_tools:
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "waiting",
                tool_name=tool,
                detail={"reason": "mcp_tools_disabled"},
            )
            evidence.append(
                {
                    "step_id": sid,
                    "type": "tool",
                    "kind": kind or typ,
                    "tool": tool,
                    "status": "skipped",
                    "result_excerpt": "MCP tools not configured for this server.",
                },
            )
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "failed",
                tool_name=tool,
                detail={"reason": "skipped_no_mcp"},
            )
        else:
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "running",
                detail={"type": "reason"},
            )
            excerpt = str(
                step.get("success_condition")
                or step.get("verify")
                or step.get("title")
                or ""
            )
            evidence.append(
                {
                    "step_id": sid,
                    "type": "reason",
                    "kind": kind or "synthesis",
                    "tool": "",
                    "status": "deferred",
                    "result_excerpt": excerpt,
                },
            )
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "succeeded",
                detail={"type": "reason_deferred_to_compose"},
            )

        await database.append_agent_turn_log(
            session_id,
            "executor_step",
            {
                "correlation_id": correlation_id,
                "step": sid,
                "evidence_tail": evidence[-1] if evidence else {},
            },
        )

    return evidence


async def run_verify_and_optional_replan(
    client: httpx.AsyncClient,
    model: str,
    *,
    session_id: str,
    correlation_id: str,
    user_message: str,
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    planner_input: dict[str, Any],
    hub: McpHub,
    has_remote_tools: bool,
) -> list[dict[str, Any]]:
    max_replan = int(os.environ.get("ALLAN_AGENT_MAX_REPLANS", "2"))
    current_plan = plan
    current_evidence = list(evidence)

    for round_i in range(max_replan + 1):
        verdict = await agent_llm.verify_objective(
            client,
            model,
            user_message=user_message,
            evidence=current_evidence,
        )
        await database.append_agent_turn_log(
            session_id,
            "verifier",
            {"correlation_id": correlation_id, "round": round_i, "verdict": verdict},
        )
        achieved = bool(verdict.get("achieved"))
        gaps = verdict.get("gaps")
        gap_list = [str(g) for g in gaps] if isinstance(gaps, list) else []
        if achieved or round_i >= max_replan:
            return current_evidence

        new_plan = await agent_llm.replan_graph(
            client,
            model,
            user_message=user_message,
            prior_plan=current_plan,
            evidence=current_evidence,
            gaps=gap_list,
            planner_input=planner_input,
        )
        await database.append_agent_turn_log(
            session_id,
            "replanner",
            {"correlation_id": correlation_id, "plan": new_plan},
        )
        steps = new_plan.get("steps")
        if not isinstance(steps, list) or not steps:
            return current_evidence
        current_plan = new_plan
        extra = await execute_plan_graph(
            hub,
            session_id=session_id,
            correlation_id=correlation_id,
            plan=current_plan,
            has_remote_tools=has_remote_tools,
        )
        r = round_i + 1
        for row in extra:
            if isinstance(row, dict):
                row["replan_round"] = r
        current_evidence.extend(extra)

    return current_evidence
