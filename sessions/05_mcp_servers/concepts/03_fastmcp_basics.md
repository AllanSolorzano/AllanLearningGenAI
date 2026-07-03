# 03. FastMCP Basics

FastMCP is a Python framework that makes building MCP servers as easy as decorating functions.
Without it, you'd write hundreds of lines of JSON-RPC boilerplate. With it: a few decorators.

---

## Install

```bash
pip install fastmcp
```

FastMCP brings:
- `FastMCP` class — your server
- `@mcp.tool()` — expose a function as a Tool
- `@mcp.resource()` — expose data as a Resource
- `@mcp.prompt()` — expose a prompt template
- `fastmcp dev` CLI — local dev with browser inspector
- `fastmcp run` CLI — run a server file

---

## Minimal Server

```python
from fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

if __name__ == "__main__":
    mcp.run()   # stdio transport by default
```

Run it:
```bash
python server.py               # stdio — pipe JSON-RPC in/out
fastmcp dev server.py          # opens browser inspector UI at localhost:5173
fastmcp run server.py          # same as python server.py
```

---

## Tool Decorator

`@mcp.tool()` introspects the function signature automatically.

```python
@mcp.tool()
def get_incident(incident_id: str, include_history: bool = False) -> dict:
    """
    Look up an incident by its ID.

    Args:
        incident_id: The incident identifier (e.g., INC-1001)
        include_history: Whether to include event history
    """
    data = INCIDENT_DB.get(incident_id)
    if not data:
        return {"error": f"Incident {incident_id} not found"}
    if not include_history:
        data = {k: v for k, v in data.items() if k != "history"}
    return data
```

FastMCP generates the JSON schema from:
- **Type hints** → parameter types
- **Default values** → optional vs required
- **Docstring** → tool + parameter descriptions

No manual schema writing needed.

---

## Type Hints FastMCP Understands

```python
@mcp.tool()
def example(
    name: str,                    # required string
    count: int = 10,              # optional int with default
    enabled: bool = True,         # optional bool
    tags: list[str] = None,       # optional list
    severity: str = "SEV3",       # optional with string default
) -> dict:
    ...
```

Use Pydantic models for complex input validation:
```python
from pydantic import BaseModel

class IncidentFilter(BaseModel):
    severity: str
    service: str
    limit: int = 20

@mcp.tool()
def search_incidents(filters: IncidentFilter) -> list[dict]:
    """Search incidents by criteria."""
    ...
```

---

## Resource Decorator

Resources are data endpoints — like files or database records the model can read.

```python
@mcp.resource("runbook://payments/restart")
def get_payment_restart_runbook() -> str:
    """Runbook for restarting the payments service."""
    return """
    # Payments Restart Runbook
    1. Drain existing connections: kubectl drain payments-*
    2. Scale down: kubectl scale deploy payments --replicas=0
    3. Scale up: kubectl scale deploy payments --replicas=3
    4. Verify: kubectl rollout status deploy/payments
    """
```

Resource URIs work like URLs. You can use templates:
```python
@mcp.resource("incident://{incident_id}")
def get_incident_resource(incident_id: str) -> str:
    """Fetch incident as a readable document."""
    data = INCIDENT_DB.get(incident_id, {})
    return f"Incident {incident_id}: {data}"
```

---

## Prompt Decorator

Prompts are reusable, parameterized message templates.

```python
from mcp.types import GetPromptResult, PromptMessage, TextContent

@mcp.prompt()
def diagnose_incident(severity: str, service: str) -> str:
    """Generate a diagnostic prompt for an incident."""
    return f"""You are an SRE on-call. 
A {severity} incident has been detected on the {service} service.

Please:
1. Check recent deployments
2. Review error rates
3. Identify the probable root cause
4. Recommend immediate mitigation steps"""
```

---

## Server Configuration

```python
mcp = FastMCP(
    name="devops-tools",           # server name (shown to clients)
    instructions="DevOps tools for incident management and deployment checks.",
)
```

`instructions` is shown to the model when it connects — use it to explain what the server does.

---

## Running Modes

```python
# stdio (default) — for Claude Desktop, subprocess clients
mcp.run()
mcp.run(transport="stdio")

# HTTP + SSE — for remote/shared access
mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

---

## Development Workflow

```bash
# 1. Write your server
vim server.py

# 2. Test interactively with the MCP inspector
fastmcp dev server.py
# Opens http://localhost:5173 — browser UI to call tools manually

# 3. Run it for real
fastmcp run server.py
# or just: python server.py
```

The MCP inspector lets you call each tool and inspect the schema before wiring up Claude.
Think of it like Postman for your MCP server.

---

## Error Handling

Return errors as dicts — the model can read them and respond:

```python
@mcp.tool()
def get_pod_status(namespace: str, pod_name: str) -> dict:
    """Get Kubernetes pod status."""
    try:
        # ... kubectl call ...
        return {"status": "Running", "restarts": 0}
    except Exception as e:
        return {"error": str(e), "namespace": namespace, "pod": pod_name}
```

Raise exceptions for truly unexpected failures — FastMCP catches and formats them.

---

## Async Support

FastMCP supports async functions natively:

```python
import httpx

@mcp.tool()
async def check_service_health(url: str) -> dict:
    """Check if a service URL is healthy."""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=5.0)
            return {"status": r.status_code, "healthy": r.status_code == 200}
        except Exception as e:
            return {"error": str(e), "healthy": False}
```

Sync and async tools can coexist in the same server.
