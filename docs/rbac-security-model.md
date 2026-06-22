# RBAC Security Model

## Principles

- No AI-agent service account receives cluster-admin.
- Permissions are namespace-scoped with Role and RoleBinding.
- Chaos execution is separated from discovery, planning, and observation.
- Sample chaos experiments are bounded to `chaos-app`.

## Service Accounts

### `discovery-agent-sa`

Namespace: `ai-agents`

Purpose: discover app state in `chaos-app`.

Permissions:

- get/list/watch pods, services, endpoints, configmaps, events
- get/list/watch deployments, statefulsets, replicasets
- get/list/watch ingress, HPA, PDB
- read pod logs

### `chaos-planner-sa`

Namespace: `ai-agents`

Purpose: inspect app state and propose experiments.

Permissions: same read-only role as discovery. It cannot create experiments.

### `observer-agent-sa`

Namespace: `ai-agents`

Purpose: observe status, events, and logs during GameDay.

Permissions: same read-only role as discovery, plus namespace-scoped pod metrics through `metrics.k8s.io`.

### `chaos-executor-sa`

Namespace: `ai-agents`

Purpose: execute approved Chaos Mesh experiments.

Permissions in `chaos-app`:

- get/list/watch/create/delete `podchaos`, `networkchaos`, `stresschaos`
- get/list/watch pods and events

Permissions in `chaos-system`:

- get/list/watch Chaos Mesh experiment resources for status visibility

## Human Approval Boundary

The included `gameday-agent-config` ConfigMap declares guardrails:

- require human approval before creating or deleting chaos experiments
- deny cluster-admin
- deny node deletion
- deny persistent volume deletion

Treat this ConfigMap as agent policy input, not a Kubernetes enforcement layer. Kubernetes enforcement comes from RBAC.

## Extending Permissions

Add permissions only when a scenario requires them. Prefer a new Role with narrow verbs/resources over expanding a shared role.
