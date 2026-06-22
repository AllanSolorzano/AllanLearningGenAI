data "aws_iam_policy_document" "aws_load_balancer_controller" {
  statement {
    effect = "Allow"
    actions = [
      "iam:CreateServiceLinkedRole"
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["elasticloadbalancing.amazonaws.com"]
    }
  }

  statement {
    effect = "Allow"
    actions = [
      "ec2:DescribeAccountAttributes",
      "ec2:DescribeAddresses",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeCoipPools",
      "ec2:DescribeInstances",
      "ec2:DescribeInternetGateways",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeTags",
      "ec2:DescribeVpcPeeringConnections",
      "ec2:DescribeVpcs",
      "elasticloadbalancing:DescribeListenerAttributes",
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeLoadBalancerAttributes",
      "elasticloadbalancing:DescribeLoadBalancers",
      "elasticloadbalancing:DescribeRules",
      "elasticloadbalancing:DescribeSSLPolicies",
      "elasticloadbalancing:DescribeTags",
      "elasticloadbalancing:DescribeTargetGroupAttributes",
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetHealth",
      "elasticloadbalancing:DescribeTrustStores",
      "elasticloadbalancing:DescribeListenerCertificates",
      "acm:DescribeCertificate",
      "acm:ListCertificates",
      "iam:GetServerCertificate",
      "iam:ListServerCertificates",
      "cognito-idp:DescribeUserPoolClient",
      "waf-regional:GetWebACL",
      "waf-regional:GetWebACLForResource",
      "waf-regional:AssociateWebACL",
      "waf-regional:DisassociateWebACL",
      "wafv2:GetWebACL",
      "wafv2:GetWebACLForResource",
      "wafv2:AssociateWebACL",
      "wafv2:DisassociateWebACL",
      "shield:DescribeProtection",
      "shield:GetSubscriptionState",
      "shield:CreateProtection",
      "shield:DeleteProtection",
      "tag:GetResources",
      "tag:TagResources"
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:RevokeSecurityGroupIngress",
      "ec2:CreateSecurityGroup",
      "ec2:DeleteSecurityGroup",
      "ec2:CreateTags",
      "ec2:DeleteTags",
      "elasticloadbalancing:AddTags",
      "elasticloadbalancing:CreateListener",
      "elasticloadbalancing:CreateLoadBalancer",
      "elasticloadbalancing:CreateRule",
      "elasticloadbalancing:CreateTargetGroup",
      "elasticloadbalancing:DeleteListener",
      "elasticloadbalancing:DeleteLoadBalancer",
      "elasticloadbalancing:DeleteRule",
      "elasticloadbalancing:DeleteTargetGroup",
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyLoadBalancerAttributes",
      "elasticloadbalancing:ModifyRule",
      "elasticloadbalancing:ModifyTargetGroup",
      "elasticloadbalancing:ModifyTargetGroupAttributes",
      "elasticloadbalancing:RegisterTargets",
      "elasticloadbalancing:RemoveTags",
      "elasticloadbalancing:SetIpAddressType",
      "elasticloadbalancing:SetRulePriorities",
      "elasticloadbalancing:SetSecurityGroups",
      "elasticloadbalancing:SetSubnets",
      "elasticloadbalancing:SetWebAcl",
      "elasticloadbalancing:DeregisterTargets"
    ]
    resources = ["*"]
  }
}

module "aws_load_balancer_controller_irsa" {
  source = "./modules/irsa"

  role_name            = "${local.name}-aws-lbc"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider
  namespace            = "kube-system"
  service_account_name = "aws-load-balancer-controller"
  policy_json          = data.aws_iam_policy_document.aws_load_balancer_controller.json
  tags                 = local.tags
}

module "ebs_csi_irsa" {
  source = "./modules/irsa"

  role_name            = "${local.name}-ebs-csi"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider
  namespace            = "kube-system"
  service_account_name = "ebs-csi-controller-sa"
  managed_policy_arns  = ["arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"]
  create_inline_policy = false
  tags                 = local.tags
}

data "aws_iam_policy_document" "external_dns" {
  count = var.enable_external_dns_irsa ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "route53:ChangeResourceRecordSets"
    ]
    resources = var.external_dns_hosted_zone_arns
  }

  statement {
    effect = "Allow"
    actions = [
      "route53:ListHostedZones",
      "route53:ListResourceRecordSets"
    ]
    resources = ["*"]
  }
}

module "external_dns_irsa" {
  count  = var.enable_external_dns_irsa ? 1 : 0
  source = "./modules/irsa"

  role_name            = "${local.name}-external-dns"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider
  namespace            = "external-dns"
  service_account_name = "external-dns"
  policy_json          = data.aws_iam_policy_document.external_dns[0].json
  tags                 = local.tags
}

data "aws_iam_policy_document" "dynatrace_readonly" {
  count = var.enable_dynatrace_irsa ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "autoscaling:Describe*",
      "ec2:Describe*",
      "eks:DescribeCluster",
      "eks:ListClusters",
      "elasticloadbalancing:Describe*"
    ]
    resources = ["*"]
  }
}

module "dynatrace_irsa" {
  count  = var.enable_dynatrace_irsa ? 1 : 0
  source = "./modules/irsa"

  role_name            = "${local.name}-dynatrace"
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider
  namespace            = "dynatrace"
  service_account_name = "dynatrace-operator"
  policy_json          = data.aws_iam_policy_document.dynatrace_readonly[0].json
  tags                 = local.tags
}
