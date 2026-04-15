# 02. Tool Schema Design

Good schemas reduce model errors before runtime.

## Practical rules

- Keep tool names action-oriented: `get_service_status`, `create_incident_ticket`.
- Write short, explicit descriptions.
- Use tight JSON schema:
  - required fields
  - enums for bounded values
  - clear field descriptions
- Prefer several small tools over one giant polymorphic tool.

## Example

```json
{
  "type": "function",
  "function": {
    "name": "get_service_status",
    "description": "Get service health metrics",
    "parameters": {
      "type": "object",
      "properties": {
        "service": {"type": "string"},
        "environment": {"type": "string", "enum": ["prod", "staging"]}
      },
      "required": ["service"]
    }
  }
}
```

## Failure patterns

- Ambiguous field names (`name`, `id`) with no domain context.
- Missing enums (`environment` becomes random string).
- Overly broad tools that combine read/write side effects.

