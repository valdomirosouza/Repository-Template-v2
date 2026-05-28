variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
}

variable "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for the EKS cluster"
  type        = string
}

variable "oidc_provider_url" {
  description = "IAM OIDC provider URL without https:// prefix"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "default"
}

variable "service_account_name" {
  description = "Kubernetes ServiceAccount name for domain-service"
  type        = string
  default     = "domain-service"
}

variable "db_secret_arn" {
  description = "Secrets Manager ARN for the PostgreSQL credentials secret"
  type        = string
}

variable "helm_chart_version" {
  description = "Helm chart version to deploy"
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
