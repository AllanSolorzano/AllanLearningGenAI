#!/usr/bin/env python3
"""
Demo: Chain-of-Thought for Infrastructure Debugging
=====================================================
Watch chain-of-thought reasoning work through a complex multi-service
incident in real time. Compare the direct answer vs the reasoned analysis
to see why CoT produces better, more auditable root cause analysis.

Requires: ANTHROPIC_API_KEY in .env

Usage:
    python demo_cot_debugging.py
"""

import json
import os
import re
import sys
import time

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


# Use Sonnet for CoT — better reasoning quality
MODEL = "claude-sonnet-4-6"


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def stream_response(client: anthropic.Anthropic, system: str, user: str, max_tokens: int = 1000) -> str:
    """Stream the response so we can watch the reasoning unfold in real time."""
    full_text = ""
    print()
    with client.messages.stream(
        model=MODEL, max_tokens=max_tokens, temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text
    print()
    return full_text


def ask(client: anthropic.Anthropic, system: str, user: str, max_tokens: int = 800) -> str:
    r = client.messages.create(
        model=MODEL, max_tokens=max_tokens, temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text


def extract_output_block(text: str) -> dict | None:
    """Extract JSON from <output> tags."""
    match = re.search(r"<output>(.*?)</output>", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None


# ── Incident data ─────────────────────────────────────────────────────────────

INCIDENT_DATA = """\
INCIDENT: CheckoutServiceDegraded
Time: 2024-10-15 14:20 UTC

Timeline of events:
  14:15  Marketing campaign "FLASH50" launched (50% discount on all orders)
  14:16  Order submission rate increased: 450/min → 2,800/min (+522%)
  14:17  checkout-service CPU: 23% → 87%
  14:17  checkout-service: connection wait time increasing
  14:18  inventory-service: request queue depth 0 → 2,400 requests
  14:18  inventory-service p99 latency: 45ms → 3,200ms
  14:19  checkout-service: 12% of requests timing out (waiting on inventory)
  14:19  payment-service: 8% error rate (checkout retrying on timeout = duplicate payment attempts)
  14:20  alertmanager: FIRING CheckoutErrorRate >5%
  14:20  alertmanager: FIRING PaymentDuplicateAttempts

Current metrics:
  checkout-service:   3/3 pods Running, CPU 91%, Memory 58%
  inventory-service:  2/2 pods Running, CPU 78%, Memory 72%
  payment-service:    4/4 pods Running, CPU 34%, Memory 41%
  database:           primary healthy, read replica healthy, connections 187/200

Recent changes:
  14:15  Marketing team activated FLASH50 campaign (no engineering review)
  13:45  checkout-service v3.2.1 deployed (minor UI change, no backend changes)
  Yesterday  inventory-service max_connections reduced from 500 to 200 (cost optimization)

Infrastructure config:
  checkout-service:   HPA configured, min=3, max=10, target CPU=70%
  inventory-service:  NO HPA configured
  payment-service:    HPA configured, min=4, max=20, target CPU=60%"""


def main() -> None:
    client = get_client()

    print("═" * 70)
    print("  DEMO: Chain-of-Thought for Infrastructure Debugging")
    print("═" * 70)
    print("\nIncident: CheckoutServiceDegraded")
    print("3 alerts firing: error rate, duplicate payments, latency")
    print("\nWatching the model reason through it in real time...\n")

    # ── Step 1: Direct answer (fast, shallow) ──────────────────────────────────
    print("─" * 70)
    print("APPROACH 1: Direct Answer (no CoT)")
    print("─" * 70)
    print("\nQuestion: What's the root cause and immediate fix?\n")

    direct_system = """\
You are a senior SRE. Analyze the incident data and provide:
- Root cause (1 sentence)
- Immediate action (1 sentence)
Be concise."""

    direct = ask(client, direct_system, INCIDENT_DATA, max_tokens=200)
    print(direct)

    input("\n  Press Enter to see Chain-of-Thought analysis...")

    # ── Step 2: Full CoT (verbose, thorough) ───────────────────────────────────
    print("\n" + "─" * 70)
    print("APPROACH 2: Chain-of-Thought (streaming in real time)")
    print("─" * 70)

    cot_system = """\
You are a senior SRE performing a root cause analysis. Think step by step.

Follow this structure exactly:

OBSERVATIONS: List every meaningful fact from the timeline, in chronological order

CAUSALITY CHAIN: Trace the sequence: what triggered what?
  (e.g., X happened → which caused Y → which caused Z)

CONTRIBUTING FACTORS: What made this worse than it should have been?
  (config choices, missing safeguards, recent changes)

ROOT CAUSE: The single upstream cause. One sentence.

IMMEDIATE ACTIONS (next 15 minutes):
  1. [most urgent action to stop the bleeding]
  2. [second action]
  3. [third action if needed]

PERMANENT FIXES (this week):
  1. [change to prevent recurrence]
  2. [second change]"""

    cot_response = stream_response(client, cot_system, INCIDENT_DATA, max_tokens=900)

    input("\n  Press Enter to see Scratchpad pattern (reasoning + structured output)...")

    # ── Step 3: Scratchpad pattern ─────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("APPROACH 3: Scratchpad Pattern (audit trail + pipeline-ready JSON)")
    print("─" * 70)

    scratchpad_system = """\
You are a senior SRE. Analyze incidents using this exact format:

<reasoning>
Think step by step through the causality chain. Be thorough.
</reasoning>
<output>
{
  "root_cause": "one sentence",
  "root_cause_category": "traffic_spike|deployment|resource_exhaustion|configuration|external|cascading",
  "confidence": "HIGH|MEDIUM|LOW",
  "primary_culprit_service": "service name",
  "contributing_factors": ["factor1", "factor2"],
  "immediate_actions": ["action1", "action2", "action3"],
  "permanent_fixes": ["fix1", "fix2"],
  "time_to_resolve_estimate_minutes": number
}
</output>

Output ONLY these two blocks. Nothing else."""

    print("\n[Reasoning — shown in logs for audit, hidden from pipeline consumers]\n")
    scratchpad_raw = stream_response(client, scratchpad_system, INCIDENT_DATA, max_tokens=1000)

    parsed = extract_output_block(scratchpad_raw)

    print("\n" + "─" * 70)
    print("[Structured Output — goes into your incident management system]")
    print("─" * 70)
    if parsed:
        print(json.dumps(parsed, indent=2))
    else:
        print("(JSON extraction failed)")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  KEY INSIGHTS FROM THIS INCIDENT")
    print("═" * 70)
    print("""
  Root cause: Marketing campaign launched without capacity review
  → Traffic spike 5× → inventory-service overwhelmed (no HPA, reduced conn limit)
  → Checkout timeouts → payment retries → duplicate payment attempts

  What direct answer missed: The inventory-service conn limit reduction
  (done yesterday for cost savings) was a critical contributing factor.
  The HPA gap on inventory was the structural problem.

  Why CoT found it: The timeline correlation forced the model to notice
  that the traffic spike (14:16) preceded ALL other symptoms (14:17+).
  The conn limit change from yesterday was only visible when reasoning
  about "what made this worse than it should have been."

  Scratchpad value:
  - <reasoning> block: auditable log for post-mortem review
  - <output> block: feeds directly into Jira/PagerDuty/Slack without parsing
""")


if __name__ == "__main__":
    main()
