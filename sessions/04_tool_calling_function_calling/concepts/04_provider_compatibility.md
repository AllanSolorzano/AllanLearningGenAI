# 04. Provider Compatibility (OpenAI, Compatible APIs, Ollama)

Most modern tool-calling clients share the same pattern:

- OpenAI SDK client
- `chat.completions.create(...)`
- `tools=[...]`
- consume `message.tool_calls`

## Why this matters

You can keep one orchestration loop and swap only runtime config:

- `model`
- `base_url`
- `api_key`

## Typical provider mapping

- OpenAI hosted:
  - `base_url=None` (default)
- OpenAI-compatible hosted provider:
  - `base_url=https://provider.example.com/v1`
- Ollama local:
  - `base_url=http://localhost:11434/v1`
  - often accepts placeholder key like `ollama`

Note:
- Capability differs by model. Not every model handles tool calls equally well.
- Use evaluation prompts to verify behavior per model before production rollout.

