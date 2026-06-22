variable "project_name" {
  description = "Project prefix used for AWS resource names."
  type        = string
  default     = "ai-chaos-gameday-platform"
}

variable "environment" {
  description = "Environment name used in tags and names."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the EKS VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to use. Use 2 or 3 for this demo."
  type        = number
  default     = 3

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "single_nat_gateway" {
  description = "Use one NAT Gateway for demo cost control. Set false for one NAT Gateway per AZ."
  type        = bool
  default     = true
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.32"
}

variable "cluster_endpoint_public_access" {
  description = "Whether the EKS API endpoint is publicly reachable."
  type        = bool
  default     = true
}

variable "node_instance_types" {
  description = "EC2 instance types for the default managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_min_size" {
  description = "Minimum managed node group size."
  type        = number
  default     = 2
}

variable "node_desired_size" {
  description = "Desired managed node group size."
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum managed node group size."
  type        = number
  default     = 5
}

variable "ecr_force_delete" {
  description = "Allow Terraform destroy to remove non-empty ECR repositories. Useful for demo teardown."
  type        = bool
  default     = true
}

variable "enable_aws_load_balancer_controller" {
  description = "Install AWS Load Balancer Controller with Helm using the IRSA role created by Terraform."
  type        = bool
  default     = true
}

variable "aws_load_balancer_controller_chart_version" {
  description = "Optional Helm chart version for aws-load-balancer-controller. Empty uses the chart repository latest."
  type        = string
  default     = ""
}

variable "enable_external_dns_irsa" {
  description = "Create an ExternalDNS IRSA role. ExternalDNS itself is not installed by default."
  type        = bool
  default     = false
}

variable "external_dns_hosted_zone_arns" {
  description = "Route53 hosted zone ARNs ExternalDNS may update when enable_external_dns_irsa is true."
  type        = list(string)
  default     = []
}

variable "enable_dynatrace_irsa" {
  description = "Create an optional Dynatrace Operator IRSA role for AWS read-only metadata access."
  type        = bool
  default     = false
}
