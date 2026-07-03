"""§5.1 Layered intent discovery: L1 (deterministic) → L2 (semantic LLM) → L3–L5 (registry + policy + scoring)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx

from . import agent_llm
from . import agent_resolve
from .agent_resolve import _is_shellish_tool


def _tools_flat(ollama_tools: list[dict[str, Any]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for t in ollama_tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        desc = str(fn.get("description") or "").strip()
        if name:
            out.append((name, desc))
    return out


def _layer3_registry_scores(
    candidates: list[dict[str, Any]],
    ollama_tools: list[dict[str, Any]],
    layer1: dict[str, Any],
    normalized_message: str,
) -> list[dict[str, Any]]:
    tools_flat = _tools_flat(ollama_tools)
    user_blob = normalized_message.lower()
    rows: list[dict[str, Any]] = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        intent = str(cand.get("intent") or "")
        blob = json.dumps(
            {
                "intent": intent,
                "entities": cand.get("entities"),
                "constraints": cand.get("constraints"),
                "reasoning": cand.get("reasoning"),
            },
            default=str,
        )[:3500]
        best = 0.0
        best_tool: str | None = None
        scorer = agent_resolve.score_tool_registry_match
        if intent == "query_kb":
            scorer = agent_resolve.score_tool_for_query_kb_intent
        elif intent == "delegate_agent":
            scorer = agent_resolve.score_tool_for_delegate_intent
        elif intent not in ("invoke_mcp", "actuate"):
            rows.append(
                {
                    **cand,
                    "registry_best_tool": None,
                    "registry_best_score": 0.0,
                }
            )
            continue
        for name, desc in tools_flat:
            s = float(scorer(blob, name, desc, user_blob))
            if s > best:
                best = s
                best_tool = name
        rows.append({**cand, "registry_best_tool": best_tool, "registry_best_score": best})
    return rows


def _layer4_policy_filter(
    matches: list[dict[str, Any]],
    layer1: dict[str, Any],
    normalized_message: str,
) -> list[dict[str, Any]]:
    low = normalized_message.lower()
    risk = set(layer1.get("risk_flags") or [])
    hints = set(layer1.get("source_hints") or [])
    out: list[dict[str, Any]] = []
    for row in matches:
        r = dict(row)
        notes: list[str] = []
        if isinstance(r.get("policy_notes"), list):
            notes.extend(str(x) for x in r["policy_notes"])
        score = float(r.get("registry_best_score") or 0.0)
        tool = r.get("registry_best_tool")
        if tool and "local_first" in hints:
            if re.search(r"(aws|gcp|azure|cloud)", str(tool), re.I):
                score *= 0.55
                notes.append("local_first_downrank_cloud_tool")
        if tool and _is_shellish_tool(str(tool)):
            score *= 0.65
            notes.append("shell_route_penalty")
        approval = "credential" in risk and str(r.get("intent")) in ("actuate", "invoke_mcp")
        if approval:
            cons = dict(r.get("constraints") or {})
            cons["human_approval_recommended"] = True
            r["constraints"] = cons
        r["policy_adjusted_score"] = round(score, 4)
        r["human_approval_suggested"] = approval
        r["policy_notes"] = notes
        out.append(r)
    return out


def _layer5_score_and_contract(
    filtered: list[dict[str, Any]],
    layer2: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pem = str(layer2.get("primary_execution_mode") or "explanation")
    for row in filtered:
        conf = float(row.get("confidence") or 0.5)
        rs = max(0.0, float(row.get("policy_adjusted_score") or 0.0))
        norm = min(1.0, rs / 1.8)
        row["final_intent_score"] = round(conf * (0.15 + 0.85 * norm), 4)
    ranked = sorted(filtered, key=lambda r: -float(r.get("final_intent_score") or 0.0))
    contract_list: list[dict[str, Any]] = []
    for r in ranked[:8]:
        ent = r.get("entities")
        if ent is None:
            ent = {}
        contract_list.append(
            {
                "intent": r.get("intent"),
                "confidence": r.get("final_intent_score"),
                "entities": ent,
                "constraints": r.get("constraints") or {},
            }
        )
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    contract = {"message_id": message_id, "candidate_intents": contract_list}
    return ranked, contract


def _build_intents_payload(
    ranked: list[dict[str, Any]],
    layer2: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    primary = ranked[0] if ranked else {}
    pi = str(primary.get("intent") or "compose").lower()
    pem = str(layer2.get("primary_execution_mode") or "explanation")
    if pi == "actuate":
        rt = "state_changing_execution"
    elif pi in ("invoke_mcp", "delegate_agent", "query_kb"):
        rt = "read_only_execution" if pem != "state_changing" else "state_changing_execution"
    else:
        rt = {
            "explanation": "explanation",
            "read_only": "read_only_execution",
            "state_changing": "state_changing_execution",
        }.get(pem, "explanation")
    cands: list[dict[str, Any]] = []
    for r in ranked:
        cands.append(
            {
                "intent": r.get("intent"),
                "confidence": float(r.get("final_intent_score") or r.get("confidence") or 0.0),
                "entities": r.get("entities") if r.get("entities") is not None else {},
                "constraints": r.get("constraints") if isinstance(r.get("constraints"), dict) else {},
                "reasoning": str(r.get("reasoning") or ""),
            }
        )
    return {
        "message_id": message_id,
        "request_type": rt,
        "candidate_intents": cands,
        "needs_clarification": bool(layer2.get("needs_clarification")),
        "clarification_question": layer2.get("clarification_question"),
        "primary_execution_mode": pem,
    }


async def run_layered_intent_discovery(
    client: httpx.AsyncClient,
    model: str,
    *,
    normalized_message: str,
    layer1: dict[str, Any],
    recent_context: list[str],
    memory_refs: list[dict[str, Any]],
    ollama_tools: list[dict[str, Any]],
    available_skills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    titles = [
        str(m.get("title") or m.get("path") or "")
        for m in memory_refs
        if isinstance(m, dict)
    ]
    titles = [t for t in titles if t][:12]

    layer2 = await agent_llm.semantic_intent_classify(
        client,
        model,
        normalized_user_message=normalized_message,
        layer1_deterministic=layer1,
        recent_context=recent_context,
        memory_ref_titles=titles,
        available_skills=available_skills or [],
    )
    candidates = list(layer2.get("candidate_intents") or [])
    layer3 = _layer3_registry_scores(candidates, ollama_tools, layer1, normalized_message)
    layer4 = _layer4_policy_filter(layer3, layer1, normalized_message)
    ranked, contract = _layer5_score_and_contract(layer4, layer2)
    mid = str(contract.get("message_id") or f"msg_{uuid.uuid4().hex[:16]}")
    intents_payload = _build_intents_payload(ranked, layer2, mid)
    return {
        "layer1": layer1,
        "layer2": layer2,
        "layer3_matches": layer3,
        "layer4_filtered": layer4,
        "layer5_ranked": ranked,
        "intent_contract": contract,
        "intents_payload": intents_payload,
    }
