#!/usr/bin/env python3
"""
Demo: JSON Extraction — Reliable Structured Output from LLMs
=============================================================
This demo shows the complete production pipeline for extracting structured
JSON from LLM output: prompt engineering + robust parsing + schema validation.

We process 10 messy log lines and extract structured fields, aiming for
100% parse rate and valid schema on every response.

Requires: ANTHROPIC_API_KEY in .env

Usage:
    python demo_json_extraction.py
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


MODEL = "claude-haiku-4-5-20251001"

# ── Sample log lines (varied formats, as you'd see in real infrastructure) ──
LOG_LINES = [
    # Standard structured-ish
    "2024-10-15 14:23:01.123 ERROR [auth-service] [req-id:abc-123] DB connection pool exhausted: 20/20 used",
    # Python traceback style
    "ERROR:root:Failed to connect to Redis: ConnectionRefusedError: [Errno 111] Connection refused",
    # Nginx access log
    '192.168.1.45 - - [15/Oct/2024:14:23:05 +0000] "POST /api/v1/checkout" 503 0 "-" "Go-http-client/2.0"',
    # K8s event
    "Warning  BackOff  2m    kubelet  Back-off restarting failed container api-server in pod api-server-7d9f2-xkj2m",
    # AWS CloudWatch style
    "[ERROR] 2024-10-15T14:23:10Z lambda-payment-processor RequestId: e1b3c921 Process exited before completing request",
    # Prometheus alert
    "ALERT PaymentServiceDown: value=1 labels={service='payment',env='prod',severity='critical'} for 5m",
    # Terraform error
    "Error: Error creating IAM role: EntityAlreadyExists: Role with name ProductionEKSRole already exists.",
    # Go application log
    `{"level":"error","ts":1697379800,"caller":"db/pool.go:142","msg":"query timeout","duration_ms":5023,"query":"SELECT * FROM orders"}`,
    # systemd journal
    "Oct 15 14:23:20 worker-node-3 kubelet[1234]: E1015 14:23:20.123456 1234 pod_workers.go:190] Error syncing pod: failed to mount secret",
    # Datadog APM trace error
    "service:checkout env:production version:2.1.0 error:true http.status_code:500 http.url:/api/checkout duration:4523ms",
]

# Expected schema for extracted fields
REQUIRED_FIELDS = ["timestamp", "level", "service", "message", "error_type"]


def get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or len(key) < 20:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


# ── Robust JSON extraction ─────────────────────────────────────────────────────

def extract_json(text: str) -> dict | None:
    """Three-layer robust JSON extraction."""
    # Layer 1: direct
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
    # Layer 3: find first {...} block
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def validate(data: dict) -> tuple[bool, list[str]]:
    """Validate extracted fields."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing '{field}'")
    valid_levels = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL", None}
    if "level" in data and data["level"] not in valid_levels:
        errors.append(f"invalid level: {data['level']!r}")
    return len(errors) == 0, errors


# ── LLM extraction pipeline ────────────────────────────────────────────────────

SYSTEM = """\
You are a log line parser. Extract structured fields from any log format.

Output ONLY a JSON object. No text before or after. No markdown. No code fences.

Schema (use null for missing fields):
{
  "timestamp": "ISO 8601 format or null",
  "level": "DEBUG|INFO|WARN|ERROR|CRITICAL|FATAL|null",
  "service": "service or component name or null",
  "message": "the core error/event message (concise)",
  "error_type": "error class/type/category or null",
  "request_id": "request/trace ID if present or null",
  "duration_ms": number or null
}

Handle ALL log formats: structured JSON, nginx access logs, systemd, Python
tracebacks, AWS CloudWatch, Kubernetes events, Terraform errors, etc."""

# Anchor with one representative few-shot example
FEW_SHOT = [
    {
        "role": "user",
        "content": '2024-01-20 09:12:33 CRITICAL [payment-svc] [req-id:xyz-789] Stripe API timeout after 30000ms: connection refused',
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "timestamp": "2024-01-20T09:12:33",
            "level": "CRITICAL",
            "service": "payment-svc",
            "message": "Stripe API timeout: connection refused",
            "error_type": "network_timeout",
            "request_id": "xyz-789",
            "duration_ms": 30000,
        }),
    },
]


def extract_log(client: anthropic.Anthropic, log_line: str) -> tuple[dict | None, str, float]:
    """Extract fields from a log line. Returns (parsed, raw, latency_ms)."""
    start = time.time()
    response = client.messages.create(
        model=MODEL, max_tokens=300, temperature=0.0,
        system=SYSTEM,
        messages=FEW_SHOT + [{"role": "user", "content": log_line}],
    )
    latency_ms = (time.time() - start) * 1000
    raw = response.content[0].text
    parsed = extract_json(raw)
    return parsed, raw, latency_ms


def main() -> None:
    print("\n" + "═" * 70)
    print("  Demo: JSON Extraction Pipeline")
    print(f"  Processing {len(LOG_LINES)} log lines from varied formats")
    print("═" * 70)

    client = get_client()
    parse_count = 0
    valid_count = 0
    total_latency = 0.0

    for i, log_line in enumerate(LOG_LINES, 1):
        print(f"\n[{i:02d}] Input:")
        print(f"  {log_line[:100]}{'...' if len(log_line) > 100 else ''}")

        parsed, raw, latency_ms = extract_log(client, log_line)
        total_latency += latency_ms

        if parsed:
            parse_count += 1
            valid, errors = validate(parsed)
            if valid:
                valid_count += 1
                status = "✓ VALID"
            else:
                status = f"⚠ INVALID ({', '.join(errors)})"
        else:
            valid = False
            status = "✗ PARSE FAILED"

        print(f"  Status: {status}  ({latency_ms:.0f}ms)")

        if parsed:
            # Show key fields compactly
            fields = {
                k: v for k, v in parsed.items()
                if v is not None and k in ["timestamp", "level", "service", "message", "error_type"]
            }
            for k, v in fields.items():
                val_str = str(v)[:60] + ("..." if len(str(v)) > 60 else "")
                print(f"  {k}: {val_str}")

    # Summary
    total = len(LOG_LINES)
    print(f"\n\n{'═' * 70}")
    print(f"  Results")
    print(f"{'═' * 70}")
    print(f"  Parsed:  {parse_count}/{total} ({parse_count/total:.0%})")
    print(f"  Valid:   {valid_count}/{total} ({valid_count/total:.0%})")
    print(f"  Avg latency: {total_latency/total:.0f}ms per log line")

    cost_per_line = (150 / 1_000_000) * 0.25 + (80 / 1_000_000) * 1.25
    print(f"  Est. cost: ~${cost_per_line:.5f}/line → ${cost_per_line * 1000:.3f}/1K lines")

    print(f"""
  Production pattern:
  1. System prompt with explicit schema + null handling
  2. One few-shot example anchors the exact output format
  3. Three-layer JSON extractor handles all model output variations
  4. Schema validation catches missing/invalid fields before downstream use
  5. Fallback to null for unrecognized log formats (don't fabricate)
""")


if __name__ == "__main__":
    main()
