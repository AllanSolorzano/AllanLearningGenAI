"""§6.4–6.5: Deterministic capability matching, policy, and planner-ready bundles (prefer MCP over shell)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from . import agent_intent_context


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if len(t) > 2}


_SHELLISH = re.compile(
    r"(shell|bash|/bin/sh|cmd\.exe|terminal|exec_command|run_command|"
    r"execute_command|subprocess|invoke_shell)",
    re.I,
)
_STRUCTURED = re.compile(
    r"(docker|container|image|pull_image|run_container|compose|kubectl|k8s|helm|"
    r"mcp|filesystem|read_file|search)",
    re.I,
)


def _is_shellish_tool(name: str) -> bool:
    return bool(_SHELLISH.search(name))


def _is_structured_tool(name: str) -> bool:
    return bool(_STRUCTURED.search(name))


def _candidate_intents_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    ci = payload.get("candidate_intents")
    if isinstance(ci, list) and ci:
        return [c for c in ci if isinstance(c, dict)]
    legacy = payload.get("intents")
    if not isinstance(legacy, list):
        return []
    out: list[dict[str, Any]] = []
    for it in legacy:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "intent": str(it.get("label") or it.get("id") or "legacy_intent"),
                "confidence": float(it.get("confidence") or 0.5),
                "entities": it.get("inferred_defaults")
                if isinstance(it.get("inferred_defaults"), dict)
                else {},
                "constraints": {},
                "reasoning": str(it.get("rationale") or ""),
            }
        )
    return out


def _primary_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(candidates, key=lambda c: float(c.get("confidence") or 0.0))


def normalize_intent_entities(entities: Any) -> dict[str, Any]:
    """§5.3: entities may be a dict or a list of strings."""
    if isinstance(entities, dict):
        return dict(entities)
    if isinstance(entities, list):
        return {"phrases": [str(x) for x in entities if str(x).strip()][:24]}
    return {}


def _score_tool_for_intent(blob: str, name: str, desc: str, user_blob: str) -> float:
    bt = _tokens(blob)
    dt = _tokens(desc) | _tokens(name.replace("__", " "))
    if not dt:
        score = 0.0
    else:
        inter = len(bt & dt)
        score = inter / max(1, len(bt)) + 0.15 * inter
    name_l = name.lower()
    for piece in bt:
        if piece and piece in name_l:
            score += 0.35
    low = user_blob.lower()
    tn = name.lower()
    if re.search(r"\b(pull|image|container|docker)\b", low) and re.search(
        r"(pull|image|container|docker)", tn
    ):
        score += 0.55
    if re.search(r"\b(run|start|up)\b", low) and re.search(r"(run|start|container)", tn):
        score += 0.45
    if _is_shellish_tool(name):
        score *= 0.35
    if _is_structured_tool(name):
        score += 0.12
    return score


def score_tool_registry_match(blob: str, name: str, desc: str, user_blob: str) -> float:
    """Layer 3 intent pipeline: same heuristic as resolver tool scoring."""
    return _score_tool_for_intent(blob, name, desc, user_blob)


def score_tool_for_query_kb_intent(blob: str, name: str, desc: str, user_blob: str) -> float:
    base = _score_tool_for_intent(blob, name, desc, user_blob)
    n = name.lower() + " " + desc.lower()
    if re.search(r"\b(search|list|read|get|fetch|resource|kb|doc|index)\b", n):
        base += 0.35
    return base


def score_tool_for_delegate_intent(blob: str, name: str, desc: str, user_blob: str) -> float:
    base = _score_tool_for_intent(blob, name, desc, user_blob)
    n = name.lower() + " " + desc.lower()
    if re.search(r"\b(agent|delegate|specialist|subagent)\b", n):
        base += 0.45
    return base


def _routing_policy(
    request_type: str,
    risk_flags: list[str],
    has_structured: bool,
    has_shell: bool,
    entities: dict[str, Any],
) -> dict[str, Any]:
    rt = (request_type or "explanation").lower()
    state_like = rt == "state_changing_execution" or "state_change" in risk_flags
    pol: dict[str, Any] = {
        "prefer_mcp_over_shell": True,
        "allow_shell_fallback": bool(has_shell and has_structured),
        "require_verification_for_state_change": state_like,
        "require_explicit_plan_args": [],
    }
    if entities.get("host_port") is not None:
        pol["require_explicit_plan_args"].append("ports")
    paths = entities.get("paths") or []
    if isinstance(paths, list) and any(
            isinstance(p, str) and "mount" in p.lower() for p in paths
        ):
        pol["require_explicit_plan_args"].append("mounts")
    if "network_exposure" in risk_flags:
        notes = pol.get("notes")
        if not isinstance(notes, list):
            notes = []
        notes.append("network_surface_change_review")
        pol["notes"] = notes
    return pol


def _verification_candidates_from_context(
    entities: dict[str, Any],
    risk_flags: list[str],
) -> list[str]:
    cands: list[str] = []
    hp = entities.get("host_port")
    if hp is not None:
        cands.append(f"HTTP HEAD/GET to http://127.0.0.1:{hp}/ or http://localhost:{hp}/")
    urls = entities.get("urls") or []
    if isinstance(urls, list) and urls:
        cands.append(f"HTTP check against user URL: {urls[0]}")
    if "state_change" in risk_flags:
        cands.append(
            "Read-only inspection of target resource state before further state changes "
            "(e.g. list containers, describe service)."
        )
    return cands


def resolve_and_policy(
    intents_payload: dict[str, Any],
    ollama_tools: list[dict[str, Any]],
    preparse: dict[str, Any] | None = None,
    *,
    deterministic_parse: dict[str, Any] | None = None,
    available_capabilities_full: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Deterministic resolution (§6.5): map intents to live tools, apply routing rules,
    emit ``planner_input`` for §6.6 (no chat history).
    """
    det = deterministic_parse or {}
    risk_flags = list(det.get("risk_flags") or [])

    request_type = str(intents_payload.get("request_type") or "explanation")
    llm_needs_clar = bool(intents_payload.get("needs_clarification"))
    llm_clar_q = intents_payload.get("clarification_question")

    candidates = _candidate_intents_from_payload(intents_payload)
    primary = _primary_candidate(candidates)

    tools_flat: list[tuple[str, str]] = []
    for t in ollama_tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        desc = str(fn.get("description") or "").strip()
        if name:
            tools_flat.append((name, desc))

    has_structured = any(_is_structured_tool(n) for n, _ in tools_flat)
    has_shell = any(_is_shellish_tool(n) for n, _ in tools_flat)

    merged_entities: dict[str, Any] = {}
    if isinstance(det.get("entities"), dict):
        merged_entities.update(det["entities"])
    if primary:
        pe = primary.get("entities")
        merged_entities = {**merged_entities, **normalize_intent_entities(pe)}
    pc = {}
    if primary:
        raw_c = primary.get("constraints")
        if isinstance(raw_c, dict):
            pc = dict(raw_c)
    policy = _routing_policy(
        request_type,
        risk_flags,
        has_structured,
        has_shell,
        merged_entities,
    )

    if policy.get("require_verification_for_state_change"):
        pc.setdefault("verify_http_after_run", bool(merged_entities.get("host_port")))
    pc.setdefault("prefer_structured_tools", policy["prefer_mcp_over_shell"])

    canon = str(primary.get("intent") or "").strip().lower() if primary else ""

    selected_bundle = {
        "intent": str(primary.get("intent") or "general") if primary else "general",
        "confidence": float(primary.get("confidence") or 0.0) if primary else 0.0,
        "entities": merged_entities,
        "constraints": pc,
        "reasoning": str(primary.get("reasoning") or "") if primary else "",
        "canonical_intent": canon or None,
    }

    blob = json.dumps(selected_bundle, default=str)[:4000]
    user_blob = " ".join(
        [
            blob,
            " ".join(str(x) for x in risk_flags),
            str(det.get("verbs") or []),
        ]
    )

    min_score = float(os.environ.get("ALLAN_CAPABILITY_SCORE_MIN", "0.18"))
    scored_all: list[tuple[float, str, str]] = []
    for name, desc in tools_flat:
        scored_all.append((_score_tool_for_intent(blob, name, desc, user_blob), name, desc))
    scored_all.sort(key=lambda x: -x[0])
    top = scored_all[:12]

    actions: list[dict[str, Any]] = []
    for score, name, desc in top:
        if score <= 0:
            continue
        actions.append(
            {
                "tool": name,
                "score": round(score, 4),
                "description": desc[:400],
                "arg_hints": {},
                "policy": (
                    "preferred_structured"
                    if _is_structured_tool(name) and not _is_shellish_tool(name)
                    else ("shellish" if _is_shellish_tool(name) else "neutral")
                ),
            }
        )

    best = top[0][0] if top else 0.0
    needs_exec = request_type in ("read_only_execution", "state_changing_execution")
    if canon in ("compose", "plan_only", "clarify"):
        needs_exec = False
    elif canon == "query_kb" and best < min_score:
        needs_exec = False
    policy_notes: list[str] = []
    rejected: list[dict[str, str]] = []
    if needs_exec and tools_flat and best < min_score:
        rejected.append(
            {
                "intent_id": selected_bundle["intent"],
                "reason": f"no_tool_above_threshold (best={best:.3f}, min={min_score})",
            }
        )
        policy_notes.append("intent_below_threshold")

    resolved = [
        {
            "intent_id": selected_bundle["intent"],
            "label": selected_bundle["intent"],
            "needs_tools": needs_exec,
            "actions": actions,
            "best_score": round(best, 4),
        }
    ]

    clarification_needed = bool(llm_needs_clar)
    clarification_reason = str(llm_clar_q) if llm_clar_q else None
    if clarification_needed:
        policy_notes.append("llm_marked_needs_clarification")

    risk_blob = " ".join(str(det.get("risk_hints") or []))
    destructive = bool(
        re.search(
            r"\b(destructive|delete\s+all|drop\s+table|wipe\s+(disk|data))\b",
            risk_blob,
            re.I,
        )
    )
    if destructive and tools_flat:
        has_safe = any(
            _is_structured_tool(n) and not _is_shellish_tool(n) for n, _ in tools_flat
        )
        if not has_safe and any(_is_shellish_tool(n) for n, _ in tools_flat):
            clarification_needed = True
            clarification_reason = (
                "High-risk phrasing with no structured MCP tools available."
            )
            policy_notes.append("blocked_destructive_without_structured_tool")
    elif needs_exec:
        if not tools_flat:
            clarification_needed = True
            clarification_reason = (
                "Execution request but MCP tool registry is empty; enable MCP tools "
                "and configure servers."
            )
            policy_notes.append("execution_intent_empty_registry")
        elif best < min_score and not clarification_needed:
            clarification_needed = True
            clarification_reason = (
                f"No tool matched above threshold ({min_score}); add structured tools "
                "or rephrase."
            )
            policy_notes.append("all_execution_intents_below_threshold")

    avail = available_capabilities_full or agent_intent_context.build_available_capabilities_detailed(
        ollama_tools
    )
    verification_candidates = _verification_candidates_from_context(merged_entities, risk_flags)
    if policy.get("require_verification_for_state_change"):
        policy_notes.append("mark_for_verification_after_state_change")

    planner_input = {
        "selected_intent": {
            "intent": selected_bundle["intent"],
            "entities": merged_entities,
            "constraints": selected_bundle["constraints"],
        },
        "available_capabilities": avail,
        "policy": policy,
        "verification_candidates": verification_candidates,
        "request_type": request_type,
        "intent_message_id": intents_payload.get("message_id"),
    }

    return {
        "resolved": resolved,
        "policy_notes": sorted(set(policy_notes)),
        "clarification_needed": clarification_needed,
        "clarification_reason": clarification_reason,
        "rejected": rejected,
        "selected_intent_bundle": selected_bundle,
        "planner_input": planner_input,
        "best_tool_score": round(best, 4),
    }
