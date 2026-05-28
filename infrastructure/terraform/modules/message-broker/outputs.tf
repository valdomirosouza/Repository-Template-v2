output "bootstrap_brokers_sasl_scram" {
  description = "SASL/SCRAM bootstrap broker endpoints (comma-separated). Use as KAFKA_BOOTSTRAP_SERVERS."
  value       = aws_msk_cluster.main.bootstrap_brokers_sasl_scram
}

output "cluster_arn" {
  description = "ARN of the MSK cluster."
  value       = aws_msk_cluster.main.arn
}

output "cluster_name" {
  description = "Name of the MSK cluster."
  value       = aws_msk_cluster.main.cluster_name
}

output "credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Kafka SASL/SCRAM credentials."
  value       = aws_secretsmanager_secret.kafka.arn
}

output "security_group_id" {
  description = "Security group ID attached to the MSK brokers."
  value       = aws_security_group.msk.id
}

output "zookeeper_connect_string" {
  description = "ZooKeeper connection string (legacy — use bootstrap_brokers for Kafka clients)."
  value       = aws_msk_cluster.main.zookeeper_connect_string
}
