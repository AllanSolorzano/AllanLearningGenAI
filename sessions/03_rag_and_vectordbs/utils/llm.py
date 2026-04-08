"""
LLM abstraction layer for Session 03.

Automatically chooses the backend:
  1. Anthropic Claude   — if ANTHROPIC_API_KEY is set
  2. Ollama (local)     — fallback, model configurable

Usage:
    from utils.llm import get_llm, ask

    llm = get_llm()
    response = ask(llm, system="You are an SRE.", user="What is a CrashLoopBackOff?")
    print(response)
"""

import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class LLMConfig:
    backend: Literal["anthropic", "ollama"]
    model: str
    api_key: str | None = None
    base_url: str = "http://localhost:11434"


def get_llm(
    prefer_local: bool = False,
    ollama_model: str = "llama3.2",
    anthropic_model: str = "claude-haiku-4-5-20251001",
) -> LLMConfig:
    """Return the best available LLM config.

    Args:
        prefer_local: Force Ollama even if Anthropic key is available
        ollama_model: Which Ollama model to use
        anthropic_model: Which Anthropic model to use
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_anthropic = bool(api_key) and len(api_key) > 20

    if has_anthropic and not prefer_local:
        return LLMConfig(backend="anthropic", model=anthropic_model, api_key=api_key)

    # Check if Ollama is reachable
    if _ollama_available():
        return LLMConfig(backend="ollama", model=ollama_model)

    if has_anthropic:
        # Ollama not available, fall back to Anthropic even if prefer_local
        print("  [LLM] Ollama not running — falling back to Anthropic API")
        return LLMConfig(backend="anthropic", model=anthropic_model, api_key=api_key)

    raise RuntimeError(
        "No LLM backend available.\n"
        "Option A: Add ANTHROPIC_API_KEY to your .env file\n"
        "Option B: Install and start Ollama: https://ollama.com\n"
        "          Then run: ollama pull llama3.2"
    )


def _ollama_available() -> bool:
    """Check if Ollama is running on localhost."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def ask(
    config: LLMConfig,
    user: str,
    system: str = "",
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """Send a message and return the response text.

    Args:
        config: LLMConfig from get_llm()
        user: The user message
        system: Optional system prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature

    Returns:
        Response text as a string
    """
    if config.backend == "anthropic":
        return _ask_anthropic(config, user, system, max_tokens, temperature)
    else:
        return _ask_ollama(config, user, system, max_tokens, temperature)


def _ask_anthropic(config: LLMConfig, user: str, system: str, max_tokens: int, temperature: float) -> str:
    try:
        import anthropic as anthropic_sdk
    except ImportError:
        raise RuntimeError("pip install anthropic")

    client = anthropic_sdk.Anthropic(api_key=config.api_key)
    kwargs: dict = {
        "model": config.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text


def _ask_ollama(config: LLMConfig, user: str, system: str, max_tokens: int, temperature: float) -> str:
    try:
        import ollama
    except ImportError:
        raise RuntimeError("pip install ollama")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    response = ollama.chat(
        model=config.model,
        messages=messages,
        options={"num_predict": max_tokens, "temperature": temperature},
    )
    return response["message"]["content"]


def describe(config: LLMConfig) -> str:
    """Human-readable description of the active backend."""
    if config.backend == "anthropic":
        return f"Anthropic ({config.model})"
    else:
        return f"Ollama local ({config.model})"
