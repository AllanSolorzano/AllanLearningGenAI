# Python Integration

Two ways to call Ollama from Python: **raw `requests`** or the **`ollama` Python SDK**.

## Raw requests

Full control. Works in any Python environment. Only dependency: `requests`.

```python
import requests

def chat(messages: list[dict], model: str = "llama3.2") -> str:
    r = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": model, "messages": messages, "stream": False},
    )
    r.raise_for_status()
    return r.json()["message"]["content"]
```

Use raw requests when:
- You want to inspect response headers, status codes, or timing data
- You're integrating into an existing HTTP client or session pool
- You need custom retry logic, proxies, or connection settings

## ollama Python SDK

```bash
pip install ollama
```

```python
import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "What is a Pod?"}],
)
print(response["message"]["content"])
```

The SDK is a thin wrapper — same REST API underneath. It adds:
- Type hints and IDE autocompletion
- Convenience methods: `ollama.generate`, `ollama.chat`, `ollama.list`, `ollama.show`
- Automatic connection management

Use the SDK when:
- You want cleaner, more idiomatic Python
- You don't need custom HTTP behaviour
- You're prototyping quickly

## Side-by-Side Comparison

```python
msgs = [{"role": "user", "content": "What is a Kubernetes Pod?"}]

# --- raw requests ---
import requests
r = requests.post(
    "http://localhost:11434/api/chat",
    json={"model": "llama3.2", "messages": msgs, "stream": False},
)
answer = r.json()["message"]["content"]

# --- ollama SDK (identical result) ---
import ollama
r = ollama.chat(model="llama3.2", messages=msgs)
answer = r["message"]["content"]
```

Both return the exact same data. The SDK just saves you from spelling out the URL.

## Error Handling

```python
import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout

def safe_chat(messages: list[dict], model: str = "llama3.2") -> str | None:
    try:
        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=120,          # local models can be slow on CPU
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    except ConnectionError:
        print("Ollama is not running. Start it: ollama serve")
    except HTTPError as e:
        error = e.response.json().get("error", str(e))
        if "not found" in error:
            print(f"Model '{model}' not pulled. Run: ollama pull {model}")
        else:
            print(f"API error: {error}")
    except Timeout:
        print("Request timed out — model may be too large for your hardware")

    return None
```

## Checking Ollama is Running Before Calling

```python
def is_ollama_running() -> bool:
    try:
        return requests.get("http://localhost:11434/api/tags", timeout=3).status_code == 200
    except Exception:
        return False

if not is_ollama_running():
    print("Start Ollama: ollama serve")
    exit(1)
```

## Reusing Connections (Performance)

For high-throughput scripts, use a `requests.Session` to reuse the TCP connection:

```python
session = requests.Session()

def chat(messages, model="llama3.2"):
    r = session.post(
        "http://localhost:11434/api/chat",
        json={"model": model, "messages": messages, "stream": False},
    )
    return r.json()["message"]["content"]
```
