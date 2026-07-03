# 03 — Chain of Thought: Making the Model Reason

> **TL;DR:** Chain-of-thought (CoT) tells the model to reason step-by-step before answering.
> For multi-step problems — incident diagnosis, root cause analysis, architecture trade-offs —
> CoT dramatically improves accuracy and produces auditable reasoning you can review.

---

## DevOps Analogy

Chain-of-thought is like **writing a post-mortem before giving the action items**.

A junior engineer asked "what caused the outage?" might immediately say "the database." A senior engineer runs through the timeline: "Traffic spiked at 14:23. Auth service latency increased 30 seconds later. Connection pool errors appeared at 14:24. Database CPU maxed at 14:25. So the root cause was the traffic spike causing connection pool exhaustion — the database was a symptom."

Same underlying knowledge. The difference is *structured reasoning before the answer*.

Without CoT, the model jumps to the first plausible answer — like `grep`ing for the first match and stopping. With CoT, it reasons through the evidence systematically before committing.

```
# Without CoT: fast, potentially wrong
"What's wrong?"
→ "The database is down."

# With CoT: slower, systematically correct
"Think step-by-step: what evidence do we have, what does it imply,
what are alternative explanations, what's the most likely root cause?"
→ "Step 1: The auth service started failing before the database errors appeared.
   Step 2: Connection pool exhaustion was logged 90 seconds into the incident.
   Step 3: The traffic spike preceded both by 30 seconds.
   Conclusion: Traffic spike → connection pool exhaustion → cascading auth failure.
   The database is a victim, not the cause."
```

---

## When CoT Helps (and When It Doesn't)

### CoT helps for:
- **Multi-step reasoning**: root cause analysis with multiple contributing factors
- **Trade-off evaluation**: "should we scale vertically or horizontally?" — needs to weigh constraints
- **Debugging**: interpreting ambiguous error messages in context
- **Planning**: generating a migration plan that accounts for dependencies
- **Math and counting**: any task that requires sequential computation

### CoT doesn't help (and wastes tokens) for:
- **Simple lookup**: "What does `kubectl rollout undo` do?"
- **Structured extraction**: parsing a log line into JSON — just do it
- **Short classification**: P1/P2/P3 with clear criteria and good few-shot examples
- **Creative tasks**: reasoning constrains creativity

---

## How to Prompt for CoT

### Method 1: The Magic Phrase (simplest)
Adding "Let's think step by step" or "Think through this carefully" triggers CoT:

```python
"Analyze this incident timeline and determine root cause.
Think step by step before giving your conclusion."
```

### Method 2: Structured Reasoning Template
More reliable for consistent output:

```python
"Analyze this incident. Follow this reasoning structure:

OBSERVATIONS: List the key facts from the data provided
TIMELINE: Order events chronologically
HYPOTHESES: List 2-3 possible root causes
EVIDENCE FOR/AGAINST: Evaluate each hypothesis
CONCLUSION: State the most likely root cause and confidence level
NEXT ACTION: The single most important diagnostic step"
```

### Method 3: Few-Shot CoT
Show the model an example of good reasoning, then ask it to reason the same way:

```python
# Example:
User: [incident data]
Assistant:
OBSERVATIONS: Auth service latency spike at 14:23. Connection pool errors at 14:24.
TIMELINE: Traffic spike (14:22) → auth latency (14:23) → pool exhaustion (14:24)
HYPOTHESES: (1) Traffic spike overwhelmed pool, (2) slow query held connections
EVIDENCE: Traffic spike precedes all symptoms. Query times normal before 14:22.
CONCLUSION: Traffic spike caused pool exhaustion. Confidence: HIGH
NEXT ACTION: kubectl get hpa -n auth — check if autoscaling was configured

# Actual query:
User: [your incident data]
```

Few-shot CoT is the most reliable approach for production tools.

---

## Scratchpad Pattern: Reasoning + Structured Output

A common production pattern: let the model reason freely, then output a structured result at the end.

```python
system_prompt = """
You are an incident analyzer. When given incident data:

1. First, reason through the problem in a <reasoning> section
2. Then output your conclusion as JSON in an <output> section

Format:
<reasoning>
[your step-by-step analysis here]
</reasoning>
<output>
{"root_cause": string, "confidence": "HIGH"|"MEDIUM"|"LOW", "next_action": string}
</output>
"""
```

Your application then parses only the `<output>` block. The `<reasoning>` block is visible in logs for debugging but doesn't pollute the downstream data pipeline.

```python
import re

def extract_output(response: str) -> str:
    match = re.search(r"<output>(.*?)</output>", response, re.DOTALL)
    return match.group(1).strip() if match else response
```

---

## CoT for Infrastructure Decisions

CoT is especially valuable for architecture and capacity decisions where trade-offs matter:

```
Prompt: "We need to decide between vertical scaling (bigger nodes) vs horizontal scaling
(more nodes) for our stateful auth service. Current state: 3 nodes, 16GB RAM each,
running at 70% memory utilization. Traffic is growing 20% per quarter."

Without CoT: "Use horizontal scaling for better reliability."

With CoT:
CONSTRAINTS: Stateful service — horizontal scaling requires session sharing or sticky routing
VERTICAL PATH: Upgrade to 32GB nodes. 2x capacity. ~$800/month more. Simple.
  Risk: Single node failures more impactful. Vertical scaling has an upper bound.
HORIZONTAL PATH: Add more 16GB nodes. Requires Redis session store (new dependency).
  Benefit: Fault tolerance, linear scalability. Takes 2 weeks to implement properly.
TRAFFIC PROJECTION: 20% quarterly growth → need 2× capacity in ~4 quarters
RECOMMENDATION: Short-term: vertical scale now (immediate, low risk).
  Plan: Implement Redis sessions in next sprint for horizontal scaling readiness.
```

The reasoning is auditable, challengeable, and much more useful than a one-line answer.

---

## Token Cost of CoT

CoT uses more tokens — the reasoning steps are real output. Estimate:

| Task | Without CoT | With CoT | Extra cost |
|------|-------------|----------|------------|
| Alert classification | ~50 tokens | ~200 tokens | 4× output cost |
| Incident root cause | ~150 tokens | ~600 tokens | 4× output cost |
| Architecture decision | ~200 tokens | ~1000 tokens | 5× output cost |

For production pipelines processing thousands of events: use CoT selectively (P1/P2 incidents only) or use structured CoT where reasoning is bounded.

---

## Key Takeaways

1. **CoT forces step-by-step reasoning** — prevents the model from jumping to the first plausible answer.
2. **Use structured templates** for consistent, auditable output in production tools.
3. **Scratchpad pattern** (reasoning block + output block) gives you the best of both worlds: rich reasoning in logs, clean data in your pipeline.

---

## Hands-On

→ [Lab 03: Chain of Thought](../labs/lab03_chain_of_thought/lab.py)  
→ [Demo: CoT Debugging](../demos/demo_cot_debugging.py)
