#!/usr/bin/env python3
"""
Demo: Temperature Effects
==========================
See how temperature changes model output for the same prompt.
Run the same prompt at temperature 0.0, 0.5, and 1.0 — multiple times each.
Watch what stays the same and what changes.

Requires: ANTHROPIC_API_KEY in your .env file or environment.

Cost estimate: ~50 tokens × 15 calls = ~750 tokens ≈ less than $0.001

Usage:
    python demo_temperature_effect.py
"""

import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)


MODEL = "claude-haiku-4-5-20251001"   # Fast and cheap for demos
RUNS_PER_TEMP = 3                      # How many times to run each temperature
MAX_TOKENS = 80                        # Short responses so differences are obvious


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or len(api_key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set or invalid.")
        print("  Copy .env.example to .env and add your API key.")
        print("  Get a key at: https://console.anthropic.com")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def complete(
    client: anthropic.Anthropic,
    prompt: str,
    temperature: float,
    system: str = "",
) -> tuple[str, int, int]:
    """Make a single completion. Returns (response_text, input_tokens, output_tokens)."""
    kwargs = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    text = response.content[0].text.strip()
    return text, response.usage.input_tokens, response.usage.output_tokens


def run_temperature_experiment(
    client: anthropic.Anthropic,
    title: str,
    prompt: str,
    temperatures: list[float],
    system: str = "",
) -> None:
    """Run a prompt at multiple temperatures and display results."""
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}")
    print(f"  Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    if system:
        print(f"  System: {system[:80]}{'...' if len(system) > 80 else ''}")

    total_input = 0
    total_output = 0

    for temp in temperatures:
        print(f"\n  Temperature = {temp}")
        print(f"  {'─' * 60}")

        for run in range(1, RUNS_PER_TEMP + 1):
            text, inp, out = complete(client, prompt, temp, system)
            total_input += inp
            total_output += out
            print(f"  Run {run}: {text}")
            time.sleep(0.3)  # Gentle rate limiting

    print(f"\n  Tokens used this experiment: {total_input} input, {total_output} output")


def main() -> None:
    print("\n" + "═" * 70)
    print("  DEMO: Temperature Effects on LLM Output")
    print(f"  Model: {MODEL}")
    print(f"  Runs per temperature: {RUNS_PER_TEMP}")
    print("═" * 70)

    client = get_client()

    temperatures = [0.0, 0.5, 1.0]
    grand_total_input = 0
    grand_total_output = 0

    # ── Experiment 1: Structured output (temperature should not matter) ────────
    run_temperature_experiment(
        client,
        title="Experiment 1: Structured Output (YAML generation)",
        prompt="Generate a Kubernetes resource limits block for a web server with 100m CPU request, 500m CPU limit, 128Mi memory request, and 256Mi memory limit. Output only the YAML, no explanation.",
        temperatures=temperatures,
        system="You are a Kubernetes expert. Output only valid YAML.",
    )

    print("\n  Observation: At temp=0, output is identical across runs.")
    print("  At temp=1.0, output may vary (comments, whitespace, ordering).")
    print("  For infrastructure code going into pipelines, ALWAYS use temp=0.")

    # ── Experiment 2: Factual question (low temp preferred) ───────────────────
    run_temperature_experiment(
        client,
        title="Experiment 2: Factual Question",
        prompt="What does a Kubernetes liveness probe do? Answer in one sentence.",
        temperatures=temperatures,
    )

    print("\n  Observation: Low temperature gives consistent, accurate answers.")
    print("  High temperature may introduce subtle variations or errors.")

    # ── Experiment 3: Creative task (temperature matters a lot) ───────────────
    run_temperature_experiment(
        client,
        title="Experiment 3: Creative Task (naming a tool)",
        prompt="Suggest a name for a new internal DevOps platform that automates deployments. Give only the name and a 5-word tagline. Format: NAME: <name> / TAGLINE: <tagline>",
        temperatures=temperatures,
    )

    print("\n  Observation: At temp=0, same name every time.")
    print("  At temp=1.0, diverse suggestions — useful for brainstorming.")
    print("  Neither is 'better' — it depends on your use case.")

    # ── Experiment 4: Completion (open-ended, shows distribution) ─────────────
    run_temperature_experiment(
        client,
        title="Experiment 4: Open-Ended Completion",
        prompt="Complete this sentence in exactly 10 words: 'The best thing about containerizing applications is'",
        temperatures=temperatures,
    )

    print("\n  Observation: temp=0 always produces the 'most likely' completion.")
    print("  temp=1.0 samples from the full probability distribution.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n\n" + "═" * 70)
    print("  KEY TAKEAWAYS")
    print("═" * 70)
    print("""
  Temperature controls how the model samples from its probability distribution:

  temperature = 0.0  →  Always pick the most likely token (deterministic)
                         Use for: code gen, YAML, JSON, data extraction, CI/CD

  temperature = 0.5  →  Mostly likely tokens, some variation
                         Use for: summarization, Q&A, explanations

  temperature = 1.0  →  Sample from the full distribution (creative)
                         Use for: brainstorming, creative writing, exploration

  temperature > 1.0  →  Rarely useful — often produces incoherent output

  RULE FOR DEVOPS:
  If the output goes into a file, pipeline, or system → use temperature = 0
  If you're generating text for human review → use temperature 0.3–0.7
""")


if __name__ == "__main__":
    main()
