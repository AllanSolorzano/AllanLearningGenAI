#!/usr/bin/env python3
"""Lab 02: Single Tool Loop (SOLUTION)"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI


SERVICE_DB = {
    ("payments", "prod"): {"status": "degraded", "error_rate": 2.8, "p95_ms": 780},
    ("payments", "staging"): {"status": "healthy", "error_rate": 0.2, "p95_ms": 140},
}


def build_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_service_status",
                "description": "Get service status and core SLI metrics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "environment": {"type": "string", "enum": ["prod", "staging"]},
                    },
                    "required": ["service"],
                },
            },
        }
    ]


def get_service_status(service: str, environment: str = "prod") -> dict:
    data = SERVICE_DB.get((service, environment))
    if not data:
        return {"error": f"unknown service/environment: {service}/{environment}"}
    return {"service": service, "environment": environment, **data}


def run_single_tool_loop(client: OpenAI, model: str, prompt: str) -> str:
    tools = build_tools()
    messages = [
        {"role": "system", "content": "You are an SRE assistant. Use tools when needed."},
        {"role": "user", "content": prompt},
    ]

    first = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0,
    ).choices[0].message

    messages.append(
        {
            "role": "assistant",
            "content": first.content or "",
            "tool_calls": [tc.model_dump() for tc in (first.tool_calls or [])],
        }
    )

    if not first.tool_calls:
        return first.content or "(empty response)"

    tc = first.tool_calls[0]
    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
    result = get_service_status(
        service=args["service"],
        environment=args.get("environment", "prod"),
    )
    messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    final = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    ).choices[0].message

    return final.content or "(empty response)"


def main() -> None:
    print("\nLab 02: Single Tool Loop (Solution)\n")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is missing.")
        return
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    prompt = "How is payments service doing in prod? Give 2 bullets."
    print(run_single_tool_loop(client, model, prompt))


if __name__ == "__main__":
    main()

