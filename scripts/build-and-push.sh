#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${IMAGE_TAG:-}" ]]; then
  if git -C "$ROOT_DIR" rev-parse --verify HEAD >/dev/null 2>&1 \
    && [[ -z "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
    IMAGE_TAG="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"
  else
    IMAGE_TAG="$(date +%Y%m%d%H%M%S)"
    echo "Worktree is dirty or has no commit; using timestamp image tag ${IMAGE_TAG}."
    echo "Commit and push the exact source plus Kustomize image updates before Argo CD sync."
  fi
fi

API_GATEWAY_REPO="$(terraform -chdir="$ROOT_DIR/terraform" output -raw ecr_api_gateway_repo_url)"
FRONTEND_REPO="$(terraform -chdir="$ROOT_DIR/terraform" output -raw ecr_frontend_repo_url)"
ORDER_SERVICE_REPO="$(terraform -chdir="$ROOT_DIR/terraform" output -raw ecr_order_service_repo_url)"
INVENTORY_SERVICE_REPO="$(terraform -chdir="$ROOT_DIR/terraform" output -raw ecr_inventory_service_repo_url)"
PAYMENT_SERVICE_REPO="$(terraform -chdir="$ROOT_DIR/terraform" output -raw ecr_payment_service_repo_url)"
REGION="$(terraform -chdir="$ROOT_DIR/terraform" output -raw region)"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

echo "Logging in to ECR for account ${ACCOUNT_ID} in ${REGION}..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "Building api-gateway image..."
docker build -t "${API_GATEWAY_REPO}:${IMAGE_TAG}" -t "${API_GATEWAY_REPO}:latest" "$ROOT_DIR/app/backend/api-gateway"

echo "Building order-service image..."
docker build -t "${ORDER_SERVICE_REPO}:${IMAGE_TAG}" -t "${ORDER_SERVICE_REPO}:latest" "$ROOT_DIR/app/backend/order-service"

echo "Building inventory-service image..."
docker build -t "${INVENTORY_SERVICE_REPO}:${IMAGE_TAG}" -t "${INVENTORY_SERVICE_REPO}:latest" "$ROOT_DIR/app/backend/inventory-service"

echo "Building payment-service image..."
docker build -t "${PAYMENT_SERVICE_REPO}:${IMAGE_TAG}" -t "${PAYMENT_SERVICE_REPO}:latest" "$ROOT_DIR/app/backend/payment-service"

echo "Building frontend image..."
docker build -t "${FRONTEND_REPO}:${IMAGE_TAG}" -t "${FRONTEND_REPO}:latest" "$ROOT_DIR/app/frontend"

echo "Pushing images..."
docker push "${API_GATEWAY_REPO}:${IMAGE_TAG}"
docker push "${API_GATEWAY_REPO}:latest"
docker push "${ORDER_SERVICE_REPO}:${IMAGE_TAG}"
docker push "${ORDER_SERVICE_REPO}:latest"
docker push "${INVENTORY_SERVICE_REPO}:${IMAGE_TAG}"
docker push "${INVENTORY_SERVICE_REPO}:latest"
docker push "${PAYMENT_SERVICE_REPO}:${IMAGE_TAG}"
docker push "${PAYMENT_SERVICE_REPO}:latest"
docker push "${FRONTEND_REPO}:${IMAGE_TAG}"
docker push "${FRONTEND_REPO}:latest"

for overlay in dev gameday; do
  tag="$IMAGE_TAG"
  extra_patch=""
  if [[ "$overlay" == "gameday" ]]; then
    extra_patch="  - target:
      group: apps
      version: v1
      kind: Deployment
      name: payment-service
    path: remove-payment-readiness.yaml"
  fi

  cat > "$ROOT_DIR/k8s/app/overlays/${overlay}/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
patches:
  - path: patch.yaml
${extra_patch}
images:
  - name: chaos-api-gateway
    newName: ${API_GATEWAY_REPO}
    newTag: ${tag}
  - name: chaos-order-service
    newName: ${ORDER_SERVICE_REPO}
    newTag: ${tag}
  - name: chaos-inventory-service
    newName: ${INVENTORY_SERVICE_REPO}
    newTag: ${tag}
  - name: chaos-payment-service
    newName: ${PAYMENT_SERVICE_REPO}
    newTag: ${tag}
  - name: chaos-frontend
    newName: ${FRONTEND_REPO}
    newTag: ${tag}
EOF
done

echo "Updated k8s/app/overlays/dev and k8s/app/overlays/gameday image overrides to tag ${IMAGE_TAG}."
echo "Commit and push those overlay changes before Argo CD syncs from Git."
