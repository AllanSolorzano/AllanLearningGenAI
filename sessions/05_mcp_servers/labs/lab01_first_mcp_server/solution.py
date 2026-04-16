#!/usr/bin/env python3
"""
Lab 01 Solution: Your First MCP Server
"""

from fastmcp import FastMCP


INCIDENT_DB = {
    "INC-1001": {
        "severity": "SEV2",
        "service": "payments",
        "status": "investigating",
        "owner": "payments-team",
        "created_at": "2024-01-15T14:30:00Z",
    },
    "INC-1002": {
        "severity": "SEV1",
        "service": "auth",
        "status": "mitigating",
        "owner": "platform-team",
        "created_at": "2024-01-15T15:00:00Z",
    },
    "INC-1003": {
        "severity": "SEV3",
        "service": "reporting",
        "status": "resolved",
        "owner": "data-team",
        "created_at": "2024-01-15T10:00:00Z",
    },
}


# TODO 1 Solution: Create the server
mcp = FastMCP(
    "incident-ops",
    instructions="SRE incident lookup and management tools.",
)


# TODO 2 Solution: get_incident tool
@mcp.tool()
def get_incident(incident_id: str) -> dict:
    """
    Look up a specific incident by its ID and return all details.

    Args:
        incident_id: The incident identifier, e.g. INC-1001
    """
    data = INCIDENT_DB.get(incident_id)
    if not data:
        return {"error": f"Incident {incident_id} not found"}
    return {"incident_id": incident_id, **data}


# TODO 3 Solution: list_by_severity tool
@mcp.tool()
def list_by_severity(severity: str) -> dict:
    """
    List all incidents matching a given severity level.

    Args:
        severity: Severity level to filter by, e.g. SEV1, SEV2, SEV3
    """
    matching = [
        {"incident_id": iid, **data}
        for iid, data in INCIDENT_DB.items()
        if data["severity"] == severity
    ]
    return {
        "severity": severity,
        "count": len(matching),
        "incidents": matching,
    }


if __name__ == "__main__":
    print("Starting MCP server (stdio mode)...")
    print("Tip: run 'fastmcp dev solution.py' to open the browser inspector.")
    mcp.run()
