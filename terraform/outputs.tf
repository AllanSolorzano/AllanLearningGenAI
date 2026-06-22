output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "region" {
  description = "AWS region."
  value       = var.aws_region
}

output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs."
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs."
  value       = module.vpc.public_subnets
}

output "ecr_api_gateway_repo_url" {
  description = "API Gateway ECR repository URL."
  value       = aws_ecr_repository.api_gateway.repository_url
}

output "ecr_frontend_repo_url" {
  description = "Frontend ECR repository URL."
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecr_order_service_repo_url" {
  description = "Order service ECR repository URL."
  value       = aws_ecr_repository.order_service.repository_url
}

output "ecr_inventory_service_repo_url" {
  description = "Inventory service ECR repository URL."
  value       = aws_ecr_repository.inventory_service.repository_url
}

output "ecr_payment_service_repo_url" {
  description = "Payment service ECR repository URL."
  value       = aws_ecr_repository.payment_service.repository_url
}

output "ecr_agent_repo_url" {
  description = "Agent ECR repository URL."
  value       = aws_ecr_repository.agent.repository_url
}

output "aws_load_balancer_controller_role_arn" {
  description = "IRSA role ARN for AWS Load Balancer Controller."
  value       = module.aws_load_balancer_controller_irsa.iam_role_arn
}

output "ebs_csi_role_arn" {
  description = "IRSA role ARN for EBS CSI Driver."
  value       = module.ebs_csi_irsa.iam_role_arn
}

output "external_dns_role_arn" {
  description = "Optional ExternalDNS IRSA role ARN."
  value       = var.enable_external_dns_irsa ? module.external_dns_irsa[0].iam_role_arn : null
}

output "dynatrace_role_arn" {
  description = "Optional Dynatrace IRSA role ARN."
  value       = var.enable_dynatrace_irsa ? module.dynatrace_irsa[0].iam_role_arn : null
}

output "kubeconfig_update_command" {
  description = "Command to configure kubectl for the cluster."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
