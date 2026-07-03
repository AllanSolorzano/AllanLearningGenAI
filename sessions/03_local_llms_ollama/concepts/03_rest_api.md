# Ollama REST API

Ollama exposes a REST API at `http://localhost:11434`. No authentication required for localhost.

## Endpoints at a Glance

| Method | Path           | Purpose                        |
|--------|----------------|--------------------------------|
| GET    | `/api/tags`    | List installed models          |
| POST   | `/api/generate`| Single-turn text completion    |
| POST   | `/api/chat`    | Multi-turn chat                |
| POST   | `/api/show`    | Model metadata                 |
| POST   | `/api/pull`    | Download a model               |
| DELETE | `/api/delete`  | Remove a model                 |

---

## GET /api/tags — List Models

```bash
curl http://localhost:11434/api/tags
```

Response:
```json
{
  "models": [
    {
      "name": "llama3.2:latest",
      "size": 2019393189,
      "modified_at": "2024-11-01T10:00:00Z"
    }
  ]
}
```

---

## POST /api/generate — Single-Turn Completion

Stateless — no conversation history. Good for one-shot tasks (summarise, classify, transform).

Request:
```json
{
  "model": "llama3.2",
  "prompt": "What is a Kubernetes Pod?",
  "stream": false,
  "options": {
    "temperature": 0.0,
    "num_predict": 256
  }
}
```

Response:
```json
{
  "response": "A Kubernetes Pod is the smallest deployable unit...",
  "done": true,
  "total_duration": 1234567890,
  "prompt_eval_count": 15,
  "eval_count": 67,
  "eval_duration": 987654321
}
```

Tokens per second = `eval_count / (eval_duration / 1e9)`

---

## POST /api/chat — Multi-Turn Chat

Stateful conversation via message history. You maintain the list — append each turn yourself.

Request:
```json
{
  "model": "llama3.2",
  "messages": [
    {"role": "system",    "content": "You are a helpful SRE assistant."},
    {"role": "user",      "content": "My pod keeps crashing."},
    {"role": "assistant", "content": "Run: kubectl logs <pod> --previous"},
    {"role": "user",      "content": "Logs show OOMKilled."}
  ],
  "stream": false
}
```

Response:
```json
{
  "message": {
    "role": "assistant",
    "content": "OOMKilled means your container exceeded its memory limit..."
  },
  "done": true
}
```

**Key point**: the model has no memory — you send the full history on every request.
This is identical to every cloud LLM API (OpenAI, Anthropic, etc.).

---

## POST /api/show — Model Details

```json
{"name": "llama3.2"}
```

Response includes `details` (family, parameters, quantization, context_length),
`modelfile`, and `parameters` (default temperature settings).

---

## Streaming

Set `"stream": true` on `/api/generate` or `/api/chat`.

The response body is **NDJSON** — one JSON object per line:

```
{"model":"llama3.2","response":"A","done":false}
{"model":"llama3.2","response":" Pod","done":false}
{"model":"llama3.2","response":" is","done":false}
...
{"model":"llama3.2","response":"","done":true,"total_duration":1234,"eval_count":45}
```

The final chunk has `"done": true` and includes timing metadata.

```python
import json, requests

r = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "llama3.2", "prompt": "Hello", "stream": True},
    stream=True,
)
for line in r.iter_lines():
    chunk = json.loads(line)
    print(chunk["response"], end="", flush=True)
    if chunk["done"]:
        break
```

---

## Error Responses

| HTTP Status | Meaning                              |
|-------------|--------------------------------------|
| 200         | Success                              |
| 404         | Model not found — run `ollama pull`  |
| 500         | Server error (check `ollama serve` logs) |
| Connection refused | Ollama is not running         |

```python
r = requests.post(...)
if r.status_code == 404:
    print("Model not found. Run: ollama pull", model)
r.raise_for_status()  # raises on any 4xx/5xx
```
