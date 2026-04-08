#!/usr/bin/env python3
"""
Lab 01: Zero-Shot vs Few-Shot — Incident Severity Classification
=================================================================
You're building an alert classifier that categorizes incoming incidents
as P1, P2, or P3. In this lab you'll compare how zero-shot, 1-shot,
and 5-shot prompting differ in accuracy and consistency.

Requires: ANTHROPIC_API_KEY in .env

Run:
    python lab.py

When stuck: check solution.py
"""

import json
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


MODEL = "claude-haiku-4-5-20251001"   # Fast + cheap for classification tasks
TEMPERATURE = 0.0                      # Deterministic — classification should be consistent


# ── Test dataset ──────────────────────────────────────────────────────────────
# Ground truth: what the correct classification should be
# This represents your team's severity definitions:
#   P1 = customer impact, service down or severely degraded
#   P2 = degraded performance, elevated errors, or imminent risk
#   P3 = warning, non-critical, needs monitoring

TEST_ALERTS = [
    # P1 cases
    {"alert": "payment-service: error rate 100%, all requests returning 500", "expected": "P1"},
    {"alert": "database primary is unreachable, 0 healthy replicas", "expected": "P1"},
    {"alert": "all pods in production namespace in CrashLoopBackOff", "expected": "P1"},
    {"alert": "SSL certificate expired, HTTPS completely broken", "expected": "P1"},
    # P2 cases
    {"alert": "auth-service p99 latency 1800ms, SLO threshold 500ms", "expected": "P2"},
    {"alert": "worker nodes running at 88% CPU, autoscaler not triggering", "expected": "P2"},
    {"alert": "2 of 5 payment pods OOMKilled, 3 still serving traffic", "expected": "P2"},
    {"alert": "Terraform state lock held for 47 minutes, pipeline blocked", "expected": "P2"},
    # P3 cases
    {"alert": "disk usage at 71% on log-archive volume, threshold 85%", "expected": "P3"},
    {"alert": "backup job failed overnight, previous backup is 36 hours old", "expected": "P3"},
    {"alert": "staging environment pod restart count elevated: 12 in last hour", "expected": "P3"},
    {"alert": "cost anomaly detected: S3 spend +22% vs last week", "expected": "P3"},
]


# ── API client ────────────────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to your .env file.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


# ── Core classification function ──────────────────────────────────────────────

def classify(
    client: anthropic.Anthropic,
    alert_text: str,
    system_prompt: str,
    few_shot_messages: list[dict] | None = None,
) -> str:
    """Classify an alert. Returns the severity string (P1/P2/P3) or 'ERROR'.

    Args:
        client: Anthropic client
        alert_text: The alert text to classify
        system_prompt: The system prompt defining the classifier
        few_shot_messages: Optional list of prior turns (the few-shot examples)
    """
    messages = list(few_shot_messages or [])
    messages.append({"role": "user", "content": alert_text})

    # TODO 1: Call the Anthropic API to classify the alert.
    # Use: client.messages.create(model=MODEL, max_tokens=32, temperature=TEMPERATURE,
    #                             system=system_prompt, messages=messages)
    # Return: response.content[0].text.strip()
    # Hint: the response should be just "P1", "P2", or "P3"
    pass


def run_evaluation(
    client: anthropic.Anthropic,
    name: str,
    system_prompt: str,
    few_shot_messages: list[dict] | None = None,
) -> dict:
    """Run all test alerts through a classifier and return accuracy stats.

    Returns a dict with: name, results (list of per-alert dicts), accuracy, by_severity
    """
    print(f"\n  Running: {name}")
    results = []

    for item in TEST_ALERTS:
        raw = classify(client, item["alert"], system_prompt, few_shot_messages)

        # TODO 2: Extract severity from the raw response.
        # The model should return "P1", "P2", or "P3", but may include extra text.
        # Hint: check if "P1", "P2", or "P3" appear anywhere in raw.upper()
        severity = "ERROR"  # Replace with your extraction logic

        correct = severity == item["expected"]
        results.append({
            "alert": item["alert"],
            "expected": item["expected"],
            "got": severity,
            "correct": correct,
        })
        marker = "✓" if correct else "✗"
        print(f"    {marker} [{item['expected']}→{severity}] {item['alert'][:60]}")

    accuracy = sum(1 for r in results if r["correct"]) / len(results)

    # Accuracy broken down by expected severity
    by_severity: dict[str, dict] = {}
    for sev in ["P1", "P2", "P3"]:
        subset = [r for r in results if r["expected"] == sev]
        correct_count = sum(1 for r in subset if r["correct"])
        by_severity[sev] = {"correct": correct_count, "total": len(subset)}

    return {"name": name, "results": results, "accuracy": accuracy, "by_severity": by_severity}


# ── Exercises ──────────────────────────────────────────────────────────────────

def build_zero_shot_system() -> str:
    """Exercise 1: Write a zero-shot system prompt for severity classification.

    The model should classify alerts as P1, P2, or P3.
    No examples are provided — only a description of the task and criteria.

    Rules:
    - Output ONLY the severity label: P1, P2, or P3
    - Nothing else — no explanation, no punctuation
    """
    # TODO 3: Write a system prompt that:
    #   a) Defines the role (alert classifier / SRE)
    #   b) Defines P1 / P2 / P3 with concrete criteria
    #   c) Specifies output format: only "P1", "P2", or "P3"
    #   d) Specifies what to do for ambiguous cases (use P2 as a safe default)
    return ""  # Replace with your system prompt


def build_one_shot_system() -> tuple[str, list[dict]]:
    """Exercise 2: Build a 1-shot classifier with a single example.

    One example is often enough to anchor format. Choose the example wisely —
    pick one that demonstrates the hardest boundary to judge.
    """
    system = """You are an alert severity classifier. Classify incoming alerts as P1, P2, or P3.
Output ONLY the severity label. Nothing else."""

    # TODO 4: Add ONE well-chosen few-shot example as prior conversation turns.
    # Hint: pick a borderline case (e.g., degraded but not down = P2)
    # Format: [{"role": "user", "content": alert}, {"role": "assistant", "content": "P2"}]
    few_shot: list[dict] = []  # Replace with your example

    return system, few_shot


def build_five_shot_system() -> tuple[str, list[dict]]:
    """Exercise 3: Build a 5-shot classifier that covers all severity levels.

    5 examples should cover at least one clear P1, one borderline P2, one P3,
    and ideally one of the tricky cases from the test set.
    """
    system = """You are an alert severity classifier for a production platform team.
Classify incoming alerts as P1, P2, or P3.
P1 = customer impact, service down or severely degraded
P2 = degraded performance, elevated errors, or imminent risk
P3 = warning, non-critical, needs monitoring
Output ONLY the severity label. Nothing else."""

    # TODO 5: Build 5 few-shot examples as prior conversation turns.
    # Cover: clear P1, clear P3, two P2 cases (different types), one borderline case.
    # Use realistic alert text different from the test set.
    few_shot: list[dict] = []  # Replace with your 5 examples

    return system, few_shot


def build_engineered_system() -> tuple[str, list[dict]]:
    """Exercise 4: Your best prompt — combine everything you've learned.

    Combine a strong system prompt + well-chosen few-shot examples.
    Goal: hit 100% accuracy on the test set.

    Think about:
    - What criteria distinguish P1 from P2?
    - What should happen for staging vs production alerts?
    - How should the model handle cost/billing alerts?
    """
    # TODO 6: Design the best prompt you can. No constraints — use everything.
    # Try to hit 100% accuracy on TEST_ALERTS.
    system = ""
    few_shot: list[dict] = []
    return system, few_shot


# ── Main ──────────────────────────────────────────────────────────────────────

def print_summary(evaluations: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Strategy':<25} {'Overall':>8} {'P1':>6} {'P2':>6} {'P3':>6}")
    print("─" * 56)

    for ev in evaluations:
        if not ev:
            continue
        p1 = ev["by_severity"].get("P1", {})
        p2 = ev["by_severity"].get("P2", {})
        p3 = ev["by_severity"].get("P3", {})

        def pct(d: dict) -> str:
            if not d.get("total"):
                return "  -"
            return f"{d['correct']}/{d['total']}"

        print(
            f"{ev['name']:<25} {ev['accuracy']:>7.0%}  "
            f"{pct(p1):>6}  {pct(p2):>6}  {pct(p3):>6}"
        )

    print()
    print("Insight: Compare how each strategy handles P2 (the hardest category).")
    print("P1 and P3 are usually obvious; P2 is where your examples earn their cost.")


def main() -> None:
    print("\nLab 01: Zero-Shot vs Few-Shot — Incident Severity Classification\n")
    client = get_client()
    evaluations = []

    # Exercise 1: Zero-shot
    system = build_zero_shot_system()
    if system:
        ev = run_evaluation(client, "Zero-shot", system)
        evaluations.append(ev)
    else:
        print("  Skipping zero-shot (TODO 3 not complete)")

    # Exercise 2: 1-shot
    system, few_shot = build_one_shot_system()
    if few_shot:
        ev = run_evaluation(client, "1-shot", system, few_shot)
        evaluations.append(ev)
    else:
        print("  Skipping 1-shot (TODO 4 not complete)")

    # Exercise 3: 5-shot
    system, few_shot = build_five_shot_system()
    if few_shot:
        ev = run_evaluation(client, "5-shot", system, few_shot)
        evaluations.append(ev)
    else:
        print("  Skipping 5-shot (TODO 5 not complete)")

    # Exercise 4: Engineered prompt
    system, few_shot = build_engineered_system()
    if system:
        ev = run_evaluation(client, "Engineered", system, few_shot or None)
        evaluations.append(ev)
    else:
        print("  Skipping engineered (TODO 6 not complete)")

    if evaluations:
        print_summary(evaluations)

    print("\n" + "=" * 70)
    print("Key takeaways:")
    print("  1. Few-shot examples anchor the model to YOUR definitions, not defaults.")
    print("  2. P2 (degraded, not down) is the hardest category — examples help most here.")
    print("  3. Combining good system prompt + few-shot usually beats either alone.")
    print("=" * 70)


if __name__ == "__main__":
    main()
