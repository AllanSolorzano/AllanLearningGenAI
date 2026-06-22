#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

AUTO_COMMIT_PUSH="${AUTO_COMMIT_PUSH:-false}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres-demo-password-change-me}"
WAIT_FOR_ALB_SECONDS="${WAIT_FOR_ALB_SECONDS:-900}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-15}"
ARGOCD_REPO_URL="${ARGOCD_REPO_URL:-}"

log() {
  printf '\n==> %s\n' "$*"
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing required command: $1"
  fi
}

ensure_tfvars() {
  if [[ ! -f "$ROOT_DIR/terraform/terraform.tfvars" ]]; then
    log "terraform.tfvars not found; copying terraform.tfvars.example"
    cp "$ROOT_DIR/terraform/terraform.tfvars.example" "$ROOT_DIR/terraform/terraform.tfvars"
  fi
}

ensure_argocd_repo_url() {
  if [[ -z "$ARGOCD_REPO_URL" ]]; then
    fail "ARGOCD_REPO_URL is required. Example: export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git"
  fi
}

ensure_gitops_ready() {
  if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "This script expects the repo to be a Git worktree so Argo CD can sync committed manifests."
  fi

  local branch
  branch="$(git -C "$ROOT_DIR" branch --show-current)"
  if [[ -z "$branch" ]]; then
    fail "Git is in detached HEAD state; checkout a branch before deploying with Argo CD."
  fi

  if ! git -C "$ROOT_DIR" remote get-url origin >/dev/null 2>&1; then
    fail "Git remote 'origin' is not configured. Add it before running the happy path."
  fi

  if [[ "$AUTO_COMMIT_PUSH" == "true" ]]; then
    log "AUTO_COMMIT_PUSH=true; committing and pushing generated GitOps changes"
    git -C "$ROOT_DIR" add -A
    if git -C "$ROOT_DIR" diff --cached --quiet; then
      echo "No Git changes to commit."
    else
      git -C "$ROOT_DIR" commit -m "Deploy AI Chaos Arena platform"
    fi
    git -C "$ROOT_DIR" push -u origin "$branch"
    return
  fi

  if [[ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
    cat >&2 <<EOF
Generated or local changes are present and AUTO_COMMIT_PUSH is not enabled.

Review, commit, and push the repo before running the deploy step, or rerun with:

  AUTO_COMMIT_PUSH=true ARGOCD_REPO_URL=$ARGOCD_REPO_URL scripts/happy-path-deploy.sh

EOF
    git -C "$ROOT_DIR" status --short
    exit 1
  fi

  local local_sha remote_sha
  local_sha="$(git -C "$ROOT_DIR" rev-parse HEAD)"
  if remote_sha="$(git -C "$ROOT_DIR" rev-parse "@{u}" 2>/dev/null)"; then
    if [[ "$local_sha" != "$remote_sha" ]]; then
      fail "Local HEAD differs from upstream. Push your branch before deploying, or set AUTO_COMMIT_PUSH=true."
    fi
  else
    fail "Current branch has no upstream. Push it first, or set AUTO_COMMIT_PUSH=true."
  fi
}

wait_for_workload() {
  local namespace="$1"
  local kind="$2"
  local name="$3"
  local timeout="$4"

  log "Waiting for ${kind}/${name} in ${namespace}"
  local elapsed=0
  until kubectl -n "$namespace" get "$kind" "$name" >/dev/null 2>&1; do
    if (( elapsed >= timeout )); then
      fail "Timed out waiting for ${kind}/${name} to be created in ${namespace}"
    fi
    sleep "$WAIT_INTERVAL_SECONDS"
    elapsed=$((elapsed + WAIT_INTERVAL_SECONDS))
  done

  kubectl -n "$namespace" rollout status "${kind}/${name}" --timeout="${timeout}s"
}

wait_for_alb_health() {
  log "Waiting for ALB hostname and /health"
  local elapsed=0
  local host=""

  while (( elapsed < WAIT_FOR_ALB_SECONDS )); do
    host="$(kubectl -n chaos-app get ingress chaos-store -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
    if [[ -n "$host" ]]; then
      if command -v curl >/dev/null 2>&1 && curl --fail --silent --show-error "http://${host}/health" >/dev/null; then
        echo "Application is healthy: http://${host}/"
        return
      fi
      echo "ALB exists but health is not ready yet: http://${host}/health"
    else
      echo "ALB hostname not ready yet."
    fi

    sleep "$WAIT_INTERVAL_SECONDS"
    elapsed=$((elapsed + WAIT_INTERVAL_SECONDS))
  done

  fail "Timed out waiting for ALB health after ${WAIT_FOR_ALB_SECONDS}s"
}

log "Checking prerequisites"
for command_name in aws terraform kubectl docker jq git sed; do
  require_command "$command_name"
done

ensure_argocd_repo_url
ensure_tfvars

log "Bootstrap checks"
bash "$ROOT_DIR/scripts/bootstrap.sh"

log "Provisioning or reconciling AWS infrastructure"
bash "$ROOT_DIR/scripts/deploy-infra.sh"

log "Building and pushing images"
bash "$ROOT_DIR/scripts/build-and-push.sh"

log "Configuring Argo CD repo URLs"
bash "$ROOT_DIR/scripts/configure-argocd-repo.sh"

ensure_gitops_ready

log "Installing or reconciling Argo CD"
bash "$ROOT_DIR/scripts/install-argocd.sh"

log "Applying namespaces, platform resources, secrets, agent RBAC, and Argo CD applications"
DB_USER="$DB_USER" DB_PASSWORD="$DB_PASSWORD" bash "$ROOT_DIR/scripts/deploy-apps.sh"

wait_for_workload chaos-app statefulset postgres 600
wait_for_workload chaos-app deployment inventory-service 600
wait_for_workload chaos-app deployment order-service 600
wait_for_workload chaos-app deployment payment-service 600
wait_for_workload chaos-app deployment api-gateway 600
wait_for_workload chaos-app deployment frontend 600
wait_for_alb_health

log "Final validation snapshot"
bash "$ROOT_DIR/scripts/validate.sh"

log "Happy path deployment complete"
