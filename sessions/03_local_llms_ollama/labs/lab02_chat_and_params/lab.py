#!/usr/bin/env python3
"""
Lab 02: Chat API & Model Parameters
=====================================
Use /api/chat for multi-turn conversations. Tune temperature and other
parameters to control how the model generates output.

Key insight:
  The model has NO memory. You send the full conversation history on every
  request — the model reads it fresh each time. This is how every LLM API
  works (OpenAI, Anthropic, Ollama — all the same pattern).

Prerequisites:
    pip install requests
    ollama pull llama3.2

Run:
    python lab.py

When stuck: check solution.py
"""

import sys
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2"


# ── Implement these functions ──────────────────────────────────────────────────

def chat(messages: list[dict], model: str = MODEL, temperature: float = 0.0) -> str:
    """Send a chat request and return the assistant's reply text."""
    # TODO 1: POST /api/chat with body:
    #   {
    #     "model": model,
    #     "messages": messages,
    #     "stream": False,
    #     "options": {"temperature": temperature}
    #   }
    # Return r.json()["message"]["content"]
    pass


def multi_turn(system_prompt: str, turns: list[str], model: str = MODEL) -> list[str]:
    """Run a multi-turn conversation. Returns list of assistant replies.

    Args:
        system_prompt: The system message (sets model persona/role).
        turns: User messages to send in order.
        model: Ollama model name.
    """
    # TODO 2: Build the conversation incrementally.
    # Start: messages = [{"role": "system", "content": system_prompt}]
    # For each turn in turns:
    #   1. Append {"role": "user", "content": turn}
    #   2. Call chat(messages, model=model) to get the reply
    #   3. Append {"role": "assistant", "content": reply}
    #   4. Collect the reply in a list
    # Return the list of assistant replies.
    pass


def compare_temperatures(prompt: str, temperatures: list[float], model: str = MODEL) -> dict:
    """Run the same prompt at multiple temperatures. Returns {temp: response}."""
    # TODO 3: For each temperature in the list:
    #   Call chat([{"role": "user", "content": prompt}], model=model, temperature=t)
    # Return a dict mapping temperature (float) → response (str).
    pass


def generate_with_options(prompt: str, options: dict, model: str = MODEL) -> str:
    """Single-turn generation with a custom options dict."""
    # TODO 4: POST /api/generate with:
    #   {"model": model, "prompt": prompt, "stream": False, "options": options}
    # Return r.json()["response"]
    # options can include: temperature, top_p, top_k, num_predict, repeat_penalty
    pass


# ── Exercises (do not modify) ──────────────────────────────────────────────────

def exercise1_system_prompt() -> None:
    print("=" * 60)
    print("Exercise 1: Chat with a System Prompt")
    print("=" * 60)

    messages = [
        {"role": "system", "content": "You are a concise SRE assistant. Reply in bullet points only."},
        {"role": "user",   "content": "What are the top 3 causes of a pod CrashLoopBackOff?"},
    ]

    reply = chat(messages)
    if reply is None:
        print("  (TODO 1 not complete)")
        return

    print(f"\n  System: {messages[0]['content']}")
    print(f"  User:   {messages[1]['content']}")
    print(f"\n  Assistant:\n  {reply}")
    print("\n  The system prompt shapes the model's persona and output format.")


def exercise2_multi_turn() -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Multi-Turn Conversation")
    print("=" * 60)

    system = "You are a Kubernetes expert. Be concise — one paragraph max."
    turns = [
        "My pod has status CrashLoopBackOff. What's the first kubectl command I should run?",
        "The logs show 'OOMKilled'. What does that mean and what should I do?",
        "I increased the memory limit. How do I apply the change without downtime?",
    ]

    replies = multi_turn(system, turns)
    if replies is None:
        print("  (TODO 2 not complete)")
        return

    for user_msg, reply in zip(turns, replies):
        print(f"\n  User:      {user_msg}")
        print(f"  Assistant: {reply}")

    print("\n  The model understood the progression: crash → OOMKilled → fix → rollout.")
    print("  It only knows this because you sent the full history each time.")


def exercise3_temperature() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Temperature Effect")
    print("=" * 60)

    prompt = "Suggest a creative name for an internal developer platform."
    temps = [0.0, 0.7, 1.5]

    print(f"\n  Prompt: '{prompt}'")
    print(f"  Testing temperatures: {temps}\n")

    results = compare_temperatures(prompt, temps)
    if results is None:
        print("  (TODO 3 not complete)")
        return

    labels = {0.0: "deterministic", 0.7: "balanced", 1.5: "creative/chaotic"}
    for temp, response in sorted(results.items()):
        print(f"  temp={temp}  ({labels.get(temp, '')})")
        print(f"  → {response.strip()[:200]}\n")

    print("  Run this twice — temp=0.0 gives the same answer every time.")
    print("  temp=1.5 will differ significantly on each run.")


def exercise4_options() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Custom Generation Options")
    print("=" * 60)

    prompt = "Write a one-line description of what Terraform does."

    configs = [
        {"temperature": 0.0, "num_predict": 20},                       # very short
        {"temperature": 0.0, "num_predict": 100},                      # more detail
        {"temperature": 0.7, "num_predict": 60, "top_p": 0.95},        # creative, medium
    ]

    for opts in configs:
        response = generate_with_options(prompt, opts)
        if response is None:
            print("  (TODO 4 not complete)")
            return
        print(f"\n  options: {opts}")
        print(f"  → {response.strip()}")

    print("\n  num_predict caps output length.")
    print("  Combine temperature + top_p for fine-grained randomness control.")
    print("  For DevOps tooling: keep temperature at 0.0 for consistent output.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 02: Chat API & Model Parameters\n")

    # Quick health check
    try:
        requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: Ollama is not running at {OLLAMA_BASE}")
        print("Fix: ollama serve")
        sys.exit(1)

    print(f"  Model: {MODEL} | Endpoint: {OLLAMA_BASE}\n")

    exercise1_system_prompt()
    exercise2_multi_turn()
    exercise3_temperature()
    exercise4_options()

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. System prompt sets the model's role and output format.")
    print("  2. Multi-turn: YOU append each exchange to the message list.")
    print("  3. The model has no memory — send the full history every time.")
    print("  4. temperature=0 → deterministic; use for any DevOps tooling.")
    print("  5. num_predict caps length; top_p controls sampling breadth.")
    print("=" * 60)


if __name__ == "__main__":
    main()
