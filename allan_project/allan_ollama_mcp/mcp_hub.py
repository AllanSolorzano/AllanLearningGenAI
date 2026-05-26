"""Connect to external MCP servers (stdio) and expose their tools to Ollama / MCP tools.

Config: JSON file (see ``mcp_remote_servers.example.json`` in the project root).

  MCP_REMOTE_SERVERS_CONFIG  Path to JSON (default: ``<project>/mcp_remote_servers.json``)

Each server entry::

  { \"id\": \"myserver\", \"command\": \"npx\", \"args\": [...], \"env\": {}, \"cwd\": null,
    \"kind\": \"stdio\", \"label\": \"Human-readable name\" }

Optional ``kind`` (default ``stdio``) and ``label`` are exposed to the planner as
``registered_execution_backends`` for routing visibility. Tool names sent to Ollama are
prefixed as ``{id}__{tool_name}`` to avoid collisions.
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
    kind: str | None = None
    label: str | None = None
    enabled: bool = True


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
        kind_raw = str(raw.get("kind") or "").strip() or None
        label_raw = str(raw.get("label") or "").strip() or None
        en_raw = raw.get("enabled", True)
        enabled = not (
            en_raw is False
            or (isinstance(en_raw, str) and en_raw.strip().lower() in ("0", "false", "no"))
        )
        out.append(
            RemoteServerEntry(
                id=sid,
                command=cmd,
                args=arg_list,
                env=env_dict,
                cwd=cwd_str,
                kind=kind_raw,
                label=label_raw,
                enabled=enabled,
            )
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
        kind_opt = str(item.get("kind") or "").strip()
        if kind_opt:
            row["kind"] = kind_opt
        label_opt = str(item.get("label") or "").strip()
        if label_opt:
            row["label"] = label_opt
        if item.get("enabled") is False:
            row["enabled"] = False
        out.append(row)
    return {"servers": out}


def load_remote_config_dict() -> dict[str, Any]:
    exists, text = read_remote_config_raw()
    if not exists or not text:
        return {"servers": []}
    try:
        root = json.loads(text)
    except json.JSONDecodeError:
        return {"servers": []}
    if not isinstance(root, dict):
        return {"servers": []}
    return root


def write_remote_config_dict(root: dict[str, Any]) -> Path:
    return write_remote_config_raw(json.dumps(root, indent=2))


def set_server_enabled(server_id: str, enabled: bool) -> bool:
    root = load_remote_config_dict()
    servers = root.get("servers")
    if not isinstance(servers, list):
        return False
    found = False
    for item in servers:
        if isinstance(item, dict) and str(item.get("id") or "").strip() == server_id.strip():
            item["enabled"] = bool(enabled)
            found = True
            break
    if not found:
        return False
    write_remote_config_dict(root)
    reset_global_mcp_hub()
    return True


def delete_server(server_id: str) -> bool:
    sid = server_id.strip()
    root = load_remote_config_dict()
    servers = root.get("servers")
    if not isinstance(servers, list):
        return False
    new_list = [
        s for s in servers if isinstance(s, dict) and str(s.get("id") or "").strip() != sid
    ]
    if len(new_list) == len(servers):
        return False
    root["servers"] = new_list
    write_remote_config_dict(root)
    reset_global_mcp_hub()
    return True


def servers_for_api() -> list[dict[str, Any]]:
    """Summary rows for the settings UI."""
    out: list[dict[str, Any]] = []
    for i, e in enumerate(load_remote_servers(), start=1):
        env_n = len(e.env or {})
        cmd_preview = f"{e.command} {json.dumps(e.args)}"
        out.append(
            {
                "index": i,
                "id": e.id,
                "label": (e.label or e.id).strip(),
                "command": e.command,
                "args": e.args,
                "command_preview": cmd_preview[:240],
                "env_count": env_n,
                "enabled": e.enabled,
                "kind": e.kind or "stdio",
            }
        )
    return out


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


def merge_mcp_health_into_backends(
    backends: list[dict[str, Any]],
    server_health: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach ``healthy``, ``tool_count``, optional ``list_error`` from a list-tools probe."""
    by_id = {str(h.get("backend_id") or ""): h for h in server_health if h.get("backend_id")}
    out: list[dict[str, Any]] = []
    for b in backends:
        row = dict(b)
        bid = str(row.get("backend_id") or "")
        h = by_id.get(bid) if bid else None
        if isinstance(h, dict):
            row["healthy"] = bool(h.get("healthy"))
            row["tool_count"] = int(h.get("tool_count") or 0)
            err = h.get("error")
            if err:
                row["list_error"] = str(err)[:800]
        out.append(row)
    return out


class McpHub:
    """Stateless stdio MCP client: spawns a process per list/call (simple lifecycle)."""

    def __init__(self) -> None:
        self._entries = load_remote_servers()
        self._cache: (
            tuple[list[dict[str, Any]], dict[str, tuple[str, str]], float, list[dict[str, Any]]] | None
        ) = None
        self._ttl = float(os.environ.get("MCP_TOOLS_CACHE_TTL", "60"))

    def has_servers(self) -> bool:
        return bool(self._entries)

    def execution_backends_summary(self) -> list[dict[str, Any]]:
        """Planner-visible registry: stdio MCP processes (extensible to more transports later)."""
        out: list[dict[str, Any]] = []
        for e in self._entries:
            if not e.enabled:
                continue
            transport = (e.kind or "stdio").strip() or "stdio"
            out.append(
                {
                    "backend_id": e.id,
                    "transport": transport,
                    "label": (e.label or e.id).strip(),
                    "command": e.command,
                    "args_preview": e.args[:4],
                }
            )
        return out

    def _invalidate_cache(self) -> None:
        self._cache = None

    def invalidate_tools_cache(self) -> None:
        """Drop cached tool list (e.g. after catalog toggle)."""
        self._invalidate_cache()

    def _entry_by_id(self, server_id: str) -> RemoteServerEntry | None:
        sid = server_id.strip()
        for e in self._entries:
            if e.id == sid:
                return e
        return None

    async def _list_mcp_tools_for_entry(
        self, entry: RemoteServerEntry
    ) -> tuple[list[mcp_types.Tool], str | None]:
        """Connect once and return raw MCP tools (or error message)."""
        params = StdioServerParameters(
            command=entry.command,
            args=entry.args,
            env=entry.env,
            cwd=entry.cwd,
        )
        tools: list[mcp_types.Tool] = []
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
                        tools.extend(lr.tools)
                        cursor = getattr(lr, "nextCursor", None)
                        if not cursor:
                            break
            return tools, None
        except Exception as exc:
            logger.exception("Failed to list tools from MCP server %r", entry.id)
            return [], f"{type(exc).__name__}: {exc}"[:800]

    async def discover_tools_for_server(
        self, server_id: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Live list-tools for one server (for UI catalog refresh)."""
        entry = self._entry_by_id(server_id)
        if entry is None:
            raise KeyError(f"Unknown MCP server: {server_id!r}")
        t0 = time.perf_counter()
        if not entry.enabled:
            return [], {
                "backend_id": entry.id,
                "healthy": None,
                "enabled": False,
                "error": "Server is disabled",
                "tool_count": 0,
                "list_latency_ms": 0,
            }
        raw_tools, err = await self._list_mcp_tools_for_entry(entry)
        out: list[dict[str, Any]] = []
        for t in raw_tools:
            prefixed = f"{entry.id}__{t.name}"
            schema = t.inputSchema
            if hasattr(schema, "model_dump"):
                schema = schema.model_dump(exclude_none=True)
            if not isinstance(schema, dict):
                schema = {}
            out.append(
                {
                    "tool_name": t.name,
                    "prefixed_name": prefixed,
                    "description": (t.description or t.title or "").strip()
                    or f"MCP tool {t.name}",
                    "parameters": schema,
                }
            )
        health = {
            "backend_id": entry.id,
            "healthy": err is None,
            "enabled": True,
            "error": err,
            "tool_count": len(out),
            "list_latency_ms": int((time.perf_counter() - t0) * 1000),
        }
        self._invalidate_cache()
        return out, health

    async def list_ollama_tools_and_routes(
        self,
        *,
        force_refresh: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]], list[dict[str, Any]]]:
        """Returns (ollama_tools, routes, server_health). ``server_health`` is one row per configured backend."""
        now = time.monotonic()
        if (
            not force_refresh
            and self._cache is not None
            and now - self._cache[2] < self._ttl
        ):
            return self._cache[0], self._cache[1], self._cache[3]

        from . import mcp_store

        ollama_tools: list[dict[str, Any]] = []
        routes: dict[str, tuple[str, str]] = {}
        server_health: list[dict[str, Any]] = []

        for entry in self._entries:
            t0 = time.perf_counter()
            if not entry.enabled:
                server_health.append(
                    {
                        "backend_id": entry.id,
                        "healthy": None,
                        "enabled": False,
                        "error": None,
                        "tool_count": 0,
                        "list_latency_ms": 0,
                    }
                )
                continue

            raw_tools, err_msg = await self._list_mcp_tools_for_entry(entry)
            tool_filter = await mcp_store.enabled_tool_filter(entry.id)
            n_tools = 0
            for t in raw_tools:
                if tool_filter is not None and not tool_filter.get(t.name, True):
                    continue
                prefixed = f"{entry.id}__{t.name}"
                routes[prefixed] = (entry.id, t.name)
                ollama_tools.append(_mcp_tool_to_ollama(prefixed, t))
                n_tools += 1
            server_health.append(
                {
                    "backend_id": entry.id,
                    "healthy": err_msg is None,
                    "enabled": True,
                    "error": err_msg,
                    "tool_count": n_tools,
                    "list_latency_ms": int((time.perf_counter() - t0) * 1000),
                }
            )

        self._cache = (ollama_tools, routes, now, server_health)
        return ollama_tools, routes, server_health

    def _resolve_entry_and_tool(self, prefixed_name: str) -> tuple[RemoteServerEntry, str]:
        for entry in self._entries:
            prefix = f"{entry.id}__"
            if prefixed_name.startswith(prefix):
                return entry, prefixed_name[len(prefix) :]
        raise KeyError(f"Unknown MCP tool: {prefixed_name!r}")

    async def invoke_tool(self, prefixed_name: str, arguments: dict[str, Any]) -> str:
        from . import mcp_store

        entry, tool_name = self._resolve_entry_and_tool(prefixed_name)
        if not entry.enabled:
            raise RuntimeError(f"MCP server {entry.id!r} is disabled")
        tool_filter = await mcp_store.enabled_tool_filter(entry.id)
        if tool_filter is not None and not tool_filter.get(tool_name, True):
            raise RuntimeError(f"MCP tool {prefixed_name!r} is disabled in catalog")

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
