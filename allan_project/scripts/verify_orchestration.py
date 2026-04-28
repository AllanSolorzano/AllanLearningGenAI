#!/usr/bin/env python3
"""Exercise HTTP orchestration surfaces (requires ``uv run allan-api`` and Ollama).

Checks:
  - POST /sessions, POST /chat with use_agent_pipeline
  - GET /sessions/{id}/agent-trace returns turn_logs (phases) for auditability

Usage:
  API_BASE=http://127.0.0.1:8000 uv run python scripts/verify_orchestration.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")

    def req(
        method: str,
        path: str,
        *,
        data: dict | None = None,
    ) -> tuple[int, dict | list | str]:
        url = f"{base}{path}"
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        r = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                code = resp.getcode() or 200
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            print(f"HTTP {e.code} {path}: {parsed}", file=sys.stderr)
            return e.code, parsed
        except urllib.error.URLError as e:
            print(f"Cannot reach {base}: {e}", file=sys.stderr)
            print("Start the API:  cd allan_project && uv run allan-api", file=sys.stderr)
            return 1, str(e)
        try:
            return code, json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return code, raw

    code, health = req("GET", "/health")
    if code != 200:
        return 1
    print("health:", health)

    code, sess = req("POST", "/sessions", data={"title": "verify_orchestration"})
    if code != 200 or not isinstance(sess, dict) or not sess.get("id"):
        print("Failed to create session", file=sys.stderr)
        return 1
    sid = sess["id"]
    print("session:", sid[:8] + "…")

    code, chat = req(
        "POST",
        "/chat",
        data={
            "message": "Say hello in one short sentence. No tools needed.",
            "session_id": sid,
            "history_limit": 10,
            "use_mcp_tools": False,
            "use_agent_pipeline": True,
        },
    )
    if code != 200:
        print("POST /chat failed (is Ollama running?)", file=sys.stderr)
        return 1
    assert isinstance(chat, dict)
    print("reply snippet:", (chat.get("reply") or "")[:120].replace("\n", " "))
    orch = chat.get("orchestration")
    if not orch:
        print("WARN: orchestration missing (agent path should return it)", file=sys.stderr)
    else:
        print("orchestration keys:", sorted(orch.keys()))
        stages = orch.get("pipeline_stages") or []
        print("pipeline stages:", [s.get("label") for s in stages])

    code, trace = req("GET", f"/sessions/{sid}/agent-trace?log_limit=80&event_limit=100")
    if code != 200 or not isinstance(trace, dict):
        print("GET agent-trace failed", file=sys.stderr)
        return 1
    logs = trace.get("turn_logs") or []
    events = trace.get("step_events") or []
    phases = [x.get("phase") for x in logs if isinstance(x, dict)]
    print("agent-trace turn_logs:", len(logs), "phases sample:", phases[:12], "…" if len(phases) > 12 else "")
    print("agent-trace step_events:", len(events))
    ho = trace.get("handoffs") or []
    print("agent-trace handoffs:", len(ho))
    if not phases:
        print("WARN: no turn_logs yet — run used agent pipeline?", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
