# Session 05: MCP Servers with FastMCP

Build MCP (Model Context Protocol) servers so your tools work with any AI client —
Claude Desktop, Cursor, VS Code, or your own application — without changing a line of server code.

## DevOps Analogy

| MCP Concept | DevOps Equivalent |
|-------------|-------------------|
| MCP Server | gRPC microservice / Kubernetes Deployment |
| MCP Client | API gateway / service consumer |
| Tool | RPC method (has side effects) |
| Resource | S3 object / ConfigMap (read-only, by URI) |
| Prompt | Helm values template |
| stdio transport | Unix domain socket (local IPC) |
| HTTP+SSE transport | REST endpoint behind an ingress |

## Why MCP vs Function Calling?

You already know function calling (Session 04). Here is when you level up to MCP:

| | Function Calling | MCP |
|---|---|---|
| Tool schema | Hardcoded in each API call | Declared once in the server |
| Tool execution | Your code runs the tool | Server runs the tool |
| Who can use it | Only your app | Any MCP client |
| Reusability | None — per-request | Build once, use everywhere |
| Extras | Tools only | Tools + Resources + Prompts |
| State | Stateless | Server can maintain state |

## What You'll Build

- FastMCP servers with tools, resources, and prompt templates
- A Python MCP client that connects Claude to your servers
- A complete DevOps incident management server
- Production-ready patterns: error handling, auth, observability

## Prerequisites

```bash
pip install -r ../../requirements.txt

# Verify your API key
python ../../setup_check.py
```

**Session 05 / FastMCP:** `fastmcp` requires **Python 3.10+**. On macOS, if `python3 --version` shows 3.9.x, use Homebrew’s interpreter when creating a venv, for example: `/opt/homebrew/bin/python3.11 -m venv .venv`.

### One-time: shared venv under `lab01_first_mcp_server` (optional)

Lab 02 in the course often uses a virtualenv next to lab01 so `fastmcp` is on `PATH` without activating the venv each time:

```bash
cd sessions/05_mcp_servers/labs/lab01_first_mcp_server
# Use 3.10+ (adjust path if needed):
/opt/homebrew/bin/python3.11 -m venv .venv
./.venv/bin/pip install -r ../../../../requirements.txt
# Or minimal MCP-only install:
# ./.venv/bin/pip install fastmcp mcp
```

## Session Structure

```
05_mcp_servers/
├── concepts/
│   ├── 01_mcp_vs_function_calling.md   ← Why MCP? Key differences explained
│   ├── 02_mcp_architecture.md          ← Protocol, transports, primitives
│   ├── 03_fastmcp_basics.md            ← FastMCP decorators and dev workflow
│   ├── 04_resources_and_prompts.md     ← Resources vs Tools vs Prompts
│   └── 05_mcp_in_production.md        ← Claude Desktop config, security, deploy
├── labs/
│   ├── lab01_first_mcp_server/         ← Write your first FastMCP server
│   ├── lab02_resources_and_tools/      ← Add Resources alongside Tools
│   ├── lab03_claude_mcp_client/        ← Connect Claude SDK to an MCP server
│   └── lab04_devops_mcp_server/        ← Capstone: full DevOps MCP server
└── demos/
    ├── demo_simple_mcp_server.py        ← Minimal server for Claude Desktop
    ├── demo_incident_mcp_server.py      ← Rich server: tools + resources + prompts
    └── demo_claude_with_mcp.py         ← Claude connected programmatically
```

## Labs

| Lab | Topic | Key Concepts |
|-----|-------|--------------|
| lab01 | First MCP server | `FastMCP`, `@mcp.tool()`, `fastmcp dev inspector` |
| lab02 | Resources and Tools | `@mcp.resource()`, URI templates, read vs write |
| lab03 | Claude as MCP client | `ClientSession`, `stdio_client`, dynamic tool discovery |
| lab04 | Full DevOps server | All primitives combined, `--demo` mode with Claude |

## Demos

| Demo | What it shows |
|------|---------------|
| `demo_simple_mcp_server.py` | Minimal server — great starting point for Claude Desktop |
| `demo_incident_mcp_server.py` | Production-style server with Tools + Resources + Prompts |
| `demo_claude_with_mcp.py` | End-to-end: Claude using the incident server via Python client |

## Quick Start

```bash
cd sessions/05_mcp_servers

# 1. Read the key concept: MCP vs function calling
cat concepts/01_mcp_vs_function_calling.md

# 2. Build your first server
vim labs/lab01_first_mcp_server/lab.py
fastmcp dev inspector labs/lab01_first_mcp_server/lab.py

# 3. Add resources (same as LearningGenAI-2: from lab02, use lab01’s venv on PATH)
cd labs/lab02_resources_and_tools
export PATH="../lab01_first_mcp_server/.venv/bin:$PATH"
fastmcp dev inspector lab.py

# 3b. Or from repo root / 05_mcp_servers without cd+PATH:
# fastmcp dev inspector labs/lab02_resources_and_tools/lab.py

# 4. Connect Claude to an MCP server
python labs/lab03_claude_mcp_client/lab.py

# 5. Build the full DevOps server + run end-to-end
python labs/lab04_devops_mcp_server/lab.py --demo

# Run demos
fastmcp dev inspector demos/demo_simple_mcp_server.py
fastmcp dev inspector demos/demo_incident_mcp_server.py
python demos/demo_claude_with_mcp.py
```

## Connect to Claude Desktop

Once you've built a server, add it to Claude Desktop's config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "incident-ops": {
      "command": "python",
      "args": ["C:/absolute/path/to/demo_incident_mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop → your tools appear automatically in every conversation.

## Development Tip: MCP Inspector

```bash
fastmcp dev inspector your_server.py
```

Opens the **MCP Inspector** (FastMCP proxies it; default UI port **6274**, proxy **6277** — the terminal prints the exact URL and optional auth token). In the browser you can:
- See all tools, resources, and prompts your server exposes
- Call tools manually and inspect the response
- Test schemas before connecting Claude

Think of it as Postman for MCP servers.

## Estimated Time

| Activity | Time |
|----------|------|
| Concepts (5 files) | 40 min |
| Labs (4 labs) | 110 min |
| Demos | 20 min |
| **Total** | **~2.5 hours** |
