#!/usr/bin/env python3
"""
Demo: Prompt Playground — Side-by-Side Strategy Comparison
============================================================
Watch how different prompting strategies produce different outputs
for the same input. No TODO markers — just run and observe.

Requires: ANTHROPIC_API_KEY in .env

Usage:
    python demo_prompt_playground.py
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic")
    sys.exit(1)


MODEL = "claude-haiku-4-5-20251001"
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def ask(system: str, user: str, few_shot: list[dict] | None = None, max_tokens: int = 200) -> str:
    messages = list(few_shot or [])
    messages.append({"role": "user", "content": user})
    r = client.messages.create(
        model=MODEL, max_tokens=max_tokens, temperature=0.0,
        system=system, messages=messages,
    )
    return r.content[0].text.strip()


def show(label: str, output: str) -> None:
    print(f"\n  [{label}]")
    for line in output.splitlines():
        print(f"  {line}")


def section(title: str) -> None:
    print(f"\n\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}")


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 1: Persona vs No Persona
# ─────────────────────────────────────────────────────────────────────────────

section("Experiment 1: Persona Matters")
print("\n  Input: 'Our pods keep OOMKilling. What should I do?'")
user = "Our pods keep OOMKilling. What should I do?"

no_persona = ask("You are a helpful assistant.", user)
sre_persona = ask(
    "You are a senior SRE with 10 years of experience in Kubernetes and production systems. "
    "Be specific — include actual kubectl commands. Don't explain Kubernetes basics.",
    user,
)

show("No persona", no_persona)
show("SRE persona", sre_persona)

print("\n  Observation: The SRE persona skips basics, gives specific kubectl commands.")
print("  The generic persona over-explains and stays vague.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 2: Vague vs Precise Output Format
# ─────────────────────────────────────────────────────────────────────────────

section("Experiment 2: Output Format Precision")
print("\n  Input: alert text → classify severity")
user = "auth-service: 3 of 6 pods OOMKilled, error rate 22%, p99 latency 800ms"

vague = ask("You are an alert classifier. Classify this alert.", user)
precise = ask(
    "You are an alert classifier. Output ONLY the severity label: P1, P2, or P3. "
    "No explanation, no punctuation, no other text.",
    user,
)
# Even more precise with a constraint
with_example = ask(
    "You are an alert classifier. Output ONLY: P1, P2, or P3.",
    user,
    few_shot=[
        {"role": "user",      "content": "payment-service down 100%"},
        {"role": "assistant", "content": "P1"},
    ],
)

show("Vague format spec", vague)
show("Precise format spec", precise)
show("Precise + example", with_example)

print("\n  Observation: Vague format produces prose. Precise gets a label.")
print("  Adding one example makes it even more reliable.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 3: No Constraints vs Guardrails
# ─────────────────────────────────────────────────────────────────────────────

section("Experiment 3: Guardrails Prevent Hallucination")
print("\n  Input: ambiguous alert with missing context")
user = "high error rate on the service"

no_guardrail = ask(
    "You are an SRE. Diagnose this alert and give the root cause.",
    user,
)
with_guardrail = ask(
    "You are an SRE. Diagnose this alert. "
    "IMPORTANT: If the alert lacks specific service names, metrics, or error messages, "
    "say what additional information you need rather than guessing. "
    "Never fabricate specific pod names, IPs, or error codes not in the input.",
    user,
)

show("No guardrail", no_guardrail)
show("With guardrail", with_guardrail)

print("\n  Observation: No guardrail — model invents specifics.")
print("  With guardrail — model asks for missing information instead.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 4: One Task vs Multiple Tasks
# ─────────────────────────────────────────────────────────────────────────────

section("Experiment 4: Single Responsibility")
print("\n  Input: incident report")
user = """\
production payment service is down. 100% error rate.
all pods are in CrashLoopBackOff. started 8 minutes ago."""

multi_task = ask(
    "You are an SRE assistant. For every incident: classify severity, identify root cause, "
    "suggest immediate action, write a Slack notification, create a Jira ticket title, "
    "and estimate resolution time.",
    user,
    max_tokens=400,
)
single_task = ask(
    "You are an alert severity classifier. "
    "Output ONLY the severity: P1, P2, or P3. Nothing else.",
    user,
)

show("Multi-task prompt", multi_task[:300] + "...")
show("Single-task prompt", single_task)

print("\n  Observation: Multi-task prompts are inconsistent under load.")
print("  Build separate, focused prompts for each task in a pipeline.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 5: The Difference Few-Shot Makes for Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

section("Experiment 5: Few-Shot on Edge Cases")
print("\n  Edge case: staging cluster completely down (should be P3, not P1)")
user = "staging Kubernetes cluster is completely unreachable, all services down"

zero_shot = ask(
    "Classify this alert as P1, P2, or P3. P1 = down, P2 = degraded, P3 = warning. Output only the label.",
    user,
)
with_staging_example = ask(
    "Classify this alert as P1, P2, or P3. P1 = down, P2 = degraded, P3 = warning. "
    "Staging/dev/test environments are always P3 — no customer impact. Output only the label.",
    user,
    few_shot=[
        {"role": "user",      "content": "staging postgres is completely down"},
        {"role": "assistant", "content": "P3"},
        {"role": "user",      "content": "dev environment all pods crashed"},
        {"role": "assistant", "content": "P3"},
    ],
)

show("Zero-shot (no staging rule)", zero_shot)
show("With staging rule + examples", with_staging_example)

print("\n  Expected: P3 (staging = no customer impact)")
print("  Observation: Without the rule, the model sees 'completely down' and says P1.")
print("  The staging rule + examples anchors it to the correct classification.")

print("\n\n" + "═" * 70)
print("  SUMMARY")
print("═" * 70)
print("""
  Five principles demonstrated:
  1. Persona shapes vocabulary, depth, and what the model skips
  2. Explicit format specs (+ examples) beat implicit ones
  3. Guardrails prevent hallucination on ambiguous input
  4. One prompt = one task (single responsibility principle)
  5. Few-shot examples are the most powerful tool for edge cases
""")
