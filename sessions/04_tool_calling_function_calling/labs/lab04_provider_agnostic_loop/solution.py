#!/usr/bin/env python3
"""Lab 04: Provider-Agnostic Tool Calling Loop (SOLUTION)"""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class ProviderConfig:
    provider: str
    model: str
    base_url: str | None
    api_key: str


SERVICE_DB = {
    ("payments", "prod"): {"status": "degraded", "error_rate": 2.8, "p95_ms": 780},
    ("payments", "staging"): {"status": "healthy", "error_rate": 0.2, "p95_ms": 140},
    ("auth", "prod"): {"status": "down", "error_rate": 18.4, "p95_ms": 0},
}


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_provider_config() -> ProviderConfig:
    load_dotenv()
    provider = os.getenv("LAB_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        return ProviderConfig(
            provider=provider,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            base_url=None,
            api_key=_required("OPENAI_API_KEY"),
        )
    if provider == "openai_compatible":
        return ProviderConfig(
            provider=provider,
            model=_required("OPENAI_COMPAT_MODEL"),
            base_url=_required("OPENAI_COMPAT_BASE_URL"),
            api_key=_required("OPENAI_COMPAT_API_KEY"),
        )
    if provider == "ollama":
        return ProviderConfig(
            provider=provider,
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            base_url=os.getenv("OLLAMA_OPENAI_BASE", "http://localhost:11434/v1"),
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
        )
    raise ValueError(f"Unknown LAB_PROVIDER: {provider}")


def build_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_service_status",
                "description": "Get service health metrics.",
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


def execute_tool(name: str, args_json: str) -> dict:
    try:
        args = json.loads(args_json) if args_json else {}
        if name != "get_service_status":
            return {"error": f"unknown tool: {name}"}
        service = args["service"]
        env = args.get("environment", "prod")
        data = SERVICE_DB.get((service, env))
        if not data:
            return {"error": f"unknown service/env: {service}/{env}"}
        return {"service": service, "environment": env, **data}
    except Exception as e:
        return {"error": str(e)}


def run_loop(client: OpenAI, model: str, prompt: str) -> str:
    tools = build_tools()
    messages = [
        {"role": "system", "content": "You are an SRE assistant. Use tools when needed."},
        {"role": "user", "content": prompt},
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
            return msg.content or "(empty response)"

        for tc in msg.tool_calls:
            result = execute_tool(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    return "Stopped after max tool steps."


def main() -> None:
    print("\nLab 04: Provider-Agnostic Tool Calling Loop (Solution)\n")
    cfg = load_provider_config()
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    print(f"Provider: {cfg.provider} | Model: {cfg.model} | Base: {cfg.base_url or 'default'}")
    print(
        "\n"
        + run_loop(
            client,
            cfg.model,
            "Compare payments status in staging vs prod in 3 bullets.",
        )
    )


if __name__ == "__main__":
    main()

