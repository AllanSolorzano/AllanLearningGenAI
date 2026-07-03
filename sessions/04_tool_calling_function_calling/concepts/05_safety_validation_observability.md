# 05. Safety, Validation, and Observability

Tool calling turns prompts into runtime actions. Treat it like production integration code.

## Safety

- Validate every tool argument before execution.
- Separate read tools from write tools.
- Add explicit approval gates for destructive actions.
- Restrict network/file/database reach per tool.

## Validation

- Reject missing required fields early.
- Normalize types (`int`, `bool`, enums).
- Return explicit error objects (not stack traces).

## Observability

Log per request:
- provider, model
- tool names called
- latency by step
- tool error counts
- final response quality signals

This makes tool pipelines debuggable and benchmarkable across providers.

