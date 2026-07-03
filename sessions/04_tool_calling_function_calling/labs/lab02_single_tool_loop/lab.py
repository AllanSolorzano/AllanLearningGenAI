#!/usr/bin/env python3
"""
Lab 02: Single Tool Loop
========================
Implement one full function-calling cycle with OpenAI Chat Completions.

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

    # TODO 1:
    # Call client.chat.completions.create(...) with model/messages/tools/tool_choice=auto.
    # Get assistant message.
    # If no tool call: return assistant content.
    # If tool call exists:
    #   parse arguments, execute get_service_status(...), append tool result message,
    #   call model one more time and return final text.
    pass


def main() -> None:
    print("\nLab 02: Single Tool Loop\n")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is missing.")
        return

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    prompt = "How is payments service doing in prod? Give 2 bullets."

    result = run_single_tool_loop(client, model, prompt)
    if result is None:
        print("TODO 1 not complete")
        return

    print(result)


if __name__ == "__main__":
    main()

