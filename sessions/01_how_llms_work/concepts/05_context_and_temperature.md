# 05 — Context Window & Temperature: The Two Most Important Knobs

> **TL;DR:** The context window is the model's working memory — everything it can "see" in one call.
> Temperature controls how deterministic vs creative the output is. These two parameters drive most
> practical LLM behavior in production systems.

---

## Part 1: The Context Window

### DevOps Analogy

The context window is **RAM, not disk**.

Everything the model "knows" for this API call must fit in RAM. Your system prompt, all previous turns of conversation, retrieved documents, tool call results, the current user message, and the response being generated — all of it shares the same fixed-size buffer.

When you exceed the context window, there's no graceful degradation. The request fails or the oldest content is silently dropped, like an out-of-memory kill. Unlike a swap file that slows things down, there's no overflow mechanism.

```
Total context used = system_prompt
                   + conversation_history (grows each turn)
                   + retrieved_documents (RAG)
                   + tool_results
                   + current_user_message
                   + response_being_generated
                   ─────────────────────────────
                   Must be < context_window_size
```

### Current Context Windows

| Model | Context Window | Rough Text Equivalent |
|-------|---------------|-----------------------|
| GPT-3.5 Turbo | 16K tokens | ~50 pages |
| GPT-4o | 128K tokens | ~400 pages |
| Claude 3.5 Sonnet | 200K tokens | ~600 pages |
| Claude 3 Opus | 200K tokens | ~600 pages |
| Gemini 1.5 Pro | 1M tokens | ~3,000 pages |

These numbers sound large. They're not unlimited.

**A real scenario:** Building a log analysis tool. An application generating 1,000 log lines/minute produces ~50,000 lines/hour. At ~15 tokens per log line, that's 750,000 tokens — 3.75× Claude's context window for a single hour of logs. You must sample, filter, or summarize before sending to the model.

### The Model Is Stateless

This is the most important thing to internalize: **the model has no memory between API calls**.

Each call starts fresh. The "conversation history" is just the `messages` array you include in the request payload — it's your application's responsibility to maintain and manage it.

This is identical to **stateless microservices**. Each request must include all the context it needs. The state lives in your application layer, not in the model. Think of it like HTTP: the server (model) doesn't remember previous requests; the client (your app) must include all necessary state in each request.

Implications:
- Building a chatbot? You must store and re-send conversation history on each turn.
- Building an agent? Tool results must be included in the next model call.
- Long conversations get expensive — and eventually overflow the context window.

### The KV Cache

When you send the same system prompt repeatedly (common in production), the model doesn't recompute it from scratch every time. Most inference systems maintain a **KV cache** — they store the intermediate "key-value" attention computations for the prompt portion.

Think of it like **prepared statement caching** in a database. The first call computes everything. Subsequent calls with the same prefix reuse the cached computation, reducing latency and sometimes cost.

Anthropic and OpenAI both offer prompt caching features that reduce costs when reusing long system prompts.

---

## Part 2: Temperature

### What It Does

After computing the probability distribution over all tokens in the vocabulary for the next position, the model needs to pick one. **Temperature** reshapes that distribution before sampling:

```
Low temperature (0.0–0.3):   Sharpen the distribution → always pick the most likely token
Medium temperature (0.4–0.7): Leave it mostly as-is → likely tokens, some variety
High temperature (0.8–1.0):  Flatten the distribution → less likely tokens get a chance
Very high (>1.0):             Over-flatten → frequently incoherent
```

### DevOps Analogy

Temperature is the **chaos level** in your system.

- `temperature=0` is like `terraform plan` with `--lock` — fully deterministic. Same input, identical output every time. Use this when you need reproducible, verifiable results.
- `temperature=0.7` is like load testing with moderate jitter — controlled variation. Good for exploring the solution space.
- `temperature=1.0` is like chaos engineering — high variance, useful for stress testing or brainstorming, not for critical infrastructure decisions.
- `temperature=1.5` is `CHAOS_LEVEL=MAX` — technically possible, almost always wrong.

### Practical Temperature Guide

| Use Case | Recommended Temperature | Why |
|----------|------------------------|-----|
| Generate Kubernetes YAML | `0.0` | You want exact, valid syntax every time |
| Extract structured data from logs | `0.0` | Deterministic parsing |
| Terraform / IaC generation | `0.0` | Infrastructure code must be reproducible |
| Q&A with factual answers | `0.1–0.3` | Mostly deterministic, slight variation acceptable |
| Summarizing a runbook | `0.3–0.5` | Some variation is fine |
| Incident post-mortem narrative | `0.5–0.7` | Human-readable prose, light creativity |
| Brainstorming architecture options | `0.7–1.0` | Exploring diverse possibilities |

**Rule for DevOps use cases:** If the output goes into a pipeline, a file, or a config — use `temperature=0`. If you're generating human-readable text for review — use `0.3–0.7`.

### Temperature ≠ Model Quality

A common misconception: higher temperature doesn't mean "smarter" responses. Temperature controls *variance*, not quality. At `temperature=0`, you get the model's single most-likely response. At `temperature=1.0`, you're sampling from the full distribution — sometimes revealing creative options, sometimes producing nonsense.

For most structured tasks (code generation, JSON extraction, YAML), the most-likely token is the correct token. `temperature=0` is the right choice.

### Related Parameters

**`max_tokens`** — Hard cap on response length. Always set this. Without it, you can receive (and pay for) unexpectedly long responses.

```python
# Tight: for structured outputs
max_tokens=256

# Generous: for analysis or explanations  
max_tokens=2048
```

**`top_p` (nucleus sampling)** — An alternative to temperature. Only sample from tokens that together account for `top_p` probability mass. `top_p=0.9` means "only consider the tokens that cover 90% of the probability." In practice, just use temperature — `top_p` adds complexity without significant benefit for most use cases.

---

## Putting It Together: Production Configuration

```python
import anthropic

client = anthropic.Anthropic()

# Infrastructure task: generate K8s YAML
# → deterministic, short, structured
infra_response = client.messages.create(
    model="claude-haiku-4-5-20251001",   # Fast, cheap for structured generation
    max_tokens=1024,
    temperature=0.0,                      # Deterministic
    system="You are an expert in Kubernetes. Output only valid YAML, no explanation.",
    messages=[{"role": "user", "content": "Write a Deployment for nginx:1.24 with 3 replicas"}]
)

# Exploratory task: brainstorm architecture approaches
# → creative, longer, prose
arch_response = client.messages.create(
    model="claude-sonnet-4-6",           # More capable for complex reasoning
    max_tokens=2048,
    temperature=0.7,                      # Some creative variation
    system="You are a senior platform engineer. Explore multiple options.",
    messages=[{"role": "user", "content": "What are 3 different approaches to handle multi-region failover?"}]
)
```

---

## Key Takeaways

1. **Context window = RAM.** Manage it explicitly — system prompt + history + docs + response must all fit. You are responsible for trimming.
2. **Temperature = chaos level.** Use `0` for anything deterministic (code, structured data, pipelines). Use `0.3–0.7` for prose. Higher only for brainstorming.
3. **The model is stateless.** Every API call is a fresh start. State management is your application's job.

---

## Hands-On

→ [Lab 03: Context Window](../labs/lab03_context_window/lab.py)  
→ [Demo: Temperature Effects](../demos/demo_temperature_effect.py)
