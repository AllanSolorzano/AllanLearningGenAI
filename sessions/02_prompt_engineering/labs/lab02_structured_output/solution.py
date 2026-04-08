#!/usr/bin/env python3
"""
Lab 02: Structured Output — SOLUTION
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

import anthropic

MODEL = "claude-haiku-4-5-20251001"
TEMPERATURE = 0.0

TEST_INCIDENTS = [
    {"id": "INC-001", "input": "hey team, payment service is totally borked. seeing 100% 503s from the api gateway. started about 10 mins ago. prod is down. all payment pods are in crashloop. customers cant checkout"},
    {"id": "INC-002", "input": "FYI auth latency is really high right now in production. p99 is like 2 seconds, normal is 200ms. logins are slow but working. started after the deploy at 2pm. no errors in logs just slow"},
    {"id": "INC-003", "input": "staging broke again, postgres wont start. need this fixed for the demo tomorrow morning but its not customer facing"},
    {"id": "INC-004", "input": "getting paged for high disk usage on the logging nodes. currently at 79%, threshold is 85%. not critical yet but growing fast. this is prod infra"},
    {"id": "INC-005", "input": "URGENT: our entire prod k8s cluster is down. all nodes showing NotReady. this started 5 mins ago. no deployments recently. everything is broken. HELP"},
    {"id": "INC-006", "input": "the nightly data pipeline failed again. third time this week. data is stale by 8 hours now. this affects the analytics dashboard but not customer transactions. staging and prod both affected"},
]


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def extract_json_robust(text: str) -> dict | None:
    # Layer 1: direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Layer 2: strip code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    # Layer 3: extract first {...} block
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def validate_incident(data: dict) -> tuple[bool, list[str]]:
    errors = []
    required = {"title", "severity", "affected_services", "environment", "symptoms", "impact", "suggested_runbook"}
    missing = required - set(data.keys())
    if missing:
        errors.append(f"Missing fields: {sorted(missing)}")

    if "severity" in data and data["severity"] not in {"P1", "P2", "P3"}:
        errors.append(f"Invalid severity: {data['severity']!r}")

    if "environment" in data and data["environment"] not in {"production", "staging", "development", "unknown", None}:
        errors.append(f"Invalid environment: {data['environment']!r}")

    if "affected_services" in data and not isinstance(data["affected_services"], list):
        errors.append("affected_services must be a list")

    return len(errors) == 0, errors


def extract_v1_basic(client: anthropic.Anthropic, incident_text: str) -> str:
    system = """\
You are an incident intake system.
Extract the following fields from the incident report and return them as JSON:
title, severity (P1/P2/P3), affected_services (list), environment,
symptoms, impact, suggested_runbook."""

    response = client.messages.create(
        model=MODEL, max_tokens=512, temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": incident_text}],
    )
    return response.content[0].text


def extract_v2_strict(client: anthropic.Anthropic, incident_text: str) -> str:
    system = f"""\
You are an incident intake system. Extract structured fields from incident reports.

Output ONLY a JSON object. No text before or after. No markdown. No code fences.

Required fields — use null if information is not present:
{{
  "title": "concise title under 80 chars",
  "severity": "P1" | "P2" | "P3",
  "affected_services": ["service1", "service2"],
  "environment": "production" | "staging" | "development" | "unknown",
  "symptoms": "what is broken",
  "impact": "who or what is affected",
  "suggested_runbook": "runbook ID if obvious, else null"
}}

Severity guide:
- P1: production down, customer-facing failure, revenue impact
- P2: degraded performance, SLO breach, partial failure
- P3: warning, staging issue, non-customer-facing

Do NOT invent information not present in the input.
"""
    response = client.messages.create(
        model=MODEL, max_tokens=512, temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": incident_text}],
    )
    return response.content[0].text


def extract_v3_few_shot(client: anthropic.Anthropic, incident_text: str) -> str:
    system = """\
You are an incident intake system. Extract structured data from incident reports.
Output ONLY valid JSON. No prose. No code fences. No explanation."""

    few_shot = [
        {
            "role": "user",
            "content": "checkout is down in prod, all pods crashlooping, customers cant pay, started 15 mins ago after a deploy",
        },
        {
            "role": "assistant",
            "content": json.dumps({
                "title": "Checkout service down — all pods CrashLoopBackOff",
                "severity": "P1",
                "affected_services": ["checkout"],
                "environment": "production",
                "symptoms": "All pods in CrashLoopBackOff after deploy 15 minutes ago",
                "impact": "Customers cannot complete purchases",
                "suggested_runbook": "RB-001"
            }),
        },
    ]

    messages = few_shot + [{"role": "user", "content": incident_text}]
    response = client.messages.create(
        model=MODEL, max_tokens=512, temperature=TEMPERATURE,
        system=system, messages=messages,
    )
    return response.content[0].text


def run_extraction_test(client, version_name, extractor_fn) -> dict:
    print(f"\n  Strategy: {version_name}")
    print("  " + "─" * 60)

    parse_successes = 0
    validation_successes = 0
    results = []

    for inc in TEST_INCIDENTS:
        raw = extractor_fn(client, inc["input"])
        parsed = extract_json_robust(raw)
        parse_ok = parsed is not None

        if parse_ok:
            parse_successes += 1
            valid, errors = validate_incident(parsed)
        else:
            valid, errors = False, ["JSON parse failed"]

        if valid:
            validation_successes += 1

        results.append({"id": inc["id"], "parse_ok": parse_ok, "valid": valid, "errors": errors})

        status = "✓ PASS" if valid else ("✗ INVALID" if parse_ok else "✗ NO JSON")
        err_str = f" — {'; '.join(errors)}" if errors else ""
        print(f"  {inc['id']}: {status}{err_str}")

    total = len(TEST_INCIDENTS)
    print(f"\n  Parse rate: {parse_successes}/{total} ({parse_successes/total:.0%})")
    print(f"  Valid rate: {validation_successes}/{total} ({validation_successes/total:.0%})")

    return {
        "name": version_name,
        "parse_rate": parse_successes / total,
        "valid_rate": validation_successes / total,
        "results": results,
    }


def exercise_xml_tags(client: anthropic.Anthropic) -> None:
    print("\n" + "=" * 60)
    print("Bonus: XML Tag Extraction")
    print("=" * 60)

    system = """\
You are an incident intake system. Extract key fields from incident reports.

Respond using ONLY these XML tags:
<title>short title under 80 chars</title>
<severity>P1|P2|P3</severity>
<environment>production|staging|development|unknown</environment>
<impact>who or what is affected</impact>

No other text. Tags only."""

    test_incident = "prod database is down, all writes failing, customers getting errors when saving data"

    response = client.messages.create(
        model=MODEL, max_tokens=200, temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": test_incident}],
    )
    raw = response.content[0].text
    print(f"\nInput:    {test_incident}")
    print(f"\nRaw output:\n{raw}")

    def extract_tag(text: str, tag: str) -> str | None:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
        return match.group(1).strip() if match else None

    print("\nExtracted fields:")
    for tag in ["title", "severity", "environment", "impact"]:
        value = extract_tag(raw, tag)
        print(f"  {tag}: {value!r}")


def main() -> None:
    print("\nLab 02: Structured Output (Solution)\n")
    client = get_client()
    all_results = []

    print("=" * 60)
    print("Testing extraction strategies on 6 incident reports")
    print("=" * 60)

    all_results.append(run_extraction_test(client, "v1_basic", extract_v1_basic))
    all_results.append(run_extraction_test(client, "v2_strict", extract_v2_strict))
    all_results.append(run_extraction_test(client, "v3_few_shot", extract_v3_few_shot))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n{'Strategy':<20} {'Parse Rate':>12} {'Valid Rate':>12}")
    print("─" * 46)
    for r in all_results:
        print(f"{r['name']:<20} {r['parse_rate']:>11.0%} {r['valid_rate']:>12.0%}")

    exercise_xml_tags(client)

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. 'Output JSON' is not enough — add no-fence and no-prose rules.")
    print("  2. Few-shot examples are the strongest signal for output format.")
    print("  3. Always write a robust extractor — don't assume clean output.")
    print("  4. Validate schema after parsing — correct JSON ≠ correct data.")
    print("=" * 60)


if __name__ == "__main__":
    main()
