# Models and Quantization

## Model Families

Popular models available on Ollama:

| Model        | Params | Best For                              |
|--------------|--------|---------------------------------------|
| `llama3.2`   | 3B     | Fast, general purpose, low RAM        |
| `llama3.1`   | 8–70B  | High quality, more RAM needed         |
| `mistral`    | 7B     | Strong instruction following          |
| `phi3`       | 3.8B   | Reasoning, coding, fast               |
| `codellama`  | 7–34B  | Code generation and explanation       |
| `gemma2`     | 9B     | Google's open model, good at tasks    |
| `deepseek-r1`| 7B+    | Chain-of-thought reasoning            |

**Params** = number of parameters. More = smarter but slower and larger.

## Quantization

A 7B parameter model at full float32 precision = ~28 GB. That won't fit on most laptops.

**Quantization** reduces numerical precision to shrink the model:

| Quantization | Bits | Size (7B model) | Quality loss  |
|--------------|------|-----------------|---------------|
| Q4_K_M       | 4-bit | ~4 GB          | Small, good default |
| Q5_K_M       | 5-bit | ~5 GB          | Better quality |
| Q8_0         | 8-bit | ~8 GB          | Near-original  |
| F16          | 16-bit | ~14 GB        | Full precision |

DevOps analogy: quantization is like JPEG compression quality on an image.
Q4 ≈ 60% quality — looks almost the same, much smaller file.

Ollama defaults to Q4_K_M for most models. You usually don't need to choose —
just `ollama pull llama3.2`.

## Choosing a Model Based on Your RAM

| Available RAM | Recommended                          |
|---------------|--------------------------------------|
| 4 GB          | `llama3.2` (3B), `phi3`              |
| 8 GB          | `llama3.1:8b`, `mistral`             |
| 16 GB         | `llama3.1:8b` comfortably            |
| 32 GB+        | `llama3.1:70b` (Q4)                  |

Check RAM usage while a model is loaded:
```bash
# macOS / Linux
watch -n1 free -h

# Or check Ollama's process
ps aux | grep ollama
```

## Inspecting a Model

```bash
ollama show llama3.2
```

Or via the API:
```python
import requests
r = requests.post("http://localhost:11434/api/show", json={"name": "llama3.2"})
details = r.json()["details"]
print(details["family"])             # llama
print(details["parameter_size"])     # 3.2B
print(details["quantization_level"]) # Q4_K_M
print(details["context_length"])     # 131072
```

## Context Length

Context length = maximum number of tokens the model can see at once (prompt + response).

| Model       | Context length |
|-------------|----------------|
| llama3.2    | 128K tokens    |
| mistral     | 32K tokens     |
| phi3        | 128K tokens    |

128K tokens ≈ ~100,000 words. You can feed entire log files, runbooks, or codebases.

## Pulling Specific Versions

```bash
# Pull default (Q4_K_M)
ollama pull llama3.2

# Pull specific tag/quantization
ollama pull llama3.1:8b
ollama pull llama3.1:70b-instruct-q4_K_M

# See all available tags
# Visit: https://ollama.com/library/llama3.1
```
