# 01 — Tokens: How LLMs See Text

> **TL;DR:** LLMs don't see words — they see *tokens*. A token is roughly a word-chunk.
> Token count determines cost, speed, and how much fits in the model's "memory."

---

## DevOps Analogy

Think of tokenization like how a **YAML parser** processes a config file.

The parser doesn't read your config as a wall of text — it breaks it into meaningful units:
keys, values, colons, indentation levels, brackets. Each unit is handled discretely.

LLMs do the same thing to your prompt. The tokenizer breaks `"kubectl get pods --namespace production"` into subword pieces before the model ever processes it.

A second analogy: **MTU (Maximum Transmission Unit)** in networking. Just as Ethernet can't send arbitrary-length frames and must split data into ≤1500-byte chunks, the LLM can't process raw Unicode characters directly — it must first chunk text into fixed-vocabulary units.

---

## What Is a Token?

A token is a chunk of text that the model treats as a single unit. It can be:

- A whole word: `"Kubernetes"` → 1 token
- Part of a word: `"unbelievable"` → 3 tokens: `["un", "believ", "able"]`
- A word with a space: `" production"` (with leading space) → 1 token
- Punctuation: `","` → 1 token
- Whitespace: `"\n"` → 1 token

```
Input:   "kubectl get pods --namespace production"
Tokens:  ["kube", "ctl", " get", " pods", " --", "names", "pace", " production"]
IDs:     [74794,  82,    636,   54947,  779,  6115,  1330,  5788]
```

Notice: `"kubectl"` splits into two tokens (`"kube"` + `"ctl"`). `" production"` (with the leading space) is a single token. This is not intuitive — and it matters when you're counting tokens for cost estimation.

---

## How Tokenization Works: BPE

The most common algorithm is **Byte Pair Encoding (BPE)**:

1. Start with individual characters as the vocabulary
2. Find the most frequently co-occurring pair of characters: merge them into a new token
3. Repeat until the vocabulary reaches the target size (~50K–100K tokens)

The result is a vocabulary where common words are single tokens, rare words are split into subword pieces, and the model can handle any text (even made-up words) by composing subword tokens.

GPT-4 and similar models use a tokenizer called `cl100k_base` with ~100,000 tokens in its vocabulary. The `tiktoken` library (used in Lab 01) implements this tokenizer.

---

## Why This Matters

### 1. Cost is measured in tokens

Every API call is billed by input tokens + output tokens. A dense Kubernetes manifest costs more than an equivalent plain-English description of the same config, because code has many special characters that each become their own tokens.

```
"Deploy nginx with 3 replicas to the production namespace"
→ ~11 tokens → ~$0.000033 per call at $3/1M input tokens

A 100-line Kubernetes YAML for the same thing
→ ~380 tokens → ~$0.00114 per call (34× more expensive)
```

### 2. Context windows are measured in tokens

When you see "200K context window," that means 200,000 tokens. Your entire conversation — system prompt, history, current message, and the response — must fit within that budget. A large log file or runbook corpus can exhaust it quickly.

### 3. Code tokenizes more densely than prose

English prose: ~1.3 tokens per word
Python code: ~3–5 tokens per line  
JSON/YAML: ~4–6 tokens per line

When building AI tools that process Terraform, Kubernetes manifests, or application logs, you need to budget aggressively.

### 4. Tokenization is model-specific

GPT-4 and Claude use *different* tokenizers. The same text produces different token counts. Always use the tokenizer for the specific model you're calling. Don't estimate from word count.

---

## Common Surprises

| Text | Expected tokens | Actual tokens |
|------|-----------------|---------------|
| `"2024-10-15"` | 1 | 4 |
| `"192.168.1.100"` | 1 | 6 |
| `"Kubernetes"` | 1 | 1 ✓ |
| `"kubernetes"` (lowercase) | 1 | 3 |
| `" kubernetes"` (space prefix) | 1 | 2 |
| `"CrashLoopBackOff"` | 1 | 5 |

Casing and spaces matter. `"Kubernetes"` and `"kubernetes"` are different token sequences.

---

## Key Takeaways

1. **Tokens ≠ words.** Rule of thumb: 1 token ≈ 0.75 English words; 1 token ≈ 4 characters for English. Code is denser.
2. **Token count drives cost and context limits.** Measure tokens, not characters or lines.
3. **Use the right tokenizer for your model.** `tiktoken` for OpenAI/GPT models; token counting APIs for Anthropic models.

---

## Hands-On

→ [Lab 01: Tokenization](../labs/lab01_tokenization/lab.py)  
→ [Demo: Tokenizer Explorer](../demos/demo_tokenizer_explorer.py)
