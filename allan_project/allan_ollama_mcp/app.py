"""FastAPI HTTP service: Ollama chat and SQLite-backed sessions.

Environment (in addition to OLLAMA_* and MCP_DATABASE_PATH):

  API_HOST                    Bind address (default: 127.0.0.1)
  API_PORT                    Port (default: 8000)
  MCP_REMOTE_SERVERS_CONFIG   Optional JSON file listing stdio MCP servers to merge as Ollama tools
  OLLAMA_TOOLS_MAX_ROUNDS     Max tool round-trips per chat request (default: 12)
  ALLAN_AGENT_MAX_REPLANS     Max replan rounds after verifier (default: 2)
  ALLAN_AGENT_TRACE_MD        Write human-readable traces under data/traces/ (default: 1)
  ALLAN_AGENT_MEMORY_WRITE    Persist turn summaries to markdown + FTS (default: 1)
  ALLAN_MEMORY_DIR            Override durable memory root directory
  ALLAN_CAPABILITY_SCORE_MIN  Min intent→tool score before clarification (default: 0.18)

HTTP (local dev, no auth):

  GET  /mcp/remotes-config   Path + current JSON (or empty template in UI)
  PUT  /mcp/remotes-config   Body ``{\"content\": \"...\"}`` writes file and reloads MCP hub
  GET  /mcp/remote-tools?refresh=true   Re-list tools from each configured server
  GET  /sessions/{id}/agent-trace       Phases + step events + handoffs (SQLite audit)

Run ``uv run allan-api``, then open ``/`` or ``/chat`` in the browser for the **allan_project** chat UI.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from . import database, ollama_service
from .mcp_hub import (
    get_default_hub,
    read_remote_config_raw,
    remote_config_path,
    write_remote_config_raw,
)
from .ollama_service import SessionNotFoundError


@asynccontextmanager
async def lifespan(_: FastAPI):
    await database.init_db()
    yield


app = FastAPI(
    title="allan_project",
    version="0.1.0",
    lifespan=lifespan,
)

_CHAT_HTML = (Path(__file__).resolve().parent / "static" / "chat.html").read_text(
    encoding="utf-8"
)


@app.get("/")
async def root() -> RedirectResponse:
    """Open the chat UI by default."""
    return RedirectResponse(url="/chat", status_code=302)


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui() -> str:
    """Browser chat window: prompts go to Ollama through ``POST /chat``."""
    return _CHAT_HTML


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "database": str(database.DB_PATH)}


class McpRemotesConfigPut(BaseModel):
    """Raw JSON body for ``mcp_remote_servers.json`` (must include a ``servers`` array)."""

    content: str = Field(..., description="Full file contents as JSON text")


@app.get("/mcp/remotes-config")
async def get_mcp_remotes_config() -> dict[str, Any]:
    """Read the MCP stdio servers config file path and contents (local dev; no auth)."""
    path = remote_config_path()
    exists, text = read_remote_config_raw()
    return {
        "path": str(path),
        "exists": exists,
        "content": text,
    }


@app.put("/mcp/remotes-config")
async def put_mcp_remotes_config(body: McpRemotesConfigPut) -> dict[str, Any]:
    """Write MCP stdio servers JSON and reload the in-process hub."""
    try:
        written = write_remote_config_raw(body.content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "path": str(written)}


@app.get("/mcp/remote-tools")
async def mcp_remote_tools(
    refresh: Annotated[bool, Query(description="Bypass cache and re-list from each server")] = False,
) -> dict[str, Any]:
    """Discover tools from configured external MCP servers (stdio)."""
    hub = get_default_hub()
    if not hub.has_servers():
        return {"configured": False, "tools": []}
    tools, _ = await hub.list_ollama_tools_and_routes(force_refresh=refresh)
    out = []
    for t in tools:
        fn = t.get("function") or {}
        out.append({"name": fn.get("name"), "description": fn.get("description") or ""})
    return {"configured": True, "tools": out}


@app.get("/models")
async def list_models() -> dict[str, list[str]]:
    try:
        models = await ollama_service.list_model_names()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=e.response.text[:4000]) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"models": models}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: str | None = None
    system: str | None = None
    session_id: str | None = None
    history_limit: int = Field(40, ge=1, le=500)
    use_mcp_tools: bool = False
    use_agent_pipeline: bool = Field(
        default=False,
        description=(
            "Structured agent flow: preparse → intents → capabilities → plan → "
            "execute/verify/replan → evidence-based reply → durable memory."
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    session_id: str | None = Field(
        default=None,
        description="Echo of the session used for SQLite persistence (null if none was sent).",
    )
    orchestration: dict[str, Any] | None = Field(
        default=None,
        description="Agent-pipeline trace (intent, policy, pipeline stages) when use_agent_pipeline is true.",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    try:
        turn = await ollama_service.chat_with_optional_session(
            message=body.message,
            model=body.model,
            system=body.system,
            session_id=body.session_id,
            history_limit=body.history_limit,
            use_mcp_tools=body.use_mcp_tools,
            use_agent_pipeline=body.use_agent_pipeline,
        )
        reply = turn.reply
        orch = turn.orchestration
    except SessionNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown session_id: {e.session_id!r}",
        ) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=e.response.text[:4000]) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    sid_echo = (body.session_id or "").strip() or None
    return ChatResponse(reply=reply, session_id=sid_echo, orchestration=orch)


class SessionCreate(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str
    message_count: int = 0


@app.post("/sessions", response_model=SessionOut)
async def create_session(body: SessionCreate) -> SessionOut:
    sid = await database.create_session(body.title)
    row = await database.get_session(sid)
    if row is None:
        raise HTTPException(status_code=500, detail="Session created but not readable")
    return SessionOut(id=row[0], title=row[1], created_at=row[2])


@app.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[SessionOut]:
    rows = await database.list_sessions(limit)
    return [
        SessionOut(id=r[0], title=r[1], created_at=r[2], message_count=r[3]) for r in rows
    ]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    model: str | None = None
    tool_name: str | None = None
    has_tool_calls: bool = False


class AgentTurnLogOut(BaseModel):
    id: int
    phase: str
    payload: dict[str, Any]
    created_at: str


class AgentStepEventOut(BaseModel):
    id: int
    correlation_id: str
    step_id: str
    state: str
    tool_name: str | None = None
    detail: dict[str, Any]
    latency_ms: int | None = None
    created_at: str


class AgentHandoffOut(BaseModel):
    id: int
    correlation_id: str
    status: str
    detail: dict[str, Any]
    created_at: str


class AgentTraceBundle(BaseModel):
    session_id: str
    turn_logs: list[AgentTurnLogOut]
    step_events: list[AgentStepEventOut]
    handoffs: list[AgentHandoffOut]


@app.get("/sessions/{session_id}/agent-trace", response_model=AgentTraceBundle)
async def get_agent_trace(
    session_id: str,
    log_limit: Annotated[int, Query(ge=1, le=500)] = 120,
    event_limit: Annotated[int, Query(ge=1, le=500)] = 200,
    handoff_limit: Annotated[int, Query(ge=1, le=300)] = 80,
) -> AgentTraceBundle:
    """SQLite-backed orchestration audit: phases, step events, and delegate handoffs."""
    sid = session_id.strip()
    if not await database.session_exists(sid):
        raise HTTPException(status_code=404, detail="Unknown session")
    log_rows = await database.list_agent_turn_logs(sid, limit=log_limit)
    ev_rows = await database.list_agent_step_events(sid, limit=event_limit)
    ho_rows = await database.list_agent_handoffs(sid, limit=handoff_limit)
    return AgentTraceBundle(
        session_id=sid,
        turn_logs=[
            AgentTurnLogOut(id=i, phase=p, payload=payload, created_at=ts)
            for i, p, payload, ts in log_rows
        ],
        step_events=[
            AgentStepEventOut(
                id=i,
                correlation_id=corr,
                step_id=step_id,
                state=st,
                tool_name=tn,
                detail=detail,
                latency_ms=lat,
                created_at=ts,
            )
            for i, corr, step_id, st, tn, detail, lat, ts in ev_rows
        ],
        handoffs=[
            AgentHandoffOut(id=i, correlation_id=corr, status=st, detail=detail, created_at=ts)
            for i, corr, st, detail, ts in ho_rows
        ],
    )


@app.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[MessageOut]:
    sid = session_id.strip()
    if not await database.session_exists(sid):
        raise HTTPException(status_code=404, detail="Unknown session")
    rows = await database.get_messages_display(sid, limit)
    return [
        MessageOut(
            id=mid,
            role=role,
            content=content,
            created_at=created_at,
            model=model,
            tool_name=tool_name,
            has_tool_calls=bool(tc_json),
        )
        for mid, role, content, created_at, model, tool_name, tc_json in rows
    ]


class MessageAppend(BaseModel):
    role: str
    content: str = Field(default="", max_length=500_000)
    model: str | None = None
    tool_name: str | None = None


_ROLES = frozenset({"user", "assistant", "system", "tool"})


@app.post("/sessions/{session_id}/messages", response_model=dict[str, int])
async def append_message(session_id: str, body: MessageAppend) -> dict[str, int]:
    sid = session_id.strip()
    role = body.role.strip().lower()
    if role not in _ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(sorted(_ROLES))}",
        )
    if role == "tool" and not (body.tool_name or "").strip():
        raise HTTPException(status_code=400, detail="tool_name is required when role is tool")
    if role != "tool" and not (body.content or "").strip():
        raise HTTPException(status_code=400, detail="content is required for this role")
    if not await database.session_exists(sid):
        raise HTTPException(status_code=404, detail="Unknown session")
    tn = (body.tool_name or "").strip() or None
    mid = await database.append_message(
        sid,
        role,
        body.content,
        body.model,
        tool_name=tn if role == "tool" else None,
    )
    return {"id": mid}


def serve() -> None:
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    import uvicorn

    uvicorn.run(
        "allan_ollama_mcp.app:app",
        host=host,
        port=port,
        factory=False,
    )


if __name__ == "__main__":
    serve()
