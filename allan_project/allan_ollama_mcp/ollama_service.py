"""Shared Ollama HTTP calls and chat orchestration (MCP + FastAPI)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from . import database
from .mcp_hub import get_default_hub

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")


def _hub():
    return get_default_hub()


class SessionNotFoundError(Exception):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


def _coerce_tool_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        return json.loads(s)
    return {}


def _messages_for_non_tool_model(messages_any: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip tool rows; collapse assistant tool-call turns for models not using tools."""
    plain: list[dict[str, Any]] = []
    for m in messages_any:
        role = str(m.get("role") or "")
        if role == "tool":
            continue
        if role == "assistant" and m.get("tool_calls"):
            c = str(m.get("content") or "").strip()
            plain.append(
                {
                    "role": "assistant",
                    "content": c
                    or "[This turn used MCP tools; replay this chat with a tools model + MCP tools for full detail.]",
                }
            )
            continue
        if role in ("user", "assistant", "system"):
            plain.append({"role": role, "content": str(m.get("content") or "")})
    return plain


async def post_chat(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict[str, Any]],
) -> str:
    response = await client.post(
        f"{OLLAMA_HOST}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=httpx.Timeout(600.0, connect=10.0),
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content
    return response.text


async def _chat_with_tools_loop(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    session_id: str | None,
    persist_model: str,
) -> str:
    max_rounds = int(os.environ.get("OLLAMA_TOOLS_MAX_ROUNDS", "12"))
    hub = _hub()
    sid = (session_id or "").strip() or None
    for _ in range(max_rounds):
        response = await client.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False,
            },
            timeout=httpx.Timeout(600.0, connect=10.0),
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        msg: dict[str, Any] = data.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            messages.append(msg)
            if sid:
                await database.append_message(
                    sid,
                    "assistant",
                    str(msg.get("content") or ""),
                    persist_model,
                    tool_calls_json=json.dumps(tool_calls),
                )
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name")
                raw_args = fn.get("arguments")
                try:
                    args = _coerce_tool_arguments(raw_args)
                    body = await hub.invoke_tool(str(name), args)
                except Exception as exc:
                    body = f"MCP tool error ({name}): {exc}"
                messages.append(
                    {"role": "tool", "tool_name": str(name), "content": body}
                )
                if sid:
                    await database.append_message(
                        sid,
                        "tool",
                        body,
                        None,
                        tool_name=str(name),
                    )
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if content is not None:
            return str(content)
        return response.text
    return "(stopped: exceeded OLLAMA_TOOLS_MAX_ROUNDS without a final reply)"


async def list_model_names() -> list[str]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{OLLAMA_HOST}/api/tags",
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        response.raise_for_status()
        payload = response.json()

    names: list[str] = []
    for entry in payload.get("models") or []:
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


async def chat_with_optional_session(
    message: str,
    model: str | None = None,
    system: str | None = None,
    session_id: str | None = None,
    history_limit: int = 40,
    *,
    use_mcp_tools: bool = False,
    use_agent_pipeline: bool = False,
) -> str:
    use_model = (model or DEFAULT_MODEL).strip()
    sid = (session_id or "").strip()

    history_msgs: list[dict[str, Any]] = []
    if sid:
        if not await database.session_exists(sid):
            raise SessionNotFoundError(sid)
        history_msgs = await database.fetch_messages_for_model(sid, history_limit)

    use_tools = bool(use_mcp_tools and _hub().has_servers())
    tools: list[dict[str, Any]] | None = None
    if use_tools:
        ollama_tools, _ = await _hub().list_ollama_tools_and_routes()
        if ollama_tools:
            tools = ollama_tools
        else:
            use_tools = False

    messages_any: list[dict[str, Any]] = []
    if system and system.strip():
        messages_any.append({"role": "system", "content": system.strip()})
    messages_any.extend(dict(m) for m in history_msgs)
    messages_any.append({"role": "user", "content": message})

    if sid:
        await database.append_message(sid, "user", message, None)

    async with httpx.AsyncClient() as client:
        if use_agent_pipeline and sid:
            from . import agent_orchestrator

            history_for_agent = await database.fetch_messages_for_model(
                sid, history_limit
            )
            reply = await agent_orchestrator.run_agent_turn(
                client,
                session_id=sid,
                user_message=message,
                model=use_model,
                history_msgs=history_for_agent,
                use_mcp_tools=use_mcp_tools,
                system_policy=system,
            )
        elif use_tools and tools:
            reply = await _chat_with_tools_loop(
                client,
                use_model,
                messages_any,
                tools,
                session_id=sid,
                persist_model=use_model,
            )
        else:
            plain = _messages_for_non_tool_model(messages_any)
            reply = await post_chat(client, use_model, plain)

    if sid:
        await database.append_message(sid, "assistant", reply, use_model)

    return reply
