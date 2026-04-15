#!/usr/bin/env python3
"""Demo: same function-calling flow, switched by provider config."""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class Provider:
    name: str
    model: str
    base_url: str | None
    api_key: str


def load_provider() -> Provider:
    load_dotenv()
    name = os.getenv("LAB_PROVIDER", "openai").strip().lower()
    if name == "openai":
        return Provider(name, os.getenv("OPENAI_MODEL", "gpt-4o-mini"), None, os.getenv("OPENAI_API_KEY", ""))
    if name == "openai_compatible":
        return Provider(
            name,
            os.getenv("OPENAI_COMPAT_MODEL", ""),
            os.getenv("OPENAI_COMPAT_BASE_URL", ""),
            os.getenv("OPENAI_COMPAT_API_KEY", ""),
        )
    if name == "ollama":
        return Provider(
            name,
            os.getenv("OLLAMA_MODEL", "llama3.2"),
            os.getenv("OLLAMA_OPENAI_BASE", "http://localhost:11434/v1"),
            os.getenv("OLLAMA_API_KEY", "ollama"),
        )
    raise ValueError(f"Unknown LAB_PROVIDER: {name}")


def main() -> None:
    provider = load_provider()
    if not provider.api_key:
        print("Missing API key for selected provider.")
        return

    client = OpenAI(api_key=provider.api_key, base_url=provider.base_url)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_status",
                "description": "Return static status for demo.",
                "parameters": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                },
            },
        }
    ]

    messages = [
        {"role": "system", "content": "Use tools when needed."},
        {"role": "user", "content": "Check payments and summarize in one line."},
    ]

    first = client.chat.completions.create(
        model=provider.model,
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

    for tc in first.tool_calls or []:
        result = {"service": "payments", "status": "degraded", "error_rate": 2.8}
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    final = client.chat.completions.create(model=provider.model, messages=messages, temperature=0).choices[0].message
    print(f"[provider={provider.name} model={provider.model}]")
    print(final.content or "(empty response)")


if __name__ == "__main__":
    main()

