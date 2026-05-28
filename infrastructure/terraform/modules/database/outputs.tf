output "endpoint" {
  description = "RDS instance endpoint (host:port)."
  value       = "${aws_db_instance.main.address}:${aws_db_instance.main.port}"
}

output "host" {
  description = "RDS instance hostname."
  value       = aws_db_instance.main.address
}

output "port" {
  description = "RDS instance port."
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Name of the initial database."
  value       = aws_db_instance.main.db_name
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing DATABASE_URL and credentials."
  value       = aws_secretsmanager_secret.db.arn
}

output "security_group_id" {
  description = "Security group ID attached to the RDS instance."
  value       = aws_security_group.db.id
}
