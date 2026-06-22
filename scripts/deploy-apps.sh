#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLACEHOLDER_REPO="https://github.com/REPLACE_ME/ai-chaos-gameday-platform.git"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres-demo-password-change-me}"

if grep -R "$PLACEHOLDER_REPO" "$ROOT_DIR/k8s/argocd" >/dev/null 2>&1; then
  echo "Argo CD repoURL placeholders are still present." >&2
  echo "Run: export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git && make configure-argocd" >&2
  echo "Then commit and push k8s/argocd before running make deploy." >&2
  exit 1
fi

echo "Applying base namespaces..."
kubectl apply -k "$ROOT_DIR/k8s/namespaces"

echo "Applying platform support resources..."
kubectl apply -k "$ROOT_DIR/k8s/platform"

echo "Creating or updating demo database secret in chaos-app..."
kubectl -n chaos-app create secret generic chaos-db-secret \
  --from-literal=DB_USER="$DB_USER" \
  --from-literal=DB_PASSWORD="$DB_PASSWORD" \
  --from-literal=POSTGRES_USER="$DB_USER" \
  --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Applying AI agent namespace and RBAC..."
kubectl apply -k "$ROOT_DIR/k8s/agents"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cp -R "$ROOT_DIR/k8s/argocd" "$TMP_DIR/argocd"

echo "Applying Argo CD project and applications..."
kubectl apply -f "$TMP_DIR/argocd/project.yaml"
kubectl apply -f "$TMP_DIR/argocd/app-application.yaml"
kubectl apply -f "$TMP_DIR/argocd/dynatrace-application.yaml"
kubectl apply -f "$TMP_DIR/argocd/chaos-application.yaml"
kubectl apply -f "$TMP_DIR/argocd/root-app.yaml"

echo "Deployment manifests submitted."
echo "Check sync with: kubectl -n argocd get applications"
