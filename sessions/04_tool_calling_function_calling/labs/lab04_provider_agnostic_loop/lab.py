#!/usr/bin/env python3
"""
Lab 04: Provider-Agnostic Tool Calling Loop
===========================================
Use one function-calling loop across:
  - OpenAI
  - OpenAI-compatible hosted providers
  - Local Ollama via OpenAI-compatible /v1 API

Run:
    python lab.py
"""

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


def load_provider_config() -> ProviderConfig:
    # TODO 1:
    # load .env and read LAB_PROVIDER defaulting to "openai".
    # provider=openai:
    #   model=OPENAI_MODEL(default gpt-4o-mini), base_url=None, api_key=OPENAI_API_KEY(required)
    # provider=openai_compatible:
    #   model/base_url/api_key from OPENAI_COMPAT_MODEL / OPENAI_COMPAT_BASE_URL / OPENAI_COMPAT_API_KEY (required)
    # provider=ollama:
    #   model=OLLAMA_MODEL(default llama3.2), base_url=OLLAMA_OPENAI_BASE(default http://localhost:11434/v1), api_key=OLLAMA_API_KEY(default ollama)
    # unknown provider -> raise ValueError
    pass


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

    # TODO 2:
    # Implement standard loop up to 5 iterations:
    # - call chat.completions with tools
    # - append assistant message incl tool_calls
    # - if no tool_calls => return assistant content
    # - execute each tool, append tool message, continue
    # - return fallback after max iterations
    pass


def main() -> None:
    print("\nLab 04: Provider-Agnostic Tool Calling Loop\n")
    cfg = load_provider_config()
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    print(f"Provider: {cfg.provider} | Model: {cfg.model} | Base: {cfg.base_url or 'default'}")
    answer = run_loop(
        client,
        cfg.model,
        "Compare payments status in staging vs prod in 3 bullets.",
    )
    if answer is None:
        print("TODO not complete")
        return
    print("\n" + answer)


if __name__ == "__main__":
    main()

