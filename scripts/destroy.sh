#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Deleting Argo CD applications if present..."
kubectl -n argocd delete application chaos-store-app dynatrace-observability chaos-tooling ai-chaos-gameday-root --ignore-not-found=true || true

echo "Deleting app and support resources if present..."
kubectl delete -k "$ROOT_DIR/k8s/agents" --ignore-not-found=true || true
kubectl delete -k "$ROOT_DIR/k8s/app/overlays/gameday" --ignore-not-found=true || true
kubectl delete -k "$ROOT_DIR/k8s/app/overlays/dev" --ignore-not-found=true || true
kubectl delete -k "$ROOT_DIR/k8s/chaos" --ignore-not-found=true || true
kubectl delete -k "$ROOT_DIR/k8s/dynatrace" --ignore-not-found=true || true
kubectl delete -k "$ROOT_DIR/k8s/platform" --ignore-not-found=true || true

echo "Waiting briefly for ALB resources to drain..."
sleep 20

echo "Destroying Terraform infrastructure..."
terraform -chdir="$ROOT_DIR/terraform" destroy

echo "Destroy complete."
