#!/usr/bin/env python3
"""Lab 02: Chat API & Model Parameters  (SOLUTION)"""

import sys
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2"


def chat(messages: list[dict], model: str = MODEL, temperature: float = 0.0) -> str:
    r = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    return r.json()["message"]["content"]


def multi_turn(system_prompt: str, turns: list[str], model: str = MODEL) -> list[str]:
    messages = [{"role": "system", "content": system_prompt}]
    replies = []
    for turn in turns:
        messages.append({"role": "user", "content": turn})
        reply = chat(messages, model=model)
        messages.append({"role": "assistant", "content": reply})
        replies.append(reply)
    return replies


def compare_temperatures(prompt: str, temperatures: list[float], model: str = MODEL) -> dict:
    return {
        t: chat([{"role": "user", "content": prompt}], model=model, temperature=t)
        for t in temperatures
    }


def generate_with_options(prompt: str, options: dict, model: str = MODEL) -> str:
    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "options": options},
    )
    return r.json()["response"]


def exercise1_system_prompt() -> None:
    print("=" * 60)
    print("Exercise 1: Chat with a System Prompt")
    print("=" * 60)
    messages = [
        {"role": "system", "content": "You are a concise SRE assistant. Reply in bullet points only."},
        {"role": "user",   "content": "What are the top 3 causes of a pod CrashLoopBackOff?"},
    ]
    reply = chat(messages)
    print(f"\n  System: {messages[0]['content']}")
    print(f"  User:   {messages[1]['content']}")
    print(f"\n  Assistant:\n  {reply}")


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
    for user_msg, reply in zip(turns, replies):
        print(f"\n  User:      {user_msg}")
        print(f"  Assistant: {reply}")
    print("\n  The model understood the progression because you sent the full history.")


def exercise3_temperature() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Temperature Effect")
    print("=" * 60)
    prompt = "Suggest a creative name for an internal developer platform."
    temps = [0.0, 0.7, 1.5]
    print(f"\n  Prompt: '{prompt}'")
    results = compare_temperatures(prompt, temps)
    labels = {0.0: "deterministic", 0.7: "balanced", 1.5: "creative/chaotic"}
    for temp, response in sorted(results.items()):
        print(f"\n  temp={temp}  ({labels.get(temp, '')})")
        print(f"  → {response.strip()[:200]}")


def exercise4_options() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Custom Generation Options")
    print("=" * 60)
    prompt = "Write a one-line description of what Terraform does."
    configs = [
        {"temperature": 0.0, "num_predict": 20},
        {"temperature": 0.0, "num_predict": 100},
        {"temperature": 0.7, "num_predict": 60, "top_p": 0.95},
    ]
    for opts in configs:
        response = generate_with_options(prompt, opts)
        print(f"\n  options: {opts}")
        print(f"  → {response.strip()}")


def main() -> None:
    print("\nLab 02: Chat API & Model Parameters  (Solution)\n")
    try:
        requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: Ollama is not running. Fix: ollama serve")
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
