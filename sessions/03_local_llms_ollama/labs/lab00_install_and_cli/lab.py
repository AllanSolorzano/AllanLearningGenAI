#!/usr/bin/env python3
"""
Lab 00: Installing Ollama & CLI Basics
========================================
Get Ollama installed, pull your first model, and learn the essential CLI commands
before touching any Python code.

DevOps analogy:
  This is 'apt install docker' + 'docker pull nginx' + 'docker images'.
  Get the runtime installed and understand how to manage images (models) from the CLI.

This lab is a guided walkthrough — run it to verify each step completed correctly.
No TODOs here; the "lab" is following the installation steps below.

---------------------------------------------------------------------------
STEP 1 — Install Ollama
---------------------------------------------------------------------------
  macOS / Windows: download from https://ollama.com/download
  Linux:           curl -fsSL https://ollama.com/install.sh | sh

  After install, the Ollama daemon starts automatically.
  Verify: open a browser to http://localhost:11434 — should show "Ollama is running"

---------------------------------------------------------------------------
STEP 2 — Pull a model
---------------------------------------------------------------------------
  ollama pull llama3.2         # ~2GB — fast general purpose model
  ollama pull phi3             # ~2GB — strong reasoning, coding
  ollama pull mistral          # ~4GB — strong instruction following

  These are stored in:
    macOS/Linux:  ~/.ollama/models/
    Windows:      C:\\Users\\<you>\\.ollama\\models\\

---------------------------------------------------------------------------
STEP 3 — Essential CLI commands
---------------------------------------------------------------------------
  ollama list                  # list installed models  (docker images)
  ollama show llama3.2         # inspect a model        (docker inspect)
  ollama run llama3.2          # interactive chat       (docker run -it)
  ollama rm llama3.2           # remove a model         (docker rmi)
  ollama serve                 # start the daemon       (dockerd)
  ollama ps                    # show running models    (docker ps)

---------------------------------------------------------------------------
STEP 4 — Run this script to verify
---------------------------------------------------------------------------
  python lab.py

---------------------------------------------------------------------------
"""

import subprocess
import sys
import requests

OLLAMA_BASE = "http://localhost:11434"


def check_step1_daemon() -> bool:
    """Verify: Ollama daemon is running."""
    print("─" * 50)
    print("Step 1: Ollama daemon")
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        if r.status_code == 200:
            print("  PASS — Ollama is running at", OLLAMA_BASE)
            return True
    except Exception:
        pass
    print("  FAIL — Ollama is not running.")
    print("         Fix: run 'ollama serve' in a terminal,")
    print("              or install from https://ollama.com/download")
    return False


def check_step2_models() -> list[str]:
    """Verify: at least one model is installed."""
    print("\n─" * 25)
    print("Step 2: Installed models")
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        models = r.json().get("models", [])
        if models:
            print(f"  PASS — {len(models)} model(s) installed:")
            for m in models:
                size_gb = m.get("size", 0) / 1e9
                print(f"         {m['name']:<35}  {size_gb:.1f} GB")
            return [m["name"] for m in models]
        else:
            print("  FAIL — No models installed.")
            print("         Fix: ollama pull llama3.2")
    except Exception as e:
        print(f"  FAIL — Could not check models: {e}")
    return []


def check_step3_cli() -> None:
    """Verify: ollama CLI is on PATH."""
    print("\n─" * 25)
    print("Step 3: ollama CLI")
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        version = result.stdout.strip() or result.stderr.strip()
        print(f"  PASS — {version}")
    except FileNotFoundError:
        print("  FAIL — 'ollama' command not found on PATH.")
        print("         On Linux: source ~/.bashrc after install.")
        print("         On Windows: restart your terminal.")
    except Exception as e:
        print(f"  FAIL — {e}")


def check_step4_model_info(models: list[str]) -> None:
    """Show model details for the first installed model."""
    if not models:
        return
    print("\n─" * 25)
    print("Step 4: Model info (ollama show equivalent)")
    name = models[0]
    try:
        r = requests.post(f"{OLLAMA_BASE}/api/show", json={"name": name})
        details = r.json().get("details", {})
        print(f"  Model:         {name}")
        print(f"  Family:        {details.get('family', 'unknown')}")
        print(f"  Parameters:    {details.get('parameter_size', 'unknown')}")
        print(f"  Quantization:  {details.get('quantization_level', 'unknown')}")
        print(f"  Context size:  {details.get('context_length', 'unknown')} tokens")
    except Exception as e:
        print(f"  Could not get model info: {e}")


def show_useful_commands() -> None:
    print("\n─" * 25)
    print("CLI Quick Reference:")
    commands = [
        ("ollama list",             "List all installed models"),
        ("ollama pull llama3.2",    "Download a model (like docker pull)"),
        ("ollama show llama3.2",    "Inspect model details"),
        ("ollama run llama3.2",     "Interactive chat in terminal"),
        ("ollama rm llama3.2",      "Remove a model"),
        ("ollama ps",               "Show currently loaded model"),
        ("ollama serve",            "Start the daemon manually"),
    ]
    for cmd, desc in commands:
        print(f"  {cmd:<35}  # {desc}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 00: Installing Ollama & CLI Basics\n")

    ok = check_step1_daemon()
    if not ok:
        print("\nComplete Step 1 first, then re-run this script.")
        sys.exit(1)

    models = check_step2_models()
    check_step3_cli()
    check_step4_model_info(models)
    show_useful_commands()

    print("\n" + "=" * 50)
    if models:
        print("All checks passed. Ready for Lab 01.")
        print(f"Available model for labs: {models[0]}")
    else:
        print("Pull a model to continue:")
        print("  ollama pull llama3.2")
    print("=" * 50)


if __name__ == "__main__":
    main()
