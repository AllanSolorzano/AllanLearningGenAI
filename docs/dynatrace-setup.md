# Dynatrace Setup

## What Is Included

This repo includes:

- `k8s/dynatrace/namespace.yaml`
- `k8s/dynatrace/secret.example.yaml`
- `k8s/dynatrace/dynakube.example.yaml`
- OpenTelemetry auto-instrumentation hooks in every Node.js service
- app pod annotations for OneAgent injection
- `chaos-app` namespace label for selective DynaKube injection

No tenant URL or token is committed.

## Tokens

Create Dynatrace tokens with the permissions required by the Dynatrace Operator version you install. At minimum, follow the current Dynatrace Operator documentation for:

- API token used by the Operator.
- Data ingest token used for metrics, logs, and traces ingest.

Store them as a Kubernetes secret:

```bash
kubectl apply -f k8s/dynatrace/namespace.yaml
kubectl -n dynatrace create secret generic dynakube \
  --from-literal=apiToken="$DYNATRACE_API_TOKEN" \
  --from-literal=dataIngestToken="$DYNATRACE_DATA_INGEST_TOKEN"
```

## Install Operator

Install the Dynatrace Operator using the current official method for your Dynatrace environment. Keep the operator install outside the app kustomization so tenant-specific settings stay explicit.

## Apply DynaKube

Copy the example:

```bash
cp k8s/dynatrace/dynakube.example.yaml /tmp/dynakube.yaml
```

Edit:

- `spec.apiUrl`
- token secret name if you changed it
- namespace selector if you want a different injection boundary

Apply:

```bash
kubectl apply -f /tmp/dynakube.yaml
```

The example uses `apiVersion: dynatrace.com/v1beta6`. Confirm this matches the Dynatrace Operator version you install.

## OpenTelemetry

Each Node.js service starts OpenTelemetry auto-instrumentation on boot. Set this value when an OTLP endpoint is available:

```yaml
OTEL_EXPORTER_OTLP_ENDPOINT: "http://YOUR_ACTIVEGATE_OR_COLLECTOR:4318"
```

Set it per service in:

- `k8s/app/base/api-gateway/configmap.yaml`
- `k8s/app/base/order-service/configmap.yaml`
- `k8s/app/base/inventory-service/configmap.yaml`
- `k8s/app/base/payment-service/configmap.yaml`

Or patch it through `k8s/app/overlays/dev/patch.yaml` and `k8s/app/overlays/gameday/patch.yaml`.

## Verify

```bash
kubectl get pods -n dynatrace
kubectl describe dynakube -n dynatrace gameday
kubectl get pods -n chaos-app -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.annotations}{"\n"}{end}'
kubectl logs -n chaos-app deploy/api-gateway
kubectl logs -n chaos-app deploy/order-service
kubectl logs -n chaos-app deploy/inventory-service
kubectl logs -n chaos-app deploy/payment-service
```

In Dynatrace, verify:

- Kubernetes cluster visible.
- services visible for `chaos-gameday-api-gateway`, `chaos-gameday-order-service`, `chaos-gameday-inventory-service`, and `chaos-gameday-payment-service`.
- traces for `/api/products` and `/api/checkout`.
- service-to-service spans across gateway, inventory, payment, and order.
- metrics for checkout success/failure, payment authorization, and request duration.
