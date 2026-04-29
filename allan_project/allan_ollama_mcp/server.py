"""MCP server (stdio) exposing tools that call a local Ollama LLM and SQLite storage.

Environment variables:
  OLLAMA_HOST                 Base URL for Ollama (default: http://127.0.0.1:11434)
  OLLAMA_MODEL                Default model when ``model`` is omitted (default: llama3.2)
  MCP_DATABASE_PATH           SQLite file path (default: ./data/app.db next to this project)
  MCP_REMOTE_SERVERS_CONFIG   JSON list of stdio MCP servers (default: ./mcp_remote_servers.json)
  OLLAMA_TOOLS_MAX_ROUNDS     Cap on tool-call turns (default: 12)

Use a `tools`-capable model from https://ollama.com/search?c=tools for ``use_mcp_tools=true``.

Run from ``allan_project``:

  uv run python -m allan_ollama_mcp.server

Cursor MCP (``~/.cursor/mcp.json`` fragment):

  "ollama-chat": {
    "command": "uv",
    "args": ["run", "python", "-m", "allan_ollama_mcp.server"],
    "cwd": "/absolute/path/to/allan_project"
  }
"""

from __future__ import annotations

import asyncio
import json

from mcp.server.fastmcp import FastMCP

from . import database, ollama_service
from .mcp_hub import get_default_hub
from .ollama_service import SessionNotFoundError

mcp = FastMCP("Ollama Chat")

_ROLES = frozenset({"user", "assistant", "system", "tool"})


@mcp.tool()
async def chat(
    message: str,
    model: str | None = None,
    system: str | None = None,
    session_id: str | None = None,
    history_limit: int = 40,
    use_mcp_tools: bool = False,
) -> str:
    """Send a user message to Ollama and return the assistant reply.

    If ``session_id`` is set (from ``db_create_session``), prior messages in that session
    are sent as context (up to ``history_limit``), then this user turn and the reply
    are stored in the database.

    Set ``use_mcp_tools`` to true to let a tools-capable Ollama model call MCP tools from
    ``mcp_remote_servers.json`` (see ``list_remote_mcp_tools``).

    Start Ollama (`ollama serve`) and pull a model first, e.g. `ollama pull llama3.2`.
    """
    try:
        turn = await ollama_service.chat_with_optional_session(
            message=message,
            model=model,
            system=system,
            session_id=session_id,
            history_limit=history_limit,
            use_mcp_tools=use_mcp_tools,
        )
        return turn.reply
    except SessionNotFoundError:
        return (
            f"Unknown session_id: {session_id!r}. "
            "Create one with db_create_session first."
        )


@mcp.tool()
async def list_models() -> str:
    """Return names of models installed in the local Ollama instance (one per line)."""
    names = await ollama_service.list_model_names()
    return "\n".join(names) if names else "(no models reported by Ollama)"


@mcp.tool()
async def list_remote_mcp_tools() -> str:
    """List tools from external MCP servers configured in mcp_remote_servers.json.

    Names are ``serverId__toolName`` and can be passed to ``invoke_remote_mcp_tool`` or used
    when ``chat(..., use_mcp_tools=true)`` with a tools-capable Ollama model.
    """
    hub = get_default_hub()
    if not hub.has_servers():
        return "(no MCP_REMOTE_SERVERS_CONFIG / mcp_remote_servers.json servers configured)"
    tools, _, _ = await hub.list_ollama_tools_and_routes(force_refresh=True)
    if not tools:
        return "(no tools returned from configured MCP servers)"
    lines: list[str] = []
    for t in tools:
        fn = t.get("function") or {}
        lines.append(f"{fn.get('name')}\t{fn.get('description', '')}")
    return "\n".join(lines)


@mcp.tool()
async def invoke_remote_mcp_tool(
    tool_name: str,
    arguments_json: str = "{}",
) -> str:
    """Run one tool on a connected MCP server. ``tool_name`` is e.g. ``filesystem__read_file``.

    ``arguments_json`` must be a JSON object string matching that tool's input schema.
    """
    hub = get_default_hub()
    try:
        args = json.loads(arguments_json) if arguments_json.strip() else {}
        if not isinstance(args, dict):
            return "arguments_json must be a JSON object, e.g. {} or {\"path\": \"/tmp\"}"
        return await hub.invoke_tool(tool_name.strip(), args)
    except json.JSONDecodeError as e:
        return f"Invalid JSON arguments: {e}"
    except KeyError as e:
        return str(e)
    except Exception as e:
        return f"MCP error: {e}"


@mcp.tool()
async def db_create_session(title: str | None = None) -> str:
    """Create a new chat session. Returns ``session_id`` for ``chat`` and other db tools."""
    return await database.create_session(title)


@mcp.tool()
async def db_list_chat_sessions(limit: int = 20) -> str:
    """List recent chat sessions: id, title, created_at (ISO) per line, tab-separated."""
    rows = await database.list_sessions(limit)
    if not rows:
        return "(no sessions yet)"
    lines = ["id\ttitle\tcreated_at\tmessage_count"]
    for sid, title, created, n in rows:
        lines.append(f"{sid}\t{title}\t{created}\t{n}")
    return "\n".join(lines)


@mcp.tool()
async def db_get_chat_messages(session_id: str, limit: int = 100) -> str:
    """Fetch the latest ``limit`` messages for a session (chronological): id, role, time, model, body."""
    sid = session_id.strip()
    if not await database.session_exists(sid):
        return f"Unknown session_id: {sid!r}"
    rows = await database.get_messages_display(sid, limit)
    if not rows:
        return "(no messages in this session)"
    parts: list[str] = []
    for mid, role, content, created_at, model, tool_name, tc_json in rows:
        extra = []
        if tool_name:
            extra.append(f"tool_name={tool_name!r}")
        if tc_json:
            extra.append("has_tool_calls=true")
        suf = (" " + " ".join(extra)) if extra else ""
        parts.append(f"[{mid}] {role} @ {created_at} model={model!r}{suf}")
        parts.append(content)
        parts.append("")
    return "\n".join(parts).rstrip()


@mcp.tool()
async def db_append_chat_message(
    session_id: str,
    role: str,
    content: str,
    model: str | None = None,
    tool_name: str | None = None,
) -> str:
    """Append a message to a session. ``role`` must be user, assistant, system, or tool.

    For ``role=tool``, set ``tool_name`` to the MCP-style tool id (e.g. ``filesystem__read_file``).
    """
    sid = session_id.strip()
    r = role.strip().lower()
    if r not in _ROLES:
        return f"Invalid role {role!r}; use one of: {', '.join(sorted(_ROLES))}"
    if r == "tool" and not (tool_name or "").strip():
        return "tool_name is required when role is tool"
    if r != "tool" and not (content or "").strip():
        return "content is required for this role"
    if not await database.session_exists(sid):
        return f"Unknown session_id: {sid!r}"
    tn = (tool_name or "").strip() or None
    mid = await database.append_message(
        sid,
        r,
        content,
        model,
        tool_name=tn if r == "tool" else None,
    )
    return f"inserted message id={mid}"


def main() -> None:
    asyncio.run(database.init_db())
    mcp.run()


if __name__ == "__main__":
    main()
