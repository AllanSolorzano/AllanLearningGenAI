#!/usr/bin/env python3
"""Demo: minimal single-tool function calling."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI


def get_cluster_health(cluster: str) -> dict:
    data = {
        "prod-us-east-1": {"status": "healthy", "node_pressure": 3},
        "prod-eu-west-1": {"status": "degraded", "node_pressure": 17},
    }
    return {"cluster": cluster, **data.get(cluster, {"status": "unknown"})}


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
                "name": "get_cluster_health",
                "description": "Return health metrics for a cluster.",
                "parameters": {
                    "type": "object",
                    "properties": {"cluster": {"type": "string"}},
                    "required": ["cluster"],
                },
            },
        }
    ]

    messages = [
        {"role": "system", "content": "You are an SRE assistant. Use tools when useful."},
        {"role": "user", "content": "How is prod-eu-west-1? 2 bullets."},
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

    if first.tool_calls:
        tc = first.tool_calls[0]
        args = json.loads(tc.function.arguments)
        tool_result = get_cluster_health(args["cluster"])
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(tool_result)})

    final = client.chat.completions.create(model=model, messages=messages, temperature=0).choices[0].message
    print(final.content or "(empty response)")


if __name__ == "__main__":
    main()

