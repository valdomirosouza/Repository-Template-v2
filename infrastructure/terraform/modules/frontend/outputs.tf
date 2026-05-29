output "irsa_role_arn" {
  description = "IAM role ARN for the frontend ServiceAccount (IRSA)"
  value       = aws_iam_role.frontend.arn
}

output "irsa_role_name" {
  description = "IAM role name for the frontend ServiceAccount"
  value       = aws_iam_role.frontend.name
}

output "helm_release_status" {
  description = "Status of the frontend Helm release"
  value       = helm_release.frontend.status
}

output "helm_release_version" {
  description = "Deployed chart version"
  value       = helm_release.frontend.version
}
