output "bootstrap_brokers_sasl_iam" {
  description = "SASL/IAM bootstrap broker endpoints (comma-separated). Use as KAFKA_BOOTSTRAP_SERVERS; clients auth via the IRSA-bound IAM role."
  value       = aws_msk_cluster.main.bootstrap_brokers_sasl_iam
}

output "cluster_arn" {
  description = "ARN of the MSK cluster."
  value       = aws_msk_cluster.main.arn
}

output "cluster_name" {
  description = "Name of the MSK cluster."
  value       = aws_msk_cluster.main.cluster_name
}

output "kafka_client_iam_policy_arn" {
  description = "ARN of the least-privilege Kafka SASL/IAM policy to attach to the application's IRSA role (FR-06)."
  value       = aws_iam_policy.kafka_client.arn
}

output "kms_key_arn" {
  description = "ARN of the CMK used for MSK encryption at rest."
  value       = aws_kms_key.msk.arn
}

output "security_group_id" {
  description = "Security group ID attached to the MSK brokers."
  value       = aws_security_group.msk.id
}
