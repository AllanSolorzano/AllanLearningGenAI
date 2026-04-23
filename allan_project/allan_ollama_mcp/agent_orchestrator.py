"""Pipeline: §6.1 intent context → intent JSON (§6.2–6.4) → deterministic resolve (§6.5) → plan (§6.6–6.7) → execute → verify/replan (§6.9) → compose → memory."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx

from . import agent_execute
from . import agent_intent_context
from . import agent_intent_pipeline
from . import agent_llm
from . import agent_preparse
from . import agent_resolve
from . import database
from . import memory_store
from .mcp_hub import get_default_hub


def _history_tail_for_evidence(messages: list[dict[str, Any]], max_turns: int = 8) -> str:
    lines: list[str] = []
    for m in messages[-max_turns:]:
        role = str(m.get("role") or "")
        if role == "tool":
            continue
        c = str(m.get("content") or "").strip()
        if not c:
            continue
        if len(c) > 1200:
            c = c[:1200] + "…"
        lines.append(f"{role}: {c}")
    return "\n".join(lines)


async def run_agent_turn(
    client: httpx.AsyncClient,
    *,
    session_id: str,
    user_message: str,
    model: str,
    history_msgs: list[dict[str, Any]],
    use_mcp_tools: bool,
    system_policy: str | None = None,
) -> str:
    sid = session_id.strip()
    correlation_id = str(uuid.uuid4())

    async def log(phase: str, payload: dict[str, Any]) -> None:
        merged = {**payload, "correlation_id": correlation_id}
        await database.append_agent_turn_log(sid, phase, merged)

    hub = get_default_hub()
    has_tools = bool(use_mcp_tools and hub.has_servers())
    ollama_tools: list[dict[str, Any]] = []
    if has_tools:
        ollama_tools, _ = await hub.list_ollama_tools_and_routes()

    memory_hits = await memory_store.search_relevant_memory(sid, user_message, limit=8)
    await log(
        "session_bootstrap",
        {"memory_refs": memory_hits, "note": "correlation assigned; no tools executed"},
    )

    normalized = agent_intent_context.normalize_latest_user_message(user_message)
    pre = agent_preparse.preparse_user_request(normalized)
    pre_d = pre.to_dict()
    memory_store.enrich_memory_hits_with_previews(memory_hits, max_files=3)
    await log("memory_enriched", {"memory_refs": memory_hits})
    await log("preparse", pre_d)

    det = agent_intent_context.deterministic_intent_parse(normalized)
    recent_ctx = agent_intent_context.recent_context_for_intent(
        history_msgs,
        normalized,
        max_turns=6,
    )
    avail_full = agent_intent_context.build_available_capabilities_detailed(ollama_tools)
    mem_compact = [
        {"path": h.get("path"), "title": h.get("title"), "snippet": h.get("snippet")}
        for h in memory_hits[:6]
    ]

    pipeline = await agent_intent_pipeline.run_layered_intent_discovery(
        client,
        model,
        normalized_message=normalized,
        layer1=det,
        recent_context=recent_ctx,
        memory_refs=mem_compact,
        ollama_tools=ollama_tools,
    )
    await log("intent_layer1", pipeline["layer1"])
    await log("intent_layer2", pipeline["layer2"])
    await log(
        "intent_layer3",
        {
            "matches": [
                {
                    "intent": m.get("intent"),
                    "registry_best_tool": m.get("registry_best_tool"),
                    "registry_best_score": m.get("registry_best_score"),
                }
                for m in pipeline["layer3_matches"][:16]
            ]
        },
    )
    await log(
        "intent_layer4",
        {
            "rows": [
                {
                    "intent": m.get("intent"),
                    "policy_adjusted_score": m.get("policy_adjusted_score"),
                    "approval": m.get("human_approval_suggested"),
                }
                for m in pipeline["layer4_filtered"][:16]
            ]
        },
    )
    await log(
        "intent_layer5",
        {
            "ranked": [
                {"intent": m.get("intent"), "final_intent_score": m.get("final_intent_score")}
                for m in pipeline["layer5_ranked"][:12]
            ]
        },
    )
    await log("intent_contract", pipeline["intent_contract"])
    intents_raw = pipeline["intents_payload"]
    await log("intent_discovery", intents_raw)

    cap = agent_resolve.resolve_and_policy(
        intents_raw,
        ollama_tools,
        pre_d,
        deterministic_parse=det,
        available_capabilities_full=avail_full,
    )
    await log("capability_resolve", cap)

    resolved_list = cap.get("resolved") or []
    planner_input = cap.get("planner_input") or {}
    planner_input["normalized_user_request"] = normalized

    if cap.get("clarification_needed"):
        evidence: list[dict[str, Any]] = [
            {
                "step_id": "ctx",
                "type": "context",
                "status": "ok",
                "result_excerpt": _history_tail_for_evidence(history_msgs),
            },
            {
                "step_id": "mem",
                "type": "memory",
                "status": "ok",
                "result_excerpt": json.dumps(memory_hits, indent=2)[:8000],
            },
            {
                "step_id": "policy",
                "type": "policy",
                "status": "blocked",
                "result_excerpt": json.dumps(
                    {
                        "clarification_reason": cap.get("clarification_reason"),
                        "policy_notes": cap.get("policy_notes"),
                        "rejected": cap.get("rejected"),
                    },
                    indent=2,
                )[:12000],
            },
        ]
        reply = await agent_llm.compose_final_reply(
            client,
            model,
            user_message=user_message,
            evidence=evidence,
            preparse=pre_d,
            system_policy=system_policy,
        )
        await log(
            "response_composed",
            {"reply_excerpt": reply[:2000], "via": "clarification_short_circuit"},
        )
        await _maybe_write_memory(client, model, sid, user_message, reply, evidence, log)
        await _write_trace(sid, correlation_id, pre_d, intents_raw, cap, {}, evidence)
        return reply

    plan = await agent_llm.plan_graph(client, model, planner_input=planner_input)
    if plan.get("steps") and "plan_status" not in plan:
        plan = {**plan, "plan_status": "ready"}
    if not plan.get("goal"):
        plan = {**plan, "goal": normalized[:240]}
    await log("planning", plan)

    plan_status = str(plan.get("plan_status") or "ready").lower()
    if plan_status in ("blocked", "needs_clarification"):
        evidence = [
            {
                "step_id": "ctx",
                "type": "context",
                "status": "ok",
                "result_excerpt": _history_tail_for_evidence(history_msgs),
            },
            {
                "step_id": "mem",
                "type": "memory",
                "status": "ok",
                "result_excerpt": json.dumps(memory_hits, indent=2)[:8000],
            },
            {
                "step_id": "plan",
                "type": "plan",
                "status": plan_status,
                "result_excerpt": json.dumps(plan, indent=2, default=str)[:12000],
            },
        ]
        reply = await agent_llm.compose_final_reply(
            client,
            model,
            user_message=user_message,
            evidence=evidence,
            preparse=pre_d,
            system_policy=system_policy,
        )
        await log(
            "response_composed",
            {"reply_excerpt": reply[:2000], "via": f"plan_{plan_status}"},
        )
        await _maybe_write_memory(client, model, sid, user_message, reply, evidence, log)
        await _write_trace(sid, correlation_id, pre_d, intents_raw, cap, plan, evidence)
        return reply

    evidence = [
        {
            "step_id": "ctx",
            "type": "context",
            "status": "ok",
            "result_excerpt": _history_tail_for_evidence(history_msgs),
        },
        {
            "step_id": "mem",
            "type": "memory",
            "status": "ok",
            "result_excerpt": json.dumps(memory_hits, indent=2)[:8000],
        },
    ]

    step_evidence = await agent_execute.execute_plan_graph(
        hub,
        session_id=sid,
        correlation_id=correlation_id,
        plan=plan,
        has_remote_tools=has_tools,
    )
    evidence.extend(step_evidence)

    evidence = await agent_execute.run_verify_and_optional_replan(
        client,
        model,
        session_id=sid,
        correlation_id=correlation_id,
        user_message=user_message,
        plan=plan,
        evidence=evidence,
        planner_input=planner_input,
        hub=hub,
        has_remote_tools=has_tools,
    )

    reply = await agent_llm.compose_final_reply(
        client,
        model,
        user_message=user_message,
        evidence=evidence,
        preparse=pre_d,
        system_policy=system_policy,
    )
    await log("response_composed", {"reply_excerpt": reply[:2000]})

    await _maybe_write_memory(client, model, sid, user_message, reply, evidence, log)

    await _write_trace(sid, correlation_id, pre_d, intents_raw, cap, plan, evidence)

    return reply


async def _maybe_write_memory(
    client: httpx.AsyncClient,
    model: str,
    sid: str,
    user_message: str,
    reply: str,
    evidence: list[dict[str, Any]],
    log,
) -> None:
    if os.environ.get("ALLAN_AGENT_MEMORY_WRITE", "1").strip().lower() in ("0", "false", "no"):
        return
    mem_json = await agent_llm.summarize_for_memory(
        client,
        model,
        user_message=user_message,
        reply=reply,
        evidence=evidence,
    )
    title = str(mem_json.get("title") or "Session note").strip()
    summary = str(mem_json.get("summary") or "").strip()
    tags = mem_json.get("tags")
    tag_line = ""
    if isinstance(tags, list) and tags:
        tag_line = "\n\nTags: " + ", ".join(str(x) for x in tags[:12])
    if summary:
        await memory_store.write_memory_markdown(
            sid,
            title,
            summary + tag_line,
        )
        await log("memory_writer", {"title": title, "stored": True})


async def _write_trace(
    sid: str,
    correlation_id: str,
    pre_d: dict[str, Any],
    intents_raw: dict[str, Any],
    cap: dict[str, Any],
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> None:
    trace_body = "\n\n".join(
        [
            f"correlation_id: `{correlation_id}`",
            "## Preparse\n" + json.dumps(pre_d, indent=2),
            "## Intents\n" + json.dumps(intents_raw, indent=2)[:12000],
            "## Capability + policy\n" + json.dumps(cap, indent=2)[:12000],
            "## Plan\n" + json.dumps(plan, indent=2)[:12000],
            "## Evidence (final)\n" + json.dumps(evidence, indent=2, default=str)[:16000],
        ]
    )
    await memory_store.append_trace_markdown(sid, "Agent pipeline trace", trace_body)
