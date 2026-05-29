variable "environment" {
  description = "Deployment environment (dev | staging | production)"
  type        = string
}

variable "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for the EKS cluster (output of the kubernetes module)"
  type        = string
}

variable "oidc_provider_url" {
  description = "IAM OIDC provider URL without https:// prefix (output of the kubernetes module)"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID — used to scope IAM ARNs"
  type        = string
}

variable "aws_region" {
  description = "AWS region — used to scope IAM ARNs"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace where the frontend is deployed"
  type        = string
  default     = "default"
}

variable "service_account_name" {
  description = "Kubernetes ServiceAccount name for the frontend pod"
  type        = string
  default     = "frontend"
}

variable "secrets_manager_arns" {
  description = "List of Secrets Manager ARN prefixes the frontend may read (OIDC client secret, etc.)"
  type        = list(string)
  default     = []
}

variable "helm_chart_version" {
  description = "Helm chart version to deploy (from infrastructure/helm/frontend/Chart.yaml)"
  type        = string
  default     = "0.1.0"
}

variable "helm_values_file" {
  description = "Path to the environment-specific values override file"
  type        = string
}

variable "image_tag" {
  description = "Container image tag to deploy"
  type        = string
  default     = "latest"
}

variable "tags" {
  description = "Additional tags applied to all AWS resources"
  type        = map(string)
  default     = {}
}
