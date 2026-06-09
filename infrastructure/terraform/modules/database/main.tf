# Database module — Amazon Aurora PostgreSQL 17 cluster.
#
# Spec: SPEC-INFRA-001 FR-02 (§15.8 decision) — 1 writer + 2 reader instances,
#       one per AZ across 3 AZs, on shared cluster storage (sub-second replica lag);
#       readers are first-class auto-failover targets.
# ADR:  ADR-0062 (Aurora PostgreSQL — platform RDBMS),
#       ADR-0063 (brownfield reconciliation — rewrite this module in place, do not fork),
#       ADR-0018 (encryption at rest — storage encrypted with a customer-managed KMS key).
#
# Master credentials are managed by RDS (manage_master_user_password = true): RDS
# creates and rotates the secret in Secrets Manager and the password never lands in
# Terraform state (ADR-0018, CLAUDE.md §3.2).
#
# DATABASE_URL contract: the RDS-managed secret holds ONLY {username, password}.
# It does NOT contain a ready-to-use url/host/port/dbname (the master password is
# never readable in TF, so a full DSN cannot be assembled here). Consumers compose
# DATABASE_URL at runtime from the username/password in the secret plus the
# cluster_writer_endpoint / port / db_name / username outputs of this module.

# ── Encryption key (CMK) ──────────────────────────────────────────────────────
# Encryption at rest is always customer-managed (ADR-0018, CLAUDE.md §3.2): when no
# external key ARN is supplied, the module creates a dedicated CMK with rotation so
# storage, the master secret, and Performance Insights never fall back to the
# AWS-managed aws/rds key. Pass var.kms_key_arn to reuse an org-wide key instead.

resource "aws_kms_key" "db" {
  count = var.kms_key_arn == null ? 1 : 0

  description             = "CMK for ${var.name_prefix} Aurora storage + master secret encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-aurora-cmk" })
}

locals {
  kms_key_arn = var.kms_key_arn != null ? var.kms_key_arn : aws_kms_key.db[0].arn
}

# ── Security group ────────────────────────────────────────────────────────────

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-aurora-sg"
  description = "Allow PostgreSQL access from application security groups."
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-aurora-sg" })
}

# ── Subnet group (3 AZs) ──────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name        = "${var.name_prefix}-aurora-subnet-group"
  description = "Aurora subnet group for ${var.name_prefix} (3 AZs)"
  subnet_ids  = var.subnet_ids
  tags        = var.tags
}

# ── Cluster parameter group ───────────────────────────────────────────────────

resource "aws_rds_cluster_parameter_group" "main" {
  name        = "${var.name_prefix}-aurora-pg17"
  family      = var.cluster_parameter_group_family
  description = "Custom cluster parameter group for ${var.name_prefix} Aurora PostgreSQL 17"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # log queries > 1 s
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  tags = var.tags
}

# ── Aurora cluster ────────────────────────────────────────────────────────────

resource "aws_rds_cluster" "main" {
  cluster_identifier = "${var.name_prefix}-aurora"

  engine         = "aurora-postgresql"
  engine_version = var.engine_version
  engine_mode    = "provisioned"

  database_name = var.db_name
  port          = 5432

  # RDS-managed master password — created and rotated in Secrets Manager,
  # never written to Terraform state (ADR-0018, CLAUDE.md §3.2).
  master_username               = var.db_username
  manage_master_user_password   = true
  master_user_secret_kms_key_id = local.kms_key_arn

  # Storage encrypted at rest with the customer-managed KMS key (ADR-0018).
  storage_encrypted = true
  kms_key_id        = local.kms_key_arn

  # Aurora I/O-Optimized for steady write workloads (ADR-0062 §15.1 cost).
  storage_type = var.storage_type

  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.main.name

  backup_retention_period      = var.backup_retention_days
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "Mon:04:00-Mon:05:00"
  copy_tags_to_snapshot        = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.name_prefix}-aurora-final-snapshot" : null

  enabled_cloudwatch_logs_exports = ["postgresql"]

  apply_immediately = false

  tags = merge(var.tags, { Name = "${var.name_prefix}-aurora" })
}

# ── Cluster instances (1 writer + var.reader_count readers, one per AZ) ────────
# Aurora promotes the writer/readers automatically; readers are first-class
# auto-failover targets (FR-02). Instance 0 starts as the writer; on writer
# failure Aurora auto-promotes a reader (~30s) and the cluster writer endpoint
# follows it — no manual promotion path.

resource "aws_rds_cluster_instance" "main" {
  count = 1 + var.reader_count

  identifier         = "${var.name_prefix}-aurora-${count.index}"
  cluster_identifier = aws_rds_cluster.main.id

  engine         = aws_rds_cluster.main.engine
  engine_version = aws_rds_cluster.main.engine_version
  instance_class = var.instance_class

  db_subnet_group_name = aws_db_subnet_group.main.name

  # Spread instances across the cluster's AZs (one per AZ for 3-AZ HA).
  availability_zone = length(var.availability_zones) > 0 ? element(var.availability_zones, count.index) : null

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = local.kms_key_arn
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_enhanced_monitoring.arn

  # Promote writer (0) ahead of readers; readers are still failover targets.
  promotion_tier = count.index

  publicly_accessible = false
  apply_immediately   = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-aurora-${count.index}"
    Role = count.index == 0 ? "writer" : "reader"
  })
}

# ── Enhanced monitoring IAM role ──────────────────────────────────────────────

resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.name_prefix}-aurora-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
