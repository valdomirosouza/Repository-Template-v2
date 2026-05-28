output "irsa_role_arn" {
  description = "IAM role ARN for the event-worker ServiceAccount (IRSA)"
  value       = aws_iam_role.event_worker.arn
}

output "irsa_role_name" {
  description = "IAM role name for the event-worker ServiceAccount"
  value       = aws_iam_role.event_worker.name
}

output "helm_release_status" {
  description = "Status of the event-worker Helm release"
  value       = helm_release.event_worker.status
}

output "helm_release_version" {
  description = "Deployed chart version"
  value       = helm_release.event_worker.version
}
