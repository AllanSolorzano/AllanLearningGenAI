# 04. Resources and Prompts

Tools are the main primitive — but Resources and Prompts unlock patterns
that function calling can't express at all.

---

## DevOps Analogy

| MCP Primitive | DevOps Equivalent | Use Case |
|--------------|------------------|----------|
| Tool | `kubectl exec` / API call | Actions with side effects |
| Resource | S3 object / ConfigMap | Read-only data by URI |
| Prompt | Helm values template | Reusable parameterized prompts |

---

## Resources — Read-Only Data

Resources are addressable data sources the model (or host app) can read.
Think of them as "files" the LLM can browse.

### Why Resources Instead of Tools?

Function calling approach (tools): inject all context into the prompt yourself.
MCP Resources: the model (or client) requests what it needs, on demand.

```
Without resources:
  You: "Here is the full k8s config, all runbooks, all incidents..."
  Model: processes 50k tokens of context it mostly doesn't need

With resources:
  Model: "I need the runbook for payments"
  Client: read_resource("runbook://payments/restart")
  Model: gets just that runbook, uses it
```

### Static Resource

```python
@mcp.resource("config://k8s/prod/limits")
def get_k8s_limits() -> str:
    """Production Kubernetes resource limits."""
    return """
    payments:  cpu: 500m, memory: 512Mi
    auth:      cpu: 250m, memory: 256Mi
    gateway:   cpu: 1000m, memory: 1Gi
    """
```

### Dynamic Resource (Template)

URI templates let one function serve many resources:

```python
@mcp.resource("incident://{incident_id}/details")
def get_incident_details(incident_id: str) -> str:
    """Full incident details as a readable document."""
    inc = INCIDENT_DB.get(incident_id)
    if not inc:
        return f"Incident {incident_id} not found."
    return f"""
INCIDENT: {incident_id}
Severity: {inc['severity']}
Service:  {inc['service']}
Status:   {inc['status']}
Owner:    {inc.get('owner', 'unassigned')}
Created:  {inc.get('created_at', 'unknown')}
"""
```

Client requests `incident://INC-1001/details` → FastMCP extracts `incident_id="INC-1001"` automatically.

### Resource Return Types

```python
@mcp.resource("runbook://payments/restart")
def get_runbook() -> str:        # plain text
    return "Step 1: ..."

@mcp.resource("schema://db/incidents")
def get_db_schema() -> dict:     # JSON (auto-serialized)
    return {"table": "incidents", "columns": [...]}
```

### Listing Resources

The client can discover available resources:
```python
resources = await session.list_resources()
# returns URIs + names + descriptions
```

For templates, it lists the template URI pattern, not every possible instance.

---

## Prompts — Reusable Templates

Prompts expose named, parameterized message templates.
When the client requests one, the server fills it in and returns a message list.

### Simple Prompt

```python
@mcp.prompt()
def incident_triage(incident_id: str, severity: str) -> str:
    """Prompt for triaging an incident."""
    return f"""You are an SRE on-call.
    
Incident {incident_id} has been raised with severity {severity}.

Steps to follow:
1. Check the service dashboard
2. Look at recent deployments (last 2 hours)
3. Review error logs
4. Page the service owner if SEV1 or SEV2
5. Post status update in #incidents channel

Start by calling get_incident('{incident_id}') to get current details."""
```

### Multi-Turn Prompt

Return a list of messages for multi-turn setups:
```python
from mcp.types import PromptMessage, TextContent

@mcp.prompt()
def postmortem_assistant(incident_id: str) -> list[PromptMessage]:
    """Multi-turn postmortem writing assistant."""
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"I need to write a postmortem for incident {incident_id}."
            )
        ),
        PromptMessage(
            role="assistant", 
            content=TextContent(
                type="text",
                text="I'll help you write a postmortem. Let me first look up the incident details."
            )
        ),
    ]
```

---

## Resources vs Tools — Decision Guide

| Question | Resource | Tool |
|----------|----------|------|
| Read-only? | Yes | Maybe |
| Side effects possible? | No | Yes |
| Addressed by URI? | Yes | No (called by name) |
| Model-initiated? | Can be | Always |
| Example | "Get this runbook" | "Restart this service" |

Rule of thumb:
- If it's **data the model reads** → Resource
- If it's **an action the model takes** → Tool

---

## Combining All Three in a Real Server

```python
from fastmcp import FastMCP

mcp = FastMCP("incident-ops", instructions="SRE incident management tools.")

# Tool: action with side effect
@mcp.tool()
def acknowledge_incident(incident_id: str, responder: str) -> dict:
    """Mark an incident as acknowledged by a responder."""
    ...

# Tool: query (read, but needs arguments — better as tool than resource)
@mcp.tool()
def search_incidents(severity: str, service: str = None) -> list[dict]:
    """Search incidents by severity and optional service filter."""
    ...

# Resource: addressable data
@mcp.resource("incident://{incident_id}")
def incident_resource(incident_id: str) -> str:
    """Full incident details as readable text."""
    ...

# Resource: static reference data
@mcp.resource("runbooks://index")
def list_runbooks() -> str:
    """Index of available runbooks."""
    ...

# Prompt: reusable starting point
@mcp.prompt()
def triage_prompt(incident_id: str) -> str:
    """Structured triage starting prompt."""
    ...
```

This server gives a client three surfaces:
- Execute actions via tools
- Read structured data via resources
- Start conversations with pre-built prompts
