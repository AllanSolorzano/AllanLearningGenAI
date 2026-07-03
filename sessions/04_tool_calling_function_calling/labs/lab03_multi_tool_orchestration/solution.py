#!/usr/bin/env python3
"""Lab 03: Multi-Tool Orchestration (SOLUTION)"""

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
    return [
        {
            "type": "function",
            "function": {
                "name": "get_service_status",
                "description": "Get service status and SLI metrics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "environment": {"type": "string", "enum": ["prod", "staging"]},
                    },
                    "required": ["service"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_runbook",
                "description": "Get owning team and runbook URL.",
                "parameters": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                },
            },
        },
    ]


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

    for _ in range(6):
        msg = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0,
        ).choices[0].message

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in (msg.tool_calls or [])],
            }
        )

        if not msg.tool_calls:
            return msg.content or "(empty response)"

        for tc in msg.tool_calls:
            result = execute_tool(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    return "Stopped after max tool steps."


def main() -> None:
    print("\nLab 03: Multi-Tool Orchestration (Solution)\n")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is missing.")
        return
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = "Auth is failing in prod. Get status + runbook and give me a 5-step response plan."
    print(run_loop(client, model, prompt))


if __name__ == "__main__":
    main()

