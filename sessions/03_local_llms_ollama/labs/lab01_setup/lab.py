#!/usr/bin/env python3
"""
Lab 01: Ollama Setup & First API Call
=======================================
Verify Ollama is running, explore what's installed, and make your first Python call.

DevOps analogy:
  This is 'docker ps' + 'docker inspect' + 'docker run hello-world' in one lab.
  Confirm the daemon is up, inspect a model, make your first inference call.

Prerequisites:
    1. Install Ollama: https://ollama.com/download
    2. Start Ollama:   ollama serve  (or it auto-starts on most installs)
    3. Pull a model:   ollama pull llama3.2
    4. pip install requests

Run:
    python lab.py

When stuck: check solution.py
"""

import sys
import requests

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2"   # change this if you pulled a different model


# ── Implement these functions ──────────────────────────────────────────────────

def check_health() -> bool:
    """Return True if the Ollama daemon is reachable."""
    # TODO 1: GET f"{OLLAMA_BASE}/api/tags"
    # Return True if status_code == 200, False on any exception.
    # Use timeout=3 to avoid hanging.
    # Hint: requests.get(url, timeout=3) inside try/except Exception
    pass


def list_models() -> list[dict]:
    """Return the raw list of model dicts from /api/tags."""
    # TODO 2: GET /api/tags and return r.json()["models"]
    # Each dict has: "name", "size", "modified_at"
    # Return [] on any failure.
    pass


def model_info(name: str) -> dict:
    """Return model metadata from /api/show."""
    # TODO 3: POST /api/show with body {"name": name}
    # Return r.json() — contains "details", "modelfile", "parameters"
    # "details" keys: family, parameter_size, quantization_level, context_length
    pass


def first_generate(prompt: str) -> str:
    """Make a basic single-turn completion call via /api/generate."""
    # TODO 4: POST /api/generate with:
    #   {"model": MODEL, "prompt": prompt, "stream": False}
    # Return r.json()["response"]
    pass


# ── Exercises (do not modify) ──────────────────────────────────────────────────

def exercise1_health() -> None:
    print("=" * 60)
    print("Exercise 1: Is Ollama Running?")
    print("=" * 60)

    result = check_health()
    if result is None:
        print("  (TODO 1 not complete)")
        return

    if not result:
        print("\n  Ollama is NOT running.")
        print("  Fix: open a terminal and run:  ollama serve")
        sys.exit(1)

    print(f"\n  Ollama is UP at {OLLAMA_BASE}")
    print("  (equivalent to: systemctl status ollama)")


def exercise2_list_models() -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: List Available Models")
    print("=" * 60)

    models = list_models()
    if models is None:
        print("  (TODO 2 not complete)")
        return

    if not models:
        print("  No models found locally.")
        print("  Pull one with: ollama pull llama3.2")
        sys.exit(1)

    print(f"\n  {len(models)} model(s) installed:")
    for m in models:
        size_gb = m.get("size", 0) / 1e9
        print(f"    {m['name']:<35}  {size_gb:.1f} GB")

    names = [m["name"] for m in models]
    if not any(MODEL in n for n in names):
        print(f"\n  Note: '{MODEL}' is not installed.")
        print(f"  Run: ollama pull {MODEL}")
        print(f"  Or change MODEL at the top of this file to one of: {names[:3]}")


def exercise3_model_info() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Inspect a Model")
    print("=" * 60)

    info = model_info(MODEL)
    if info is None:
        print("  (TODO 3 not complete)")
        return

    details = info.get("details", {})
    print(f"\n  Model:         {MODEL}")
    print(f"  Family:        {details.get('family', 'unknown')}")
    print(f"  Parameters:    {details.get('parameter_size', 'unknown')}")
    print(f"  Quantization:  {details.get('quantization_level', 'unknown')}")
    print(f"  Context size:  {details.get('context_length', 'unknown')} tokens")
    print("\n  (like 'docker inspect <image>' — see what's inside before running)")


def exercise4_first_call() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: First Generate Call")
    print("=" * 60)

    prompt = "In exactly one sentence: what is a Kubernetes Pod?"
    print(f"\n  Prompt: {prompt}")
    print("  Calling model (may take a moment on first run)...\n")

    response = first_generate(prompt)
    if response is None:
        print("  (TODO 4 not complete)")
        return

    print(f"  Response: {response}")
    print("\n  No API key. No cloud. Ran entirely on this machine.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 01: Ollama Setup & First API Call\n")
    print(f"  Model:    {MODEL}")
    print(f"  Endpoint: {OLLAMA_BASE}\n")

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
