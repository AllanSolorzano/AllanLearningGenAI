# AI Chaos Arena 2026

## Theme

Build AI SRE agents that autonomously validate the resilience of ResilienceMart, a cloud-native microservices platform running on AWS EKS.

Teams are not evaluated on how much damage they can create. Teams are evaluated on infrastructure understanding, agent architecture, safe experimentation, observability usage, root cause analysis, remediation quality, agent reasoning, and guardrail implementation.

## Story

You have joined ResilienceMart. Management believes the EKS platform is resilient. Your AI SRE Team must prove whether that claim is true.

You are provided access to:

- AWS environment
- Kubernetes cluster
- Observability tools
- Chaos tooling

Your agents must:

1. Discover the environment.
2. Understand dependencies.
3. Create hypotheses.
4. Design chaos experiments.
5. Execute approved experiments safely.
6. Observe outcomes.
7. Produce RCA.
8. Recommend fixes.

## Objective

Build an AI SRE Team, not a script collection.

Expected agents:

- Discovery Agent
- Chaos Planning Agent
- Execution Agent
- Observer Agent
- RCA Agent
- Optional Safety Officer Agent

Hardcoded workflows, predefined YAML execution, and shell-script-only solutions should score poorly even if they can trigger an experiment.

## Platform Under Test

```text
React frontend
  -> api-gateway
  -> inventory-service
  -> payment-service
  -> order-service
  -> PostgreSQL
```

Core namespace:

```text
chaos-app
```

Supporting namespaces exist for platform operators:

```text
argocd
dynatrace
chaos-system
ai-agents
```

Participants should treat `chaos-app` as their Kubernetes boundary.

## Agent Responsibilities

### Discovery Agent

Responsibilities:

- Kubernetes discovery
- service discovery
- dependency mapping
- resource inventory
- risk identification

Example output:

```text
Services discovered:
- api-gateway
- order-service
- inventory-service
- payment-service

Dependencies:
api-gateway
  -> inventory-service
  -> payment-service
  -> order-service

Risks:
- payment-service replicas=1 in gameday overlay
- payment-service readiness probe removed in gameday overlay
- inventory-service CPU request is intentionally low
```

### Chaos Planning Agent

Responsibilities:

- generate hypotheses
- design experiments
- define blast radius
- define rollback
- request human approval before execution

Example:

```text
Hypothesis:
inventory-service should remain available after one pod failure.

Experiment:
Kill one inventory-service pod.

Blast radius:
chaos-app namespace, inventory-service pods only.

Success:
GET /api/products remains available and checkout failure rate does not exceed agreed threshold.

Rollback:
Delete the PodChaos experiment and verify deployment returns to desired replicas.
```

### Execution Agent

Responsibilities:

- execute only approved chaos experiments
- create/delete allowed Chaos Mesh experiment resources
- track experiment status
- refuse forbidden actions

### Observer Agent

Responsibilities:

- monitor metrics
- monitor logs
- monitor events
- measure impact
- preserve evidence for RCA

### RCA Agent

Responsibilities:

- explain what happened
- explain why it happened
- explain user and business impact
- produce a timeline
- recommend fixes

## Allowed Frameworks

Teams may use LangGraph, CrewAI, AutoGen, Semantic Kernel, PydanticAI, OpenAI SDK, Anthropic SDK, Gemini SDK, or custom Python.

## Allowed MCP Servers

Teams may create MCP servers. Useful examples:

- Kubernetes MCP: `get_pods()`, `get_deployments()`, `get_events()`, `describe_pod()`
- Prometheus MCP: `query_promql()`, `get_alerts()`, `get_metrics()`
- Dynatrace MCP: `query_problems()`, `query_services()`, `query_traces()`
- AWS MCP: `describe_eks()`, `describe_nodegroups()`, `describe_asgs()`
- Chaos MCP: `run_pod_kill()`, `run_cpu_stress()`, `run_network_delay()`

Tool abstractions should enforce guardrails before reaching the underlying API.

## Access Model

Participants do not receive `cluster-admin`, AWS `AdministratorAccess`, or root access.

AWS access is read-only plus limited chaos permissions, such as CloudWatch read, EKS read, EC2 describe, and controlled experiment execution where configured.

Kubernetes access is namespace scoped to `chaos-app`. Participants must not access `kube-system`, `argocd`, `dynatrace`, or `chaos-system`.

See [participant-guardrails.md](participant-guardrails.md) and [rbac-security-model.md](rbac-security-model.md).

## Allowed Chaos Levels

- Level 1: pod failure
- Level 2: network latency or packet loss
- Level 3: CPU stress
- Level 4: memory pressure
- Level 5: service dependency failure
- Level 6: autoscaling validation
- Level 7: GitOps drift detection, with recommendation only and no auto-repair

## Winning Criteria

The winner is not the team that broke the cluster. The winner is the team whose AI agents most accurately understood the platform, executed safe experiments, found weaknesses, and produced actionable remediation.
