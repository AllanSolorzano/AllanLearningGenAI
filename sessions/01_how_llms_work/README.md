# Session 01 — How LLMs Actually Work

> "You deploy Kubernetes pods. This session explains what's running inside the LLM pod."

---

## Learning Objectives

By the end of this session you will be able to:

1. **Explain tokenization** — how LLMs convert text to numbers, and why token count drives cost and limits
2. **Explain embeddings** — how meaning becomes math, and why this enables semantic search
3. **Explain the Transformer architecture** — what attention is and why it replaced RNNs
4. **Distinguish training from inference** — the Docker image vs running container analogy
5. **Tune context window and temperature** — the two most impactful runtime parameters

---

## Prerequisites

- Python 3.10+
- Packages installed: `pip install -r ../../requirements.txt`
- **No API key required** for this session

---

## Estimated Time

| Activity | Time |
|----------|------|
| Read all concept files | 45 min |
| Lab 01 — Tokenization | 20 min |
| Lab 02 — Embeddings | 25 min |
| Lab 03 — Context Window | 20 min |
| Demos (all 3) | 15 min |
| **Total** | **~2 hours** |

---

## How to Work Through This Session

### Step 1 — Read the concepts (in order)

```
concepts/
├── 01_tokens.md                  ← Start here
├── 02_embeddings.md
├── 03_transformers.md
├── 04_training_vs_inference.md
└── 05_context_and_temperature.md
```

Each concept file follows the same structure:
- **DevOps Analogy** — maps the concept to something you already know
- **How It Works** — the actual mechanism, no unnecessary math
- **Why It Matters** — practical implications for building AI-powered systems
- **Key Takeaways** — 3-bullet summary

### Step 2 — Run the labs

```bash
# Lab 01: Tokenization (no API key, offline)
cd labs/lab01_tokenization
python lab.py

# Lab 02: Embeddings (no API key, downloads ~90MB model on first run)
cd labs/lab02_embeddings
python lab.py

# Lab 03: Context Window (no API key, offline)
cd labs/lab03_context_window
python lab.py
```

Fill in the `# TODO` markers in each `lab.py`. Check `solution.py` if stuck.

### Step 3 — Run the demos

```bash
# Demo 1: Interactive tokenizer — try any text
cd demos
python demo_tokenizer_explorer.py

# Demo 2: Semantic search over DevOps runbooks
python demo_semantic_search.py

# Demo 3: Temperature effects (requires ANTHROPIC_API_KEY)
python demo_temperature_effect.py
```

---

## What's Next

**Session 02 — Prompt Engineering** teaches you how to communicate effectively with LLMs:
system prompts, few-shot examples, chain-of-thought reasoning, and prompt injection defense.

→ See [../02_prompt_engineering/README.md](../02_prompt_engineering/README.md)
