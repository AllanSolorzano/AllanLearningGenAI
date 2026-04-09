#!/usr/bin/env python3
"""
Demo: SRE Assistant (Fully Local)
===================================
A DevOps incident assistant powered entirely by Ollama.
No cloud API, no API key, no data leaving your network.

Usage:
    python demo_sre_assistant.py              # interactive mode
    python demo_sre_assistant.py --demo       # run preset incident scenarios
    python demo_sre_assistant.py --model phi3

Why run this locally?
  - Production logs and incident details should not leave your network
  - Works during cloud provider outages (exactly when you need it most)
  - No token costs on high-volume incident triage
"""

import argparse
import json
import sys
import requests

OLLAMA_BASE = "http://localhost:11434"

SYSTEM_PROMPT = """\
You are an expert Site Reliability Engineer (SRE) assistant.
Your job is to help engineers diagnose and resolve infrastructure incidents quickly.

Guidelines:
- Give specific, actionable commands (kubectl, docker, terraform, etc.)
- Prioritise what to check first — triage before deep investigation
- Keep answers concise — engineers are under pressure during incidents
- If you need more information to diagnose, ask one targeted question
- Always suggest how to verify that your fix worked"""

DEMO_SCENARIOS = [
    {
        "title": "Pod CrashLoopBackOff",
        "question": (
            "My pod 'api-server-7d4b9c-xkp2' is in CrashLoopBackOff. "
            "Deployment has been stable for 2 weeks. No recent code changes. "
            "What do I check first?"
        ),
    },
    {
        "title": "Sudden High Latency",
        "question": (
            "P99 API latency jumped from 50ms to 2000ms 10 minutes ago. "
            "No deployment happened. CPU and memory look normal. "
            "Database connections are fine. Where do I look?"
        ),
    },
    {
        "title": "Terraform State Lock",
        "question": (
            "Our Terraform CI pipeline is failing with: 'Error acquiring the state lock'. "
            "Lock ID is abc-123. No one is running Terraform manually. "
            "What's happening and how do I fix it safely?"
        ),
    },
    {
        "title": "Node NotReady",
        "question": (
            "One node is NotReady. Other nodes are fine. "
            "The node had a kernel upgrade 30 minutes ago. "
            "kubectl describe shows 'Kubelet stopped posting node status'. SSH is working."
        ),
    },
]


def ask(question: str, history: list[dict], model: str) -> str:
    """Send question with history, stream reply, return full text."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    messages.append({"role": "user", "content": question})

    r = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": model, "messages": messages, "stream": True,
              "options": {"temperature": 0.1}},
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


def run_demo(model: str) -> None:
    print("\n" + "=" * 65)
    print("SRE ASSISTANT DEMO — Preset Incident Scenarios")
    print("=" * 65)
    print(f"  Model: {model}  (running locally — no cloud)\n")

    for i, scenario in enumerate(DEMO_SCENARIOS, 1):
        print(f"\n{'─' * 65}")
        print(f"Scenario {i}: {scenario['title']}")
        print("─" * 65)
        print(f"\nEngineer: {scenario['question']}\n")
        print("Assistant: ", end="", flush=True)
        ask(scenario["question"], [], model)
        print()

    print("=" * 65)
    print("Run without --demo for interactive mode.")


def run_interactive(model: str) -> None:
    print("\n" + "=" * 65)
    print("SRE ASSISTANT — Interactive Mode")
    print("=" * 65)
    print(f"\n  Model: {model}  (fully local, no API key)")
    print("  Describe your incident. Commands: /exit  /clear")
    print("  " + "─" * 61)

    history = []
    while True:
        try:
            user_input = input("\n  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Session ended.")
            break

        if not user_input:
            continue
        if user_input == "/exit":
            print("  Goodbye.")
            break
        if user_input == "/clear":
            history = []
            print("  [Conversation history cleared]")
            continue

        print("\n  Assistant: ", end="", flush=True)
        reply = ask(user_input, history, model)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local SRE assistant powered by Ollama")
    parser.add_argument("--demo",  action="store_true", help="Run preset incident scenarios")
    parser.add_argument("--model", default="llama3.2",  help="Ollama model to use")
    args = parser.parse_args()

    try:
        requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3).raise_for_status()
    except Exception:
        print(f"ERROR: Ollama not running at {OLLAMA_BASE}. Fix: ollama serve")
        sys.exit(1)

    if args.demo:
        run_demo(args.model)
    else:
        run_interactive(args.model)


if __name__ == "__main__":
    main()
