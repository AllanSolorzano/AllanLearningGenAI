#!/usr/bin/env python3
"""
Lab 03: Pre-built MCP Server
=============================
This server is already complete — do not modify it.
Your task in lab.py is to write the MCP CLIENT that connects to this server,
discovers its tools, and connects Claude to use them.

This simulates a real-world scenario where the MCP server is already running
(built by another team, or a third-party tool) and you're integrating it
into your Claude-powered application.

Tools exposed by this server:
  - get_service_status(service, environment) -> dict
  - list_recent_alerts(limit) -> dict
"""

from fastmcp import FastMCP

mcp = FastMCP(
    "ops-status",
    instructions="Real-time service status and alert monitoring tools.",
)

# Simulated data (in a real server this would call your monitoring APIs)
SERVICE_REGISTRY = {
    "payments": {
        "prod":    {"status": "degraded",  "latency_p99_ms": 850, "error_rate_pct": 2.3},
        "staging": {"status": "healthy",   "latency_p99_ms": 120, "error_rate_pct": 0.1},
    },
    "auth": {
        "prod":    {"status": "healthy",   "latency_p99_ms": 45,  "error_rate_pct": 0.0},
        "staging": {"status": "healthy",   "latency_p99_ms": 40,  "error_rate_pct": 0.0},
    },
    "gateway": {
        "prod":    {"status": "healthy",   "latency_p99_ms": 210, "error_rate_pct": 0.5},
        "staging": {"status": "deploying", "latency_p99_ms": 0,   "error_rate_pct": 0.0},
    },
}

RECENT_ALERTS = [
    {"id": "ALT-001", "service": "payments", "severity": "SEV2",
     "message": "P99 latency exceeded 800ms threshold", "fired_at": "2024-01-15T14:28:00Z"},
    {"id": "ALT-002", "service": "payments", "severity": "SEV3",
     "message": "Error rate above 2% for 5 minutes", "fired_at": "2024-01-15T14:30:00Z"},
    {"id": "ALT-003", "service": "gateway",  "severity": "SEV3",
     "message": "Error rate elevated during deploy window", "fired_at": "2024-01-15T13:00:00Z"},
]


@mcp.tool()
def get_service_status(service: str, environment: str = "prod") -> dict:
    """
    Get the current operational status of a service in a given environment.

    Args:
        service: Service name, e.g. payments, auth, gateway
        environment: Deployment environment — prod or staging (default: prod)
    """
    svc = SERVICE_REGISTRY.get(service)
    if not svc:
        available = list(SERVICE_REGISTRY.keys())
        return {"error": f"Service '{service}' not found. Available: {available}"}
    env_data = svc.get(environment)
    if not env_data:
        return {"error": f"Environment '{environment}' not found for {service}"}
    return {
        "service": service,
        "environment": environment,
        **env_data,
    }


@mcp.tool()
def list_recent_alerts(limit: int = 5) -> dict:
    """
    List the most recent infrastructure alerts, newest first.

    Args:
        limit: Maximum number of alerts to return (default: 5)
    """
    alerts = RECENT_ALERTS[:limit]
    return {
        "count": len(alerts),
        "alerts": alerts,
    }


if __name__ == "__main__":
    mcp.run()
