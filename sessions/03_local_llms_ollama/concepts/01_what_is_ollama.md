# What is Ollama?

## DevOps Analogy First

Think of Ollama as **Docker for language models**.

| Docker                        | Ollama                              |
|-------------------------------|-------------------------------------|
| `dockerd` daemon              | `ollama serve` daemon               |
| `docker pull nginx`           | `ollama pull llama3.2`              |
| Container image (layers)      | Model file (GGUF format on disk)    |
| `docker run -it ubuntu bash`  | `ollama run llama3.2`               |
| Docker REST API `:2375`       | Ollama REST API `:11434`            |
| `docker images`               | `ollama list`                       |
| `docker inspect <image>`      | `ollama show llama3.2`              |

Just like Docker abstracts away container runtimes (containerd, runc), Ollama abstracts
away the model inference engine (llama.cpp under the hood). You just pull and run.

## What Ollama Does

1. **Serves a REST API** at `http://localhost:11434`
2. **Manages model files** — downloads, stores, and loads them into memory
3. **Runs inference** — processes your prompts and returns responses
4. **Handles GPU/CPU automatically** — uses GPU if available, falls back to CPU

## Architecture

```
Your Python code
      ↓  HTTP POST to :11434
Ollama daemon (ollama serve)
      ↓
llama.cpp (inference engine)
      ↓
Model file (GGUF on disk, ~/.ollama/models/)
      ↓
CPU / GPU
```

## Why Run Locally?

| Cloud API                          | Ollama (local)                      |
|------------------------------------|-------------------------------------|
| Costs per token                    | Free after hardware                 |
| Data leaves your network           | Data stays on-prem                  |
| Rate limits apply                  | No limits                           |
| Requires internet                  | Works air-gapped                    |
| Managed, always available          | You manage the daemon               |

For DevOps use cases — incident analysis, log parsing, runbook generation — your
production logs and error traces should never leave your network. Local LLMs solve this.

## Quick Start

```bash
# 1. Install Ollama — https://ollama.com/download

# 2. Start the server (auto-starts on most installs)
ollama serve

# 3. Pull a model
ollama pull llama3.2       # ~2GB, good general purpose
ollama pull phi3           # ~2GB, fast, strong reasoning
ollama pull mistral        # ~4GB, strong instruction following

# 4. Chat in the terminal (like docker run -it)
ollama run llama3.2

# 5. Manage models
ollama list                # list installed models
ollama show llama3.2       # inspect model details
ollama rm llama3.2         # remove a model
```

## Verify the API is Running

```bash
curl http://localhost:11434/api/tags
# Returns: {"models": [...]}
```

Or in Python:
```python
import requests
r = requests.get("http://localhost:11434/api/tags", timeout=3)
print(r.json())
```
