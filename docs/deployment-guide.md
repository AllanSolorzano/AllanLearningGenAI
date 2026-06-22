# Deployment Guide

This guide is for platform organizers or builders who own the AWS sandbox. Participants in AI Chaos Arena 2026 should use the namespace-scoped credentials, observability access, and approved chaos tools provided for the event.

## Happy Path Script

For a clean AWS account, configured AWS CLI credentials, and a Git repo with an `origin` remote:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git
AUTO_COMMIT_PUSH=true make happy-path
```

What it does:

- checks local tools, AWS identity, and Docker daemon.
- creates `terraform/terraform.tfvars` from the example if missing.
- runs Terraform init, plan, and apply.
- updates kubeconfig.
- builds and pushes frontend plus all four service images to ECR.
- rewrites Argo CD repo URLs.
- optionally commits and pushes generated GitOps changes.
- installs Argo CD.
- applies namespaces, platform resources, DB secret, agent RBAC, and Argo CD apps.
- waits for Postgres, `api-gateway`, `order-service`, `inventory-service`, `payment-service`, frontend, and the ALB health endpoint.

Idempotency is best-effort and practical: Terraform, `kubectl apply`, Argo CD manifests, and ECR image pushes are safe to rerun. Chaos experiments and Dynatrace tenant secrets remain manual by design.

## 1. Configure Terraform

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit values:

- `aws_region`
- `kubernetes_version`
- `node_instance_types`
- `single_nat_gateway`
- optional IRSA toggles

## 2. Verify Local Prerequisites

```bash
make bootstrap
```

This checks `aws`, `terraform`, `kubectl`, `docker`, and `jq`, then verifies AWS identity and Docker daemon access.

## 3. Deploy Infrastructure

```bash
make infra
```

This runs Terraform init, plan, apply, and updates kubeconfig.

## 4. Build and Push Images

```bash
make build-push
```

The script reads ECR repository URLs from Terraform outputs, builds `frontend`, `api-gateway`, `order-service`, `inventory-service`, and `payment-service`, pushes immutable and `latest` tags, and updates Kustomize image overrides. If the worktree is dirty, it uses a timestamp tag rather than pretending the image matches the current Git commit.

## 5. Configure GitOps Repo URL

Set the repository URL Argo CD should sync:

```bash
export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git
make configure-argocd
```

Because the root app reads those files from Git, commit and push the repo URL changes, image override changes, and generated package locks before expecting Argo CD to converge:

```bash
git add k8s/argocd k8s/app/overlays terraform/.terraform.lock.hcl \
  app/backend/api-gateway/package-lock.json app/backend/order-service/package-lock.json \
  app/backend/inventory-service/package-lock.json app/backend/payment-service/package-lock.json \
  app/frontend/package-lock.json
git commit -m "Configure GitOps deployment"
git push
```

## 6. Install Argo CD

```bash
make argocd
```

Optional UI access:

```bash
kubectl -n argocd port-forward svc/argocd-server 8081:443
```

## 7. Deploy Apps

```bash
make deploy
```

This applies namespaces, gp3 StorageClass, metrics-server, a demo DB secret, AI-agent RBAC, and Argo CD applications.

Override the demo DB secret:

```bash
export DB_USER=postgres
export DB_PASSWORD='replace-with-your-demo-secret'
make deploy
```

## 8. Validate

```bash
make validate
```

If the ALB hostname is not ready, wait a few minutes and run validation again.

## 9. Destroy

```bash
make destroy
```

If Terraform cannot delete VPC resources, check that the ALB and target groups have been removed by AWS Load Balancer Controller.
