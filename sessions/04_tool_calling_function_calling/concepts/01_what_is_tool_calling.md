# 01. What Is Tool Calling?

Tool calling (function calling) lets the model request a function execution instead of hallucinating data.

Without tools:
- Model guesses current status.

With tools:
- Model asks for `get_service_status(service="payments", environment="prod")`
- Your code executes it.
- Result is sent back to model.
- Model produces grounded final answer.

Core flow:

1. You send user message + tool schemas.
2. Model returns either:
   - normal text, or
   - one/more tool calls with JSON arguments.
3. Your code runs tool(s).
4. You send tool result(s) back as tool messages.
5. Model writes final answer using tool output.

Important:
- The model never executes code directly.
- Your application is always the execution boundary.
- Tool calling is structured orchestration, not autonomous shell access.

