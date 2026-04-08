#!/usr/bin/env python3
"""
Lab 03: Chain of Thought — Multi-Step Incident Diagnosis
==========================================================
You're building an AI-powered incident analyzer that not only classifies
incidents but explains its reasoning — step by step. Engineers reviewing
the analysis need to be able to audit the logic, not just trust the conclusion.

You'll compare direct answers vs chain-of-thought reasoning, and implement
the scratchpad pattern (reasoning + structured output, cleanly separated).

Requires: ANTHROPIC_API_KEY in .env

Run:
    python lab.py

When stuck: check solution.py
"""

import json
import os
import re
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


MODEL = "claude-sonnet-4-6"   # Use Sonnet for CoT — better reasoning than Haiku
TEMPERATURE = 0.0


# ── Incident scenarios ─────────────────────────────────────────────────────────
# Multi-step scenarios where reasoning chain matters.
# Each has multiple data points that must be correlated to reach the right answer.

INCIDENTS = [
    {
        "id": "SCENARIO-A",
        "title": "Cascading Failure — What's the Root Cause?",
        "data": """\
Timeline:
  14:22:00  Traffic spike: requests/sec jumped from 1200 to 3100 (+158%)
  14:22:45  auth-service: p99 latency increased from 80ms to 340ms
  14:23:10  auth-service: connection pool errors starting (pool size: 20)
  14:23:30  api-gateway: auth-service returning 503s, circuit breaker opening
  14:24:00  payment-service: cannot validate tokens (auth unavailable)
  14:24:15  alertmanager: FIRING AuthServiceDown
  14:24:30  alertmanager: FIRING PaymentServiceDegraded

Current state:
  - auth-service: 4/4 pods Running, CPU 78%, Memory 45%
  - database connections: 20/20 used, 34 waiting
  - Recent deployments: none in last 6 hours
  - HPA: auth-service has no HPA configured""",
    },
    {
        "id": "SCENARIO-B",
        "title": "Silent Data Corruption — Is It Infrastructure or Application?",
        "data": """\
Observations:
  - Users reporting incorrect account balances since 09:00 this morning
  - Error logs: zero errors in payment-service or account-service
  - Database: no replication lag, all replicas healthy
  - Recent events:
      08:45  payment-service deployed v2.3.1 (added new fee calculation logic)
      08:50  First reports of incorrect balances begin
      08:55  Rollback attempted but rejected: "DB migration v45 is irreversible"
  - A/B comparison: accounts updated before 08:45 are correct, after are wrong
  - The migration v45 added a new 'processing_fee' column with default value 0

Developer note: "The new version calculates fees differently but all unit tests passed" """,
    },
    {
        "id": "SCENARIO-C",
        "title": "Node Pressure — Which Service Is the Culprit?",
        "data": """\
Cluster state:
  - 3 worker nodes, each 16 vCPU / 64GB RAM
  - Node utilization: node-1=94% CPU, node-2=87% CPU, node-3=52% CPU
  - Kubernetes scheduler: failing to place new pods (node pressure)
  - Some pods evicted from node-1 in last 30 minutes

Pod CPU usage (top 10, across all nodes):
  ml-inference-7d9f2    2800m   (limit: 4000m)  ← node-1
  ml-inference-8c1a3    2650m   (limit: 4000m)  ← node-1
  ml-inference-2b4e1    2700m   (limit: 4000m)  ← node-2
  data-pipeline-xxk9r   1200m   (limit: 2000m)  ← node-2
  api-gateway-p9j2k      890m   (limit: 1000m)  ← node-1
  auth-service-m3n8x     210m   (limit: 500m)   ← node-2
  payment-svc-q7r3t      185m   (limit: 500m)   ← node-3
  cache-worker-l5p2v     170m   (limit: 256m)   ← node-3
  log-aggregator-w8y4z   155m   (limit: 256m)   ← node-1

Recent events:
  Yesterday 16:30  ml-inference deployment scaled from 1 replica to 3
  Today 08:00      data-pipeline scheduled job started (runs daily 08:00-10:00) """,
    },
]


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


# ── Analysis functions ─────────────────────────────────────────────────────────

def analyze_direct(client: anthropic.Anthropic, incident: dict) -> str:
    """Direct answer — no CoT instruction. Just ask for the root cause."""
    system = """\
You are a senior SRE. Analyze the incident data and provide:
1. Root cause (1 sentence)
2. Immediate action (1 sentence)
3. Prevention (1 sentence)

Be concise."""

    # TODO 1: Call the API with the direct system prompt.
    # Use MODEL, temperature=TEMPERATURE, max_tokens=300
    # The user message should include the incident title and data.
    pass


def analyze_with_cot(client: anthropic.Anthropic, incident: dict) -> str:
    """Chain-of-thought analysis — explicit reasoning steps before conclusion."""
    system = """\
You are a senior SRE analyzing an incident. Think step by step.

Follow this reasoning process:
1. OBSERVATIONS: List the key facts from the data (what happened, in order)
2. CORRELATIONS: What patterns or causal links do you see between the observations?
3. HYPOTHESES: What are 2-3 possible root causes?
4. EVIDENCE: For each hypothesis, what evidence supports or refutes it?
5. CONCLUSION: What is the most likely root cause? Confidence level: HIGH/MEDIUM/LOW
6. IMMEDIATE ACTION: The single most important step to take right now
7. PREVENTION: One concrete change to prevent recurrence"""

    # TODO 2: Call the API with the CoT system prompt.
    # Use MODEL, temperature=TEMPERATURE, max_tokens=800
    pass


def analyze_scratchpad(client: anthropic.Anthropic, incident: dict) -> tuple[str, dict | None]:
    """Scratchpad pattern: free reasoning + structured JSON output, cleanly separated.

    Returns (raw_response, parsed_output_dict)
    The reasoning is in <reasoning> tags, structured output in <output> tags.
    """
    system = """\
You are a senior SRE. Analyze incidents using this format:

<reasoning>
Think through the problem step by step. Consider timeline, causality,
and alternative explanations. Be thorough.
</reasoning>
<output>
{
  "root_cause": "one sentence",
  "root_cause_category": "traffic_spike | deployment | resource_exhaustion | configuration | external | unknown",
  "confidence": "HIGH | MEDIUM | LOW",
  "affected_services": ["service1", "service2"],
  "immediate_action": "the single most important thing to do right now",
  "prevention": "one concrete change to prevent recurrence",
  "estimated_duration_minutes": number or null
}
</output>

Output ONLY the <reasoning> and <output> blocks. Nothing else."""

    # TODO 3: Call the API and extract the output.
    # Steps:
    #   a) Call the API (max_tokens=1000)
    #   b) Extract raw response text
    #   c) Use regex to find content between <output> and </output> tags:
    #      re.search(r"<output>(.*?)</output>", raw, re.DOTALL)
    #   d) Try to parse the extracted JSON
    #   e) Return (raw_response, parsed_dict_or_None)
    pass


# ── Display helpers ────────────────────────────────────────────────────────────

def print_divider(title: str = "") -> None:
    if title:
        print(f"\n{'─' * 20} {title} {'─' * (37 - len(title))}")
    else:
        print("─" * 60)


def display_comparison(incident: dict, direct: str, cot: str, scratchpad_raw: str, scratchpad_parsed: dict | None) -> None:
    print("\n" + "=" * 70)
    print(f"  {incident['id']}: {incident['title']}")
    print("=" * 70)

    print_divider("DIRECT ANSWER")
    print(direct or "(TODO 1 not complete)")

    print_divider("CHAIN OF THOUGHT")
    print(cot or "(TODO 2 not complete)")

    print_divider("SCRATCHPAD — Reasoning")
    if scratchpad_raw:
        # Extract just the reasoning section for display
        reasoning_match = re.search(r"<reasoning>(.*?)</reasoning>", scratchpad_raw, re.DOTALL)
        if reasoning_match:
            print(reasoning_match.group(1).strip())
        else:
            print(scratchpad_raw[:500])
    else:
        print("(TODO 3 not complete)")

    print_divider("SCRATCHPAD — Structured Output")
    if scratchpad_parsed:
        print(json.dumps(scratchpad_parsed, indent=2))
    elif scratchpad_raw:
        print("(JSON parse failed)")
    else:
        print("(TODO 3 not complete)")


# ── Exercises ──────────────────────────────────────────────────────────────────

def exercise_compare_approaches(client: anthropic.Anthropic) -> None:
    """Run all 3 incidents through all 3 analysis approaches and compare."""
    print("=" * 70)
    print("Comparing: Direct vs Chain-of-Thought vs Scratchpad")
    print("=" * 70)

    for incident in INCIDENTS:
        direct = analyze_direct(client, incident)
        cot = analyze_with_cot(client, incident)

        if analyze_scratchpad(client, incident) is not None:
            scratchpad_raw, scratchpad_parsed = analyze_scratchpad(client, incident)
        else:
            scratchpad_raw, scratchpad_parsed = None, None

        display_comparison(incident, direct, cot, scratchpad_raw, scratchpad_parsed)
        input("\n  Press Enter for next scenario...")


def exercise_cot_vs_direct_accuracy(client: anthropic.Anthropic) -> None:
    """Exercise: For SCENARIO-A, check if direct and CoT reach the same conclusion.

    Expected: CoT should identify that the ROOT CAUSE is no HPA on auth-service
    combined with a traffic spike — NOT the database or the auth-service code.
    Direct answer may jump to "database is overloaded" or "auth-service crashed".
    """
    incident = INCIDENTS[0]
    print("=" * 70)
    print(f"Accuracy Check: {incident['id']}")
    print("=" * 70)
    print(f"\nExpected root cause: Traffic spike + no HPA on auth-service")
    print(f"→ Connection pool exhausted → cascading failure to payment-service\n")

    print("Direct answer:")
    direct = analyze_direct(client, incident)
    print(direct or "(TODO 1 not complete)")

    print("\n\nCoT answer:")
    cot = analyze_with_cot(client, incident)
    print(cot or "(TODO 2 not complete)")

    print("\n\nObservation: Does the direct answer identify the HPA gap?")
    print("Does the CoT reasoning trace the causality correctly?")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 03: Chain of Thought\n")
    print("Choose an exercise:")
    print("  1 — Compare all approaches on all 3 scenarios (interactive)")
    print("  2 — Accuracy check on Scenario A (quick, non-interactive)")
    print()

    choice = input("Enter 1 or 2 [default: 2]: ").strip() or "2"
    client = get_client()

    if choice == "1":
        exercise_compare_approaches(client)
    else:
        exercise_cot_vs_direct_accuracy(client)

    print("\n" + "=" * 70)
    print("Key takeaways:")
    print("  1. CoT prevents 'jumping to the first plausible answer'.")
    print("  2. Scratchpad separates auditable reasoning from pipeline-ready data.")
    print("  3. For multi-step problems, CoT + Sonnet > direct + Haiku.")
    print("=" * 70)


if __name__ == "__main__":
    main()
