# AWS Load Balancer Controller Notes

Terraform creates an IRSA role and, by default, installs AWS Load Balancer Controller with Helm in `kube-system`.

If you set `enable_aws_load_balancer_controller = false`, install it manually with the Terraform output role ARN:

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName="$(terraform -chdir=terraform output -raw cluster_name)" \
  --set region="$(terraform -chdir=terraform output -raw region)" \
  --set vpcId="$(terraform -chdir=terraform output -raw vpc_id)" \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="$(terraform -chdir=terraform output -raw aws_load_balancer_controller_role_arn)"
```

The app ingress uses `ingressClassName: alb` and `alb.ingress.kubernetes.io/target-type: ip`.
