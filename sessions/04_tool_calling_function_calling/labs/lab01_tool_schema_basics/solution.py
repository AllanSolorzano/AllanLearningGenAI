#!/usr/bin/env python3
"""Lab 01: Tool Schema Basics (SOLUTION)"""

import json


INCIDENT_DB = {
    "INC-1001": {"severity": "SEV2", "service": "payments", "status": "investigating"},
    "INC-1002": {"severity": "SEV1", "service": "auth", "status": "mitigating"},
}


def build_tools_schema() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_incident",
                "description": "Fetch a single incident by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {"incident_id": {"type": "string"}},
                    "required": ["incident_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_incidents_by_severity",
                "description": "List incidents matching a severity level.",
                "parameters": {
                    "type": "object",
                    "properties": {"severity": {"type": "string"}},
                    "required": ["severity"],
                },
            },
        },
    ]


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
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        if name == "get_incident":
            return get_incident(args["incident_id"])
        if name == "list_incidents_by_severity":
            return list_incidents_by_severity(args["severity"])
        return {"error": f"unknown tool: {name}"}
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    print("\nLab 01: Tool Schema Basics (Solution)\n")
    tools = build_tools_schema()
    print("Tools defined:")
    for t in tools:
        print(f"  - {t['function']['name']}")
    print("\nLocal tool execution checks:")
    print(f"  get_incident -> {execute_tool('get_incident', json.dumps({'incident_id': 'INC-1002'}))}")
    print(
        "  list_incidents_by_severity -> "
        f"{execute_tool('list_incidents_by_severity', json.dumps({'severity': 'SEV1'}))}"
    )


if __name__ == "__main__":
    main()

