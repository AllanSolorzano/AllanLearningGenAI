#!/usr/bin/env python3
"""
Lab 03: Multi-Tool Orchestration
================================
Handle multiple tool calls and return a grounded final incident plan.

Prerequisites:
    OPENAI_API_KEY set

Run:
    python lab.py
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI


SERVICE_DB = {
    ("payments", "prod"): {"status": "degraded", "error_rate": 2.8, "p95_ms": 780},
    ("auth", "prod"): {"status": "down", "error_rate": 18.4, "p95_ms": 0},
}

RUNBOOK_DB = {
    "payments": {"owner": "team-payments", "url": "https://internal/runbooks/payments"},
    "auth": {"owner": "team-identity", "url": "https://internal/runbooks/auth"},
}


def build_tools() -> list[dict]:
    # TODO 1:
    # Return two tool schemas:
    # - get_service_status(service, environment)
    # - get_runbook(service)
    pass


def execute_tool(name: str, arguments_json: str) -> dict:
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        if name == "get_service_status":
            data = SERVICE_DB.get((args["service"], args.get("environment", "prod")))
            if not data:
                return {"error": "service status not found"}
            return {"service": args["service"], "environment": args.get("environment", "prod"), **data}
        if name == "get_runbook":
            data = RUNBOOK_DB.get(args["service"])
            if not data:
                return {"error": "runbook not found"}
            return {"service": args["service"], **data}
        return {"error": f"unknown tool: {name}"}
    except Exception as e:
        return {"error": str(e)}


def run_loop(client: OpenAI, model: str, prompt: str) -> str:
    tools = build_tools()
    messages = [
        {"role": "system", "content": "You are an SRE assistant. Use tools and cite tool-derived facts."},
        {"role": "user", "content": prompt},
    ]

    # TODO 2:
    # Implement loop up to 6 iterations:
    # - call model with tools
    # - append assistant message (with tool_calls)
    # - if no tool_calls, return text
    # - for each tool call, execute and append tool message
    # - after max iterations, return fallback text
    pass


def main() -> None:
    print("\nLab 03: Multi-Tool Orchestration\n")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is missing.")
        return

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = "Auth is failing in prod. Get status + runbook and give me a 5-step response plan."
    answer = run_loop(client, model, prompt)
    if answer is None:
        print("TODO not complete")
        return
    print(answer)


if __name__ == "__main__":
    main()

