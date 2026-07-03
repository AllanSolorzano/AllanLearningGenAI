"""Plan execution: DAG waves with parallel ready steps (§9), MCP tool calls, normalized audit rows."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict
from typing import Any

from . import agent_llm
from . import database
from .mcp_hub import McpHub
from .ollama_service import _coerce_tool_arguments


def _step_priority(step: dict[str, Any]) -> int:
    p = step.get("priority")
    try:
        return int(p)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


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


async def _run_single_plan_step(
    hub: McpHub,
    *,
    session_id: str,
    correlation_id: str,
    plan_row_id: str | None,
    step: dict[str, Any],
    has_remote_tools: bool,
) -> tuple[str, dict[str, Any]]:
    """Execute one plan step; return (step_id, evidence_row)."""
    from .orch_store import insert_tool_call_row, update_task_status

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
    if plan_row_id:
        await update_task_status(plan_row_id, sid, "ready")

    ev: dict[str, Any]

    if do_tool and tool and has_remote_tools:
        await database.append_agent_step_event(
            session_id,
            correlation_id,
            sid,
            "running",
            tool_name=tool,
            detail={"args_keys": list(args.keys()) if isinstance(args, dict) else []},
        )
        if plan_row_id:
            await update_task_status(plan_row_id, sid, "running")
        t0 = time.perf_counter()
        try:
            body = await hub.invoke_tool(tool, args if isinstance(args, dict) else {})
            ms = int((time.perf_counter() - t0) * 1000)
            excerpt = body[:8000]
            ev = {
                "step_id": sid,
                "type": "tool",
                "kind": kind or typ,
                "title": str(step.get("title") or ""),
                "tool": tool,
                "status": "ok",
                "result_excerpt": excerpt,
                "latency_ms": ms,
                "success_condition": step.get("success_condition"),
            }
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "succeeded",
                tool_name=tool,
                detail={"response_chars": len(body)},
                latency_ms=ms,
            )
            if plan_row_id:
                await insert_tool_call_row(
                    session_id,
                    correlation_id,
                    plan_row_id,
                    sid,
                    tool,
                    args if isinstance(args, dict) else {},
                    excerpt,
                    "ok",
                    ms,
                )
                await update_task_status(plan_row_id, sid, "completed", output_json=ev)
        except Exception as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            err = str(exc)[:4000]
            ev = {
                "step_id": sid,
                "type": "tool",
                "kind": kind or typ,
                "title": str(step.get("title") or ""),
                "tool": tool,
                "status": "error",
                "result_excerpt": err,
                "latency_ms": ms,
                "on_failure": step.get("on_failure"),
            }
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                sid,
                "failed",
                tool_name=tool,
                detail={"error": err[:1200]},
                latency_ms=ms,
            )
            if plan_row_id:
                await insert_tool_call_row(
                    session_id,
                    correlation_id,
                    plan_row_id,
                    sid,
                    tool,
                    args if isinstance(args, dict) else {},
                    err,
                    "error",
                    ms,
                )
                await update_task_status(plan_row_id, sid, "failed", output_json=ev)
    elif do_tool and tool and not has_remote_tools:
        await database.append_agent_step_event(
            session_id,
            correlation_id,
            sid,
            "waiting",
            tool_name=tool,
            detail={"reason": "mcp_tools_disabled"},
        )
        ev = {
            "step_id": sid,
            "type": "tool",
            "kind": kind or typ,
            "tool": tool,
            "status": "skipped",
            "result_excerpt": "MCP tools not configured for this server.",
        }
        await database.append_agent_step_event(
            session_id,
            correlation_id,
            sid,
            "failed",
            tool_name=tool,
            detail={"reason": "skipped_no_mcp"},
        )
        if plan_row_id:
            await update_task_status(plan_row_id, sid, "failed", output_json=ev)
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
        ev = {
            "step_id": sid,
            "type": "reason",
            "kind": kind or "synthesis",
            "tool": "",
            "status": "deferred",
            "result_excerpt": excerpt,
        }
        await database.append_agent_step_event(
            session_id,
            correlation_id,
            sid,
            "succeeded",
            detail={"type": "reason_deferred_to_compose"},
        )
        if plan_row_id:
            await update_task_status(plan_row_id, sid, "completed", output_json=ev)

    await database.append_agent_turn_log(
        session_id,
        "executor_step",
        {
            "correlation_id": correlation_id,
            "step": sid,
            "evidence_tail": ev,
        },
    )
    return sid, ev


async def execute_plan_graph(
    hub: McpHub,
    *,
    session_id: str,
    correlation_id: str,
    plan: dict[str, Any],
    has_remote_tools: bool,
    plan_row_id: str | None = None,
) -> list[dict[str, Any]]:
    from .orch_store import emit_event

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

    by_id: dict[str, dict[str, Any]] = {}
    for s in steps_in:
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

    remaining: set[str] = set(by_id.keys())
    in_deg = {sid: len(preds[sid]) for sid in by_id}
    evidence: list[dict[str, Any]] = []

    ec_raw = plan.get("execution_constraints")
    if isinstance(ec_raw, list) and ec_raw:
        constraints = [str(x) for x in ec_raw[:48] if str(x).strip()]
        if constraints:
            await database.append_agent_step_event(
                session_id,
                correlation_id,
                "_constraints",
                "ok",
                detail={"execution_constraints": constraints},
            )

    await emit_event(
        session_id,
        "orchestration_execute_start",
        {"step_count": len(by_id), "plan_row_id": plan_row_id},
        correlation_id=correlation_id,
    )

    while remaining:
        ready_ids = [sid for sid in remaining if in_deg[sid] == 0]
        if not ready_ids:
            for sid in sorted(remaining):
                evidence.append(
                    {
                        "step_id": sid,
                        "type": "reason",
                        "status": "dead_letter",
                        "result_excerpt": "dependency cycle or missing predecessor; step not executed",
                    }
                )
            remaining.clear()
            break
        ready_ids.sort(key=lambda sid: (_step_priority(by_id[sid]), sid))
        batch = [by_id[sid] for sid in ready_ids]
        results = await asyncio.gather(
            *[
                _run_single_plan_step(
                    hub,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    plan_row_id=plan_row_id,
                    step=st,
                    has_remote_tools=has_remote_tools,
                )
                for st in batch
            ]
        )
        for sid_done, ev in results:
            remaining.discard(sid_done)
            evidence.append(ev)
            for sid2 in remaining:
                if sid_done in preds[sid2]:
                    in_deg[sid2] -= 1

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
    plan_row_id: str | None = None,
    root_message_id: int | None = None,
) -> list[dict[str, Any]]:
    from .orch_store import insert_plan, insert_tasks_for_plan

    max_replan = int(os.environ.get("ALLAN_AGENT_MAX_REPLANS", "2"))
    current_plan = plan
    current_evidence = list(evidence)
    current_plan_id = plan_row_id
    plan_version = 1

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
        plan_version += 1
        if current_plan_id:
            goal = str(new_plan.get("goal") or user_message[:240])
            new_id = await insert_plan(
                session_id,
                correlation_id,
                root_message_id,
                plan_version,
                goal,
                new_plan,
                status="active",
                supersedes_plan_id=current_plan_id,
            )
            await insert_tasks_for_plan(new_id, session_id, correlation_id, steps)
            current_plan_id = new_id
        extra = await execute_plan_graph(
            hub,
            session_id=session_id,
            correlation_id=correlation_id,
            plan=current_plan,
            has_remote_tools=has_remote_tools,
            plan_row_id=current_plan_id,
        )
        r = round_i + 1
        for row in extra:
            if isinstance(row, dict):
                row["replan_round"] = r
        current_evidence.extend(extra)

    return current_evidence
