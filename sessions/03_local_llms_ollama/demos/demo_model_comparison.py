#!/usr/bin/env python3
"""
Demo: Model Comparison
=======================
Send the same prompts to multiple locally installed models and compare responses
side by side — useful for picking the right model for your use case.

Usage:
    python demo_model_comparison.py
    python demo_model_comparison.py --models llama3.2,mistral
    python demo_model_comparison.py --question "How do I debug a Kubernetes OOMKilled pod?"
"""

import argparse
import time
import requests

OLLAMA_BASE = "http://localhost:11434"

PRESET_QUESTIONS = [
    "In one sentence: what is a Kubernetes Pod?",
    "Name three common causes of high memory usage in a container.",
    "What does 'terraform force-unlock' do and when is it safe to use it?",
]


def get_available_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def generate(prompt: str, model: str) -> tuple[str, float]:
    """Return (response_text, seconds_elapsed)."""
    start = time.time()
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0}},
            timeout=120,
        )
        text = r.json().get("response", "[no response]")
    except Exception as e:
        text = f"[ERROR: {e}]"
    return text, time.time() - start


def run_comparison(models: list[str], questions: list[str]) -> None:
    print(f"\n  Models: {', '.join(models)}")
    print(f"  Questions: {len(questions)}\n")

    for question in questions:
        print("=" * 70)
        print(f"Q: {question}")
        print("=" * 70)
        for model in models:
            response, elapsed = generate(question, model)
            print(f"\n  [{model}]  ({elapsed:.1f}s)")
            for line in response.strip().split("\n"):
                print(f"    {line}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Ollama models side by side")
    parser.add_argument("--models", help="Comma-separated model names (default: all installed)")
    parser.add_argument("--question", help="Single question to ask (overrides presets)")
    args = parser.parse_args()

    print("\nDemo: Ollama Model Comparison\n")

    available = get_available_models()
    if not available:
        print("ERROR: No models installed or Ollama not running.")
        print("Fix: ollama serve && ollama pull llama3.2")
        return

    if args.models:
        models = [m.strip() for m in args.models.split(",")]
        missing = [m for m in models if not any(m in a for a in available)]
        if missing:
            print(f"WARNING: Not installed — {missing}. Skipping.")
            models = [m for m in models if m not in missing]
        if not models:
            return
    else:
        models = available[:3]   # cap at 3 to keep output readable

    if len(models) < 2:
        print(f"Only 1 model available ({models}). Pull another to compare:")
        print("  ollama pull mistral")
        print("  ollama pull phi3")

    questions = [args.question] if args.question else PRESET_QUESTIONS
    run_comparison(models, questions)

    print("  Observation: same question, different answers.")
    print("  Quality, speed, and verbosity vary by model and quantization.")
    print("  Pick based on your latency/quality/RAM trade-off.")


if __name__ == "__main__":
    main()
