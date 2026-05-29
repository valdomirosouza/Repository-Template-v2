# Database module — RDS PostgreSQL 16.
#
# Spec: specs/system/architecture.md
# ADR:  ADR-0002 (Technology Stack Selection)
#
# Credentials are generated randomly and stored in AWS Secrets Manager.
# The application reads DATABASE_URL from the secret at startup via
# AWS SDK or an EKS init container — never hard-code credentials.

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%^&*()-_=+[]{}|;:,.<>?"
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "${var.name_prefix}/rds/credentials"
  recovery_window_in_days = 7
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    dbname   = var.db_name
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    url      = "postgresql+asyncpg://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${var.db_name}"
  })

  depends_on = [aws_db_instance.main]
}

# ── Security group ────────────────────────────────────────────────────────────

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-rds-sg"
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

  tags = merge(var.tags, { Name = "${var.name_prefix}-rds-sg" })
}

# ── Subnet group ──────────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name        = "${var.name_prefix}-rds-subnet-group"
  description = "RDS subnet group for ${var.name_prefix}"
  subnet_ids  = var.subnet_ids
  tags        = var.tags
}

# ── Parameter group ───────────────────────────────────────────────────────────

resource "aws_db_parameter_group" "main" {
  name        = "${var.name_prefix}-pg16"
  family      = "postgres16"
  description = "Custom parameter group for ${var.name_prefix} PostgreSQL 16"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

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

# ── RDS instance ──────────────────────────────────────────────────────────────

resource "aws_db_instance" "main" {
  identifier = "${var.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb > 0 ? var.max_allocated_storage_gb : null
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  multi_az                  = var.multi_az
  publicly_accessible       = false
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.name_prefix}-final-snapshot" : null

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_enhanced_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  apply_immediately = false

  tags = merge(var.tags, { Name = "${var.name_prefix}-postgres" })
}

# ── Enhanced monitoring IAM role ──────────────────────────────────────────────

resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.name_prefix}-rds-monitoring"

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
