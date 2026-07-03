#!/usr/bin/env python3
"""
Lab 03: ollama Python SDK & Streaming
=======================================
Call Ollama two ways — raw HTTP (requests) and the ollama Python SDK —
then add streaming so tokens appear live as they're generated.

Prerequisites:
    pip install requests ollama
    ollama pull llama3.2

Run:
    python lab.py

When stuck: check solution.py
"""

import json
import sys
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2"


# ── Implement these functions ──────────────────────────────────────────────────

def generate(prompt: str, model: str = MODEL) -> str:
    """Single-turn completion via POST /api/generate (no chat history)."""
    # TODO 1: POST f"{OLLAMA_BASE}/api/generate" with:
    #   {"model": model, "prompt": prompt, "stream": False}
    # Return r.json()["response"]
    pass


def chat(messages: list[dict], model: str = MODEL) -> str:
    """Multi-turn chat via POST /api/chat.

    messages format: [{"role": "user"/"assistant"/"system", "content": "..."}]
    """
    # TODO 2: POST f"{OLLAMA_BASE}/api/chat" with:
    #   {"model": model, "messages": messages, "stream": False}
    # Return r.json()["message"]["content"]
    pass


def chat_via_sdk(messages: list[dict], model: str = MODEL) -> str:
    """Same chat call using the ollama Python library instead of raw requests."""
    # TODO 3: import ollama at the top of the file (add to imports).
    # Call: ollama.chat(model=model, messages=messages)
    # Return: response["message"]["content"]
    # This does exactly the same thing as TODO 2 — it's a thin wrapper.
    pass


def generate_streaming(prompt: str, model: str = MODEL) -> str:
    """Stream tokens as they arrive; print them live. Return the full text."""
    # TODO 4: POST /api/generate with "stream": True
    #   Also set stream=True on the requests.post() call itself.
    # Iterate over response.iter_lines():
    #   - Skip empty lines
    #   - Parse each line: chunk = json.loads(line)
    #   - Print the token: print(chunk["response"], end="", flush=True)
    #   - Accumulate tokens in a list
    #   - When chunk["done"] is True, break
    # Return the assembled full response string.
    pass


# ── Exercises (do not modify) ──────────────────────────────────────────────────

def exercise1_generate() -> None:
    print("=" * 60)
    print("Exercise 1: POST /api/generate")
    print("=" * 60)

    prompt = "In one sentence: what is a Kubernetes Pod?"
    print(f"\n  Prompt: {prompt}")

    response = generate(prompt)
    if response is None:
        print("  (TODO 1 not complete)")
        return

    print(f"  Response: {response}")
    print("\n  /api/generate is stateless — no conversation history.")


def exercise2_chat() -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: POST /api/chat (multi-turn)")
    print("=" * 60)

    messages = [
        {"role": "system",  "content": "You are a concise SRE assistant."},
        {"role": "user",    "content": "My pod keeps restarting. First kubectl command?"},
    ]

    print(f"\n  System: {messages[0]['content']}")
    print(f"  User:   {messages[1]['content']}")

    answer = chat(messages)
    if answer is None:
        print("  (TODO 2 not complete)")
        return

    print(f"\n  Assistant: {answer}")

    # Second turn
    messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": "Logs show 'OOMKilled'. What now?"})
    print(f"\n  User: {messages[-1]['content']}")

    follow_up = chat(messages)
    if follow_up:
        print(f"  Assistant: {follow_up}")

    print("\n  YOU manage the message list — append each turn to maintain context.")


def exercise3_sdk_vs_raw() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: ollama SDK vs raw requests")
    print("=" * 60)

    messages = [{"role": "user", "content": "What does 'exit code 137' mean in a container?"}]

    print("\n  [raw requests — TODO 2]")
    api_answer = chat(messages)
    if api_answer:
        print(f"  {api_answer[:250]}")

    print("\n  [ollama SDK — TODO 3]")
    sdk_answer = chat_via_sdk(messages)
    if sdk_answer is None:
        print("  (TODO 3 not complete)")
        return
    print(f"  {sdk_answer[:250]}")

    print("\n  Both return equivalent results.")
    print("  SDK = convenience wrapper; raw requests = full control over the API.")


def exercise4_streaming() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Streaming Response")
    print("=" * 60)

    prompt = "List three common causes of high memory usage in a Kubernetes pod. Be brief."
    print(f"\n  Prompt: {prompt}")
    print("  Streaming response (tokens appear as generated):\n")

    full = generate_streaming(prompt)
    if full is None:
        print("  (TODO 4 not complete)")
        return

    print(f"\n\n  Total length: {len(full)} chars")
    print("  Response delivered as NDJSON chunks over chunked HTTP transfer.")
    print("  Use streaming whenever you need a live UI instead of a long wait.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 03: ollama SDK & Streaming\n")

    try:
        requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: Ollama is not running at {OLLAMA_BASE}")
        print("Fix: ollama serve")
        sys.exit(1)

    print(f"  Model: {MODEL} | Endpoint: {OLLAMA_BASE}\n")

    exercise1_generate()
    exercise2_chat()
    exercise3_sdk_vs_raw()
    exercise4_streaming()

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. /api/generate  — stateless single-turn completion.")
    print("  2. /api/chat      — multi-turn; YOU maintain message history.")
    print("  3. ollama SDK     — thin Python wrapper, same REST API.")
    print("  4. stream=True    — NDJSON chunks; build live token-by-token UIs.")
    print("=" * 60)


if __name__ == "__main__":
    main()
