"""Deterministic pre-parser: verbs, entities (images, paths, ports, clouds), risk hints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_URL_RE = re.compile(
    r"https?://[^\s)>\]}]+|www\.[^\s)>\]}]+",
    re.I,
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
_HOST_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+(?:[a-zA-Z]{2,})\b"
)
_QUOTED_RE = re.compile(r'"([^"]{1,200})"|\'([^\']{1,200})\'')

# OCI-style image refs (heuristic): repo/name or registry/repo/name[:tag]
_DOCKER_IMAGE_RE = re.compile(
    r"\b(?:docker\s+)?(?:pull|run|push)\s+([a-z0-9@._/:+-]{2,120})\b|"
    r"\b([a-z0-9][a-z0-9_.-]{0,40}/[a-z0-9][a-z0-9_.-]{0,40}(?::[a-z0-9_.-]{1,40})?)\b",
    re.I,
)
_PORT_RE = re.compile(
    r"\b(?:localhost|127\.0\.0\.1)[=:](\d{2,5})\b|\bport\s+(\d{2,5})\b|\b:\s*(\d{2,5})\b",
    re.I,
)
_UNIX_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])(/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.@_-]+)+)(?=\s|$|[,;:\"')]])"
)
_WIN_PATH_RE = re.compile(r"\b[a-zA-Z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*")

_CLOUD_RE = re.compile(
    r"\b(aws|amazon web services|gcp|google cloud|azure|microsoft azure|"
    r"kubernetes|k8s|eks|gke|aks|helm|terraform|pulumi)\b",
    re.I,
)
_AGENT_RE = re.compile(
    r"\b(ai\s+agent|llm agent|copilot|cursor\s*agent|chatgpt|claude|gemini)\b",
    re.I,
)

_RISK_WORDS = re.compile(
    r"\b("
    r"outage|incident|sev[0-3]|rollback|blast\s*radius|"
    r"production|prod\b|customer|pii|credential|secret|password|api[_-]?key|token|"
    r"exploit|vulnerability|cve|root\s*shell|privilege|"
    r"irreversible|destructive|delete\s+all|drop\s+table|rm\s+-rf"
    r")\b",
    re.I,
)
_SHELL_RISK_RE = re.compile(
    r"\b(shell|bash|sh\b|sudo|chmod\s+777|curl\s+[^|\n]+\|\s*sh|wget\s+[^|\n]+\|\s*bash|"
    r"eval\s*\(|exec\s*\(|subprocess|pipe\s+to)\b",
    re.I,
)
_NET_EXPOSE_RE = re.compile(
    r"\b(expose|public|0\.0\.0\.0|::/0|ingress|load\s*balancer|"
    r"open\s+port|port\s+forward|unauthenticated)\b",
    re.I,
)

_CONSTRAINT_WORDS = re.compile(
    r"\b("
    r"must|should\s+not|do\s+not|don't|never|only|at\s+least|at\s+most|"
    r"before|after|deadline|sla|budget|timeout|throttle|rate\s*limit"
    r")\b",
    re.I,
)

_OPERATION_VERBS = (
    "pull",
    "run",
    "stop",
    "start",
    "inspect",
    "search",
    "explain",
    "summarize",
    "ask",
    "list",
    "show",
    "get",
    "fetch",
    "check",
    "verify",
    "fix",
    "deploy",
    "restart",
    "delete",
    "create",
    "update",
    "compare",
    "debug",
)


@dataclass
class PreParseResult:
    entities: list[str] = field(default_factory=list)
    verbs: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risk_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "entities": self.entities,
            "verbs": self.verbs,
            "constraints": self.constraints,
            "risk_hints": self.risk_hints,
        }


def preparse_user_request(text: str) -> PreParseResult:
    t = (text or "").strip()
    out = PreParseResult()
    seen: set[str] = set()

    def add(target: list[str], s: str) -> None:
        s = s.strip()
        if len(s) < 2 or s in seen:
            return
        seen.add(s)
        target.append(s[:500])

    for m in _URL_RE.finditer(t):
        add(out.entities, m.group(0))
    for m in _EMAIL_RE.finditer(t):
        add(out.entities, m.group(0))
    for m in _IPV4_RE.finditer(t):
        add(out.entities, m.group(0))
    for m in _HOST_RE.finditer(t):
        g = m.group(0)
        if g.lower() not in ("e.g.", "i.e."):
            add(out.entities, g)
    for m in _QUOTED_RE.finditer(t):
        inner = m.group(1) or m.group(2) or ""
        add(out.entities, inner)

    for m in _DOCKER_IMAGE_RE.finditer(t):
        g = next((x for x in m.groups() if x), "")
        if g:
            add(out.entities, g.strip())
    for m in _PORT_RE.finditer(t):
        port = next((x for x in m.groups() if x), "")
        if port:
            add(out.entities, f"port:{port}")
    for m in _UNIX_PATH_RE.finditer(t):
        add(out.entities, m.group(1))
    for m in _WIN_PATH_RE.finditer(t):
        add(out.entities, m.group(0))
    for m in _CLOUD_RE.finditer(t):
        add(out.entities, m.group(1))
    for m in _AGENT_RE.finditer(t):
        add(out.entities, m.group(1))

    first = t.split()
    if first:
        w0 = re.sub(r"[^a-zA-Z]", "", first[0])
        if w0 and not w0[0].islower() and len(w0) > 2:
            add(out.verbs, w0.lower())

    low = t.lower()
    for v in _OPERATION_VERBS:
        if re.search(rf"\b{re.escape(v)}(ing|ed|s)?\b", low):
            add(out.verbs, v)

    for m in _CONSTRAINT_WORDS.finditer(t):
        add(out.constraints, m.group(0))
    for m in _RISK_WORDS.finditer(t):
        add(out.risk_hints, m.group(0))
    for m in _SHELL_RISK_RE.finditer(t):
        add(out.risk_hints, f"shell_usage:{m.group(0)}")
    for m in _NET_EXPOSE_RE.finditer(t):
        add(out.risk_hints, f"network_exposure:{m.group(0)}")

    return out
