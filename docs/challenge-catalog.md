# Challenge Catalog

## Challenge 1: The Disappearing Pod

Points: 50

Validate:

```text
inventory-service survives pod loss
```

Expected agent behavior:

- discover inventory replicas and PDB.
- form a pod-loss hypothesis.
- request approval.
- run a bounded PodChaos experiment against one `inventory-service` pod.
- observe `/api/products`, gateway readiness, pod events, and request metrics.
- delete the experiment and verify recovery.

## Challenge 2: Slow Payments

Points: 75

Inject:

```text
1500ms latency into payment-service path
```

Determine:

```text
Does checkout fail gracefully?
```

Expected agent behavior:

- discover payment dependency from gateway config and traffic evidence.
- design latency blast radius from `api-gateway` to `payment-service`.
- observe checkout latency, failures, logs, and traces.
- explain whether users see graceful failure or timeout behavior.

## Challenge 3: Inventory Meltdown

Points: 100

Apply:

```text
CPU stress to inventory-service
```

Validate:

```text
HPA reaction
```

Expected agent behavior:

- read inventory HPA and CPU requests.
- identify that the gameday overlay sets a very low CPU request.
- run bounded CPU stress.
- observe HPA metrics and replica changes.
- recommend resource request and HPA tuning.

## Challenge 4: Checkout Outage

Points: 150

Organizer secretly injects:

```text
misconfiguration
```

Expected agent behavior:

- detect changed symptoms without hints.
- compare current configuration to known steady state.
- use events, logs, readiness, and service dependency data.
- identify the broken component and recommend a fix.

## Challenge 5: Unknown Incident

Points: 250

No hints.

Agents must discover:

- what broke
- why it broke
- how to fix it

Expected agent behavior:

- run discovery first.
- gather evidence from Kubernetes, metrics, logs, traces, and events.
- avoid random chaos execution until a hypothesis exists.
- produce a causal timeline.

## Challenge 6: Executive Brief

Points: 100

Create:

```text
1-page RCA for CTO
```

Expected output:

- one-page summary.
- user impact.
- root cause.
- timeline.
- immediate mitigation.
- durable remediation.
- confidence level.

Use [executive-brief-template.md](executive-brief-template.md).
