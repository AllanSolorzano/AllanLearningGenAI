# Streaming and Model Parameters

## Why Streaming Matters

Without streaming: your code blocks for 10–30 seconds waiting for the full response.
With streaming: tokens arrive as they're generated — you can display them immediately.

For a terminal tool or chat UI, streaming makes the difference between "it feels broken"
and "it feels alive".

## How Streaming Works

Ollama sends **NDJSON** (Newline-Delimited JSON) — one JSON object per line over a
persistent HTTP connection (chunked transfer encoding):

```
{"model":"llama3.2","response":"A","done":false}
{"model":"llama3.2","response":" Kubernetes","done":false}
{"model":"llama3.2","response":" Pod","done":false}
...
{"model":"llama3.2","response":"","done":true,"total_duration":2345678,"eval_count":45}
```

The final line has `"done": true` and includes timing metadata.

## Streaming /api/generate

```python
import json, requests

def stream_generate(prompt: str, model: str = "llama3.2") -> str:
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": True},
        stream=True,        # keep the HTTP connection open for chunked transfer
    )
    tokens = []
    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        print(chunk["response"], end="", flush=True)   # print token immediately
        tokens.append(chunk["response"])
        if chunk["done"]:
            break
    print()  # newline when done
    return "".join(tokens)
```

## Streaming /api/chat

Same pattern — just use `chunk["message"]["content"]` instead of `chunk["response"]`:

```python
def stream_chat(messages: list[dict], model: str = "llama3.2") -> str:
    r = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
    )
    tokens = []
    for line in r.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        token = chunk.get("message", {}).get("content", "")
        print(token, end="", flush=True)
        tokens.append(token)
        if chunk.get("done"):
            break
    print()
    return "".join(tokens)
```

---

## Model Parameters

Pass under `"options"` in your request body:

```python
requests.post("http://localhost:11434/api/generate", json={
    "model": "llama3.2",
    "prompt": "...",
    "stream": False,
    "options": {
        "temperature": 0.0,
        "top_p": 0.9,
        "top_k": 40,
        "num_predict": 256,
        "repeat_penalty": 1.1,
        "seed": 42,
    }
})
```

## Parameter Reference

| Parameter        | Range   | Effect                                                      |
|------------------|---------|-------------------------------------------------------------|
| `temperature`    | 0.0–2.0 | 0 = deterministic, 0.7 = balanced, >1.2 = creative/chaotic |
| `top_p`          | 0.0–1.0 | Nucleus sampling — tokens from top_p probability mass only  |
| `top_k`          | 1–100   | Sample only from the K most likely next tokens              |
| `num_predict`    | -1 to N | Max tokens to generate (-1 = model default)                 |
| `repeat_penalty` | 1.0–2.0 | Penalise repeating the same phrases                         |
| `seed`           | int     | Fixed seed for reproducible output (use with temperature=0) |

## Practical Settings by Use Case

| Use case                  | temperature | top_p | num_predict |
|---------------------------|-------------|-------|-------------|
| SRE runbook answers       | 0.0         | 0.9   | 512         |
| Code generation           | 0.1         | 0.95  | 1024        |
| Log classification        | 0.0         | 0.9   | 50          |
| Creative text             | 0.8         | 0.9   | -1          |
| Brainstorming             | 1.2         | 0.95  | -1          |

**Rule of thumb for DevOps tooling**: keep `temperature` at 0.0–0.2.
You want consistent, deterministic output — not poetry.

## Measuring Performance

```python
import requests

r = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "llama3.2", "prompt": "Hello", "stream": False},
)
data = r.json()
tokens_generated = data["eval_count"]
duration_sec = data["eval_duration"] / 1e9
print(f"{tokens_generated / duration_sec:.1f} tokens/sec")
```

Typical performance on modern hardware:
- CPU only (M2 MacBook): 20–40 tokens/sec for a 3B model
- GPU (RTX 3080):        80–120 tokens/sec for a 7B model
