#!/usr/bin/env python3
"""Lab 01: Ollama Setup & First API Call  (SOLUTION)"""

import sys
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2"


def check_health() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[dict]:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return r.json().get("models", [])
    except Exception:
        return []


def model_info(name: str) -> dict:
    r = requests.post(f"{OLLAMA_BASE}/api/show", json={"name": name})
    return r.json()


def first_generate(prompt: str) -> str:
    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False},
    )
    return r.json()["response"]


def exercise1_health() -> None:
    print("=" * 60)
    print("Exercise 1: Is Ollama Running?")
    print("=" * 60)
    if not check_health():
        print("\n  Ollama is NOT running. Fix: ollama serve")
        sys.exit(1)
    print(f"\n  Ollama is UP at {OLLAMA_BASE}")


def exercise2_list_models() -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: List Available Models")
    print("=" * 60)
    models = list_models()
    if not models:
        print("  No models found. Run: ollama pull llama3.2")
        sys.exit(1)
    print(f"\n  {len(models)} model(s) installed:")
    for m in models:
        size_gb = m.get("size", 0) / 1e9
        print(f"    {m['name']:<35}  {size_gb:.1f} GB")
    names = [m["name"] for m in models]
    if not any(MODEL in n for n in names):
        print(f"\n  Note: '{MODEL}' not installed. Run: ollama pull {MODEL}")


def exercise3_model_info() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Inspect a Model")
    print("=" * 60)
    info = model_info(MODEL)
    details = info.get("details", {})
    print(f"\n  Model:         {MODEL}")
    print(f"  Family:        {details.get('family', 'unknown')}")
    print(f"  Parameters:    {details.get('parameter_size', 'unknown')}")
    print(f"  Quantization:  {details.get('quantization_level', 'unknown')}")
    print(f"  Context size:  {details.get('context_length', 'unknown')} tokens")


def exercise4_first_call() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: First Generate Call")
    print("=" * 60)
    prompt = "In exactly one sentence: what is a Kubernetes Pod?"
    print(f"\n  Prompt: {prompt}")
    print("  Calling model...\n")
    response = first_generate(prompt)
    print(f"  Response: {response}")
    print("\n  No API key. No cloud. Ran entirely on this machine.")


def main() -> None:
    print("\nLab 01: Ollama Setup & First API Call  (Solution)\n")
    print(f"  Model: {MODEL} | Endpoint: {OLLAMA_BASE}\n")
    exercise1_health()
    exercise2_list_models()
    exercise3_model_info()
    exercise4_first_call()
    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. GET /api/tags confirms Ollama is running + lists local models.")
    print("  2. POST /api/show gives model details (params, quantization, context).")
    print("  3. POST /api/generate = your first LLM call over plain HTTP.")
    print("  4. No API key, no internet — model runs entirely on this machine.")
    print("=" * 60)


if __name__ == "__main__":
    main()
