# Session 03: Local LLMs with Ollama

Run production-grade language models on your own machine — no API key, no cloud costs,
no data leaving your environment.

## DevOps Analogy

| Ollama Concept            | DevOps Equivalent                              |
|---------------------------|------------------------------------------------|
| `ollama serve`            | `dockerd` — the daemon that serves models      |
| `ollama pull llama3.2`    | `docker pull nginx:latest` — fetch an image    |
| Model file (GGUF)         | Container image layers cached on disk          |
| REST API at `:11434`      | Docker daemon socket / REST API                |
| `ollama run llama3.2`     | `docker run -it ubuntu bash`                   |
| `ollama list`             | `docker images`                                |
| `ollama rm llama3.2`      | `docker rmi nginx`                             |

## What You'll Learn

- Install and operate Ollama locally
- Call the Ollama REST API with raw `requests`
- Use the `ollama` Python SDK
- Run multi-turn conversations and manage chat history
- Stream responses token-by-token for live UIs
- Tune temperature and sampling parameters

## Prerequisites

```bash
# 1. Install Ollama
#    https://ollama.com/download

# 2. Pull a model (like docker pull)
ollama pull llama3.2        # ~2GB, good general purpose model

# 3. Install Python packages
pip install requests ollama
```

## Session Structure

```
03_local_llms_ollama/
├── concepts/               ← read these first
│   ├── 01_what_is_ollama.md
│   ├── 02_models_and_quantization.md
│   ├── 03_rest_api.md
│   ├── 04_python_integration.md
│   └── 05_streaming_and_parameters.md
├── labs/                   ← hands-on exercises
│   ├── lab01_setup/        ← health check, list models, first call
│   ├── lab02_chat_and_params/  ← multi-turn chat, temperature
│   └── lab03_sdk_and_streaming/  ← ollama SDK + streaming tokens
└── demos/                  ← runnable showcases
    ├── demo_model_comparison.py
    ├── demo_streaming_chat.py
    └── demo_sre_assistant.py
```

## Labs

| Lab | Topic | Key Concepts |
|-----|-------|-------------|
| lab01_setup | Install, list models, first API call | `/api/tags`, `/api/show`, `/api/generate` |
| lab02_chat_and_params | Multi-turn chat, temperature tuning | `/api/chat`, `options`, message history |
| lab03_sdk_and_streaming | ollama Python SDK + streaming | `ollama.chat()`, NDJSON streaming |

## Demos

| Demo | What it shows |
|------|---------------|
| `demo_model_comparison.py` | Same prompt → multiple models, side-by-side timing |
| `demo_streaming_chat.py` | Interactive REPL with live token streaming |
| `demo_sre_assistant.py` | SRE incident assistant — zero cloud dependency |

## Quick Verification

```bash
# Is Ollama running?
curl http://localhost:11434/api/tags

# List models in Python
python -c "import requests; print([m['name'] for m in requests.get('http://localhost:11434/api/tags').json()['models']])"
```
