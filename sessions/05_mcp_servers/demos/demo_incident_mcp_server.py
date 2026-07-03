#!/usr/bin/env python3
"""
Demo: Incident Management MCP Server
======================================
A rich MCP server combining Tools + Resources + Prompts for SRE work.

Showcases all three MCP primitives:
  Tools     — actions (get incident, claim, update severity)
  Resources — read-only URI-addressed data (runbooks, incident documents)
  Prompts   — reusable starting prompts (triage, postmortem)

Run:
    fastmcp dev demo_incident_mcp_server.py    # browser inspector
    python demo_incident_mcp_server.py          # stdio

To connect Claude Desktop, add to claude_desktop_config.json:
    "incident-ops": {
      "command": "python",
      "args": ["/absolute/path/to/demo_incident_mcp_server.py"]
    }
"""

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Data (mock — replace with real API calls in production)
# ---------------------------------------------------------------------------

INCIDENTS: dict = {
    "INC-3001": {
        "severity": "SEV1",
        "service": "checkout",
        "status": "open",
        "owner": None,
        "summary": "Checkout flow returning 503 — orders cannot be placed",
        "created_at": "2024-01-16T09:00:00Z",
        "history": ["09:00 - PagerDuty alert fired", "09:01 - SEV1 declared"],
    },
    "INC-3002": {
        "severity": "SEV2",
        "service": "notifications",
        "status": "investigating",
        "owner": "sre-diana",
        "summary": "Email notifications delayed by 15+ minutes",
        "created_at": "2024-01-16T08:30:00Z",
        "history": ["08:30 - Alert fired", "08:45 - Assigned to sre-diana"],
    },
    "INC-3003": {
        "severity": "SEV3",
        "service": "reporting",
        "status": "resolved",
        "owner": "sre-evan",
        "summary": "Dashboard load time increased to 8s",
        "created_at": "2024-01-15T14:00:00Z",
        "history": ["14:00 - Alert fired", "16:00 - Cache config fixed", "16:30 - Resolved"],
    },
}

RUNBOOKS = {
    "checkout": """# Checkout Service Runbook

## Immediate Checks (first 5 minutes)
```bash
# Pod health
kubectl get pods -n checkout
kubectl describe pod -l app=checkout -n checkout | grep -A5 "Events:"

# Error logs
kubectl logs -l app=checkout -n checkout --since=10m | grep -E "(ERROR|FATAL)"

# Upstream dependencies
curl -f https://internal.payments-api/health
curl -f https://internal.inventory-api/health
```

## Rollback (if recent deploy)
```bash
kubectl rollout undo deploy/checkout -n checkout
kubectl rollout status deploy/checkout -n checkout
```

## Escalation
- SEV1: Page checkout-oncall + VP Engineering
- SEV2: Ping #checkout-team (15min SLA)
""",
    "notifications": """# Notifications Service Runbook

## Immediate Checks
```bash
# Queue depth (high = bottleneck)
rabbitmq-admin queue-depth notifications-email

# Worker pods
kubectl get pods -n notifications -l app=notif-worker

# Dead letter queue
rabbitmq-admin dlq-count notifications-email-dlq
```

## Mitigation
```bash
# Scale up workers if queue is deep
kubectl scale deploy notif-worker --replicas=10 -n notifications

# Restart if workers are stuck
kubectl rollout restart deploy/notif-worker -n notifications
```

## Escalation
- SEV2+: Ping #platform-team, SLA 30min
""",
}


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "incident-ops",
    instructions=(
        "SRE incident management: look up incidents, check runbooks, "
        "claim ownership, and get structured triage prompts."
    ),
)


# =============
# TOOLS
# =============

@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """
    Get full details of an incident by its ID.

    Args:
        incident_id: Incident identifier, e.g. INC-3001
    """
    incident = INCIDENTS.get(incident_id)
    if not incident:
        return {"error": f"Incident {incident_id} not found. Open incidents: {list(INCIDENTS.keys())}"}
    return {"incident_id": incident_id, **incident}


@mcp.tool()
def list_incidents(status: str = None, severity: str = None) -> dict:
    """
    List incidents, with optional filters for status and severity.

    Args:
        status: Filter by status — open, investigating, resolved. Omit for all.
        severity: Filter by severity — SEV1, SEV2, SEV3. Omit for all.
    """
    results = []
    for iid, data in INCIDENTS.items():
        if status and data["status"] != status:
            continue
        if severity and data["severity"] != severity:
            continue
        results.append({"incident_id": iid, **data})

    results.sort(key=lambda x: x["severity"])
    return {"count": len(results), "incidents": results}


@mcp.tool()
def claim_incident(incident_id: str, responder: str) -> dict:
    """
    Claim an incident as the primary responder. Updates status to investigating.

    Args:
        incident_id: The incident ID to claim
        responder: Your username or name
    """
    incident = INCIDENTS.get(incident_id)
    if not incident:
        return {"error": f"Incident {incident_id} not found"}
    if incident["status"] == "resolved":
        return {"error": f"Incident {incident_id} is already resolved"}

    incident["owner"] = responder
    incident["status"] = "investigating"
    incident["history"].append(f"Claimed by {responder}")

    return {
        "claimed": True,
        "incident_id": incident_id,
        "responder": responder,
        "new_status": "investigating",
    }


@mcp.tool()
def update_severity(incident_id: str, new_severity: str, reason: str) -> dict:
    """
    Change the severity of an incident with a documented reason.

    Args:
        incident_id: The incident ID
        new_severity: New severity level — SEV1, SEV2, or SEV3
        reason: Brief reason for the severity change (required for audit trail)
    """
    valid_severities = {"SEV1", "SEV2", "SEV3"}
    if new_severity not in valid_severities:
        return {"error": f"Invalid severity '{new_severity}'. Must be one of: {valid_severities}"}

    incident = INCIDENTS.get(incident_id)
    if not incident:
        return {"error": f"Incident {incident_id} not found"}

    old_severity = incident["severity"]
    incident["severity"] = new_severity
    incident["history"].append(f"Severity changed {old_severity} → {new_severity}: {reason}")

    return {
        "updated": True,
        "incident_id": incident_id,
        "old_severity": old_severity,
        "new_severity": new_severity,
        "reason": reason,
    }


# =============
# RESOURCES
# =============

@mcp.resource("incidents://open")
def open_incidents_resource() -> str:
    """Live snapshot of all open and investigating incidents."""
    active = [
        (iid, data) for iid, data in INCIDENTS.items()
        if data["status"] != "resolved"
    ]
    if not active:
        return "No open incidents."

    lines = ["# Open Incidents\n"]
    for iid, data in sorted(active, key=lambda x: x[1]["severity"]):
        lines.append(f"## {iid} — {data['severity']}")
        lines.append(f"Service:  {data['service']}")
        lines.append(f"Status:   {data['status']}")
        lines.append(f"Owner:    {data['owner'] or 'UNOWNED'}")
        lines.append(f"Summary:  {data['summary']}")
        lines.append("")
    return "\n".join(lines)


@mcp.resource("runbook://{service}")
def get_runbook(service: str) -> str:
    """
    Fetch the operational runbook for a service.

    Args:
        service: Service name, e.g. checkout, notifications
    """
    runbook = RUNBOOKS.get(service)
    if not runbook:
        available = list(RUNBOOKS.keys())
        return f"No runbook found for '{service}'. Available: {available}"
    return runbook


@mcp.resource("incident://{incident_id}")
def incident_document(incident_id: str) -> str:
    """
    Full incident document as formatted text.

    Args:
        incident_id: Incident identifier
    """
    incident = INCIDENTS.get(incident_id)
    if not incident:
        return f"Incident {incident_id} not found."

    history_text = "\n".join(f"  - {e}" for e in incident["history"])
    return f"""# Incident Report: {incident_id}

Severity:   {incident['severity']}
Service:    {incident['service']}
Status:     {incident['status']}
Owner:      {incident['owner'] or 'Unowned'}
Created:    {incident['created_at']}

## Summary
{incident['summary']}

## Event Timeline
{history_text}
"""


# =============
# PROMPTS
# =============

@mcp.prompt()
def triage_incident(incident_id: str) -> str:
    """
    Generate a structured triage prompt for an incident.

    Args:
        incident_id: The incident to triage
    """
    return f"""You are an experienced SRE on-call. You've been paged for incident {incident_id}.

Your immediate priorities:
1. Call get_incident('{incident_id}') to understand current state
2. If the incident is unowned, claim it immediately
3. Check if there was a recent deployment to the affected service
4. Fetch the runbook for the service via the runbook:// resource
5. Identify the most likely root cause based on available information
6. Recommend the next 3 actions in order of priority

Be decisive. In a SEV1, every minute counts."""


@mcp.prompt()
def postmortem_template(incident_id: str, author: str) -> str:
    """
    Generate a postmortem writing prompt for a resolved incident.

    Args:
        incident_id: The resolved incident to write a postmortem for
        author: Name of the postmortem author
    """
    return f"""You are helping {author} write a blameless postmortem for {incident_id}.

Start by calling get_incident('{incident_id}') to review the timeline and details.

Then structure the postmortem with these sections:
1. **Summary** — one paragraph, non-technical overview
2. **Timeline** — chronological events from first alert to resolution
3. **Root Cause** — the specific technical cause (not "human error")
4. **Contributing Factors** — what made this worse or harder to catch
5. **Impact** — user-facing impact and duration
6. **Action Items** — 3-5 specific, trackable tasks with owners
7. **Lessons Learned** — what this incident taught us

Write it in clear, blameless language. The goal is to prevent recurrence, not assign fault."""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Incident Operations MCP Server")
    print("-" * 40)
    print("Tools:     get_incident, list_incidents, claim_incident, update_severity")
    print("Resources: incidents://open, runbook://{service}, incident://{id}")
    print("Prompts:   triage_incident, postmortem_template")
    print()
    print("Connect with:")
    print("  fastmcp dev demo_incident_mcp_server.py")
    print()
    mcp.run()
