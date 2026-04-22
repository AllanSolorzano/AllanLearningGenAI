"""Connect to external MCP servers (stdio) and expose their tools to Ollama / MCP tools.

Config: JSON file (see ``mcp_remote_servers.example.json`` in the project root).

  MCP_REMOTE_SERVERS_CONFIG  Path to JSON (default: ``<project>/mcp_remote_servers.json``)

Each server entry::

  { \"id\": \"myserver\", \"command\": \"npx\", \"args\": [...], \"env\": {}, \"cwd\": null }

Tool names sent to Ollama are prefixed as ``{id}__{tool_name}`` to avoid collisions.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "mcp_remote_servers.json"


@dataclass(frozen=True)
class RemoteServerEntry:
    id: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None
    cwd: str | None = None


def _config_path() -> Path:
    raw = os.environ.get("MCP_REMOTE_SERVERS_CONFIG")
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_CONFIG


def load_remote_servers() -> list[RemoteServerEntry]:
    path = _config_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read MCP remote config %s: %s", path, e)
        return []
    servers = payload.get("servers")
    if not isinstance(servers, list):
        return []
    out: list[RemoteServerEntry] = []
    for raw in servers:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("id") or "").strip()
        cmd = str(raw.get("command") or "").strip()
        args = raw.get("args")
        if not sid or not cmd or not isinstance(args, list):
            continue
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", sid):
            logger.warning("Skipping MCP server id with invalid characters: %r", sid)
            continue
        arg_list = [str(a) for a in args]
        env = raw.get("env")
        env_dict = {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else None
        cwd = raw.get("cwd")
        cwd_str = str(cwd) if cwd else None
        out.append(
            RemoteServerEntry(id=sid, command=cmd, args=arg_list, env=env_dict, cwd=cwd_str)
        )
    return out


def remote_config_path() -> Path:
    """Filesystem path for the MCP stdio servers JSON file."""
    return _config_path()


def read_remote_config_raw() -> tuple[bool, str | None]:
    """Return (file_exists, text_or_none)."""
    path = _config_path()
    if not path.is_file():
        return False, None
    return True, path.read_text(encoding="utf-8")


def strict_validate_servers_json(raw: str) -> dict[str, Any]:
    """Parse and validate MCP remotes JSON; returns normalized dict for writing."""
    try:
        root = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    if not isinstance(root, dict):
        raise ValueError("Root must be a JSON object.")
    if "servers" not in root:
        raise ValueError('Missing required key "servers" (array).')
    servers = root["servers"]
    if not isinstance(servers, list):
        raise ValueError('"servers" must be a JSON array.')
    out: list[dict[str, Any]] = []
    for i, item in enumerate(servers):
        if not isinstance(item, dict):
            raise ValueError(f"servers[{i}] must be an object.")
        sid = str(item.get("id") or "").strip()
        cmd = str(item.get("command") or "").strip()
        args = item.get("args")
        if not sid or not cmd:
            raise ValueError(f"servers[{i}] needs non-empty id and command.")
        if not isinstance(args, list) or len(args) == 0:
            raise ValueError(f"servers[{i}].args must be a non-empty JSON array.")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", sid):
            raise ValueError(f"servers[{i}].id uses invalid characters: {sid!r}")
        arg_list = [str(a) for a in args]
        env = item.get("env")
        env_dict: dict[str, str] | None = None
        if env is not None:
            if not isinstance(env, dict):
                raise ValueError(f"servers[{i}].env must be an object or null.")
            env_dict = {str(k): str(v) for k, v in env.items()}
        cwd = item.get("cwd")
        cwd_str: str | None = str(cwd) if cwd else None
        row: dict[str, Any] = {
            "id": sid,
            "command": cmd,
            "args": arg_list,
            "env": env_dict if env_dict else {},
        }
        if cwd_str:
            row["cwd"] = cwd_str
        out.append(row)
    return {"servers": out}


def write_remote_config_raw(raw: str) -> Path:
    """Validate ``raw`` JSON, write to the configured path, and reset the in-process MCP hub."""
    normalized = strict_validate_servers_json(raw)
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    reset_global_mcp_hub()
    return path


def _mcp_tool_to_ollama(prefixed_name: str, tool: mcp_types.Tool) -> dict[str, Any]:
    params: dict[str, Any]
    schema = tool.inputSchema
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(exclude_none=True)
    if isinstance(schema, dict) and schema:
        params = schema
    else:
        params = {"type": "object", "properties": {}}
    if params.get("type") != "object":
        params = {"type": "object", "properties": {"value": params}}
    return {
        "type": "function",
        "function": {
            "name": prefixed_name,
            "description": (tool.description or tool.title or "").strip() or f"MCP tool {tool.name}",
            "parameters": params,
        },
    }


def _format_tool_result(result: mcp_types.CallToolResult) -> str:
    parts: list[str] = []
    if result.isError:
        parts.append("TOOL_ERROR")
    for block in result.content or []:
        if isinstance(block, mcp_types.TextContent):
            parts.append(block.text)
        else:
            parts.append(block.model_dump_json())
    if result.structuredContent is not None:
        parts.append(json.dumps(result.structuredContent, default=str))
    text = "\n".join(parts).strip()
    if not text:
        text = result.model_dump_json()
    max_len = int(os.environ.get("MCP_TOOL_RESULT_MAX_CHARS", "50000"))
    if len(text) > max_len:
        text = text[: max_len - 80] + "\n…(truncated for context size)"
    return text


class McpHub:
    """Stateless stdio MCP client: spawns a process per list/call (simple lifecycle)."""

    def __init__(self) -> None:
        self._entries = load_remote_servers()
        self._cache: tuple[list[dict[str, Any]], dict[str, tuple[str, str]], float] | None = None
        self._ttl = float(os.environ.get("MCP_TOOLS_CACHE_TTL", "60"))

    def has_servers(self) -> bool:
        return bool(self._entries)

    def _invalidate_cache(self) -> None:
        self._cache = None

    async def list_ollama_tools_and_routes(
        self,
        *,
        force_refresh: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cache is not None
            and now - self._cache[2] < self._ttl
        ):
            return self._cache[0], self._cache[1]

        ollama_tools: list[dict[str, Any]] = []
        routes: dict[str, tuple[str, str]] = {}

        for entry in self._entries:
            params = StdioServerParameters(
                command=entry.command,
                args=entry.args,
                env=entry.env,
                cwd=entry.cwd,
            )
            try:
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        cursor: str | None = None
                        while True:
                            if cursor:
                                lr = await session.list_tools(
                                    params=mcp_types.PaginatedRequestParams(cursor=cursor)
                                )
                            else:
                                lr = await session.list_tools()
                            for t in lr.tools:
                                prefixed = f"{entry.id}__{t.name}"
                                routes[prefixed] = (entry.id, t.name)
                                ollama_tools.append(_mcp_tool_to_ollama(prefixed, t))
                            cursor = getattr(lr, "nextCursor", None)
                            if not cursor:
                                break
            except Exception:
                logger.exception("Failed to list tools from MCP server %r", entry.id)

        self._cache = (ollama_tools, routes, now)
        return ollama_tools, routes

    def _resolve_entry_and_tool(self, prefixed_name: str) -> tuple[RemoteServerEntry, str]:
        for entry in self._entries:
            prefix = f"{entry.id}__"
            if prefixed_name.startswith(prefix):
                return entry, prefixed_name[len(prefix) :]
        raise KeyError(f"Unknown MCP tool: {prefixed_name!r}")

    async def invoke_tool(self, prefixed_name: str, arguments: dict[str, Any]) -> str:
        entry, tool_name = self._resolve_entry_and_tool(prefixed_name)

        params = StdioServerParameters(
            command=entry.command,
            args=entry.args,
            env=entry.env,
            cwd=entry.cwd,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
        self._invalidate_cache()
        return _format_tool_result(result)


_GLOBAL_HUB: McpHub | None = None


def reset_global_mcp_hub() -> None:
    """Drop cached hub so the next access reloads ``mcp_remote_servers.json``."""
    global _GLOBAL_HUB
    _GLOBAL_HUB = None


def get_default_hub() -> McpHub:
    global _GLOBAL_HUB
    if _GLOBAL_HUB is None:
        _GLOBAL_HUB = McpHub()
    return _GLOBAL_HUB
