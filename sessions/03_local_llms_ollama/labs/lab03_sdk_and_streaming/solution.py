#!/usr/bin/env python3
"""Lab 03: ollama SDK & Streaming  (SOLUTION)"""

import json
import sys

import ollama as ollama_sdk
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2"


def generate(prompt: str, model: str = MODEL) -> str:
    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
    )
    return r.json()["response"]


def chat(messages: list[dict], model: str = MODEL) -> str:
    r = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
    )
    return r.json()["message"]["content"]


def chat_via_sdk(messages: list[dict], model: str = MODEL) -> str:
    response = ollama_sdk.chat(model=model, messages=messages)
    return response["message"]["content"]


def generate_streaming(prompt: str, model: str = MODEL) -> str:
    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={"model": model, "prompt": prompt, "stream": True},
        stream=True,
    )
    tokens = []
    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        token = chunk.get("response", "")
        print(token, end="", flush=True)
        tokens.append(token)
        if chunk.get("done"):
            break
    return "".join(tokens)


def exercise1_generate() -> None:
    print("=" * 60)
    print("Exercise 1: POST /api/generate")
    print("=" * 60)
    prompt = "In one sentence: what is a Kubernetes Pod?"
    print(f"\n  Prompt: {prompt}")
    response = generate(prompt)
    print(f"  Response: {response}")


def exercise2_chat() -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: POST /api/chat (multi-turn)")
    print("=" * 60)
    messages = [
        {"role": "system", "content": "You are a concise SRE assistant."},
        {"role": "user",   "content": "My pod keeps restarting. First kubectl command?"},
    ]
    print(f"\n  System: {messages[0]['content']}")
    print(f"  User:   {messages[1]['content']}")
    answer = chat(messages)
    print(f"\n  Assistant: {answer}")
    messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": "Logs show 'OOMKilled'. What now?"})
    print(f"\n  User: {messages[-1]['content']}")
    follow_up = chat(messages)
    print(f"  Assistant: {follow_up}")


def exercise3_sdk_vs_raw() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: ollama SDK vs raw requests")
    print("=" * 60)
    messages = [{"role": "user", "content": "What does 'exit code 137' mean in a container?"}]
    print("\n  [raw requests]")
    print(f"  {chat(messages)[:250]}")
    print("\n  [ollama SDK]")
    print(f"  {chat_via_sdk(messages)[:250]}")
    print("\n  Both return equivalent results. SDK = convenience wrapper.")


def exercise4_streaming() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Streaming Response")
    print("=" * 60)
    prompt = "List three common causes of high memory usage in a Kubernetes pod. Be brief."
    print(f"\n  Prompt: {prompt}")
    print("  Streaming response:\n")
    full = generate_streaming(prompt)
    print(f"\n\n  Total length: {len(full)} chars")


def main() -> None:
    print("\nLab 03: ollama SDK & Streaming  (Solution)\n")
    try:
        requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: Ollama not running. Fix: ollama serve")
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
