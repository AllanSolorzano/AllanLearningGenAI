#!/usr/bin/env python3
"""
Lab 01: Tool Schema Basics
==========================
Build tool definitions and a local dispatcher before involving any LLM API.

Run:
    python lab.py

When stuck: check solution.py
"""

import json


INCIDENT_DB = {
    "INC-1001": {"severity": "SEV2", "service": "payments", "status": "investigating"},
    "INC-1002": {"severity": "SEV1", "service": "auth", "status": "mitigating"},
}


def build_tools_schema() -> list[dict]:
    # TODO 1:
    # Return a list with two function tools:
    # 1) get_incident(incident_id: string) -> required ["incident_id"]
    # 2) list_incidents_by_severity(severity: string) -> required ["severity"]
    # Keep descriptions concise and clear.
    pass


def get_incident(incident_id: str) -> dict:
    data = INCIDENT_DB.get(incident_id)
    if not data:
        return {"error": f"incident not found: {incident_id}"}
    return {"incident_id": incident_id, **data}


def list_incidents_by_severity(severity: str) -> dict:
    items = [
        {"incident_id": iid, **meta}
        for iid, meta in INCIDENT_DB.items()
        if meta["severity"] == severity
    ]
    return {"severity": severity, "count": len(items), "incidents": items}


def execute_tool(name: str, arguments_json: str) -> dict:
    # TODO 2:
    # Parse JSON args, then dispatch:
    # - get_incident -> get_incident(args["incident_id"])
    # - list_incidents_by_severity -> list_incidents_by_severity(args["severity"])
    # Unknown tool should return {"error": "..."}.
    # Catch exceptions and return {"error": str(e)}.
    pass


def main() -> None:
    print("\nLab 01: Tool Schema Basics\n")

    tools = build_tools_schema()
    if tools is None:
        print("TODO 1 not complete")
        return

    print("Tools defined:")
    for t in tools:
        print(f"  - {t['function']['name']}")

    print("\nLocal tool execution checks:")
    call_1 = execute_tool("get_incident", json.dumps({"incident_id": "INC-1002"}))
    call_2 = execute_tool("list_incidents_by_severity", json.dumps({"severity": "SEV1"}))

    if call_1 is None or call_2 is None:
        print("TODO 2 not complete")
        return

    print(f"  get_incident -> {call_1}")
    print(f"  list_incidents_by_severity -> {call_2}")

    print("\nKey takeaway: tool schemas + deterministic dispatcher come first.")


if __name__ == "__main__":
    main()

