#!/usr/bin/env python3
"""
Lab 01: Zero-Shot vs Few-Shot — SOLUTION
==========================================
Reference implementation. Try lab.py yourself first.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic

MODEL = "claude-haiku-4-5-20251001"
TEMPERATURE = 0.0

TEST_ALERTS = [
    {"alert": "payment-service: error rate 100%, all requests returning 500", "expected": "P1"},
    {"alert": "database primary is unreachable, 0 healthy replicas", "expected": "P1"},
    {"alert": "all pods in production namespace in CrashLoopBackOff", "expected": "P1"},
    {"alert": "SSL certificate expired, HTTPS completely broken", "expected": "P1"},
    {"alert": "auth-service p99 latency 1800ms, SLO threshold 500ms", "expected": "P2"},
    {"alert": "worker nodes running at 88% CPU, autoscaler not triggering", "expected": "P2"},
    {"alert": "2 of 5 payment pods OOMKilled, 3 still serving traffic", "expected": "P2"},
    {"alert": "Terraform state lock held for 47 minutes, pipeline blocked", "expected": "P2"},
    {"alert": "disk usage at 71% on log-archive volume, threshold 85%", "expected": "P3"},
    {"alert": "backup job failed overnight, previous backup is 36 hours old", "expected": "P3"},
    {"alert": "staging environment pod restart count elevated: 12 in last hour", "expected": "P3"},
    {"alert": "cost anomaly detected: S3 spend +22% vs last week", "expected": "P3"},
]


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def classify(
    client: anthropic.Anthropic,
    alert_text: str,
    system_prompt: str,
    few_shot_messages: list[dict] | None = None,
) -> str:
    messages = list(few_shot_messages or [])
    messages.append({"role": "user", "content": alert_text})
    response = client.messages.create(
        model=MODEL,
        max_tokens=32,
        temperature=TEMPERATURE,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text.strip()


def extract_severity(raw: str) -> str:
    raw_upper = raw.upper()
    for sev in ["P1", "P2", "P3"]:
        if sev in raw_upper:
            return sev
    return "ERROR"


def run_evaluation(
    client: anthropic.Anthropic,
    name: str,
    system_prompt: str,
    few_shot_messages: list[dict] | None = None,
) -> dict:
    print(f"\n  Running: {name}")
    results = []

    for item in TEST_ALERTS:
        raw = classify(client, item["alert"], system_prompt, few_shot_messages)
        severity = extract_severity(raw)
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
    by_severity: dict[str, dict] = {}
    for sev in ["P1", "P2", "P3"]:
        subset = [r for r in results if r["expected"] == sev]
        by_severity[sev] = {
            "correct": sum(1 for r in subset if r["correct"]),
            "total": len(subset),
        }
    return {"name": name, "results": results, "accuracy": accuracy, "by_severity": by_severity}


# ── Prompt Implementations ─────────────────────────────────────────────────────

def build_zero_shot_system() -> str:
    return """\
You are an alert severity classifier for a production platform team.

Classify each incoming alert as exactly one of: P1, P2, or P3.

Severity definitions:
- P1: Active customer impact. Service is completely down, data loss occurring,
      or payment processing broken. Requires immediate response.
- P2: Degraded service, elevated error rates, SLO violations, or imminent risk
      of P1 if not addressed. Not fully down but significantly impaired.
- P3: Warning state. No current customer impact. Trending toward a problem
      or a non-critical issue that needs attention in business hours.

Rules:
- Staging environment issues are always P3 (no production customer impact)
- Cost/billing anomalies are P3 unless spend is catastrophically high
- If ambiguous between P1 and P2, use P2 (safer default than P1)
- If ambiguous between P2 and P3, use P2

Output ONLY the severity label: P1, P2, or P3. Nothing else."""


def build_one_shot_system() -> tuple[str, list[dict]]:
    system = """\
You are an alert severity classifier for a production platform team.
Classify alerts as P1, P2, or P3.
P1 = customer impact, service down or severely degraded
P2 = degraded performance, elevated errors, or imminent risk
P3 = warning, non-critical, monitoring only
Staging issues are always P3.
Output ONLY the severity label. Nothing else."""

    # One carefully chosen example: the tricky "partially degraded" P2 case
    few_shot = [
        {"role": "user",      "content": "3 of 10 API gateway replicas OOMKilled, 7 still healthy, error rate 12%"},
        {"role": "assistant", "content": "P2"},
    ]
    return system, few_shot


def build_five_shot_system() -> tuple[str, list[dict]]:
    system = """\
You are an alert severity classifier for a production platform team.
P1 = customer impact, service down or severely degraded
P2 = degraded performance, elevated errors, or imminent risk
P3 = warning, non-critical, monitoring only
Staging issues are always P3. Output ONLY the severity label."""

    few_shot = [
        # Clear P1
        {"role": "user",      "content": "checkout-service returning 503 for 100% of requests, revenue impact"},
        {"role": "assistant", "content": "P1"},
        # Partial outage → P2
        {"role": "user",      "content": "3 of 10 API gateway replicas OOMKilled, 7 still healthy, error rate 12%"},
        {"role": "assistant", "content": "P2"},
        # SLO breach → P2
        {"role": "user",      "content": "search-service p99 latency 2400ms, SLO target 800ms, degraded not down"},
        {"role": "assistant", "content": "P2"},
        # Warning → P3
        {"role": "user",      "content": "disk usage 68% on data volume, threshold 85%, growth rate 2%/day"},
        {"role": "assistant", "content": "P3"},
        # Staging → P3 regardless
        {"role": "user",      "content": "staging-api completely down, no pods running, all CrashLoopBackOff"},
        {"role": "assistant", "content": "P3"},
    ]
    return system, few_shot


def build_engineered_system() -> tuple[str, list[dict]]:
    # Best version: strong system prompt + 5 well-chosen examples covering edge cases
    system = """\
You are an alert severity classifier for a production platform engineering team.

SEVERITY DEFINITIONS:
P1 — Immediate action required. Active customer-facing impact:
     complete service failure, payment processing down, data loss, all replicas down,
     security breach, certificates expired in production.

P2 — Urgent attention needed within 1 hour. Degraded but not fully down:
     partial replica failure (some pods OOMKilled, others serving), SLO breach,
     elevated error rate (>5%), resource pressure where autoscaler isn't responding,
     blocked pipelines affecting deployment velocity, high latency impacting UX.

P3 — Monitor in business hours. No current customer impact:
     disk/memory below threshold warnings, cost anomalies, backup delays,
     staging/dev environment issues (regardless of severity), scheduled job failures
     where data is still available from prior successful run.

RULES:
- Staging/dev/test environments: always P3
- Cost anomalies under 50%: always P3
- Single pod failure where service is still healthy overall: P3
- Ambiguous P1/P2: choose P2
- Ambiguous P2/P3: choose P2

Output ONLY: P1, P2, or P3. No other text."""

    few_shot = [
        # Clear P1 — complete payment failure
        {"role": "user",      "content": "payment-api: 100% error rate, all 6 pods in CrashLoopBackOff, revenue stopped"},
        {"role": "assistant", "content": "P1"},
        # P2 — partial degradation
        {"role": "user",      "content": "auth-service: 2 of 5 pods OOMKilled, error rate 18%, remaining pods handling load"},
        {"role": "assistant", "content": "P2"},
        # P2 — SLO breach, not down
        {"role": "user",      "content": "api-gateway p99 latency 2.1s, SLO is 500ms, no errors but slow"},
        {"role": "assistant", "content": "P2"},
        # P3 — staging, looks scary but isn't production
        {"role": "user",      "content": "staging environment: postgres primary unreachable, all staging services down"},
        {"role": "assistant", "content": "P3"},
        # P3 — warning, not critical
        {"role": "user",      "content": "S3 costs up 22% vs last week, investigating usage patterns"},
        {"role": "assistant", "content": "P3"},
    ]
    return system, few_shot


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


def main() -> None:
    print("\nLab 01: Zero-Shot vs Few-Shot (Solution)\n")
    client = get_client()
    evaluations = []

    evaluations.append(run_evaluation(client, "Zero-shot", build_zero_shot_system()))

    sys1, fs1 = build_one_shot_system()
    evaluations.append(run_evaluation(client, "1-shot", sys1, fs1))

    sys5, fs5 = build_five_shot_system()
    evaluations.append(run_evaluation(client, "5-shot", sys5, fs5))

    sys_e, fs_e = build_engineered_system()
    evaluations.append(run_evaluation(client, "Engineered", sys_e, fs_e))

    print_summary(evaluations)
    print("\n" + "=" * 70)
    print("Key takeaways:")
    print("  1. Few-shot examples anchor the model to YOUR definitions, not defaults.")
    print("  2. P2 is the hardest category — examples help most here.")
    print("  3. Strong system prompt + good few-shot beats either alone.")
    print("=" * 70)


if __name__ == "__main__":
    main()
