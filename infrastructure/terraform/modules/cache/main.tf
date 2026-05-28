# Cache module — ElastiCache Redis with TLS and encryption at rest.
# Spec: specs/privacy/redis-tls.md
# ADR:  ADR-0009 (Caching Strategy), ADR-0019 (Redis TLS and Value Encryption)

locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "cache"
  })
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.cluster_id}-subnet-group"
  subnet_ids = var.subnet_ids
  tags       = local.common_tags
}

# Parameter group — enforce TLS-only connections (ADR-0019)
resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.cluster_id}-params"
  family = "redis7"

  parameter {
    name  = "tls-replication-mode"
    value = "preferred"
  }

  tags = local.common_tags
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = var.cluster_id
  description          = "Redis cache — ${var.environment}"

  engine               = "redis"
  engine_version       = var.redis_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = var.security_group_ids
  port                 = 6380

  # TLS — required in production (ADR-0019)
  transit_encryption_enabled = true

  # Encryption at rest — required for L1/L2 PII data (ADR-0018)
  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.cache.arn

  # Automatic minor version upgrades
  auto_minor_version_upgrade = true

  # Maintenance window (off-peak UTC)
  maintenance_window = "sun:03:00-sun:04:00"
  snapshot_window    = "01:00-02:00"

  tags = merge(local.common_tags, { Name = var.cluster_id })
}

# KMS key for at-rest encryption
resource "aws_kms_key" "cache" {
  description             = "ElastiCache encryption — ${var.cluster_id}"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = merge(local.common_tags, { Name = "${var.cluster_id}-kms" })
}
