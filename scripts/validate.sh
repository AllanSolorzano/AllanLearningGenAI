#!/usr/bin/env bash
set -euo pipefail

echo "Nodes:"
kubectl get nodes -o wide

echo
echo "Pods:"
kubectl get pods -A

echo
echo "Ingress:"
kubectl get ingress -n chaos-app

echo
echo "Services:"
kubectl get svc -n chaos-app

echo
echo "Workload rollout status:"
for workload in \
  statefulset/postgres \
  deployment/inventory-service \
  deployment/order-service \
  deployment/payment-service \
  deployment/api-gateway \
  deployment/frontend; do
  kubectl -n chaos-app rollout status "$workload" --timeout=60s
done

ALB_HOST="$(kubectl -n chaos-app get ingress chaos-store -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"

if [[ -z "$ALB_HOST" ]]; then
  echo "ALB hostname is not ready yet. Re-run validate after AWS Load Balancer Controller reconciles the ingress."
  exit 0
fi

echo
echo "Checking health endpoint through ALB: http://${ALB_HOST}/health"
if command -v curl >/dev/null 2>&1; then
  curl --fail --show-error --silent "http://${ALB_HOST}/health"
  echo
else
  echo "curl is not installed; open http://${ALB_HOST}/health manually."
fi

echo "Validation completed."
