output "irsa_role_arn" {
  description = "IAM role ARN for the api-gateway ServiceAccount (IRSA)"
  value       = aws_iam_role.api_gateway.arn
}

output "irsa_role_name" {
  description = "IAM role name for the api-gateway ServiceAccount"
  value       = aws_iam_role.api_gateway.name
}

output "helm_release_status" {
  description = "Status of the api-gateway Helm release"
  value       = helm_release.api_gateway.status
}

output "helm_release_version" {
  description = "Deployed chart version"
  value       = helm_release.api_gateway.version
}
