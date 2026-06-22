#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLACEHOLDER_REPO="https://github.com/REPLACE_ME/ai-chaos-gameday-platform.git"
ARGOCD_REPO_URL="${ARGOCD_REPO_URL:-}"

if [[ -z "$ARGOCD_REPO_URL" ]]; then
  echo "ARGOCD_REPO_URL is required." >&2
  echo "Example: export ARGOCD_REPO_URL=https://github.com/YOUR_ORG/ai-chaos-gameday-platform.git" >&2
  exit 1
fi

if ! grep -R "$PLACEHOLDER_REPO" "$ROOT_DIR/k8s/argocd" >/dev/null 2>&1; then
  echo "No placeholder Argo CD repoURL values found."
  exit 0
fi

echo "Replacing placeholder Argo CD repoURL values with ${ARGOCD_REPO_URL}."
for path in "$ROOT_DIR"/k8s/argocd/*.yaml; do
  tmp_path="${path}.tmp"
  sed "s#${PLACEHOLDER_REPO}#${ARGOCD_REPO_URL}#g" "$path" > "$tmp_path"
  mv "$tmp_path" "$path"
done

echo "Updated k8s/argocd/*.yaml. Commit and push these changes before make deploy."
