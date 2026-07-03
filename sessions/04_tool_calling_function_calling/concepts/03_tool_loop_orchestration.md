# 03. Tool Loop Orchestration

Canonical loop:

1. Send `messages + tools`.
2. If no tool calls -> return assistant text.
3. If tool calls exist:
   - Execute each tool with validated args.
   - Append tool results to `messages`.
   - Call model again.
4. Repeat until final text or max step limit.

## Guardrails you should always add

- Max loop depth (e.g., 5-8 iterations).
- Timeout budget per tool.
- Structured error payloads from tools:
  - `{ "error": "...", "retryable": false }`
- Idempotency for write actions.

## Message roles (Chat Completions style)

- `system`: policy, behavior constraints.
- `user`: task input.
- `assistant`: may include `tool_calls`.
- `tool`: your function output tied to `tool_call_id`.

