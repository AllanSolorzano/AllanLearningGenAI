# 01. MCP vs Function Calling — What's the Difference?

You already know function calling from Session 04. MCP is the next level.
Both let an LLM invoke tools — but they solve different problems at different layers.

---

## DevOps Analogy First

| Concept | Function Calling | MCP |
|---------|-----------------|-----|
| What it is | Writing handlers inside your app | Publishing a microservice to a registry |
| Who can use it | Only your app | Any MCP-compatible client |
| Tool discovery | You hardcode schemas per API call | Client discovers tools at connect time |
| Where tools run | Inside your API call loop | Separate long-running process |
| Portability | Provider-specific (Anthropic vs OpenAI format) | Standardized protocol — provider-agnostic |
| Lifecycle | Per-request, ephemeral | Persistent server with state |

Function calling = a Kubernetes Job that runs once and exits.
MCP = a Kubernetes Deployment behind a Service — always on, discoverable.

---

## How Function Calling Works (Recap)

```
Your App                    Anthropic API
    |                             |
    |  -- messages + tools -->    |   # you pass schemas every call
    |  <-- tool_use block --      |   # model says "call X with args Y"
    |  (you run the tool)         |
    |  -- tool result -->         |   # you send result back manually
    |  <-- final text --          |
```

**You own the entire loop.** Every call requires:
1. Passing tool schemas explicitly
2. Detecting tool_use in the response
3. Running the tool yourself
4. Sending results back

The tools exist only as JSON schemas. They live nowhere — they're just text you include in each request.

---

## How MCP Works

```
MCP Server (your code)        MCP Client (Claude Desktop, your app, Cursor...)
        |                                  |
        |  <-- initialize() -->            |   # client connects once
        |  <-- list_tools() -->            |   # client discovers tools dynamically
        |                                  |
        |  <-- call_tool("X", args) --     |   # client calls when model needs it
        |  -- result -->                   |
```

**The server is a separate process.** The client:
1. Connects once
2. Discovers tools automatically
3. Calls tools over the protocol
4. Handles results — no manual loop in your code

---

## The Protocol Layer

MCP is a **protocol** (like REST or gRPC), not a library.
It runs over:
- **stdio** — server is a subprocess, communication via stdin/stdout (local tools)
- **HTTP + SSE** — server is a web service (remote tools)
- **WebSocket** — bidirectional streaming (advanced)

This means: build your MCP server once → works with Claude Desktop, Cursor, VS Code Copilot,
your custom app, or any future MCP client. No rewrites.

---

## Three Primitives (MCP gives you more than function calling)

| Primitive | What it is | Function Calling Equivalent |
|-----------|-----------|----------------------------|
| **Tools** | Callable functions with side effects | Tool schemas + handlers |
| **Resources** | URI-addressable data the model can read | Not possible — you'd have to inject text |
| **Prompts** | Reusable parameterized prompt templates | Not possible |

Tools in MCP work the same as function calling conceptually — but Resources and Prompts are new.

---

## When to Use Each

**Use function calling when:**
- Building a one-off app where you control the full call loop
- You need to work with a provider's specific API directly
- The tools are application-specific and won't be reused elsewhere
- You want the simplest possible setup (no server process)

**Use MCP when:**
- You want ONE server that works with Claude Desktop, Cursor, and your app
- You're building tools the whole team shares (e.g., a company-wide incident lookup server)
- You need Resources (expose files, DB records, configs as readable data)
- You want persistent server state between calls
- You're building a platform others will integrate with

---

## Same Tool, Two Implementations

### Function Calling Style
```python
# Schema inline, loop in your code
tools = [{"type": "function", "function": {"name": "get_incident", ...}}]
response = client.messages.create(model=..., tools=tools, messages=messages)
# detect tool_use, run get_incident(), send result back, repeat
```

### MCP Style
```python
from fastmcp import FastMCP

mcp = FastMCP("incident-server")

@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """Look up an incident by ID."""
    return INCIDENT_DB.get(incident_id, {"error": "not found"})

mcp.run()  # now any MCP client can use this — forever
```

The function body is identical. The difference is the **deployment model**.
