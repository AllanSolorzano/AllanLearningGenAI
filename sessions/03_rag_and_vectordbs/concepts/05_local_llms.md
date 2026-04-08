# 05 — Local LLMs: Running Models on Your Own Hardware

> **TL;DR:** Ollama lets you run open-source LLMs (Llama, Mistral, Qwen) on your laptop
> or on-prem servers in minutes. For RAG workloads: zero cloud cost, no data leaves your network,
> good enough quality for most DevOps use cases.

---

## DevOps Analogy

Running a local LLM is like **self-hosting a service instead of using a managed cloud offering**.

You know this trade-off well:

| | Cloud API (Anthropic, OpenAI) | Local (Ollama) |
|---|------------------------------|----------------|
| **Setup** | API key + `pip install` | Install Ollama + `ollama pull model` |
| **Cost** | Per-token pricing | Hardware you already have |
| **Data privacy** | Sent to external servers | Never leaves your machine |
| **Reliability** | Provider SLA | Your uptime |
| **Model quality** | Frontier models | Open-source, 70–90% of frontier quality |
| **Latency** | Network round-trip | Local (fast on GPU, slower on CPU) |
| **Maintenance** | None | Model updates, server management |

**When to use local:**
- Sensitive data (internal docs, credentials in logs)
- High-volume workloads where API costs add up
- Offline development and testing
- Air-gapped environments (regulated industries)

**When to use cloud API:**
- Fastest path to production
- Need frontier model quality (complex reasoning, coding)
- Don't have GPU hardware
- Team isn't equipped to operate model serving

---

## Ollama: The Easiest Path to Local LLMs

[Ollama](https://ollama.com) packages model weights, runtime, and server into a single binary. No Python, no CUDA setup, no Docker required.

```bash
# Install (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh
# Windows: download from https://ollama.com/download

# Pull a model
ollama pull llama3.2        # 2GB — good balance
ollama pull mistral         # 4GB — strong reasoning
ollama pull qwen2.5:3b      # 2GB — fast, multilingual
ollama pull nomic-embed-text  # Embedding model (alternative to sentence-transformers)

# Verify
ollama list
ollama run llama3.2 "What is a CrashLoopBackOff?"
```

Ollama serves on `http://localhost:11434` with both its own API and an OpenAI-compatible API at `/v1`.

---

## Model Recommendations for RAG

| Task | Model | Size | Notes |
|------|-------|------|-------|
| Quick RAG answers | `llama3.2` | 2GB | Good for factual Q&A, fast |
| Better reasoning | `mistral` | 4GB | Better at multi-step analysis |
| Structured output | `qwen2.5:7b` | 5GB | Reliable JSON extraction |
| Embeddings (local) | `nomic-embed-text` | 280MB | Alternative to sentence-transformers |
| Code/IaC generation | `codellama:7b` | 4GB | Fine-tuned on code |

For RAG on runbooks and incident data: **llama3.2 or mistral** are sufficient. You don't need a frontier model for "find the relevant runbook and summarise it."

---

## Calling Ollama from Python

### Via the `ollama` Python package (simplest):
```python
import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[
        {"role": "system", "content": "You are an SRE assistant."},
        {"role": "user", "content": "What causes CrashLoopBackOff?"},
    ],
)
print(response["message"]["content"])
```

### Via REST API directly (no extra dependency):
```python
import requests, json

response = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "llama3.2",
        "messages": [{"role": "user", "content": "What is OOMKilled?"}],
        "stream": False,
    },
)
print(response.json()["message"]["content"])
```

### Via OpenAI-compatible API (reuse existing tooling):
```python
from openai import OpenAI  # pip install openai

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
response = client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "What is a Kubernetes liveness probe?"}],
)
print(response.choices[0].message.content)
```

---

## The `utils/llm.py` Abstraction

Session 03 provides `utils/llm.py` — a thin wrapper that auto-selects the backend:

```python
from utils.llm import get_llm, ask

# Auto-detects: uses Anthropic if key is set, falls back to Ollama
llm = get_llm()
print(f"Using: {llm.backend} / {llm.model}")

# Force local
llm = get_llm(prefer_local=True, ollama_model="mistral")

# Send a message — same interface regardless of backend
response = ask(llm, system="You are an SRE.", user="Explain OOMKilled.")
print(response)
```

All labs in this session use `get_llm()` — they work identically whether you're using Claude or Llama.

---

## Hardware Requirements

| Setup | RAM | GPU | Throughput |
|-------|-----|-----|-----------|
| CPU only (laptop) | 8GB+ | None | ~5-15 tokens/sec |
| Apple Silicon (M1/M2/M3) | 16GB+ | Unified (MPS) | ~30-60 tokens/sec |
| NVIDIA GPU 8GB | 16GB RAM | RTX 3070+ | ~50-100 tokens/sec |
| NVIDIA GPU 24GB | 32GB RAM | RTX 4090 | ~100-200 tokens/sec |

For RAG (short answers from retrieved context), even 5 tokens/sec is usable. For interactive chat, aim for 20+ tokens/sec.

---

## Local Embeddings with Ollama

Ollama can also serve embedding models, replacing `sentence-transformers`:

```bash
ollama pull nomic-embed-text
```

```python
import ollama

def embed_with_ollama(texts: list[str]) -> list[list[float]]:
    return [
        ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]
        for text in texts
    ]
```

**Trade-off:** `sentence-transformers` is faster for batch embedding (GPU-accelerated, batched). Ollama embedding is convenient if you're already running Ollama and want one less dependency.

---

## Key Takeaways

1. **Ollama = `docker run` for LLMs.** Install, pull a model, run. No Python required.
2. **For RAG workloads: local models are good enough.** You don't need GPT-4 to retrieve a runbook and summarise it.
3. **The `utils/llm.py` abstraction** lets you swap backends without changing lab code.

---

## Hands-On

→ [Demo: Local RAG](../demos/demo_local_rag.py) — fully offline RAG, zero cloud cost  
→ All labs auto-detect Ollama vs Anthropic via `utils/llm.py`
