# 01 — System Prompts: Setting the Stage

> **TL;DR:** The system prompt is your contract with the model. It defines persona, constraints,
> output format, and tone — before the user ever speaks. Get this right and every response is
> predictably useful. Get it wrong and you're debugging at runtime.

---

## DevOps Analogy

A system prompt is like a **container entrypoint + environment variables**.

The entrypoint defines what the process *is* — an nginx server, a Python API, a worker job.
The environment variables configure its behavior — log level, port, upstream URL.

You don't re-configure these per-request. You set them once at startup and every request inherits the context.

```dockerfile
# Container: what it is + how it behaves
ENTRYPOINT ["nginx"]
ENV LOG_LEVEL=info
ENV MAX_CONNECTIONS=1000
ENV UPSTREAM=http://api:8080
```

```
# System prompt: what the model is + how it behaves
"You are an SRE assistant that analyzes Kubernetes alerts.
Always respond in JSON. Never guess — say unknown if unsure.
Limit responses to 300 tokens."
```

A request that arrives at nginx doesn't need to say "please use log level info." It's already configured. Same with a well-written system prompt — the user message only needs to carry the actual input.

---

## Anatomy of a Good System Prompt

A solid system prompt answers four questions:

### 1. Who are you?
Define the persona. This isn't just branding — it shapes the model's knowledge emphasis, vocabulary, and default assumptions.

```
# Vague (bad):
"You are a helpful assistant."

# Specific (good):
"You are a senior Site Reliability Engineer specializing in Kubernetes and AWS.
You have experience with high-traffic production systems."
```

### 2. What do you do?
State the task explicitly. Don't assume the model will infer it from context.

```
# Implicit (fragile):
"Help with infrastructure."

# Explicit (reliable):
"Your job is to analyze incident alerts and classify them by severity (P1/P2/P3),
identify the likely root cause category, and suggest the first diagnostic step."
```

### 3. How should you format output?
If the output goes into a pipeline, parsing it must be deterministic. Specify format exactly.

```
# No format spec (unpredictable):
"Respond with the analysis."

# With format spec (parseable):
"Respond ONLY with a JSON object in this exact format:
{
  \"severity\": \"P1\" | \"P2\" | \"P3\",
  \"category\": string,
  \"first_action\": string
}
No markdown, no explanation, no code blocks."
```

### 4. What are the guardrails?
Specify what the model should *not* do. Constraints prevent the most common failure modes.

```
"If the alert text is ambiguous, use severity 'P3' as a safe default.
Never fabricate specific resource names, IPs, or pod names not in the input.
If you cannot determine the category, use category 'unknown'."
```

---

## System Prompt Patterns for DevOps Tools

### Pattern 1: The Structured Extractor
For any tool that needs to parse unstructured text into structured data:

```
You are a log analysis tool. Extract structured fields from log lines.

Rules:
- Output ONLY valid JSON, nothing else
- Use null for fields not present in the input
- timestamp must be ISO 8601 format
- severity must be one of: DEBUG, INFO, WARN, ERROR, CRITICAL
- If the log line is not parseable, return {"error": "unparseable"}

Schema:
{"timestamp": string|null, "severity": string, "service": string|null, "message": string}
```

### Pattern 2: The Opinionated Advisor
For interactive tools where users ask open-ended questions:

```
You are a senior platform engineer reviewing infrastructure configurations.

When reviewing, you:
1. Lead with the most critical finding (security or data loss risk first)
2. Use numbered lists for multiple findings
3. Include the exact kubectl or AWS CLI command to verify each finding
4. Rate severity: CRITICAL / HIGH / MEDIUM / LOW
5. Keep responses under 400 words

You do NOT:
- Suggest changes outside the scope of what was provided
- Make assumptions about services or environments not mentioned
- Use hedging language ("maybe", "perhaps", "you might want to")
```

### Pattern 3: The Strict Code Generator
For any tool generating infrastructure code:

```
You are a Kubernetes YAML generator.

Output rules:
- Output ONLY valid YAML. No explanation before or after.
- Include apiVersion, kind, metadata, and spec for every resource
- Always set resource requests AND limits
- Always include a namespace field
- Use the label set: app, version, managed-by: generated

If the request is ambiguous, add a comment in the YAML starting with "# ASSUMPTION:"
```

---

## Common Mistakes

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| "Be helpful and concise" | "Concise" means different things to different models | Set a token/word limit |
| "Output JSON" | Model wraps it in ```json``` code fences | Add "No markdown, no code blocks" |
| No error handling spec | Model invents answers when unsure | "If unsure, return {error: ...}" |
| Stacking multiple tasks | Model prioritizes inconsistently | One system prompt per use case |
| Too long (>500 tokens) | Model anchors on early instructions, ignores later ones | Front-load the critical constraints |

---

## Testing Your System Prompt

A system prompt is code. Test it like code.

```
Inputs to test:
  1. Happy path — clean, well-formed input
  2. Ambiguous input — could be interpreted multiple ways
  3. Missing fields — key information absent
  4. Adversarial input — user tries to override your instructions
  5. Edge cases — empty input, very long input, non-English
```

Lab 04 in this session builds a test harness that runs your prompt against a set of inputs and measures the pass rate automatically.

---

## Key Takeaways

1. **System prompts are configuration, not conversation.** Write them once, version them, test them.
2. **Specify format explicitly.** "JSON" is not enough — show the exact schema and say "nothing else."
3. **Define failure behavior.** What should the model return when it can't answer? Specify it, or you'll get hallucinations.

---

## Hands-On

→ [Lab 01: Zero-shot vs Few-shot](../labs/lab01_zero_vs_few_shot/lab.py)
