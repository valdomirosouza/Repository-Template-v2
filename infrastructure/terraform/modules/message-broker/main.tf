# Message-broker module — Amazon MSK (Managed Streaming for Apache Kafka).
#
# Spec: specs/system/async-event-flow.md, specs/api/async-api-design.md
# ADR:  ADR-0005 (Message Broker Selection)
#
# Authentication: SASL/SCRAM with credentials stored in Secrets Manager.
# Application reads KAFKA_BOOTSTRAP_SERVERS from the cluster outputs.

resource "random_password" "kafka_password" {
  length  = 20
  special = false
}

resource "aws_secretsmanager_secret" "kafka" {
  name                    = "${var.name_prefix}/msk/credentials"
  recovery_window_in_days = 7
  # MSK SASL/SCRAM secrets must use the "AmazonMSK_" prefix.
  kms_key_id = aws_kms_key.msk.arn
  tags       = var.tags
}

resource "aws_secretsmanager_secret_version" "kafka" {
  secret_id = aws_secretsmanager_secret.kafka.id
  secret_string = jsonencode({
    username = "kafka-app"
    password = random_password.kafka_password.result
  })
}

# MSK SASL/SCRAM secrets must be encrypted with a customer-managed KMS key.
resource "aws_kms_key" "msk" {
  description             = "CMK for MSK SASL/SCRAM secret encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-msk-cmk" })
}

resource "aws_kms_alias" "msk" {
  name          = "alias/${var.name_prefix}-msk"
  target_key_id = aws_kms_key.msk.key_id
}

# ── Security group ────────────────────────────────────────────────────────────

resource "aws_security_group" "msk" {
  name        = "${var.name_prefix}-msk-sg"
  description = "Allow Kafka access from application security groups."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Kafka SASL/SCRAM TLS from app"
    from_port       = 9096
    to_port         = 9096
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  ingress {
    description = "Kafka broker internal replication"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-msk-sg" })
}

# ── MSK cluster ───────────────────────────────────────────────────────────────

resource "aws_msk_cluster" "main" {
  cluster_name           = "${var.name_prefix}-kafka"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = length(var.subnet_ids)

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.broker_volume_size_gb

        provisioned_throughput {
          enabled           = true
          volume_throughput = 250
        }
      }
    }
  }

  client_authentication {
    sasl {
      scram = true
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-kafka" })
}

resource "aws_msk_configuration" "main" {
  name           = "${var.name_prefix}-kafka-config"
  kafka_versions = [var.kafka_version]
  server_properties = join("\n", [
    "auto.create.topics.enable=false",
    "default.replication.factor=${var.default_replication_factor}",
    "min.insync.replicas=${var.min_insync_replicas}",
    "num.partitions=12",
    "log.retention.hours=168",
    "log.retention.bytes=10737418240",
  ])
}

# Associate the SCRAM secret with the MSK cluster.
resource "aws_msk_scram_secret_association" "main" {
  cluster_arn     = aws_msk_cluster.main.arn
  secret_arn_list = [aws_secretsmanager_secret.kafka.arn]

  depends_on = [aws_secretsmanager_secret_version.kafka]
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.name_prefix}"
  retention_in_days = 30
  tags              = var.tags
}
