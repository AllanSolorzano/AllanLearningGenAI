#!/usr/bin/env python3
"""
Lab 01: Your First MCP Server
==============================
Build a FastMCP server with two tools and verify it works using
the MCP inspector (fastmcp dev) or by running it directly.

Key insight: you're building a SERVER — a separate process that any
MCP client can connect to. This is different from function calling where
your tools were just Python functions wired inline into your API loop.

Run:
    # Option A: Interactive inspector (opens browser UI at localhost:5173)
    fastmcp dev lab.py

    # Option B: Run as stdio server (pipe JSON-RPC to interact)
    python lab.py

When stuck: check solution.py
"""

from fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Sample data — same incident DB from Session 04 so concepts connect
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TODO 1: Create the FastMCP server
# ---------------------------------------------------------------------------
# Create an instance of FastMCP named "incident-ops".
# Add instructions: "SRE incident lookup and management tools."
#
# Hint:
#   mcp = FastMCP("server-name", instructions="...")
#
mcp = None  # replace this line


# ---------------------------------------------------------------------------
# TODO 2: Define a tool — get_incident
# ---------------------------------------------------------------------------
# Decorate the function below with @mcp.tool() so it becomes an MCP tool.
# The model will call it as: get_incident(incident_id="INC-1001")
#
# Requirements:
# - Decorate with @mcp.tool()
# - Keep the function body — it already works
# - The docstring becomes the tool description — make it clear
#
def get_incident(incident_id: str) -> dict:
    """
    TODO: write a clear one-line description here.
    This description is what Claude sees when deciding whether to call this tool.
    """
    data = INCIDENT_DB.get(incident_id)
    if not data:
        return {"error": f"Incident {incident_id} not found"}
    return {"incident_id": incident_id, **data}


# ---------------------------------------------------------------------------
# TODO 3: Define a second tool — list_by_severity
# ---------------------------------------------------------------------------
# Write a NEW function decorated with @mcp.tool() that:
# - Is named: list_by_severity
# - Takes: severity (str) — e.g., "SEV1", "SEV2", "SEV3"
# - Returns: dict with keys "severity", "count", "incidents"
# - Filters INCIDENT_DB to only incidents matching the severity
# - Has a helpful docstring
#
# Hint: look at how get_incident works above for the return pattern.
#


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if mcp is None:
        print("TODO 1 not complete — create the FastMCP instance first.")
    else:
        print("Starting MCP server (stdio mode)...")
        print("Tip: run 'fastmcp dev lab.py' to open the browser inspector instead.")
        mcp.run()
