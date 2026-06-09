# Message-broker module — Amazon MSK (Managed Streaming for Apache Kafka).
#
# Spec: SPEC-INFRA-001 FR-06 (§15.7 decision) — authentication = IAM (SASL/IAM),
#       bound via IRSA; no SASL/SCRAM secret, no client certs; per-topic
#       least-privilege through an IAM policy attachable to the IRSA role.
#       specs/system/async-event-flow.md, specs/api/async-api-design.md
# ADR:  ADR-0005 (Message Broker Selection),
#       ADR-0003 (async / Kafka),
#       ADR-0063 (brownfield reconciliation — flip auth in place, do not fork).
#
# Authentication: IAM (SASL/IAM). Clients (EKS pods) authenticate with their
# IRSA-bound IAM role — there is no shared SCRAM secret to store or rotate.
# Application reads KAFKA_BOOTSTRAP_SERVERS from bootstrap_brokers_sasl_iam.

# CMK for MSK encryption at rest (ADR-0018).
resource "aws_kms_key" "msk" {
  description             = "CMK for MSK encryption at rest"
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
    description     = "Kafka SASL/IAM TLS from app"
    from_port       = 9098
    to_port         = 9098
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

  # Authentication = IAM (SASL/IAM). SCRAM disabled (FR-06 §15.7).
  client_authentication {
    sasl {
      iam   = true
      scram = false
    }
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn

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

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.name_prefix}"
  retention_in_days = 30
  tags              = var.tags
}

# ── Per-topic least-privilege IAM policy (FR-06) ──────────────────────────────
# IAM policy document granting the minimum kafka-cluster actions for an IRSA role
# to connect and produce/consume on the configured topics + consumer groups.
# Attach to the application's IRSA role (no wildcard actions — CLAUDE.md §3.2).

data "aws_iam_policy_document" "kafka_client" {
  # Cluster-level connect + describe.
  statement {
    sid    = "KafkaClusterConnect"
    effect = "Allow"
    actions = [
      "kafka-cluster:Connect",
      "kafka-cluster:DescribeCluster",
    ]
    resources = [aws_msk_cluster.main.arn]
  }

  # Topic-level read/write/describe, scoped to var.client_topics.
  statement {
    sid    = "KafkaTopicReadWrite"
    effect = "Allow"
    actions = [
      "kafka-cluster:DescribeTopic",
      "kafka-cluster:ReadData",
      "kafka-cluster:WriteData",
    ]
    resources = [
      for topic in var.client_topics :
      "${replace(aws_msk_cluster.main.arn, ":cluster/", ":topic/")}/${topic}"
    ]
  }

  # Consumer-group describe/alter, scoped to var.client_consumer_groups.
  statement {
    sid    = "KafkaConsumerGroup"
    effect = "Allow"
    actions = [
      "kafka-cluster:AlterGroup",
      "kafka-cluster:DescribeGroup",
    ]
    resources = [
      for group in var.client_consumer_groups :
      "${replace(aws_msk_cluster.main.arn, ":cluster/", ":group/")}/${group}"
    ]
  }
}

# Managed policy that an IRSA role can attach for Kafka SASL/IAM access.
resource "aws_iam_policy" "kafka_client" {
  name        = "${var.name_prefix}-msk-client"
  description = "Least-privilege Kafka SASL/IAM access for ${var.name_prefix} (per-topic)."
  policy      = data.aws_iam_policy_document.kafka_client.json
  tags        = var.tags
}
