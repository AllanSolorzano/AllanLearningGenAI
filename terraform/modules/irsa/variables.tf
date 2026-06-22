variable "role_name" {
  description = "IAM role name."
  type        = string
}

variable "oidc_provider_arn" {
  description = "EKS OIDC provider ARN."
  type        = string
}

variable "oidc_provider_url" {
  description = "EKS OIDC provider URL or host."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace containing the service account."
  type        = string
}

variable "service_account_name" {
  description = "Kubernetes service account name."
  type        = string
}

variable "policy_json" {
  description = "Inline IAM policy JSON. Required when create_inline_policy is true."
  type        = string
  default     = null
}

variable "create_inline_policy" {
  description = "Whether to create and attach an inline managed policy from policy_json."
  type        = bool
  default     = true
}

variable "managed_policy_arns" {
  description = "Existing managed policy ARNs to attach to the role."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to IAM resources."
  type        = map(string)
  default     = {}
}
