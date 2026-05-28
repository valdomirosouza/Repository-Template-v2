# event-worker application module — IRSA role + Helm release.
# Service: services/event-worker/ (Go Kafka consumer)
# ADR: ADR-0005 (Message Broker), ADR-0006 (Deployment Strategy)
#
# This module provisions:
#   1. IRSA role for the event-worker Kubernetes ServiceAccount
#   2. IAM policy: MSK cluster access (describe, read, write topics)
#   3. IAM policy: SQS send for the dead-letter queue
#   4. IAM policy: CloudWatch Logs write
#   5. IAM policy: Secrets Manager read (Kafka SASL credentials)
#   6. Helm release deploying infrastructure/helm/event-worker/

locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "event-worker"
    Service     = "event-worker"
  })
}

resource "aws_iam_role" "event_worker" {
  name = "event-worker-irsa-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${var.oidc_provider_url}:sub" = "system:serviceaccount:${var.namespace}:${var.service_account_name}"
          "${var.oidc_provider_url}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "msk_access" {
  count       = var.msk_cluster_arn != "" ? 1 : 0
  name        = "event-worker-msk-${var.environment}"
  description = "Allow event-worker to consume from and produce to MSK topics"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:CreateTopic",
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = [
          var.msk_cluster_arn,
          "${var.msk_cluster_arn}/*"
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "dlq_send" {
  count       = var.dlq_sqs_arn != "" ? 1 : 0
  name        = "event-worker-dlq-send-${var.environment}"
  description = "Allow event-worker to send unprocessable messages to the dead-letter queue"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
      Resource = var.dlq_sqs_arn
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "secrets_read" {
  name        = "event-worker-secrets-${var.environment}"
  description = "Allow event-worker to read Kafka SASL credentials from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:monorepo/${var.environment}/event-worker/*"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "event-worker-cloudwatch-${var.environment}"
  description = "Allow event-worker to write logs to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ]
      Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/monorepo/${var.environment}/event-worker:*"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "msk_access" {
  count      = var.msk_cluster_arn != "" ? 1 : 0
  role       = aws_iam_role.event_worker.name
  policy_arn = aws_iam_policy.msk_access[0].arn
}

resource "aws_iam_role_policy_attachment" "dlq_send" {
  count      = var.dlq_sqs_arn != "" ? 1 : 0
  role       = aws_iam_role.event_worker.name
  policy_arn = aws_iam_policy.dlq_send[0].arn
}

resource "aws_iam_role_policy_attachment" "secrets_read" {
  role       = aws_iam_role.event_worker.name
  policy_arn = aws_iam_policy.secrets_read.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.event_worker.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

resource "helm_release" "event_worker" {
  name      = "event-worker"
  chart     = "${path.module}/../../../helm/event-worker"
  namespace = var.namespace
  version   = var.helm_chart_version

  values = [
    file("${path.root}/${var.helm_values_file}")
  ]

  set {
    name  = "image.tag"
    value = var.image_tag
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.event_worker.arn
  }

  wait            = true
  timeout         = 300
  atomic          = true
  cleanup_on_fail = true

  lifecycle {
    ignore_changes = [set]
  }
}
