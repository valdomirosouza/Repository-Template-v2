output "cluster_writer_endpoint" {
  description = "Aurora cluster writer endpoint — follows the writer on failover (FR-02)."
  value       = aws_rds_cluster.main.endpoint
}

output "cluster_reader_endpoint" {
  description = "Aurora cluster reader endpoint — load-balances across reader instances."
  value       = aws_rds_cluster.main.reader_endpoint
}

output "port" {
  description = "Aurora cluster port."
  value       = aws_rds_cluster.main.port
}

output "db_name" {
  description = "Name of the initial database."
  value       = aws_rds_cluster.main.database_name
}

output "username" {
  description = "Master username — combine with the password from master_user_secret_arn to compose DATABASE_URL."
  value       = aws_rds_cluster.main.master_username
}

output "kms_key_arn" {
  description = "ARN of the customer-managed CMK used for storage + master-secret encryption (ADR-0018)."
  value       = local.kms_key_arn
}

output "master_user_secret_arn" {
  description = "ARN of the RDS-managed master-user secret in Secrets Manager. Contains ONLY {username, password}; password never in TF state."
  value       = try(aws_rds_cluster.main.master_user_secret[0].secret_arn, null)
}

output "cluster_arn" {
  description = "ARN of the Aurora cluster."
  value       = aws_rds_cluster.main.arn
}

output "cluster_identifier" {
  description = "Identifier of the Aurora cluster."
  value       = aws_rds_cluster.main.cluster_identifier
}

output "security_group_id" {
  description = "Security group ID attached to the Aurora cluster."
  value       = aws_security_group.db.id
}

# ── Compatibility aliases (ARN-shape only) ────────────────────────────────────
# These keep existing callers (e.g. domain-service module.database.secret_arn /
# .endpoint / .host) resolving during the brownfield cutover (ADR-0063). NOTE the
# secret *contents* changed: the old self-managed secret carried a ready url/host/
# port/dbname; the RDS-managed secret holds only {username, password}. Consumers
# that read the legacy `url`/`dbname` keys MUST switch to composing DATABASE_URL
# from the username/db_name/cluster_writer_endpoint/port outputs + the secret.

output "secret_arn" {
  description = "Alias of master_user_secret_arn. RDS-managed secret holds ONLY {username, password} — no legacy url/host/dbname keys."
  value       = try(aws_rds_cluster.main.master_user_secret[0].secret_arn, null)
}

output "endpoint" {
  description = "Alias of cluster_writer_endpoint (host:port) for existing callers."
  value       = "${aws_rds_cluster.main.endpoint}:${aws_rds_cluster.main.port}"
}

output "host" {
  description = "Alias of the cluster writer host for existing callers."
  value       = aws_rds_cluster.main.endpoint
}
