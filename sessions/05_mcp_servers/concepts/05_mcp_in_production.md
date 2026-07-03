# 05. MCP in Production

Building an MCP server is straightforward. Running it reliably for a team is a different story.

---

## Connecting Claude Desktop

Claude Desktop can connect to local MCP servers via its config file.

Config location:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "incident-ops": {
      "command": "python",
      "args": ["/path/to/your/server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "...",
        "DB_HOST": "localhost"
      }
    }
  }
}
```

After saving, restart Claude Desktop. Your server's tools appear automatically.

Multiple servers:
```json
{
  "mcpServers": {
    "incident-ops": {"command": "python", "args": ["incident_server.py"]},
    "k8s-tools":    {"command": "python", "args": ["k8s_server.py"]},
    "runbook-db":   {"command": "python", "args": ["runbook_server.py"]}
  }
}
```

---

## Security

### stdio (Local) — Trust Model

The server runs as the user's own process. It has:
- All the user's file permissions
- All network access the user has
- Any env vars you pass in the config

Treat it like a terminal session — powerful, personal.

### HTTP/SSE (Remote) — Needs Auth

Add authentication before exposing MCP over HTTP:

```python
from fastmcp import FastMCP
from fastmcp.server.auth import BearerAuthProvider

mcp = FastMCP("incident-ops")

# Add bearer token auth
auth = BearerAuthProvider(token="your-secret-token")
mcp.run(transport="sse", auth=auth)
```

Or implement custom middleware for OAuth, API key headers, etc.

### Tool Safety Patterns

```python
READ_ONLY_TOOLS = {"get_incident", "list_incidents", "search_runbooks"}
WRITE_TOOLS = {"acknowledge_incident", "update_severity", "close_incident"}
DESTRUCTIVE_TOOLS = {"restart_service", "rollback_deployment"}

@mcp.tool()
def restart_service(service: str, environment: str) -> dict:
    """Restart a service in a given environment."""
    # Guard: never allow production restarts without explicit confirmation
    if environment == "prod":
        return {
            "status": "requires_confirmation",
            "message": f"Production restart of {service} requires explicit approval.",
            "action": "Call confirm_restart() with the token provided."
        }
    # Proceed with non-prod restart
    return _do_restart(service, environment)
```

Separate read and write tools. Add approval gates for destructive actions.

---

## Deployment Patterns

### Pattern 1: Developer Laptop (stdio)

```
Developer laptop
  └── Claude Desktop
        └── spawns: python incident_server.py  (stdio)
                     └── connects to: company VPN → internal APIs
```

Each developer runs their own server. Zero shared infrastructure.

### Pattern 2: Team Shared Server (HTTP+SSE)

```
Internal host (e.g., k8s pod, EC2)
  └── uvicorn incident_server:app --port 8000
  
Each developer's Claude Desktop
  └── connects to: https://mcp.internal.company.com/sse
```

One server, shared by the whole team. Requires auth.

### Pattern 3: Per-Repo MCP Server

Each repository ships its own MCP server.

```
repo/
├── .mcp/
│   └── server.py         # tools specific to this repo
├── src/
└── README.md
```

Claude Desktop config auto-discovers `.mcp/server.py` in the current project.

---

## Observability

Log every tool call — treat MCP servers like production API services.

```python
import logging
import time
from functools import wraps

logger = logging.getLogger("mcp.server")

def log_tool_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        tool_name = func.__name__
        logger.info(f"tool_call start={tool_name} args={kwargs}")
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"tool_call end={tool_name} elapsed={elapsed:.3f}s")
            return result
        except Exception as e:
            logger.error(f"tool_call error={tool_name} exc={e}")
            raise
    return wrapper

@mcp.tool()
@log_tool_call
def get_incident(incident_id: str) -> dict:
    ...
```

What to log:
- Tool name + arguments (sanitize sensitive values)
- Latency per call
- Error rates by tool
- Calling client identity (if using auth)

---

## Testing MCP Servers

### Unit Testing — Test the Functions Directly

Your tool functions are just Python functions. Test them without MCP:

```python
def test_get_incident():
    result = get_incident("INC-1001")
    assert result["severity"] == "SEV1"

def test_get_incident_not_found():
    result = get_incident("INC-XXXX")
    assert "error" in result
```

### Integration Testing — MCP Inspector

```bash
fastmcp dev server.py
# Open http://localhost:5173
# Call each tool manually, verify responses
```

### End-to-End — Client Test

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_server():
    params = StdioServerParameters(command="python", args=["server.py"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert any(t.name == "get_incident" for t in tools.tools)

asyncio.run(test_server())
```

---

## Common Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| Server not showing in Claude Desktop | Config JSON syntax error | Validate JSON, check `claude_desktop_config.json` |
| Tool not appearing | `@mcp.tool()` missing, function not decorated | Add decorator, restart Claude Desktop |
| Timeout on long tools | Default timeout too short | Use async + `asyncio.wait_for`, or return a job ID |
| "Server disconnected" | Server crashed on startup | Check server logs, test with `fastmcp dev` first |
| Works locally, fails remote | Missing env vars | Add env to HTTP server config, check secrets management |

---

## The Ecosystem

MCP is growing fast. Official servers exist for:
- **GitHub** — issues, PRs, code search
- **Postgres / SQLite** — query databases
- **Filesystem** — read/write local files
- **Slack** — post messages, search channels
- **AWS / GCP / Azure** — cloud operations
- **Kubernetes** — pod/deployment management

Find them at: https://github.com/modelcontextprotocol/servers

Build your own to wrap any internal tool, API, or database your team uses.
