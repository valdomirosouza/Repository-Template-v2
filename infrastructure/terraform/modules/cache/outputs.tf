output "primary_endpoint" {
  description = "Redis primary endpoint address (TLS, port 6380)"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "port" {
  description = "Redis port (TLS-only: 6380)"
  value       = 6380
}

output "redis_url" {
  description = "Redis connection URL for use in REDIS_URL env var (rediss:// scheme enforces TLS)"
  value       = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:6380/0"
  sensitive   = true
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for at-rest encryption"
  value       = aws_kms_key.cache.arn
}
