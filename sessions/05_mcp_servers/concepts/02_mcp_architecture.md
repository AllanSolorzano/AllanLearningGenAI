# 02. MCP Architecture

MCP (Model Context Protocol) is an open protocol created by Anthropic in 2024.
It standardizes how LLM applications talk to external tools and data sources.

---

## DevOps Analogy

| MCP Component | DevOps Equivalent |
|--------------|-------------------|
| MCP Server | gRPC microservice / Kubernetes pod |
| MCP Client | API gateway / service mesh sidecar |
| stdio transport | Unix domain socket (IPC) |
| HTTP+SSE transport | REST endpoint behind an ingress |
| Tool | RPC method |
| Resource | Read-only object storage key |
| Prompt | Helm chart template (parameterized) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   MCP Host                          │
│  (Claude Desktop, Cursor, your Python app, etc.)   │
│                                                     │
│  ┌─────────────┐   ┌─────────────┐                 │
│  │ MCP Client A│   │ MCP Client B│  (one per server)│
│  └──────┬──────┘   └──────┬──────┘                 │
└─────────┼─────────────────┼───────────────────────-┘
          │ stdio/HTTP       │ stdio/HTTP
    ┌─────▼──────┐    ┌──────▼──────┐
    │  MCP Server│    │  MCP Server │
    │  (local)   │    │  (remote)   │
    └─────┬──────┘    └──────┬──────┘
          │                  │
    ┌─────▼──────┐    ┌──────▼──────┐
    │  Your DBs  │    │  External   │
    │  Files     │    │  APIs       │
    │  Services  │    │  Cloud SDKs │
    └────────────┘    └─────────────┘
```

A single host (e.g., Claude Desktop) can connect to **multiple MCP servers simultaneously**.
Each server is isolated — separate process, separate capabilities.

---

## The Three Primitives

### 1. Tools (Model-initiated, have side effects)

The model decides to call a tool. Your server runs it.
```
client requests: call_tool("restart_service", {"service": "payments", "env": "prod"})
server executes: restarts the service, returns result
```
- Model-controlled
- Can have side effects (restart, write, delete)
- Must declare input schema
- Equivalent to function calling

### 2. Resources (Application-initiated, read-only)

Structured data exposed at a URI that the client/model can read.
```
client requests: read_resource("runbook://payments/restart")
server returns:  the runbook text content
```
- Read-only snapshots
- URI-addressable (like files or URLs)
- Can be static or dynamic
- Templates for parameterized resources

Example resource URIs:
```
incident://INC-1001          # specific incident
runbook://payments/restart   # runbook for a service
config://k8s/prod/limits     # k8s resource limits
```

### 3. Prompts (User-initiated, reusable templates)

Parameterized prompt templates your server exposes.
```
client requests: get_prompt("diagnose_incident", {"severity": "SEV1", "service": "auth"})
server returns:  a filled-in prompt ready to send to the model
```
- Templates with arguments
- Returned as a structured message list
- Great for standardizing common interactions

---

## Transport Layers

### stdio (Local — most common for development)

```
Host process spawns: python my_server.py
Communication via: stdin / stdout (newline-delimited JSON-RPC 2.0)
```

FastMCP default. Works offline, no network, lowest latency.
Claude Desktop uses this for local MCP servers.

### HTTP + SSE (Remote — for team/cloud deployments)

```
Server runs: uvicorn my_server:app --port 8000
Client connects to: http://localhost:8000/sse
```

Server-Sent Events for server→client push. HTTP POST for client→server calls.
Use when multiple users share one server, or server needs to run in the cloud.

---

## Protocol Wire Format

MCP uses **JSON-RPC 2.0** messages. You never write these by hand — FastMCP handles it.

Example: client discovering tools
```json
// Client sends:
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

// Server responds:
{"jsonrpc": "2.0", "id": 1, "result": {
  "tools": [
    {"name": "get_incident", "description": "...", "inputSchema": {...}}
  ]
}}
```

Example: client calling a tool
```json
// Client sends:
{"jsonrpc": "2.0", "id": 2, "method": "tools/call",
 "params": {"name": "get_incident", "arguments": {"incident_id": "INC-1001"}}}

// Server responds:
{"jsonrpc": "2.0", "id": 2, "result": {
  "content": [{"type": "text", "text": "{\"severity\": \"SEV1\", ...}"}]
}}
```

---

## Lifecycle

```
1. Host starts MCP server subprocess (stdio) or connects to URL (HTTP)
2. Client sends initialize() — exchanges protocol version + capabilities
3. Client calls list_tools(), list_resources(), list_prompts()
4. Model sees available tools via the host's context injection
5. When model wants a tool: client calls call_tool()
6. Server executes, returns result
7. Steps 5-6 repeat for the session lifetime
8. Host terminates the server process on exit (stdio)
```

---

## Security Model

- MCP servers run with the **same permissions as the user who launched them**
- stdio servers are local — no network exposure by default
- HTTP servers need proper auth (API keys, OAuth) — same as any web service
- The LLM cannot directly access the server — everything goes through the client host

Think of it like `kubectl exec` — powerful, scoped to what the process can access.
