#!/usr/bin/env python3
"""Demo: incident helper using two tools in one loop."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI


STATUS = {
    "auth": {"status": "down", "error_rate": 18.4},
    "payments": {"status": "degraded", "error_rate": 2.8},
}

RUNBOOKS = {
    "auth": {"owner": "team-identity", "url": "https://internal/runbooks/auth"},
    "payments": {"owner": "team-payments", "url": "https://internal/runbooks/payments"},
}


def execute_tool(name: str, args_json: str) -> dict:
    args = json.loads(args_json) if args_json else {}
    if name == "get_service_status":
        return {"service": args["service"], **STATUS.get(args["service"], {"error": "unknown service"})}
    if name == "get_runbook":
        return {"service": args["service"], **RUNBOOKS.get(args["service"], {"error": "unknown service"})}
    return {"error": f"unknown tool {name}"}


def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Set OPENAI_API_KEY first.")
        return

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_service_status",
                "description": "Get service status and error rate.",
                "parameters": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
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

    messages = [
        {"role": "system", "content": "You are an SRE incident assistant. Use tools for facts."},
        {"role": "user", "content": "Auth is failing. Get facts and return a 5-step response plan."},
    ]

    for _ in range(5):
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
            print(msg.content or "(empty response)")
            return

        for tc in msg.tool_calls:
            result = execute_tool(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    print("Stopped after max tool steps.")


if __name__ == "__main__":
    main()

