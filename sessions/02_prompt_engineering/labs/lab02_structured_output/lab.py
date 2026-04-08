#!/usr/bin/env python3
"""
Lab 02: Structured Output — Reliable JSON from Unstructured Incident Reports
=============================================================================
You're building an incident intake tool. Engineers paste raw incident
descriptions into a Slack bot, and it must extract structured fields
to create a Jira ticket automatically.

The challenge: the model sometimes wraps JSON in code fences, adds explanations,
or omits required fields. You'll build a robust extraction pipeline.

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


MODEL = "claude-haiku-4-5-20251001"
TEMPERATURE = 0.0


# ── Expected output schema ─────────────────────────────────────────────────────
# This is what your Jira integration expects. Every field must be present.

INCIDENT_SCHEMA = {
    "title": "str — short title (under 80 chars)",
    "severity": "P1 | P2 | P3",
    "affected_services": "list[str] — service names mentioned",
    "environment": "production | staging | development | unknown",
    "symptoms": "str — what's broken, from the user's description",
    "impact": "str — who/what is affected",
    "suggested_runbook": "str — runbook ID or null if unknown",
}

# ── Test incidents ─────────────────────────────────────────────────────────────
# Realistic messy Slack messages from engineers.
# Note: these are intentionally informal and unstructured.

TEST_INCIDENTS = [
    {
        "id": "INC-001",
        "input": "hey team, payment service is totally borked. seeing 100% 503s from the api gateway. started about 10 mins ago. prod is down. all payment pods are in crashloop. customers cant checkout",
    },
    {
        "id": "INC-002",
        "input": "FYI auth latency is really high right now in production. p99 is like 2 seconds, normal is 200ms. logins are slow but working. started after the deploy at 2pm. no errors in logs just slow",
    },
    {
        "id": "INC-003",
        "input": "staging broke again, postgres wont start. need this fixed for the demo tomorrow morning but its not customer facing",
    },
    {
        "id": "INC-004",
        "input": "getting paged for high disk usage on the logging nodes. currently at 79%, threshold is 85%. not critical yet but growing fast. this is prod infra",
    },
    {
        "id": "INC-005",
        "input": "URGENT: our entire prod k8s cluster is down. all nodes showing NotReady. this started 5 mins ago. no deployments recently. everything is broken. HELP",
    },
    {
        "id": "INC-006",
        "input": "the nightly data pipeline failed again. third time this week. data is stale by 8 hours now. this affects the analytics dashboard but not customer transactions. staging and prod both affected",
    },
]


# ── API client ─────────────────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


# ── Parsing utilities ──────────────────────────────────────────────────────────

def extract_json_robust(text: str) -> dict | None:
    """Robustly extract JSON from LLM output.

    Handles: direct JSON, code-fenced JSON, JSON embedded in prose.
    Returns None if all extraction attempts fail.
    """
    # TODO 1: Implement 3-layer JSON extraction:
    #
    # Layer 1: Direct parse
    #   try: return json.loads(text.strip())
    #   except JSONDecodeError: pass
    #
    # Layer 2: Strip markdown code fences, then parse
    #   Use re.sub to remove ```json, ```, and ``` blocks
    #   then try json.loads again
    #
    # Layer 3: Extract first {...} block using regex
    #   Use re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    #   then try json.loads on the match
    #
    # Return None if all layers fail
    pass


def validate_incident(data: dict) -> tuple[bool, list[str]]:
    """Validate extracted incident data against the expected schema.

    Returns (is_valid, list_of_errors).
    """
    # TODO 2: Validate the extracted dict:
    #   - Check all required keys exist: title, severity, affected_services,
    #     environment, symptoms, impact, suggested_runbook
    #   - Check severity is one of P1/P2/P3
    #   - Check environment is one of: production/staging/development/unknown
    #   - Check affected_services is a list
    #   - Return (True, []) if valid, (False, [list of error strings]) if not
    pass


# ── Prompting strategies ───────────────────────────────────────────────────────

def extract_v1_basic(client: anthropic.Anthropic, incident_text: str) -> str:
    """Version 1: Basic prompt — just ask for JSON with schema description.

    This is the naive approach most people start with. It often fails
    because the model adds prose or wraps in code fences.
    """
    # TODO 3: Write a basic system prompt that asks for JSON.
    # Keep it simple — just describe the task and schema.
    # Intentionally don't add all the defensive instructions (we'll compare).
    system = ""  # Your basic system prompt here

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": incident_text}],
    )
    return response.content[0].text


def extract_v2_strict(client: anthropic.Anthropic, incident_text: str) -> str:
    """Version 2: Strict prompt — explicit format rules and error handling.

    Add all the defensive instructions: no prose, no fences, null handling.
    """
    system = f"""\
You are an incident intake system. Extract structured fields from incident reports.

Output ONLY a JSON object. No text before or after. No markdown. No code fences.

Required fields — use null if information is not present in the input:
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

If a field cannot be determined from the input, use null.
Do NOT invent information not present in the input.

{json.dumps({"example_output": {
    "title": "Payment service 503 errors — prod",
    "severity": "P1",
    "affected_services": ["payment-service", "api-gateway"],
    "environment": "production",
    "symptoms": "100% 503 errors from API gateway, payment pods in CrashLoopBackOff",
    "impact": "Customers cannot complete checkout, revenue stopped",
    "suggested_runbook": "RB-001"
}}, indent=2)}
"""
    # TODO 4: Call the API with this strict system prompt.
    # Return the raw response text.
    pass


def extract_v3_few_shot(client: anthropic.Anthropic, incident_text: str) -> str:
    """Version 3: Few-shot — show the model an example of perfect extraction.

    The example demonstrates both the input format AND the exact output format.
    """
    system = """\
You are an incident intake system. Extract structured data from incident reports.
Output ONLY valid JSON. No prose. No code fences. No explanation."""

    # TODO 5: Add a few-shot example (one prior conversation turn pair).
    # Use a realistic, slightly messy incident report as the user message
    # and a perfect JSON extraction as the assistant message.
    # The example should cover most field types (all severities, null handling).
    few_shot: list[dict] = []  # Build your example here

    messages = few_shot + [{"role": "user", "content": incident_text}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        temperature=TEMPERATURE,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ── Evaluation ─────────────────────────────────────────────────────────────────

def run_extraction_test(
    client: anthropic.Anthropic,
    version_name: str,
    extractor_fn,
) -> dict:
    """Run all test incidents through an extractor and report results."""
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
            valid, errors = validate_incident(parsed) if parsed else (False, ["parse failed"])
        else:
            valid, errors = False, ["JSON parse failed"]

        if valid:
            validation_successes += 1

        results.append({
            "id": inc["id"],
            "parse_ok": parse_ok,
            "valid": valid,
            "errors": errors,
            "parsed": parsed,
        })

        status = "✓ PASS" if valid else ("✗ INVALID" if parse_ok else "✗ NO JSON")
        err_str = f" — {'; '.join(errors)}" if errors else ""
        print(f"  {inc['id']}: {status}{err_str}")

    total = len(TEST_INCIDENTS)
    print(f"\n  Parse rate:    {parse_successes}/{total} ({parse_successes/total:.0%})")
    print(f"  Valid rate:    {validation_successes}/{total} ({validation_successes/total:.0%})")

    return {
        "name": version_name,
        "parse_rate": parse_successes / total,
        "valid_rate": validation_successes / total,
        "results": results,
    }


# ── Bonus exercise ─────────────────────────────────────────────────────────────

def exercise_xml_tags(client: anthropic.Anthropic) -> None:
    """Bonus: Use XML tags instead of JSON for simpler field extraction.

    For flat structures, XML tags are often more reliable than JSON.
    The model can't accidentally break the structure.
    """
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
        model=MODEL,
        max_tokens=200,
        temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": test_incident}],
    )
    raw = response.content[0].text
    print(f"\nInput:    {test_incident}")
    print(f"\nRaw output:\n{raw}")

    # TODO 6: Extract fields from the XML tags using regex.
    # def extract_tag(text, tag_name) -> str | None:
    #     match = re.search(rf"<{tag_name}>(.*?)</{tag_name}>", text, re.DOTALL)
    #     return match.group(1).strip() if match else None
    #
    # Then print each extracted field.
    print("\nExtracted fields:")
    # your extraction here


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 02: Structured Output\n")

    client = get_client()
    all_results = []

    print("=" * 60)
    print("Testing extraction strategies on 6 incident reports")
    print("=" * 60)

    # V1: Basic (will likely have parse failures)
    if True:  # set False to skip while building
        r = run_extraction_test(client, "v1_basic", extract_v1_basic)
        all_results.append(r)

    # V2: Strict instructions
    r = run_extraction_test(client, "v2_strict", extract_v2_strict)
    all_results.append(r)

    # V3: Few-shot
    r = run_extraction_test(client, "v3_few_shot", extract_v3_few_shot)
    all_results.append(r)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n{'Strategy':<20} {'Parse Rate':>12} {'Valid Rate':>12}")
    print("─" * 46)
    for r in all_results:
        print(f"{r['name']:<20} {r['parse_rate']:>11.0%} {r['valid_rate']:>12.0%}")

    # Bonus
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
