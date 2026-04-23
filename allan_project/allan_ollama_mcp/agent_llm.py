"""JSON-mode and plain Ollama calls for the agent pipeline."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .ollama_service import OLLAMA_HOST


def extract_json_object(raw: str) -> dict[str, Any]:
    s = (raw or "").strip()
    if not s:
        return {}
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.I)
    if fence:
        s = fence.group(1).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


async def ollama_chat_json(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    response = await client.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "format": "json",
        },
        timeout=httpx.Timeout(600.0, connect=10.0),
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return extract_json_object(content)
    return {}


async def ollama_chat_text(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict[str, Any]],
) -> str:
    response = await client.post(
        f"{OLLAMA_HOST}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=httpx.Timeout(600.0, connect=10.0),
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    msg = data.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str) and c.strip():
        return c
    return str(c) if c is not None else response.text


SEMANTIC_INTENT_LAYER2_SYSTEM = """You are Layer 2 semantic intent classifier for a tool-orchestrating platform.
Output JSON only. Do not plan. Do not name specific MCP tool ids (you do not see the registry).

Each candidate's "intent" MUST be one of these canonical values:
query_kb | invoke_mcp | delegate_agent | compose | plan_only | clarify | actuate

Guidance:
- query_kb: find/search/retrieve docs, runbooks, indexed knowledge, "what do the docs say".
- invoke_mcp: run/list/inspect/check via MCP-exposed tools.
- delegate_agent: hand off to another agent/specialist (e.g. "ask infra agent").
- compose: summarize/explain/compare/draft without tool execution.
- plan_only: design steps / propose flow before execution.
- clarify: ambiguous or unsafe to execute without more scope.
- actuate: deploy/delete/update/restart and other state-changing ops.

Per candidate include: confidence (0..1), entities (string array OR object), constraints (object),
optional time_windows {"start": "ISO or text", "end": "ISO or text"}, reasoning (short string).

Also return:
- needs_clarification (boolean), clarification_question (string or null)
- primary_execution_mode: one of explanation | read_only | state_changing (best guess for whole message)
"""


async def semantic_intent_classify(
    client: httpx.AsyncClient,
    model: str,
    *,
    normalized_user_message: str,
    layer1_deterministic: dict[str, Any],
    recent_context: list[str],
    memory_ref_titles: list[str],
) -> dict[str, Any]:
    """§5.1 Layer 2 only: compact classifier (registry matching is NOT in this prompt)."""
    user_obj = {
        "normalized_user_message": normalized_user_message,
        "layer1_deterministic": layer1_deterministic,
        "recent_context": recent_context,
        "memory_ref_titles": memory_ref_titles,
    }
    messages = [
        {"role": "system", "content": SEMANTIC_INTENT_LAYER2_SYSTEM},
        {"role": "user", "content": json.dumps(user_obj, indent=2, default=str)},
    ]
    raw = await ollama_chat_json(client, model, messages)
    return _coerce_semantic_layer2(raw, layer1_deterministic)


async def discover_intents(
    client: httpx.AsyncClient,
    model: str,
    *,
    intent_user_payload: dict[str, Any],
) -> dict[str, Any]:
    """Backward-compatible wrapper: Layer 2 only (no L3–5). Prefer ``agent_intent_pipeline``."""
    sem = await semantic_intent_classify(
        client,
        model,
        normalized_user_message=str(intent_user_payload.get("latest_user_message", "")),
        layer1_deterministic=dict(intent_user_payload.get("deterministic_parse") or {}),
        recent_context=list(intent_user_payload.get("recent_context") or []),
        memory_ref_titles=[
            str(m.get("title") or m.get("path") or "")
            for m in (intent_user_payload.get("durable_memory_refs") or [])
            if isinstance(m, dict)
        ],
    )
    return build_resolve_intent_payload(sem)


def _coerce_semantic_layer2(
    raw: dict[str, Any],
    layer1: dict[str, Any],
) -> dict[str, Any]:
    out = raw if isinstance(raw, dict) else {}
    ci = out.get("candidate_intents")
    if not isinstance(ci, list):
        ci = []
    fixed: list[dict[str, Any]] = []
    for c in ci:
        if not isinstance(c, dict):
            continue
        intent = _normalize_canonical_intent(str(c.get("intent") or ""))
        fixed.append(
            {
                "intent": intent,
                "confidence": float(c.get("confidence") or 0.5),
                "entities": c.get("entities") if c.get("entities") is not None else {},
                "constraints": c.get("constraints")
                if isinstance(c.get("constraints"), dict)
                else {},
                "time_windows": c.get("time_windows"),
                "reasoning": str(c.get("reasoning") or "")[:500],
            }
        )
    if not fixed:
        fixed.append(
            {
                "intent": "compose",
                "confidence": 0.35,
                "entities": {},
                "constraints": {},
                "time_windows": None,
                "reasoning": "fallback_no_candidates_from_model",
            }
        )
    pem = str(out.get("primary_execution_mode") or "").lower().strip()
    if pem not in ("explanation", "read_only", "state_changing"):
        pem = str(layer1.get("execution_mode_hint") or "explanation")
    if pem not in ("explanation", "read_only", "state_changing"):
        pem = "explanation"
    return {
        "candidate_intents": fixed,
        "needs_clarification": bool(out.get("needs_clarification")),
        "clarification_question": out.get("clarification_question"),
        "primary_execution_mode": pem,
    }


CANONICAL_INTENTS = frozenset(
    {"query_kb", "invoke_mcp", "delegate_agent", "compose", "plan_only", "clarify", "actuate"}
)


def _normalize_canonical_intent(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in CANONICAL_INTENTS:
        return s
    aliases = {
        "kb": "query_kb",
        "rag": "query_kb",
        "search": "query_kb",
        "mcp": "invoke_mcp",
        "tool": "invoke_mcp",
        "tools": "invoke_mcp",
        "shell": "invoke_mcp",
        "write": "compose",
        "summarize": "compose",
        "explain": "compose",
        "plan": "plan_only",
        "ambiguous": "clarify",
        "deploy": "actuate",
        "delete": "actuate",
        "update": "actuate",
    }
    return aliases.get(s, "compose")


def build_resolve_intent_payload(sem: dict[str, Any]) -> dict[str, Any]:
    """Map Layer-2 (or full pipeline) output to ``resolve_and_policy`` input shape."""
    pem = str(sem.get("primary_execution_mode") or "explanation")
    rt = {
        "explanation": "explanation",
        "read_only": "read_only_execution",
        "state_changing": "state_changing_execution",
    }.get(pem, "explanation")
    for c in sem.get("candidate_intents") or []:
        if not isinstance(c, dict):
            continue
        if c.get("intent") == "actuate":
            rt = "state_changing_execution"
            break
    return {
        "request_type": rt,
        "candidate_intents": sem.get("candidate_intents") or [],
        "needs_clarification": sem.get("needs_clarification"),
        "clarification_question": sem.get("clarification_question"),
        "primary_execution_mode": pem,
    }


PLANNING_SYSTEM = """You are the planning engine for a tool-orchestrating multi-agent platform.
Your job is to convert a normalized request into a structured execution plan.
Do not execute anything. Return valid JSON only.
Planning rules:
1. Use atomic steps.
2. Prefer structured MCP tools over generic shell commands.
3. Add dependencies explicitly.
4. Add verification steps when the request changes state.
5. Include preconditions and postconditions where useful.
6. Add fallback only if policy allows it.
7. If the objective cannot be satisfied safely, return plan_status blocked with reason in goal/strategy fields and an empty steps array or only inspection steps.
8. Never invent a ``tool`` id: every ``tool`` value MUST be copied exactly from ``available_capabilities[].tool``. If the user asks for a capability that is not listed there, return plan_status needs_clarification or blocked instead of a fake tool name.
Return JSON with this shape:
{
  "goal": "string",
  "strategy": "string",
  "plan_status": "ready|needs_clarification|blocked",
  "steps": [
    {
      "id": "step_id",
      "title": "string",
      "kind": "action|inspection|verification|fallback",
      "tool": "exact_tool_id_from_available_capabilities",
      "args": {},
      "depends_on": [],
      "preconditions": [],
      "postconditions": [],
      "success_condition": "string or null",
      "on_failure": {"strategy": "replan|fallback|stop", "details": "string"}
    }
  ]
}
The tool field must match one of the ``tool`` values from available_capabilities exactly (e.g. serverid__toolname)."""


async def plan_graph(
    client: httpx.AsyncClient,
    model: str,
    *,
    planner_input: dict[str, Any],
) -> dict[str, Any]:
    """§6.6–6.7: Planner sees only structured planner_input (no chat transcript)."""
    user = json.dumps(planner_input, indent=2, default=str)
    messages = [
        {"role": "system", "content": PLANNING_SYSTEM},
        {"role": "user", "content": user},
    ]
    return await ollama_chat_json(client, model, messages)


async def verify_objective(
    client: httpx.AsyncClient,
    model: str,
    *,
    user_message: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    user = f"""User objective:
{user_message}

Structured execution evidence:
{json.dumps(evidence, indent=2, default=str)}

Return ONLY JSON: {{"achieved": true/false, "gaps": ["optional strings"]}}
If the user asked for a running service or reachable endpoint, require evidence of success
(e.g. tool output showing HTTP 200, listening port, or successful container start) — not only intent."""
    messages = [
        {
            "role": "system",
            "content": "You judge whether execution evidence proves the user objective. JSON only.",
        },
        {"role": "user", "content": user},
    ]
    return await ollama_chat_json(client, model, messages)


def _failed_tool_rows(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in evidence:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "tool" and e.get("status") == "error":
            out.append(
                {
                    "step_id": e.get("step_id"),
                    "tool": e.get("tool"),
                    "error_excerpt": (e.get("result_excerpt") or "")[:800],
                }
            )
    return out


REPLAN_SYSTEM = """You are the replanning engine.
A previous execution step failed or verification was incomplete.
Use the original goal, the completed steps, the failed step, and the error payload to produce a revised plan.
Return JSON only with the same schema as planning: goal, strategy, plan_status, steps (each with id, title, kind, tool, args, depends_on, preconditions, postconditions, success_condition, on_failure).
Rules:
- Do not repeat already successful steps unless required.
- If failure is caused by a conflict such as port already in use, first create inspection steps before proposing a new state-changing action.
- Prefer safe diagnostics before destructive remediation.
- Preserve the original goal unless it is impossible under policy constraints.
- tool values must match available_capabilities exactly."""


async def replan_graph(
    client: httpx.AsyncClient,
    model: str,
    *,
    user_message: str,
    prior_plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    gaps: list[str],
    planner_input: dict[str, Any],
) -> dict[str, Any]:
    failed = _failed_tool_rows(evidence)
    successful = [
        e
        for e in evidence
        if isinstance(e, dict) and e.get("type") == "tool" and e.get("status") == "ok"
    ]
    user_obj = {
        "original_user_message": user_message,
        "prior_goal": prior_plan.get("goal"),
        "prior_strategy": prior_plan.get("strategy"),
        "prior_plan_status": prior_plan.get("plan_status"),
        "completed_tool_steps_summary": successful[-12:],
        "failed_tool_steps": failed,
        "verifier_gaps": gaps,
        "available_capabilities": planner_input.get("available_capabilities"),
        "policy": planner_input.get("policy"),
        "selected_intent": planner_input.get("selected_intent"),
    }
    user = json.dumps(user_obj, indent=2, default=str)
    messages = [
        {"role": "system", "content": REPLAN_SYSTEM},
        {"role": "user", "content": user},
    ]
    return await ollama_chat_json(client, model, messages)


def _tool_ids_from_evidence(evidence: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for e in evidence or []:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "tool" and e.get("tool"):
            ids.add(str(e["tool"]))
    return sorted(ids)


async def compose_final_reply(
    client: httpx.AsyncClient,
    model: str,
    *,
    user_message: str,
    evidence: list[dict[str, Any]],
    preparse: dict[str, Any],
    system_policy: str | None = None,
) -> str:
    policy = (system_policy or "").strip()
    sys = """You write the final user-facing answer from proven facts only.
Hard rules:
- Only name MCP tools that appear in the Evidence JSON under type \"tool\" and the \"tool\" field, with the exact string shown there. If no tool step succeeded, do not describe successful tool calls.
- If every tool step has status \"skipped\" (e.g. MCP not configured) or there are no tool rows, say clearly that no remote MCP tools ran and do NOT invent tool ids such as serverid__... placeholders or generic names from the user request.
- Do not claim another agent (e.g. FinOps) ran, reviewed, or produced output unless that appears verbatim in evidence. Phrase unmet delegation as \"not executed in this turn\" or suggest what the user could do next.
- Use context/memory rows only as stated in evidence; treat pre-parse as weak hints, not facts.
- If the objective was not proven, say what was verified vs missing and the next concrete check."""
    if policy:
        sys = sys + "\n\nAdditional policy from the client system prompt:\n" + policy
    tool_ids = _tool_ids_from_evidence(evidence)
    user = f"""User message:
{user_message}

Tool ids that appear in evidence (ONLY these may be named as invoked tools; may be empty):
{json.dumps(tool_ids)}

Pre-parse (for tone/context only, not as external truth):
{json.dumps(preparse, indent=2)}

Evidence (authoritative):
{json.dumps(evidence, indent=2, default=str)}"""
    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]
    return await ollama_chat_text(client, model, messages)


async def summarize_for_memory(
    client: httpx.AsyncClient,
    model: str,
    *,
    user_message: str,
    reply: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    user = f"""Return ONLY JSON:
{{
  "title": "short title",
  "summary": "2-6 sentences of durable lessons/patterns",
  "tags": ["optional", "strings"]
}}

User:
{user_message}

Assistant reply:
{reply}

Evidence summary:
{json.dumps(evidence, indent=2, default=str)[:12000]}"""
    messages = [
        {"role": "system", "content": "Extract reusable memory for future chats. JSON only."},
        {"role": "user", "content": user},
    ]
    return await ollama_chat_json(client, model, messages)
