# AI Chaos GameDay Platform

Production-like, demo-safe infrastructure and application code for an AI-agent Chaos Engineering GameDay platform on AWS EKS.

The business app is intentionally small. The point is the platform: Terraform, EKS managed node groups, ECR, IRSA, Argo CD, Dynatrace-ready manifests, bounded chaos experiments, and least-privilege AI-agent RBAC.

## Architecture

Runtime flow:

```text
React frontend
  -> api-gateway
  -> inventory-service
  -> payment-service
  -> order-service
  -> PostgreSQL
```

Infrastructure and platform components:

- AWS VPC across 2 or 3 AZs with public/private subnets, IGW, and NAT Gateway.
- EKS cluster with managed node group, OIDC provider, and core addons.
- ECR repositories for `chaos-frontend`, `chaos-api-gateway`, `chaos-order-service`, `chaos-inventory-service`, `chaos-payment-service`, and `chaos-agent`.
- AWS Load Balancer Controller installed by Terraform by default.
- React frontend served by Nginx. Nginx proxies API traffic only to `api-gateway`.
- Express microservices with Prometheus metrics, OpenTelemetry hooks, graceful shutdown, and safe in-memory fault endpoints.
- PostgreSQL StatefulSet used by `order-service`, `inventory-service`, and `payment-service`.
- Argo CD app-of-apps manifests for app, Dynatrace, and chaos tooling.
- Dynatrace Operator/DynaKube-compatible examples with no committed secrets.
- Chaos Mesh examples for pod kill, network delay, CPU stress, memory stress, and payment failure.
- AI-agent service accounts scoped to read-only, planning, observing, or bounded chaos execution.

See [docs/architecture.md](docs/architecture.md) for the full layout.

## AWS Cost Warning

This creates billable AWS resources: EKS control plane, EC2 worker nodes, NAT Gateway, EBS volumes, ALB, and ECR storage. Defaults are demo-conscious, including one NAT Gateway, but this is not free. Run `make destroy` when finished.

## Prerequisites

- AWS CLI authenticated to a sandbox account
- Terraform >= 1.6
- kubectl
- Docker
- jq
- make

Recommended:

- Bash-compatible shell
- Helm, if you install Chaos Mesh or Dynatrace Operator manually

## Required Environment Variables

```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=your-profile
export TF_VAR_project_name=ai-chaos-gameday-platform
export TF_VAR_environment=dev
```

For Argo CD GitOps, publish this repository and set:

```bash
export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git
```

Use `make configure-argocd` to replace the placeholder `repoURL` values in `k8s/argocd/*.yaml` before running the root app.

## Deploy

### Happy Path Script

From a clean AWS account and a Git branch that can be pushed to `origin`:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git
AUTO_COMMIT_PUSH=true make happy-path
```

The script is idempotent where the underlying systems support it: Terraform reconciles AWS resources, Kubernetes resources use declarative apply, Argo CD manifests are re-applied, and images are rebuilt and pushed with a safe tag. Omit `AUTO_COMMIT_PUSH=true` if you want the script to stop and let you review GitOps changes before committing and pushing.

### Manual Steps

1. Configure Terraform:

   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   ```

   Edit `terraform/terraform.tfvars` for your AWS region, node size, and optional toggles.

2. Bootstrap local tooling and AWS credentials:

   ```bash
   make bootstrap
   ```

3. Provision AWS infrastructure:

   ```bash
   make infra
   ```

4. Build and push images to ECR:

   ```bash
   make build-push
   ```

   This builds `frontend`, `api-gateway`, `order-service`, `inventory-service`, and `payment-service`, then updates both app overlays with ECR image URLs. Commit and push those changes before Argo CD syncs from Git.

5. Set the GitOps repository URL:

   ```bash
   export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git
   make configure-argocd
   ```

   Commit and push the Argo CD repo URL changes, image override changes, and generated package locks before relying on the root app:

   ```bash
   git add k8s/argocd k8s/app/overlays terraform/.terraform.lock.hcl \
     app/api-gateway/package-lock.json app/order-service/package-lock.json \
     app/inventory-service/package-lock.json app/payment-service/package-lock.json \
     app/frontend/package-lock.json
   git commit -m "Configure GitOps deployment"
   git push
   ```

6. Install Argo CD:

   ```bash
   make argocd
   ```

7. Deploy platform resources and Argo CD applications:

   ```bash
   make deploy
   ```

8. Validate:

   ```bash
   make validate
   ```

## Access the App

After `make validate` shows an ALB hostname, open:

```bash
http://ALB_HOSTNAME/
```

Gateway endpoints:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /api/products`
- `GET /api/cart`
- `POST /api/cart`
- `GET /api/orders`
- `POST /api/checkout`
- `POST /fault/latency`
- `POST /fault/error-rate`
- `POST /fault/reset`

Service-to-service endpoints stay inside the cluster:

- `order-service`: `POST /orders`, `GET /orders/:id`, `POST /checkout`
- `inventory-service`: `GET /products`, `GET /inventory/:productId`, `POST /inventory/reserve`
- `payment-service`: `POST /payment/authorize`

## Connect Dynatrace

1. Install Dynatrace Operator using the current Dynatrace-supported method.
2. Create a real `dynakube` secret in the `dynatrace` namespace.
3. Copy `k8s/dynatrace/dynakube.example.yaml`, replace `apiUrl`, and apply it.
4. Verify OneAgent injection and ActiveGate pods.

See [docs/dynatrace-setup.md](docs/dynatrace-setup.md).

## Run Sample Chaos

Install Chaos Mesh first, then apply one experiment at a time:

```bash
kubectl apply -f k8s/chaos/pod-kill-api-gateway.yaml
kubectl apply -f k8s/chaos/network-delay-api-gateway-to-inventory.yaml
kubectl apply -f k8s/chaos/break-payment-service.yaml
```

Remove experiments:

```bash
kubectl delete -f k8s/chaos/pod-kill-api-gateway.yaml --ignore-not-found
kubectl delete -f k8s/chaos/network-delay-api-gateway-to-inventory.yaml --ignore-not-found
kubectl delete -f k8s/chaos/break-payment-service.yaml --ignore-not-found
```

See [docs/gameday-scenarios.md](docs/gameday-scenarios.md).

## Clean Up

```bash
make destroy
```

If ALB deletion is slow, wait for AWS Load Balancer Controller to remove AWS resources before re-running Terraform destroy.
