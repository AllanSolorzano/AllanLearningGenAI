# 04 — Training vs Inference: From Data to Deployed Model

> **TL;DR:** Training builds the model (expensive, done once). Inference runs it (cheap, done billions of times).
> Fine-tuning adapts a pre-trained model. These distinctions shape every architectural and cost decision.

---

## DevOps Analogy

| AI Concept | DevOps Equivalent |
|-----------|-------------------|
| Pre-training | Building a base Docker image from scratch — installing the OS, all system libs, language runtimes |
| Fine-tuning | Adding an application layer `FROM python:3.11-slim` — specializing for your use case |
| RLHF | A/B testing + gradual canary rollout guided by user feedback metrics |
| Inference | Running a container from the image: `docker run my-model` |
| Model weights | The baked-in layers of the Docker image |
| API call | A single HTTP request to the running container |

A foundation model (GPT-4, Claude, Gemini) is a **universal base image** — built once at enormous cost, then used by everyone as the starting point.

---

## Pre-Training: Building the Foundation

Pre-training is the initial, expensive phase of training on a massive corpus:

**What happens:**
- The model sees trillions of tokens from the internet, books, code, academic papers, and more
- Objective: **predict the next token** given all previous tokens (called "language modeling" or "causal LM")
- The model learns patterns, facts, reasoning strategies, and language structure as side effects of getting good at this one task

**Scale:**
- Training data: 1–15 trillion tokens
- Training time: months of compute on thousands of GPUs
- Cost: $10M–$100M+ for frontier models
- Outcome: a model that "knows" language, world knowledge, code, reasoning — but isn't yet useful as an assistant

This is **self-supervised learning** — the data doesn't need human labels. The task (predict the next token) generates its own supervision signal from raw text. This is why scale works: more data + more compute = better predictions = better emergent capabilities.

---

## Instruction Fine-Tuning: Teaching the Model to Follow Instructions

A pre-trained model is a next-token predictor, not an assistant. It would continue your prompt rather than answer it.

**Supervised Fine-Tuning (SFT)** adapts the pre-trained model using curated examples of:
- Good instructions and ideal responses
- Question-answer pairs
- Conversation transcripts with helpful behavior

The model's weights are updated (fine-tuned) on this smaller dataset. The result: a model that follows instructions, answers questions, and produces useful output — not just statistically likely continuations.

Like adding your application layer to the base image:
```dockerfile
FROM pretrained-llm:latest       # All that expensive pre-training
COPY sft_examples/ /fine-tune/   # Curated instruction-following examples
RUN fine-tune --task sft         # Relatively cheap: hours on a few GPUs
```

---

## RLHF: Teaching the Model to Be Helpful and Harmless

Instruction fine-tuning alone produces a model that tries to follow instructions but may be sycophantic, verbose, or subtly unhelpful. **Reinforcement Learning from Human Feedback (RLHF)** shapes the model to produce outputs that *humans prefer*.

**How it works:**
1. **Collect preference data:** Show human raters pairs of model responses. Which is better?
2. **Train a reward model:** A separate model that predicts human preference scores
3. **RL optimization:** Use the reward model to score responses, nudge the LLM toward higher-scoring outputs using PPO (Proximal Policy Optimization)

The DevOps analogy: **gradual canary deployment with telemetry feedback.**
- Deploy two variants of a service to production
- Measure which variant users prefer (engagement, task completion)
- Gradually shift traffic to the better variant
- Repeat until the service reaches optimal behavior

RLHF is why Claude is honest about uncertainty, declines harmful requests, and gives useful answers rather than just likely ones. These behaviors don't emerge from raw language modeling — they're instilled through human feedback signals.

---

## Inference: Running the Model

When you call an LLM API, this is what happens:

```
1. Your text arrives → tokenized into IDs
2. Token IDs pass through all transformer layers (forward pass)
3. Final layer produces a probability distribution over the vocabulary
4. One token is sampled from that distribution (using temperature)
5. That token is appended to the sequence
6. Steps 2–5 repeat until <end-of-sequence> or max_tokens
7. All generated token IDs are decoded back to text
8. Text returned to you
```

**Inference is computationally much cheaper than training.** Training requires computing gradients and updating billions of weights — inference is just a forward pass. But at billions of API calls per day across all users, inference still requires massive infrastructure.

---

## When to Use What

| Approach | When to use it | Cost |
|----------|----------------|------|
| API (pre-trained, no modification) | Most use cases — quick start, always the first option | $0.001–$0.015/1K tokens |
| Prompt engineering | Need specialized behavior, have good examples | Free |
| Fine-tuning | Domain-specific jargon, consistent format requirements, proprietary data | $10K–$100K one-time |
| Pre-training from scratch | Fundamental new capability, massive proprietary corpus, national security | $10M+ |

**For DevOps engineers building AI-powered tools:** start with the API and prompt engineering. Fine-tune only when you've exhausted prompt engineering options and have clean, labeled training data.

---

## GPU Memory: Why Model Size Matters

Model weights are stored in GPU memory (VRAM) during inference. A rough calculation:

```
70B parameters × 2 bytes (fp16) = 140 GB VRAM

That's 10× A100 GPUs (14GB each) or 2× H100 GPUs (80GB each)
just to hold the weights — before any batch processing
```

This is why:
- Smaller models (7B, 13B) can run on a single consumer GPU
- 70B+ models require server-grade multi-GPU setups
- Quantization (int8, int4) trades quality for memory reduction

For your own deployments (Session 05 covers this): `ollama` can run quantized 7B–13B models on a laptop. Production-grade 70B+ inference requires dedicated GPU servers.

---

## Key Takeaways

1. **Pre-training is the base image — don't build it yourself.** Use an existing foundation model via API.
2. **Fine-tuning is the application layer** — add it when prompt engineering can't solve your problem and you have quality training data.
3. **Inference is a forward pass** — much cheaper than training, but still requires managing GPU memory and token throughput.

---

## Further Reading

- [InstructGPT paper](https://arxiv.org/abs/2203.02155) — how RLHF turns a text predictor into an assistant
- [Scaling Laws for Neural Language Models](https://arxiv.org/abs/2001.08361) — why bigger models with more data are predictably better
