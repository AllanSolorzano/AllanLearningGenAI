# 04 — Structured Output: Getting Parseable Data Every Time

> **TL;DR:** LLMs produce natural language by default. Production tools need JSON.
> Getting reliable, parseable output requires explicit format specification, schema anchoring,
> and defensive parsing. Get this right and your LLM becomes a reliable data extraction engine.

---

## DevOps Analogy

Getting structured output from an LLM is like configuring **structured logging**.

By default, your app logs `"Error connecting to database at 14:23"` — human-readable, machine-unfriendly. With structured logging, it emits:
```json
{"level": "ERROR", "timestamp": "14:23:01Z", "component": "db", "message": "connection failed", "host": "postgres-primary"}
```

Same information. The second format is directly ingestible by Loki, Datadog, or Splunk without parsing magic.

The same principle applies to LLM output. Your application shouldn't have to parse prose — it should receive clean JSON that maps directly to your data model.

---

## The Problem: Models Are Talkative

Ask a model for JSON and it will often give you:

```
Here's the analysis you requested:

```json
{
  "severity": "P1",
  "cause": "connection pool exhausted"
}
```

Hope this helps! Let me know if you need anything else.
```

Three problems in one response:
1. Prose before the JSON
2. JSON wrapped in a code fence
3. Prose after the JSON

Your `json.loads()` call fails on all three.

---

## The Solution: Defense in Depth

Use all four layers:

### Layer 1: System Prompt Specification

Be explicit and repeated:

```
Output ONLY valid JSON. No text before or after. No markdown code fences.
No explanation. Just the JSON object.

Schema:
{
  "severity": "P1" | "P2" | "P3",
  "category": string,
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "recommended_action": string
}
```

### Layer 2: Few-Shot Examples (the strongest signal)

Show the model what good output looks like. The model learns format from examples more reliably than from instructions:

```python
messages = [
    {"role": "user", "content": "Alert: payment-service 503 error rate 100%"},
    {"role": "assistant", "content": '{"severity":"P1","category":"service_outage","confidence":"HIGH","recommended_action":"kubectl get pods -n payments"}'},
    {"role": "user", "content": actual_alert},
]
```

Note: no spaces after colons, no trailing comma — show exactly the format you want.

### Layer 3: Defensive Parsing

Even with layers 1 and 2, edge cases happen. Wrap your parse in a robust extractor:

```python
import json
import re

def extract_json(text: str) -> dict | None:
    """Extract JSON from LLM output robustly.
    
    Handles: code fences, leading/trailing prose, nested objects.
    """
    # Try direct parse first (ideal case)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Extract first {...} block from text
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None  # All attempts failed


def parse_or_fallback(text: str, fallback: dict) -> dict:
    result = extract_json(text)
    return result if result is not None else fallback
```

### Layer 4: Schema Validation

Parsing doesn't guarantee the model included all required fields with the right types. Validate:

```python
def validate_alert_response(data: dict) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    required = {"severity", "category", "confidence", "recommended_action"}
    missing = required - set(data.keys())
    if missing:
        return False, f"Missing fields: {missing}"
    
    if data["severity"] not in {"P1", "P2", "P3"}:
        return False, f"Invalid severity: {data['severity']}"
    
    if data["confidence"] not in {"HIGH", "MEDIUM", "LOW"}:
        return False, f"Invalid confidence: {data['confidence']}"
    
    return True, ""
```

---

## XML Tags: An Alternative to JSON

For extracting a single field or when JSON nesting causes problems, XML-style tags are often more reliable:

```python
system = """
Analyze the alert and respond in this format:

<severity>P1|P2|P3</severity>
<category>one of: service_outage, latency, resource_pressure, configuration, security</category>
<action>the single most important first action to take</action>
"""

# Parse:
def extract_tag(text: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else None

severity = extract_tag(response, "severity")
action = extract_tag(response, "action")
```

XML tags are more forgiving than JSON — the model can't accidentally break the structure by omitting a comma. Use JSON when you have complex nested structures; use XML tags for flat key-value extraction.

---

## Handling Schema Drift

As your application evolves, your schema changes. The model learned from your old examples. Version your prompts:

```python
PROMPT_VERSION = "v2.3"

SYSTEM_PROMPT = f"""
[PROMPT VERSION: {PROMPT_VERSION}]
You are an alert classifier. Output JSON matching schema v2.3:
{{
  "severity": "P1"|"P2"|"P3",
  "category": string,
  "runbook_id": string|null,   # NEW in v2.3
  "confidence": "HIGH"|"MEDIUM"|"LOW"
}}
"""
```

Log `PROMPT_VERSION` alongside every API call. When you update the prompt, you can trace which version produced which outputs. This is the foundation of prompt CI/CD (Session 05).

---

## Common Patterns for DevOps Tools

| Tool | Input | Output Schema |
|------|-------|---------------|
| Alert classifier | Alert text | `{severity, category, runbook_id}` |
| Log parser | Raw log line | `{timestamp, level, service, message, trace_id}` |
| Config reviewer | YAML/HCL | `[{finding, severity, line, fix}]` |
| Post-mortem generator | Incident timeline | `{title, timeline, root_cause, action_items[]}` |
| Cost explainer | AWS Cost Explorer CSV | `{top_services[], anomalies[], recommendations[]}` |

---

## Key Takeaways

1. **Specify schema in the system prompt AND in few-shot examples** — belt and suspenders.
2. **Always write a defensive JSON extractor** — assume the model will sometimes wrap output in prose.
3. **Validate schema after parsing** — a valid JSON object with wrong types is still a parsing failure for your code.

---

## Hands-On

→ [Lab 02: Structured Output](../labs/lab02_structured_output/lab.py)  
→ [Demo: JSON Extraction](../demos/demo_json_extraction.py)
