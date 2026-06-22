# AI SRE Team Design Guide

## Goal

Build an agent team that reasons about ResilienceMart. Do not submit a script that blindly applies predefined YAML.

The repo includes a framework-neutral scaffold in `agents/starter-kit`. Use it as a starting point for guardrails and agent boundaries, not as a finished solution.

The team should show:

- environment discovery
- dependency inference
- hypothesis generation
- safety review
- controlled execution
- observation
- root cause analysis
- remediation recommendations

## Reference Agent Topology

```text
Coordinator
  -> Discovery Agent
  -> Chaos Planning Agent
  -> Safety Officer Agent
  -> Execution Agent
  -> Observer Agent
  -> RCA Agent
```

The Coordinator manages task state, evidence, approvals, and handoffs. The Safety Officer can be a separate agent or a policy layer, but the safety decision should be explicit and auditable.

## Shared Memory

Recommended memory objects:

- discovered workloads
- service dependency graph
- known risks
- approved experiments
- experiment timeline
- metric snapshots
- log snippets
- Kubernetes events
- trace/problem links
- final RCA

Memory should preserve evidence and decisions. It should not become a place to hide hardcoded experiment answers.

## Tool Abstraction

Wrap raw APIs behind narrow tools:

```text
discover_workloads(namespace)
map_dependencies(namespace)
query_service_health(service)
query_promql(query)
query_dynatrace_services()
query_dynatrace_traces(service, window)
create_pod_kill_experiment(target, duration)
delete_experiment(name)
```

Each tool should validate guardrails before execution. For example, a chaos tool should reject namespaces other than `chaos-app` and services outside the allowed target list.

## Suggested MCP Servers

Kubernetes MCP:

- `get_pods(namespace)`
- `get_deployments(namespace)`
- `get_services(namespace)`
- `get_hpa(namespace)`
- `get_pdb(namespace)`
- `get_events(namespace)`

Observability MCP:

- `query_promql(query)`
- `query_logs(service, window)`
- `query_traces(service, window)`
- `query_problems(window)`

Chaos MCP:

- `run_pod_kill(service, duration)`
- `run_network_latency(source, target, latency_ms, duration)`
- `run_cpu_stress(service, duration)`
- `run_memory_stress(service, duration)`
- `delete_experiment(name)`

AWS MCP:

- `describe_eks(cluster)`
- `describe_nodegroups(cluster)`
- `describe_asgs(cluster)`
- `get_cloudwatch_alarms()`

## Required Planning Record

Before execution, persist a planning record:

```yaml
hypothesis: ""
target:
  namespace: chaos-app
  service: ""
experiment:
  type: ""
  duration: ""
blast_radius: ""
success_criteria: []
abort_criteria: []
rollback: ""
observability_plan:
  metrics: []
  logs: []
  events: []
  traces: []
approval:
  required: true
  approved_by: ""
```

## Good Agent Behavior

- asks for approval before chaos execution
- refuses forbidden operations
- explains uncertainty
- adapts after observing evidence
- separates symptoms from root cause
- recommends concrete remediation

## Poor Agent Behavior

- applies YAML without discovery
- assumes service names without reading the cluster
- executes chaos without a hypothesis
- ignores metrics, logs, traces, or events
- claims success without measuring impact
- patches or deletes workloads
- attempts to inspect out-of-scope namespaces
