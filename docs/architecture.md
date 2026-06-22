# Architecture

## Overview

This repository builds a bounded, production-like GameDay environment on AWS EKS. The platform separates infrastructure provisioning, GitOps deployment, application runtime, observability, chaos experiments, and AI-agent access boundaries.

## AWS

Terraform creates:

- VPC with public and private subnets across 2 or 3 AZs.
- Internet Gateway for public subnets.
- NAT Gateway for private subnet egress.
- EKS cluster with public API endpoint by default.
- EKS managed node group with configurable instance types and size.
- ECR repositories for `chaos-frontend`, `chaos-api-gateway`, `chaos-order-service`, `chaos-inventory-service`, `chaos-payment-service`, and `chaos-agent`.
- IRSA roles for AWS Load Balancer Controller, EBS CSI Driver, optional ExternalDNS, and optional Dynatrace metadata access.

The default topology is demo-safe. `single_nat_gateway = true` lowers cost; use one NAT Gateway per AZ for stronger availability.

## Kubernetes

Namespaces:

- `chaos-app`: frontend, api gateway, microservices, PostgreSQL, HPA, PDB, ingress, and network policies.
- `argocd`: Argo CD and Application resources.
- `dynatrace`: Dynatrace Operator and DynaKube resources.
- `chaos-system`: Chaos Mesh installation.
- `ai-agents`: AI-agent jobs and service accounts.

The application uses an AWS ALB ingress with `target-type: ip`. ALB traffic lands on the frontend service. Nginx serves the React bundle and proxies `/api`, `/health`, `/ready`, `/metrics`, and `/fault` to `api-gateway`. NetworkPolicy then keeps direct service ingress narrow:

- public ingress goes only to frontend.
- frontend talks only to `api-gateway`.
- `api-gateway` talks to `inventory-service`, `payment-service`, and `order-service`.
- database access is limited to `inventory-service`, `payment-service`, and `order-service`.

The platform folder includes metrics-server for HPA and a gp3 StorageClass for Postgres PVCs.

## Application

The app is a small PERN store split into service boundaries useful for GameDay exercises:

- `frontend`: React/Vite UI served by Nginx.
- `api-gateway`: BFF, cart state, checkout orchestration, and public API surface.
- `inventory-service`: product catalog, stock lookup, and stock reservation.
- `payment-service`: mock payment authorization with persistent payment records.
- `order-service`: order creation, order lookup, and order persistence.
- `postgres`: shared demo database for products, inventory, orders, order items, and payments.

Checkout flow:

1. Frontend sends checkout to `api-gateway`.
2. `api-gateway` validates the cart.
3. `api-gateway` checks stock through `inventory-service`.
4. `api-gateway` reserves stock through `inventory-service`.
5. `api-gateway` authorizes payment through `payment-service`.
6. `api-gateway` creates the order through `order-service`.
7. `order-service` stores the order and order items in PostgreSQL.
8. `api-gateway` returns success or a graceful failure.

If a downstream step fails after stock has been reserved, `api-gateway` asks `inventory-service` to release the reserved quantities. That keeps payment-failure GameDays from silently draining demo inventory.

## Observability

Each Node.js service exports Prometheus metrics using `prom-client`:

- `http_requests_total`
- `http_request_duration_seconds`
- `active_fault_mode`

Checkout-facing services also expose checkout or payment counters where relevant. OpenTelemetry Node.js auto-instrumentation starts during service boot. Set `OTEL_EXPORTER_OTLP_ENDPOINT` in a ConfigMap or overlay when Dynatrace ActiveGate or another OTLP endpoint is available.

## GitOps

Argo CD manifests use an app-of-apps pattern:

- `ai-chaos-gameday-root`: points at `k8s/argocd`.
- `chaos-store-app`: deploys `k8s/app/overlays/gameday` and uses automated sync, prune, and self-heal.
- `dynatrace-observability`: manual sync by default.
- `chaos-tooling`: manual sync by default.

Replace the placeholder `repoURL` values before relying on GitOps sync.

## GameDay Overlay

The `gameday` overlay intentionally introduces safe weaknesses:

- `payment-service` runs with 1 replica.
- `inventory-service` has a very low CPU request.
- `order-service` has a high gateway timeout.
- payment fallback is disabled in the gateway.
- `payment-service` has a weak PDB.
- `payment-service` readiness probe is removed as a challenge.

These are meant to create teachable failures without requiring privileged access or dangerous cluster-wide changes.

## Chaos

Chaos Mesh examples are namespaced and scoped to `chaos-app`:

- kill `api-gateway`, `order-service`, or `inventory-service` pods.
- inject latency from `api-gateway` to `inventory-service`.
- inject latency from `api-gateway` to `payment-service`.
- stress CPU on `inventory-service`.
- stress memory on `order-service`.
- break `payment-service` to verify graceful checkout failure.
- scale `order-service` down to 1 replica.

Examples are not included in the chaos kustomization so they do not run accidentally.

## AI Agents

AI-agent RBAC uses Role and RoleBinding objects instead of cluster-admin:

- discovery and planner accounts get read-only access to `chaos-app`.
- observer gets read-only access to workload status, events, and log references.
- executor can create/delete limited Chaos Mesh experiment CRs in the intended namespaces.

See `docs/rbac-security-model.md` for the permission model.
