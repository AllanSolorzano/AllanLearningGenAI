# Participant Guardrails

## Hard Boundaries

Agents must never:

- delete namespaces
- delete PVCs or PVs
- delete databases
- delete ingress resources
- delete services
- delete deployments, StatefulSets, ReplicaSets, or pods directly
- read, patch, or delete secrets
- modify IAM
- modify VPCs
- modify security groups
- modify Route53
- modify Dynatrace configuration

Immediate disqualification action:

- namespace deletion

Severe penalty actions:

- unauthorized action
- workload deletion
- missing safety validation

## Kubernetes Boundary

Participant agents operate against:

```text
chaos-app
```

They must not inspect or modify:

```text
kube-system
argocd
dynatrace
chaos-system
```

Platform operators may use those namespaces to install and run the event infrastructure. Participant agents should treat them as outside scope.

## Agent RBAC Summary

Discovery Agent:

- can get/list/watch pods, deployments, services, events, HPA, PDB, ingress, endpoints, replicasets, statefulsets, and configmaps in `chaos-app`
- cannot create, delete, update, or patch

Chaos Planning Agent:

- same read-only access as Discovery Agent
- cannot create, delete, update, or patch

Observer Agent:

- can read pod metadata, pod logs, events, and pod metrics in `chaos-app`
- cannot read secrets
- cannot create, delete, update, or patch

Chaos Executor Agent:

- can get/list/watch/create/delete only Chaos Mesh `podchaos`, `networkchaos`, and `stresschaos` resources in `chaos-app`
- cannot delete pods or workloads directly
- cannot patch experiments after creation

## Human Approval Workflow

Before execution, the system should present:

- hypothesis
- target resource selector
- experiment type
- duration
- blast radius
- expected impact
- abort condition
- rollback action
- observability plan

Execution must proceed only after approval.

## Safety Checks

Every experiment request should validate:

- target namespace is `chaos-app`
- selector matches expected application labels
- target service is in the allowed service list
- duration is bounded
- concurrent experiment count is acceptable
- rollback command is known
- success and abort criteria are defined

## Recommended Agent Refusal Message

```text
Refusing action: requested operation violates AI Chaos Arena guardrails.
Reason: <specific rule>.
Allowed alternative: <safe experiment or read-only query>.
```
