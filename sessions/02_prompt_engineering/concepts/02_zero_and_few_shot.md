# 02 — Zero-Shot & Few-Shot Prompting

> **TL;DR:** Zero-shot asks the model to perform a task with no examples.
> Few-shot gives 2–5 examples directly in the prompt to demonstrate the exact behavior you want.
> Few-shot is the cheapest, fastest way to dramatically improve output quality.

---

## DevOps Analogy

**Zero-shot** is like deploying a new service with only documentation — no runbooks, no examples, no prior incidents. It usually works for standard cases. Edge cases are unpredictable.

**Few-shot** is like giving a new team member your runbook *and* 3 annotated examples of past incidents. Same underlying knowledge, but the examples anchor their judgment to your team's specific standards.

```
# Zero-shot: here's the task, figure it out
"Classify this alert by severity."

# Few-shot: here's the task + here's exactly how we classify in this org
User:  "CPU usage 94%, threshold 80%"
Bot:   {"severity": "P2", "reason": "Degraded but not down"}

User:  "Payment service returning 100% 500s"
Bot:   {"severity": "P1", "reason": "Complete service failure"}

User:  "Disk usage 72%, threshold 85%"
Bot:   {"severity": "P3", "reason": "Warning, not yet critical"}

User:  [your actual alert]
Bot:   ???
```

The examples don't teach the model new knowledge — they *calibrate* it to your team's definitions of P1/P2/P3, which may differ from the model's defaults.

---

## When to Use Each

| Situation | Approach | Why |
|-----------|----------|-----|
| Standard, well-defined task | Zero-shot | Examples are unnecessary overhead |
| Org-specific classification | Few-shot | Your P1/P2 != the model's defaults |
| Specific output format | Few-shot | Show exactly what good looks like |
| Nuanced judgment | Few-shot | Ambiguous cases need anchoring |
| Creative / open-ended | Zero-shot | Examples constrain creativity |

**Rule of thumb for DevOps tools:** if the output needs to be consistent across your team and fed into a pipeline, use few-shot. If you're exploring or the task is standard, zero-shot is fine.

---

## Writing Good Few-Shot Examples

### Principle 1: Cover the decision boundary

Don't give 3 examples that are all clearly P1. Cover the edge cases — the borderline P1/P2, the "looks bad but is P3" case.

```
# Bad examples (all obvious)
"Payment service down" → P1
"All pods crashed" → P1
"Database unreachable" → P1

# Good examples (cover the spectrum)
"Payment service down" → P1          ← clear P1
"CPU at 87%, threshold 80%" → P2     ← elevated but not down
"Disk at 72%, threshold 85%" → P3    ← warning only
"Single pod OOMKilled, 2/3 healthy" → P2  ← degraded, not failed
```

### Principle 2: Match the format you want

The model learns format from examples, not just content. If you want JSON output, your examples must output JSON — not prose.

```
# Examples that produce JSON reliably
User: "Alert: auth-service latency p99=847ms, threshold=500ms"
Assistant: {"severity": "P2", "category": "latency", "action": "Check auth-service pod CPU and downstream dependencies"}

User: "Alert: node-1 NotReady, 12 pods evicted"
Assistant: {"severity": "P1", "category": "node_failure", "action": "SSH to node-1, check kubelet: systemctl status kubelet"}
```

### Principle 3: 3–5 examples is the sweet spot

- 1 example: better than zero-shot, not reliable on edge cases
- 3–5 examples: covers the key cases, manageable token cost
- 10+ examples: diminishing returns, high token cost, may confuse the model

### Principle 4: Use real data from your environment

Generic examples produce generic output. Use real alert texts, real log formats, real command outputs from your actual systems.

---

## How Few-Shot Works Mechanically

Few-shot examples go in the `messages` array as prior conversation turns:

```python
messages = [
    # Example 1
    {"role": "user",      "content": "Alert: payment-service error rate 100%"},
    {"role": "assistant", "content": '{"severity": "P1", "category": "service_down", "action": "Check pods: kubectl get pods -n payments"}'},
    # Example 2
    {"role": "user",      "content": "Alert: CPU 87% on worker-3, threshold 80%"},
    {"role": "assistant", "content": '{"severity": "P2", "category": "resource_pressure", "action": "Check top consumers: kubectl top pods --all-namespaces | sort -k3 -rn"}'},
    # Actual query
    {"role": "user",      "content": f"Alert: {actual_alert}"},
]
```

The model sees the pattern in the prior turns and continues it. The examples function as in-context demonstrations — no training or fine-tuning required.

---

## The Token Cost Trade-off

Few-shot examples consume tokens on every request. Calculate the cost:

```
3 examples × ~60 tokens each = 180 tokens overhead per call
At $3/1M input tokens (Claude Sonnet): $0.00054 per call
At 1000 calls/day: $0.54/day = $16/month overhead for 3 examples
```

For most production tools, this is negligible. But for high-volume pipelines (100K+ calls/day), consider whether fine-tuning is more economical.

---

## Key Takeaways

1. **Few-shot calibrates the model to your standards**, not just teaches it the task.
2. **Cover the decision boundary** — edge cases and borderline inputs are where examples earn their token cost.
3. **Match format in examples** — if you want JSON out, show JSON out in every example.

---

## Hands-On

→ [Lab 01: Zero-shot vs Few-shot](../labs/lab01_zero_vs_few_shot/lab.py)
