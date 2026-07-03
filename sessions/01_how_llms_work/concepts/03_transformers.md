# 03 — Transformers & Attention: The Engine Under the Hood

> **TL;DR:** The transformer processes all tokens simultaneously using "attention" — every token
> can directly reference every other token. This is what makes LLMs understand long-range context.

---

## DevOps Analogy: The Service Mesh

Before transformers, the dominant architecture was the **RNN (Recurrent Neural Network)**, which processed text sequentially — token by token, like a stateful firewall inspecting packets one at a time. By the time it processed token 100, the context from token 1 was distorted, like a message passed through 99 hops of NAT.

The transformer replaced this with something more like a **service mesh**.

In a service mesh (Istio, Envoy, Linkerd), every service has a sidecar proxy that can communicate directly with every other service. There's no "relay chain." Token 100 can look directly at token 1 with zero degradation. This is **self-attention**.

```
RNN (sequential, lossy):
Token 1 → Token 2 → Token 3 → ... → Token 100
                                      (token 1 is barely a whisper)

Transformer (parallel, direct):
Token 1 ←→ Token 2 ←→ Token 3 ←→ ... ←→ Token 100
         (every token sees every other token directly)
```

The **attention weights** are like traffic weights in a weighted load balancer. When processing the token `"failed"` in the sentence `"Terraform failed on the AWS provider module"`, the model assigns:
- High weight to `"Terraform"` and `"provider"` — they tell you *what* failed
- Low weight to `"on"` and `"the"` — less informative

The final representation of `"failed"` is a weighted blend of information from all tokens.

---

## Self-Attention: Query, Key, Value

Each token produces three vectors used in the attention calculation:

| Vector | Analogy | Question it answers |
|--------|---------|---------------------|
| **Query (Q)** | `kubectl get pods -l ?` | "What am I looking for?" |
| **Key (K)** | Pod labels | "What do I offer?" |
| **Value (V)** | Pod spec | "What do I actually send if selected?" |

The attention score between two tokens is computed as: `softmax(Q · K^T / √d) × V`

You don't need to understand the math. The intuition is:
1. Token A broadcasts its Query ("I'm a verb, what's my subject?")
2. All tokens broadcast their Keys ("I'm a noun," "I'm a modifier," etc.)
3. Token A computes dot products: which Keys match my Query best?
4. High-scoring tokens send their Values back to Token A
5. Token A's final representation is the weighted sum of those Values

---

## Multi-Head Attention: Parallel Monitoring

Single-head attention can only ask one "question" per layer. The transformer uses **multi-head attention** — 8, 16, or 32 heads per layer, each asking a different question simultaneously.

Think of it as **parallel monitoring dashboards**:
- Head 1 monitors: syntactic relationships (what's the subject of this verb?)
- Head 2 monitors: semantic relationships (what concepts are related?)
- Head 3 monitors: coreference (what does "it" refer to?)
- Head 4 monitors: temporal relationships (before/after ordering)

All heads run in parallel, and their outputs are concatenated and projected into the next layer's representation.

---

## The Full Transformer Block

Each layer in the model is a **transformer block**:

```
Input tokens
     ↓
┌─────────────────────────────────────────┐
│  1. Multi-Head Self-Attention           │  ← "Who should I attend to?"
│     + Residual Connection               │  ← (skip connection, like ResNet)
│     + Layer Normalization               │
├─────────────────────────────────────────┤
│  2. Feed-Forward Network (FFN)          │  ← "What do I do with this info?"
│     + Residual Connection               │
│     + Layer Normalization               │
└─────────────────────────────────────────┘
     ↓
Output (same shape, richer representation)
```

Residual connections (skip connections) are like **bypass routes** in a network — they let gradients flow during training and prevent information loss.

A GPT-4-scale model stacks ~96 of these blocks. Each layer builds a progressively richer understanding of the input.

---

## Why Position Matters: Positional Encoding

Self-attention processes all tokens simultaneously (in parallel), so it has no inherent sense of order. `"the pod killed the node"` and `"the node killed the pod"` would look identical without position information.

**Positional encoding** solves this by adding a position-dependent signal to each token's embedding before the first layer. Think of it like **TCP sequence numbers** — not content, just position information, but critical for maintaining order.

Modern models like Claude use **RoPE (Rotary Position Embedding)**, which handles very long sequences and extrapolates to contexts longer than those seen during training.

---

## Autoregressive Generation: One Token at a Time

During inference, the model generates output token by token:

```
Step 1:  Input: "The Terraform plan shows"  →  predicts: " 3"
Step 2:  Input: "The Terraform plan shows 3"  →  predicts: " resources"
Step 3:  Input: "The Terraform plan shows 3 resources"  →  predicts: " to"
...
StepN:   Input: full sequence so far  →  predicts: <end-of-sequence>
```

This is called **autoregressive generation**. Each token is sampled from the model's probability distribution over its vocabulary (more on this in Concept 05). Once a token is committed, it can't be changed.

This is why:
- LLMs can't "revise" — generation is forward-only, like a stream processor
- Longer outputs cost more — each token requires a full forward pass
- "Thinking" models spend tokens computing intermediate reasoning steps

---

## The Practical Implication

Understanding the attention mechanism helps you write better prompts:

- **Put important context early.** The model processes your entire prompt in one pass, but long-range dependencies are harder to maintain. Important constraints belong near the beginning.
- **Be explicit, not implicit.** Self-attention finds relationships, but only within what you provided. If the relevant context isn't in the prompt, the model can't attend to it.
- **Long context ≠ free context.** Attention computation scales quadratically with sequence length — a 2× longer prompt is ~4× more compute. This drives both latency and cost.

---

## Key Takeaways

1. **Self-attention lets every token directly reference every other token** — no sequential bottleneck, no long-range forgetting.
2. **Multi-head attention runs multiple attention patterns in parallel** — like having multiple specialized monitoring dashboards simultaneously.
3. **Generation is autoregressive** — one token at a time, forward-only. The model can't go back and revise.

---

## Further Reading

- [The Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/) — the best visual explanation, no math required
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — the original 2017 paper that started it all (surprisingly readable)
