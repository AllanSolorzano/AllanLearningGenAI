# Troubleshooting

## ALB Is Not Created

Checks:

```bash
kubectl get ingress -n chaos-app
kubectl describe ingress -n chaos-app chaos-store
kubectl logs -n kube-system deploy/aws-load-balancer-controller
terraform -chdir=terraform output aws_load_balancer_controller_role_arn
```

Common causes:

- AWS Load Balancer Controller is not running.
- subnet tags are missing.
- IRSA annotation is wrong.
- AWS account lacks ALB permissions.
- security group or subnet quota is exhausted.

## Image Pull Error

Checks:

```bash
kubectl describe pod -n chaos-app -l app.kubernetes.io/name=api-gateway
kubectl describe pod -n chaos-app -l app.kubernetes.io/name=order-service
kubectl describe pod -n chaos-app -l app.kubernetes.io/name=inventory-service
kubectl describe pod -n chaos-app -l app.kubernetes.io/name=payment-service
kubectl describe pod -n chaos-app -l app.kubernetes.io/name=frontend
kubectl get sa -n chaos-app
```

Common causes:

- `make build-push` was not run.
- Kustomize image overrides were not committed/pushed before Argo CD sync.
- ECR repository region/account does not match cluster account.
- node IAM permissions cannot pull ECR images.

## DB Connection Error

Checks:

```bash
kubectl get pods -n chaos-app -l app.kubernetes.io/name=postgres
kubectl logs -n chaos-app statefulset/postgres
kubectl logs -n chaos-app deploy/order-service
kubectl logs -n chaos-app deploy/inventory-service
kubectl logs -n chaos-app deploy/payment-service
kubectl get secret -n chaos-app chaos-db-secret -o yaml
```

Common causes:

- DB secret is missing.
- Postgres PVC is pending because EBS CSI Driver or gp3 StorageClass is missing.
- services started before Postgres became ready; Deployments should recover after probes retry.
- a NetworkPolicy blocks service-to-Postgres traffic.

## Checkout Fails

Checks:

```bash
curl http://ALB_HOSTNAME/api/products
curl http://ALB_HOSTNAME/ready
kubectl logs -n chaos-app deploy/api-gateway
kubectl logs -n chaos-app deploy/payment-service
kubectl logs -n chaos-app deploy/order-service
kubectl logs -n chaos-app deploy/inventory-service
```

Common causes:

- no items have been added to the gateway cart.
- `payment-service` is broken by a chaos experiment.
- inventory is exhausted or reservation failed.
- `PAYMENT_FALLBACK_ENABLED=false` in the gameday overlay, so payment failure correctly fails checkout.
- service timeout values are too low or too high for the experiment.

## Pods Pending

Checks:

```bash
kubectl describe pod -n chaos-app POD_NAME
kubectl get nodes
kubectl get events -A --sort-by=.lastTimestamp
```

Common causes:

- node group too small for requested resources.
- EBS volume cannot provision.
- unavailable AZ capacity for selected instance type.
- admission controls rejecting a workload.

## Argo App Out Of Sync

Checks:

```bash
kubectl -n argocd get applications
kubectl -n argocd describe application chaos-store-app
```

Common causes:

- placeholder `repoURL` was not replaced.
- image override changes were not pushed to Git.
- Argo CD does not have repository credentials for a private repo.
- manual cluster changes are being self-healed.

## Dynatrace Pods Not Running

Checks:

```bash
kubectl get pods -n dynatrace
kubectl describe dynakube -n dynatrace gameday
kubectl get secret -n dynatrace dynakube
```

Common causes:

- invalid `apiUrl`.
- token secret is missing or wrong.
- Operator version does not support the DynaKube API version.
- network egress from private subnets to Dynatrace is blocked.

## HPA Does Not Scale

Checks:

```bash
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl top pods -n chaos-app
kubectl describe hpa -n chaos-app api-gateway
kubectl describe hpa -n chaos-app inventory-service
kubectl describe hpa -n chaos-app order-service
kubectl describe hpa -n chaos-app payment-service
```

Common causes:

- metrics-server is not ready.
- pods do not have CPU requests.
- CPU pressure is too short-lived for HPA to react.
- the gameday overlay intentionally gives `inventory-service` a very low CPU request, which can make scaling behavior noisy.
