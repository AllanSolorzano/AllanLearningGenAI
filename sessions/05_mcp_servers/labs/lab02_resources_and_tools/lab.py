#!/usr/bin/env python3
"""
Lab 02: Resources and Tools
============================
Extend your MCP server with Resources — URI-addressable data the model can read.

Comparison:
  Tools    = kubectl exec (actions, possibly with side effects)
  Resources = S3 objects / ConfigMaps (read-only, addressed by URI)

Function calling has no equivalent of Resources. With function calling,
you had to inject all context into the prompt yourself. With MCP Resources,
the model can request exactly what it needs, when it needs it.

Run:
    # MCP Inspector (FastMCP 2.x): from this directory, reuse lab01’s venv:
    #   export PATH="../lab01_first_mcp_server/.venv/bin:$PATH"
    #   fastmcp dev inspector lab.py
    # Or: fastmcp dev inspector lab.py  (if fastmcp is already on your PATH)
    python lab.py           # stdio mode

When stuck: check solution.py
"""

from fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

INCIDENT_DB = {
    "INC-1001": {
        "severity": "SEV2",
        "service": "payments",
        "status": "investigating",
        "owner": "payments-team",
        "history": ["14:30 - Alert fired", "14:35 - On-call paged", "14:45 - Investigation started"],
    },
    "INC-1002": {
        "severity": "SEV1",
        "service": "auth",
        "status": "mitigating",
        "owner": "platform-team",
        "history": ["15:00 - Alert fired", "15:02 - SEV1 declared", "15:10 - Rollback initiated"],
    },
}

RUNBOOKS = {
    "payments": {
        "restart": """
# Payments Service Restart Runbook
1. Check current pod status: kubectl get pods -n payments
2. Drain connections: kubectl annotate svc payments traffic=draining
3. Scale down: kubectl scale deploy payments --replicas=0 -n payments
4. Wait 30s for connections to drain
5. Scale up: kubectl scale deploy payments --replicas=3 -n payments
6. Verify: kubectl rollout status deploy/payments -n payments
7. Update incident: mark mitigating
""",
        "rollback": """
# Payments Service Rollback Runbook
1. Identify last good deployment: kubectl rollout history deploy/payments
2. Rollback: kubectl rollout undo deploy/payments -n payments
3. Monitor for 5 minutes: kubectl logs -f -l app=payments -n payments
4. Verify error rate drops in Grafana
""",
    },
    "auth": {
        "restart": """
# Auth Service Restart Runbook
1. Alert auth team in #auth-oncall before restarting
2. Check active sessions: redis-cli keys 'session:*' | wc -l
3. Scale down: kubectl scale deploy auth --replicas=0 -n auth
4. Scale up: kubectl scale deploy auth --replicas=5 -n auth
5. Verify login flows work: curl https://internal.auth/health
""",
    },
}


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "incident-runbooks",
    instructions="Incident management tools and runbook library.",
)


# ---------------------------------------------------------------------------
# TODO 1: Add a tool — get_incident_details
# ---------------------------------------------------------------------------
# Decorate with @mcp.tool()
# - Takes: incident_id (str)
# - Returns: the full incident dict including history
# - Returns {"error": "..."} if not found
#
def get_incident_details(incident_id: str) -> dict:
    """
    TODO: Write a clear tool description here.
    """
    data = INCIDENT_DB.get(incident_id)
    if not data:
        return {"error": f"Incident {incident_id} not found"}
    return {"incident_id": incident_id, **data}


# ---------------------------------------------------------------------------
# TODO 2: Add a Static Resource — runbook index
# ---------------------------------------------------------------------------
# Use @mcp.resource("runbooks://index") to expose a text summary
# listing all available runbooks (which services + which runbook types).
#
# The client can call: read_resource("runbooks://index")
# to discover what runbooks exist before fetching a specific one.
#
# Hint:
#   @mcp.resource("runbooks://index")
#   def list_runbooks() -> str:
#       """Index of available runbooks."""
#       ...
#
# Build a readable text listing like:
#   payments: restart, rollback
#   auth: restart
#


# ---------------------------------------------------------------------------
# TODO 3: Add a Dynamic Resource — specific runbook
# ---------------------------------------------------------------------------
# Use a URI template so the client can request any runbook by service + type.
# URI: "runbook://{service}/{runbook_type}"
#
# Example: read_resource("runbook://payments/restart")
#          → returns the payments restart runbook text
#
# Return {"error": "..."} as a string if service or runbook_type not found.
#
# Hint:
#   @mcp.resource("runbook://{service}/{runbook_type}")
#   def get_runbook(service: str, runbook_type: str) -> str:
#       ...
#


# ---------------------------------------------------------------------------
# TODO 4: Add a tool — acknowledge_incident (write action)
# ---------------------------------------------------------------------------
# Write a new @mcp.tool() that:
# - Is named: acknowledge_incident
# - Takes: incident_id (str), responder (str)
# - Updates the incident's status to "acknowledged" in INCIDENT_DB
# - Adds a note to the history list
# - Returns {"acknowledged": True, "incident_id": ..., "responder": ...}
# - Returns {"error": "..."} if the incident doesn't exist
#
# This illustrates the difference from resources:
# - Resources = read only
# - Tools = can have side effects (mutations, API calls, etc.)
#


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting MCP server (stdio mode)...")
    print("Tip: run 'fastmcp dev inspector lab.py' to open the MCP Inspector.")
    mcp.run()
