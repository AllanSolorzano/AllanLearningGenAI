data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name         = "${var.project_name}-${var.environment}"
  cluster_name = "${local.name}-eks"
  azs          = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  private_subnets = [
    for index in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, index)
  ]

  public_subnets = [
    for index in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, index + 8)
  ]

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Repository  = "ai-chaos-gameday-platform"
  }
}
