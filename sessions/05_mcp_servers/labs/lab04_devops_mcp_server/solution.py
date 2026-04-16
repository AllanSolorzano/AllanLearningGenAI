#!/usr/bin/env python3
"""
Lab 04 Solution: Full DevOps MCP Server

Run the server alone:
    fastmcp dev solution.py
    python solution.py

Run the full demo:
    python solution.py --demo
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
# Data
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
            "deployed_at": "2024-01-15T15:55:00Z",
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
# TODO 1 Solution: Create the server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "devops-ops",
    instructions=(
        "DevOps operations tools: incident management, deployment history, "
        "and runbook access for SRE on-call response."
    ),
)


# ---------------------------------------------------------------------------
# TODO 2 Solution: get_incident tool
# ---------------------------------------------------------------------------
@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """
    Get full details for an incident by ID.

    Args:
        incident_id: Incident identifier, e.g. INC-2001
    """
    incident = INCIDENTS.get(incident_id)
    if not incident:
        return {"error": f"Incident {incident_id} not found. Known: {list(INCIDENTS.keys())}"}
    return {"incident_id": incident_id, **incident}


# ---------------------------------------------------------------------------
# TODO 3 Solution: list_open_incidents tool
# ---------------------------------------------------------------------------
@mcp.tool()
def list_open_incidents(severity: str = None) -> dict:
    """
    List all open (non-resolved) incidents, optionally filtered by severity.

    Args:
        severity: Optional severity filter, e.g. SEV1, SEV2. Omit for all severities.
    """
    results = []
    for iid, data in INCIDENTS.items():
        if data["status"] == "resolved":
            continue
        if severity and data["severity"] != severity:
            continue
        results.append({"incident_id": iid, **data})

    results.sort(key=lambda x: x["severity"])  # SEV1 first
    return {"count": len(results), "incidents": results}


# ---------------------------------------------------------------------------
# TODO 4 Solution: get_recent_deployment tool
# ---------------------------------------------------------------------------
@mcp.tool()
def get_recent_deployment(service: str, environment: str = "prod") -> dict:
    """
    Get the most recent deployment info for a service in a given environment.
    Useful for identifying whether a recent deploy caused an incident.

    Args:
        service: Service name, e.g. payments, auth
        environment: Deployment environment — prod or staging (default: prod)
    """
    svc_deploys = DEPLOYMENTS.get(service)
    if not svc_deploys:
        return {"error": f"No deployments found for service '{service}'. Known: {list(DEPLOYMENTS.keys())}"}
    env_deploy = svc_deploys.get(environment)
    if not env_deploy:
        available_envs = list(svc_deploys.keys())
        return {"error": f"No deployment data for {service} in {environment}. Available: {available_envs}"}
    return {
        "service": service,
        "environment": environment,
        **env_deploy,
    }


# ---------------------------------------------------------------------------
# TODO 5 Solution: claim_incident tool
# ---------------------------------------------------------------------------
@mcp.tool()
def claim_incident(incident_id: str, responder: str) -> dict:
    """
    Claim an incident — assign it to a responder and mark it as investigating.
    This is a write action with side effects (mutates incident state).

    Args:
        incident_id: The incident ID to claim
        responder: Username or name of the responder claiming the incident
    """
    incident = INCIDENTS.get(incident_id)
    if not incident:
        return {"error": f"Incident {incident_id} not found"}

    incident["owner"] = responder
    incident["status"] = "investigating"
    incident["history"].append(f"Claimed by {responder}")

    return {
        "claimed": True,
        "incident_id": incident_id,
        "responder": responder,
        "status": "investigating",
    }


# ---------------------------------------------------------------------------
# TODO 6 Solution: runbook resource
# ---------------------------------------------------------------------------
@mcp.resource("runbook://{service}")
def get_runbook(service: str) -> str:
    """
    Fetch the incident runbook for a given service.

    Args:
        service: Service name, e.g. payments, auth
    """
    runbook = RUNBOOKS.get(service)
    if not runbook:
        available = list(RUNBOOKS.keys())
        return f"Runbook not found for '{service}'. Available runbooks: {available}"
    return runbook


# ---------------------------------------------------------------------------
# Claude MCP client
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

    print("Lab 04 Solution: Full DevOps MCP Server — Demo Mode")
    print("=" * 50)

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
        print("Starting DevOps MCP server (stdio mode)...")
        print("Tip: 'fastmcp dev solution.py' for inspector, 'python solution.py --demo' for full demo.")
        mcp.run()
