output "irsa_role_arn" {
  description = "IAM role ARN for the domain-service ServiceAccount (IRSA)"
  value       = aws_iam_role.domain_service.arn
}

output "irsa_role_name" {
  description = "IAM role name for the domain-service ServiceAccount"
  value       = aws_iam_role.domain_service.name
}

output "helm_release_status" {
  description = "Status of the domain-service Helm release"
  value       = helm_release.domain_service.status
}

output "helm_release_version" {
  description = "Deployed chart version"
  value       = helm_release.domain_service.version
}
