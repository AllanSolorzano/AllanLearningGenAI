# GameDay Scenarios

## Steady State

Baseline checks:

```bash
kubectl get pods -n chaos-app
kubectl get hpa -n chaos-app
kubectl get ingress -n chaos-app
curl http://ALB_HOSTNAME/health
curl http://ALB_HOSTNAME/metrics
curl http://ALB_HOSTNAME/api/products
```

Expected state:

- frontend, `api-gateway`, `order-service`, and `inventory-service` have at least 2 ready replicas in the base desired state.
- `payment-service` has 1 replica in the gameday overlay.
- Postgres is ready.
- checkout succeeds with a product in the cart.
- request and checkout metrics increment after traffic.

## Kill API Gateway Pod

Hypothesis: frontend remains reachable and the gateway Deployment restores capacity after one pod is killed.

```bash
kubectl apply -f k8s/chaos/pod-kill-api-gateway.yaml
kubectl get pods -n chaos-app -w
kubectl delete -f k8s/chaos/pod-kill-api-gateway.yaml --ignore-not-found
```

Observe frontend availability, gateway readiness, ALB health, and checkout behavior.

## Kill Order Service Pod

Hypothesis: in-flight checkout may fail briefly, but the gateway returns a controlled error and the Deployment recovers.

```bash
kubectl apply -f k8s/chaos/pod-kill-order-service.yaml
kubectl get pods -n chaos-app -w
kubectl delete -f k8s/chaos/pod-kill-order-service.yaml --ignore-not-found
```

## Kill Inventory Service Pod

Hypothesis: products and checkout degrade when inventory is unavailable, while the gateway stays healthy enough to report dependency readiness.

```bash
kubectl apply -f k8s/chaos/pod-kill-inventory-service.yaml
curl http://ALB_HOSTNAME/ready
kubectl delete -f k8s/chaos/pod-kill-inventory-service.yaml --ignore-not-found
```

## Gateway to Inventory Latency

Hypothesis: checkout and product latency increase visibly in metrics and traces.

```bash
kubectl apply -f k8s/chaos/network-delay-api-gateway-to-inventory.yaml
curl http://ALB_HOSTNAME/api/products
curl http://ALB_HOSTNAME/metrics
kubectl delete -f k8s/chaos/network-delay-api-gateway-to-inventory.yaml --ignore-not-found
```

## Gateway to Payment Latency

Hypothesis: checkout latency rises, and traces show the payment dependency as the slow span.

```bash
kubectl apply -f k8s/chaos/network-delay-api-gateway-to-payment.yaml
curl -X POST http://ALB_HOSTNAME/api/checkout -H 'content-type: application/json' -d '{}'
kubectl delete -f k8s/chaos/network-delay-api-gateway-to-payment.yaml --ignore-not-found
```

## CPU Stress Inventory

Hypothesis: HPA can scale `inventory-service`, but the gameday overlay's low CPU request makes the signal noisy and instructive.

```bash
kubectl apply -f k8s/chaos/cpu-stress-inventory-service.yaml
kubectl get hpa -n chaos-app -w
kubectl delete -f k8s/chaos/cpu-stress-inventory-service.yaml --ignore-not-found
```

## Memory Stress Order Service

Hypothesis: order creation becomes unstable before the gateway itself fails.

```bash
kubectl apply -f k8s/chaos/memory-stress-order-service.yaml
kubectl get pods -n chaos-app -l app.kubernetes.io/name=order-service -w
kubectl delete -f k8s/chaos/memory-stress-order-service.yaml --ignore-not-found
```

## Break Payment Service

Hypothesis: checkout fails gracefully when payment authorization is unavailable. In the gameday overlay, payment fallback is intentionally disabled.

```bash
kubectl apply -f k8s/chaos/break-payment-service.yaml
curl -X POST http://ALB_HOSTNAME/api/checkout -H 'content-type: application/json' -d '{}'
kubectl delete -f k8s/chaos/break-payment-service.yaml --ignore-not-found
```

Expected: API response is a controlled failure, not a gateway crash.

## Scale Order Service Down

Hypothesis: reducing order capacity reveals whether the checkout path still has enough redundancy.

```bash
kubectl apply -f k8s/chaos/order-service-scale-down.yaml
kubectl -n chaos-app get deployment order-service -w
kubectl -n chaos-app scale deployment/order-service --replicas=2
```

If Argo CD app self-heal is active, it may restore the desired replica count from Git.

## App-Level Faults

Each Node service has safe in-memory fault endpoints. Through the ALB you can reach the gateway faults:

```bash
curl -X POST http://ALB_HOSTNAME/fault/latency \
  -H 'content-type: application/json' \
  -d '{"latencyMs":750}'

curl http://ALB_HOSTNAME/api/products

curl -X POST http://ALB_HOSTNAME/fault/reset \
  -H 'content-type: application/json' \
  -d '{}'
```

For internal services, use port-forwarding or an in-cluster debug pod.

## Readiness Probe Challenge

The gameday overlay removes the `payment-service` readiness probe. Ask participants to identify the missing probe, restore it in an overlay patch, commit, and watch Argo CD converge.

## GitOps Drift

Hypothesis: Argo CD self-heals manual drift in the app deployment.

```bash
kubectl -n chaos-app scale deployment/api-gateway --replicas=1
kubectl -n argocd get application chaos-store-app -w
kubectl -n chaos-app get deployment api-gateway -w
```

Expected: Argo CD restores the desired replica count from Git.
