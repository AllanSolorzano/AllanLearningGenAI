#!/usr/bin/env python3
"""
Lab 02 Solution: Resources and Tools
"""

from fastmcp import FastMCP


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


mcp = FastMCP(
    "incident-runbooks",
    instructions="Incident management tools and runbook library.",
)


# TODO 1 Solution: get_incident_details tool
@mcp.tool()
def get_incident_details(incident_id: str) -> dict:
    """
    Get full details for an incident including event history.

    Args:
        incident_id: The incident ID, e.g. INC-1001
    """
    data = INCIDENT_DB.get(incident_id)
    if not data:
        return {"error": f"Incident {incident_id} not found"}
    return {"incident_id": incident_id, **data}


# TODO 2 Solution: Static resource — runbook index
@mcp.resource("runbooks://index")
def list_runbooks() -> str:
    """Index of all available runbooks, organized by service."""
    lines = ["Available Runbooks\n=================="]
    for service, runbook_types in RUNBOOKS.items():
        types = ", ".join(runbook_types.keys())
        lines.append(f"  {service}: {types}")
    lines.append("\nAccess via URI: runbook://<service>/<type>")
    return "\n".join(lines)


# TODO 3 Solution: Dynamic resource — specific runbook
@mcp.resource("runbook://{service}/{runbook_type}")
def get_runbook(service: str, runbook_type: str) -> str:
    """
    Fetch a specific runbook by service name and runbook type.

    Args:
        service: Service name, e.g. payments, auth
        runbook_type: Runbook type, e.g. restart, rollback
    """
    service_runbooks = RUNBOOKS.get(service)
    if not service_runbooks:
        return f"Error: No runbooks found for service '{service}'. Available: {list(RUNBOOKS.keys())}"
    runbook = service_runbooks.get(runbook_type)
    if not runbook:
        available = list(service_runbooks.keys())
        return f"Error: Runbook type '{runbook_type}' not found for {service}. Available: {available}"
    return runbook


# TODO 4 Solution: acknowledge_incident tool (write action)
@mcp.tool()
def acknowledge_incident(incident_id: str, responder: str) -> dict:
    """
    Acknowledge an incident and assign it to a responder.

    This updates the incident status and adds an acknowledgement entry to its
    history. Unlike resources (which are read-only), tools can have side effects.

    Args:
        incident_id: The incident ID to acknowledge
        responder: Name or username of the responder acknowledging
    """
    incident = INCIDENT_DB.get(incident_id)
    if not incident:
        return {"error": f"Incident {incident_id} not found"}

    incident["status"] = "acknowledged"
    incident["history"].append(f"Acknowledged by {responder}")

    return {
        "acknowledged": True,
        "incident_id": incident_id,
        "responder": responder,
        "new_status": "acknowledged",
    }


if __name__ == "__main__":
    print("Starting MCP server (stdio mode)...")
    print("Tip: run 'fastmcp dev solution.py' to open the browser inspector.")
    mcp.run()
