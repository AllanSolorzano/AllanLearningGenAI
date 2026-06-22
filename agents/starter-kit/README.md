# AI SRE Team Starter Kit

This is a framework-neutral Python scaffold for AI Chaos Arena 2026.

It is not a finished agent team and it does not execute Kubernetes commands by itself. It defines the shape of a safe agent system:

- typed planning records
- guardrail validation
- tool interfaces
- role-specific agent classes

Teams can wire these classes to their framework of choice and replace the tool interfaces with MCP clients, Kubernetes clients, Prometheus clients, Dynatrace clients, or AWS SDK calls.

## Local Check

```bash
python -m compileall agents/starter-kit/src
```

## Recommended Flow

1. Discovery Agent reads `chaos-app`.
2. Chaos Planning Agent creates a hypothesis and experiment plan.
3. Safety Officer validates the plan.
4. Human approves.
5. Execution Agent creates a bounded Chaos Mesh experiment.
6. Observer Agent gathers evidence.
7. RCA Agent produces a report.

## Guardrail Example

```python
from arena_agents.guardrails import GuardrailPolicy
from arena_agents.models import ExperimentPlan, ExperimentTarget

plan = ExperimentPlan(
    hypothesis="inventory-service survives one pod failure",
    target=ExperimentTarget(namespace="chaos-app", service="inventory-service"),
    experiment_type="pod-kill",
    duration="30s",
    blast_radius="one inventory-service pod",
    success_criteria=["GET /api/products remains available"],
    abort_criteria=["checkout 5xx rate rises above threshold"],
    rollback="delete PodChaos experiment",
    observability_plan=["metrics", "logs", "events", "traces"],
)

GuardrailPolicy.default().validate(plan)
```
