"""§6.1: Normalize user text, recent dialog snippets, deterministic parse block, compact capability summary."""

from __future__ import annotations

import re
from typing import Any

from . import agent_preparse


def normalize_latest_user_message(text: str) -> str:
    s = (text or "").replace("\r\n", "\n").strip()
    s = re.sub(r"[ \t]+", " ", s)
    return s


def recent_context_for_intent(
    history_msgs: list[dict[str, Any]],
    latest_normalized: str,
    *,
    max_turns: int = 6,
    max_chars: int = 420,
) -> list[str]:
    """Last few user/assistant lines only (excludes the duplicate trailing user turn when present)."""
    tail = list(history_msgs)
    if (
        tail
        and str(tail[-1].get("role") or "") == "user"
        and str(tail[-1].get("content") or "").strip() == latest_normalized.strip()
    ):
        tail = tail[:-1]
    out: list[str] = []
    for m in tail[-max_turns:]:
        role = str(m.get("role") or "")
        if role not in ("user", "assistant", "system"):
            continue
        c = str(m.get("content") or "").strip()
        if not c:
            continue
        if len(c) > max_chars:
            c = c[: max_chars - 1] + "…"
        out.append(f"{role}: {c}")
    return out


def _structured_entities(flat_entities: list[str], raw_text: str) -> dict[str, Any]:
    ent: dict[str, Any] = {"urls": [], "paths": [], "raw_spans": flat_entities[:24]}
    low = raw_text.lower()
    for e in flat_entities:
        if e.startswith("http://") or e.startswith("https://") or e.startswith("www."):
            ent["urls"].append(e)
        elif e.startswith("/") or re.match(r"^[a-zA-Z]:\\", e):
            ent["paths"].append(e)
    port_m = re.search(
        r"(?:localhost|127\.0\.0\.1)[=:](\d{2,5})\b|\bport\s+(\d{2,5})\b",
        low,
    )
    if port_m:
        p = port_m.group(1) or port_m.group(2)
        if p:
            try:
                ent["host_port"] = int(p)
            except ValueError:
                ent["host_port"] = p
    for e in flat_entities:
        if re.match(r"^[a-z0-9._-]+(/[a-z0-9._-]+)+(:[a-z0-9._-]+)?$", e, re.I) and "/" in e:
            ent.setdefault("image", e)
            break
    if "image" not in ent:
        for e in flat_entities:
            if re.match(r"^[a-z0-9._-]+$", e, re.I) and e.lower() in (
                "nginx",
                "redis",
                "postgres",
                "alpine",
                "ubuntu",
            ):
                ent["image"] = e
                break
    if "image" in ent and isinstance(ent["image"], str) and ":" not in ent["image"]:
        if re.search(r"\bnginx\b", low):
            ent["image"] = f"{ent['image']}:latest"
    if "host_port" in ent and "container_port" not in ent and re.search(r"\bnginx\b", low):
        ent["container_port"] = 80
    return ent


def _risk_flags_from_preparse(
    verbs: list[str],
    risk_hints: list[str],
) -> list[str]:
    flags: list[str] = []
    vset = {str(x).lower() for x in verbs}
    if vset & {"run", "deploy", "delete", "create", "update", "restart", "stop", "pull", "fix"}:
        flags.append("state_change")
    rh = " ".join(risk_hints).lower()
    if any(x in rh for x in ("credential", "secret", "password", "api", "token", "pii")):
        flags.append("credential")
    if "shell" in rh or "sudo" in rh or "curl" in rh or "bash" in rh:
        flags.append("shell")
    if "network_exposure" in rh or "expose" in rh or "ingress" in rh:
        flags.append("network_exposure")
    if "destructive" in rh or "rm" in rh or "delete all" in rh:
        flags.append("destructive")
    return sorted(set(flags))


def _explicit_tools_from_text(text: str) -> list[str]:
    low = text.lower()
    found: list[str] = []
    if re.search(r"\bdocker\s+mcp\b", low):
        found.append("docker_mcp")
    if re.search(r"\bmcp\b", low) and "docker mcp" not in low:
        found.append("mcp")
    if re.search(r"\b(os\s+)?command\s+execution\b|\brun\s+command\b|\bshell\b|\bbash\b", low):
        found.append("os_function")
    if re.search(r"\bkubectl\b|\bkubernetes\b|\bk8s\b", low):
        found.append("kubernetes_cli")
    return sorted(set(found))


def _layer1_action_signals(low: str, verbs: list[str]) -> dict[str, bool]:
    vs = {str(v).lower() for v in verbs}

    def has(pat: str) -> bool:
        return bool(re.search(pat, low, re.I))

    return {
        "search": has(r"\b(search|find|lookup|retrieve|query)\b") or "search" in vs,
        "list": has(r"\blist\b") or "list" in vs or "show" in vs,
        "execute": has(r"\b(execute|run|invoke|call|apply)\b") or "run" in vs,
        "summarize": has(r"\b(summarize|summary|tl;dr)\b") or "summarize" in vs,
        "delegate": has(
            r"\b(let|have|ask)\s+.{0,40}\b(agent|specialist|expert)\b|"
            r"\bdelegate\b|\binfra\s+agent\b|\bsecurity\s+agent\b"
        ),
        "inspect": has(r"\b(inspect|describe|debug|diagnose|check)\b") or "inspect" in vs,
        "compare": has(r"\b(compare|contrast|versus|vs\.?)\b") or "compare" in vs,
        "plan": has(
            r"\b(plan|design|propose|roadmap|break\s+into\s+steps|workflow)\b"
        )
        or "plan" in vs,
    }


def _layer1_source_hints(low: str) -> list[str]:
    hints: list[str] = []
    if re.search(r"\blocal(ly)?\b|\bon-?prem\b|\boffline\b", low):
        hints.append("local_first")
    if re.search(r"\b(aws|gcp|azure|cloud)\b", low):
        hints.append("cloud")
    if re.search(r"\bmcp\b|\bstdio\b", low):
        hints.append("mcp")
    return sorted(set(hints))


def deterministic_intent_parse(raw_message: str) -> dict[str, Any]:
    """Layer 1: structured block + action signals (§5.1)."""
    pr = agent_preparse.preparse_user_request(raw_message)
    flat = pr.to_dict()
    verbs = flat.get("verbs") or []
    constraints = flat.get("constraints") or []
    risk_hints = flat.get("risk_hints") or []
    flat_ents = flat.get("entities") or []
    entities = _structured_entities([str(x) for x in flat_ents], raw_message)
    low = raw_message.lower()
    signals = _layer1_action_signals(low, verbs)
    rf = _risk_flags_from_preparse(verbs, risk_hints)
    mode = "explanation"
    if "state_change" in rf:
        mode = "state_changing"
    elif any(signals.get(k) for k in ("search", "list", "inspect", "compare")):
        mode = "read_only"
    return {
        "verbs": verbs,
        "entities": entities,
        "risk_flags": rf,
        "explicit_tools": _explicit_tools_from_text(raw_message),
        "constraints": [str(x) for x in constraints][:20],
        "risk_hints": risk_hints[:20],
        "signals": signals,
        "source_hints": _layer1_source_hints(low),
        "execution_mode_hint": mode,
    }


def _shallow_args_schema(tool_entry: dict[str, Any]) -> dict[str, str]:
    fn = tool_entry.get("function") if isinstance(tool_entry, dict) else None
    if not isinstance(fn, dict):
        return {}
    params = fn.get("parameters")
    if not isinstance(params, dict):
        return {}
    props = params.get("properties")
    if not isinstance(props, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in props.items():
        if isinstance(v, dict):
            out[str(k)] = str(v.get("type", "any"))
        else:
            out[str(k)] = "any"
    return out


def build_capability_summary(ollama_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact provider → capability names (no full JSON Schema)."""
    by_provider: dict[str, list[str]] = {}
    for t in ollama_tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        if "__" in name:
            prov, cap = name.split("__", 1)
        else:
            prov, cap = "default", name
        by_provider.setdefault(prov, []).append(cap)
    return [
        {"provider": p, "capabilities": sorted(set(caps))}
        for p, caps in sorted(by_provider.items())
    ]


def build_available_capabilities_detailed(
    ollama_tools: list[dict[str, Any]],
    *,
    max_tools: int = 24,
) -> list[dict[str, Any]]:
    """Registry slice for planner: exact ``tool`` id + shallow args_schema."""
    out: list[dict[str, Any]] = []
    for t in ollama_tools[:max_tools]:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "tool": name,
                "args_schema": _shallow_args_schema(t),
                "description": str(fn.get("description") or "")[:240],
            }
        )
    return out
