#!/usr/bin/env python3
"""
Lab 04: Full DevOps MCP Server
================================
Build a production-grade MCP server combining everything from this session:
  - Multiple tools (read + write)
  - Resources (static + dynamic)
  - Structured error handling
  - A complete Claude client that uses the server

This is the capstone lab. By the end, you'll have a server you could
wire into Claude Desktop today and start using for real incident work.

Run the server alone:
    fastmcp dev lab.py      # browser inspector
    python lab.py           # stdio

Run the full demo (server + Claude client):
    python lab.py --demo

When stuck: check solution.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Data — simulates what you'd pull from real monitoring / CMDB systems
# ---------------------------------------------------------------------------

INCIDENTS = {
    "INC-2001": {
        "severity": "SEV1",
        "service": "payments",
        "environment": "prod",
        "status": "open",
        "owner": None,
        "summary": "Payment processing failure — 100% error rate on checkout",
        "created_at": "2024-01-15T16:00:00Z",
        "history": ["16:00 - Alert fired", "16:01 - SEV1 auto-declared"],
    },
    "INC-2002": {
        "severity": "SEV2",
        "service": "auth",
        "environment": "prod",
        "status": "investigating",
        "owner": "sre-alice",
        "summary": "Login latency spike — P99 above 2s",
        "created_at": "2024-01-15T15:45:00Z",
        "history": ["15:45 - Alert fired", "15:50 - Assigned to sre-alice"],
    },
}

DEPLOYMENTS = {
    "payments": {
        "prod": {
            "version": "v2.14.1",
            "deployed_at": "2024-01-15T15:55:00Z",  # 5 min before incident
            "deployed_by": "ci-bot",
            "status": "complete",
        },
        "staging": {
            "version": "v2.14.2",
            "deployed_at": "2024-01-15T14:00:00Z",
            "deployed_by": "sre-bob",
            "status": "complete",
        },
    },
    "auth": {
        "prod": {
            "version": "v3.7.0",
            "deployed_at": "2024-01-14T10:00:00Z",
            "deployed_by": "ci-bot",
            "status": "complete",
        },
    },
}

RUNBOOKS = {
    "payments": """# Payments Incident Runbook
## Quick Checks
1. kubectl get pods -n payments | grep -v Running
2. Check error logs: kubectl logs -l app=payments -n payments --since=10m | grep ERROR
3. Check recent deployment: kubectl rollout history deploy/payments -n payments

## Rollback Procedure
kubectl rollout undo deploy/payments -n payments
kubectl rollout status deploy/payments -n payments

## Escalation
- P1: page payments-oncall immediately
- P2: ping #payments-team, expect response in 15min
""",
    "auth": """# Auth Incident Runbook
## Quick Checks
1. kubectl get pods -n auth | grep -v Running
2. Check Redis connectivity: redis-cli -h redis.auth.svc ping
3. Check token validation errors: kubectl logs -l app=auth -n auth --since=10m

## Rollback Procedure
kubectl rollout undo deploy/auth -n auth

## Escalation
- Any severity: ping #platform-team in Slack
""",
}


# ---------------------------------------------------------------------------
# TODO 1: Create the FastMCP server
# ---------------------------------------------------------------------------
# Name it "devops-ops", instructions should explain what it does.
#
mcp = None  # replace this


# ---------------------------------------------------------------------------
# TODO 2: Tool — get_incident
# ---------------------------------------------------------------------------
# @mcp.tool() that:
# - Takes: incident_id (str)
# - Returns the full incident dict
# - Returns {"error": "..."} if not found
#
# Hint: same pattern as labs 01-02.
#


# ---------------------------------------------------------------------------
# TODO 3: Tool — list_open_incidents
# ---------------------------------------------------------------------------
# @mcp.tool() that:
# - Takes: severity (str, optional, default None)
# - Returns all incidents with status != "resolved"
# - If severity is given, also filter by that severity
# - Returns {"count": N, "incidents": [...]}
#


# ---------------------------------------------------------------------------
# TODO 4: Tool — get_recent_deployment
# ---------------------------------------------------------------------------
# @mcp.tool() that:
# - Takes: service (str), environment (str, default "prod")
# - Returns the most recent deployment info for that service/env
# - Returns {"error": "..."} if service or environment not found
#


# ---------------------------------------------------------------------------
# TODO 5: Tool — claim_incident (write action with side effect)
# ---------------------------------------------------------------------------
# @mcp.tool() that:
# - Takes: incident_id (str), responder (str)
# - Updates the incident in INCIDENTS: set owner=responder, status="investigating"
# - Appends to history: "Claimed by {responder}"
# - Returns {"claimed": True, "incident_id": ..., "responder": ..., "status": ...}
# - Returns {"error": "..."} if not found
#


# ---------------------------------------------------------------------------
# TODO 6: Resource — runbook for a service
# ---------------------------------------------------------------------------
# @mcp.resource("runbook://{service}") that:
# - Returns the runbook text for the given service
# - Returns "Runbook not found for {service}" if missing
#


# ---------------------------------------------------------------------------
# Claude MCP client (same pattern as Lab 03) — already complete
# ---------------------------------------------------------------------------

def mcp_tools_to_anthropic(mcp_tools) -> list[dict]:
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
        for t in mcp_tools
    ]


async def call_mcp_tool(session: ClientSession, name: str, input_args: dict) -> str:
    result = await session.call_tool(name, input_args)
    if result.content:
        return result.content[0].text
    return "no result"


async def run_demo(session: ClientSession) -> None:
    """Run a demonstration conversation showing the complete DevOps MCP workflow."""
    client = anthropic.Anthropic()

    tools_resp = await session.list_tools()
    tools = mcp_tools_to_anthropic(tools_resp.tools)

    prompt = (
        "I just got paged. What SEV1 incidents are open right now? "
        "For each one, check whether there was a recent deployment that might have caused it. "
        "Then claim the most critical one for responder 'sre-student'."
    )

    print(f"\nUser: {prompt}")
    print("-" * 50)

    messages = [{"role": "user", "content": prompt}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nClaude: {block.text}")
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"\n[Tool] {block.name}({json.dumps(block.input)})")
            result_text = await call_mcp_tool(session, block.name, block.input)
            print(f"[Result] {result_text[:300]}{'...' if len(result_text) > 300 else ''}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})


async def main_demo() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    if mcp is None:
        print("TODOs not complete — create the FastMCP server first (TODO 1).")
        sys.exit(1)

    print("Lab 04: Full DevOps MCP Server — Demo Mode")
    print("=" * 50)
    print("Starting MCP server as subprocess and connecting Claude...")

    server_params = StdioServerParameters(
        command="python",
        args=[__file__],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            resources = await session.list_resources()
            print(f"\nServer exposes {len(tools.tools)} tools, {len(resources.resources)} resources:")
            for t in tools.tools:
                print(f"  [tool]     {t.name}")
            for r in resources.resources:
                print(f"  [resource] {r.uri}")

            await run_demo(session)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        asyncio.run(main_demo())
    else:
        if mcp is None:
            print("TODO 1 not complete — create the FastMCP instance first.")
        else:
            print("Starting DevOps MCP server (stdio mode)...")
            print("Tip: 'fastmcp dev lab.py' for browser inspector, 'python lab.py --demo' for full demo.")
            mcp.run()
