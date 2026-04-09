#!/usr/bin/env python3
"""
Demo: Interactive Streaming Chat
==================================
REPL-style chatbot with live token streaming. Maintains full conversation
history so the model remembers context across turns.

Usage:
    python demo_streaming_chat.py
    python demo_streaming_chat.py --model mistral
    python demo_streaming_chat.py --system "You are a Kubernetes expert. Be concise."

Commands during chat:
    /exit          quit
    /clear         reset conversation history
    /system <msg>  change system prompt (clears history)
    /model <name>  switch model (clears history)
    /history       show current turn count
"""

import argparse
import json
import sys
import requests

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_SYSTEM = "You are a helpful SRE assistant. Be concise and practical."


def stream_chat(messages: list[dict], model: str) -> str:
    """Stream assistant reply token by token. Return full response text."""
    r = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
        timeout=180,
    )
    tokens = []
    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        token = chunk.get("message", {}).get("content", "")
        print(token, end="", flush=True)
        tokens.append(token)
        if chunk.get("done"):
            break
    print()
    return "".join(tokens)


def run_chat(model: str, system_prompt: str) -> None:
    messages = [{"role": "system", "content": system_prompt}]

    print(f"\n  Model:  {model}")
    print(f"  System: {system_prompt}")
    print("  Commands: /exit  /clear  /system <msg>  /model <name>  /history")
    print("  " + "─" * 56)

    while True:
        try:
            user_input = input("\n  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Exiting.")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print("  Goodbye.")
            break
        elif user_input == "/clear":
            messages = [{"role": "system", "content": system_prompt}]
            print("  [History cleared]")
            continue
        elif user_input == "/history":
            turns = sum(1 for m in messages if m["role"] == "user")
            print(f"  [{turns} user turns, {len(messages)} total messages in context]")
            continue
        elif user_input.startswith("/system "):
            system_prompt = user_input[8:].strip()
            messages = [{"role": "system", "content": system_prompt}]
            print(f"  [System prompt updated. History cleared.]")
            continue
        elif user_input.startswith("/model "):
            model = user_input[7:].strip()
            messages = [{"role": "system", "content": system_prompt}]
            print(f"  [Switched to {model}. History cleared.]")
            continue

        messages.append({"role": "user", "content": user_input})
        print("\n  Assistant: ", end="", flush=True)

        try:
            reply = stream_chat(messages, model)
            messages.append({"role": "assistant", "content": reply})
        except requests.exceptions.ConnectionError:
            print("ERROR: Lost connection to Ollama.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive streaming chat with Ollama")
    parser.add_argument("--model",  default="llama3.2", help="Model to use")
    parser.add_argument("--system", default=DEFAULT_SYSTEM, help="System prompt")
    args = parser.parse_args()

    print("\nDemo: Interactive Streaming Chat (Ollama — fully local)")

    try:
        requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: Ollama not running at {OLLAMA_BASE}. Fix: ollama serve")
        sys.exit(1)

    run_chat(args.model, args.system)


if __name__ == "__main__":
    main()
