# domain-service application module — IRSA role + Helm release.
# Service: services/domain-service/ (Java/Spring Boot)
# ADR: ADR-0006 (Deployment Strategy), ADR-0008 (Secrets Management), ADR-0018 (DB Encryption)
#
# This module provisions:
#   1. IRSA role for the domain-service Kubernetes ServiceAccount
#   2. IAM policy: Secrets Manager read for DB credentials and DB_ENCRYPTION_KEY
#   3. IAM policy: CloudWatch Logs write
#   4. Helm release deploying infrastructure/helm/domain-service/

locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "domain-service"
    Service     = "domain-service"
  })
}

resource "aws_iam_role" "domain_service" {
  name = "domain-service-irsa-${var.environment}"

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

resource "aws_iam_policy" "db_secrets_read" {
  name        = "domain-service-db-secrets-${var.environment}"
  description = "Allow domain-service to read DB credentials and encryption key from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        # DB credentials secret + application secrets prefix
        Resource = [
          var.db_secret_arn,
          "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:monorepo/${var.environment}/domain-service/*"
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "domain-service-cloudwatch-${var.environment}"
  description = "Allow domain-service to write logs to CloudWatch"

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
      Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/monorepo/${var.environment}/domain-service:*"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "db_secrets_read" {
  role       = aws_iam_role.domain_service.name
  policy_arn = aws_iam_policy.db_secrets_read.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.domain_service.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

resource "helm_release" "domain_service" {
  name      = "domain-service"
  chart     = "${path.module}/../../../helm/domain-service"
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
    value = aws_iam_role.domain_service.arn
  }

  wait            = true
  timeout         = 360
  atomic          = true
  cleanup_on_fail = true

  lifecycle {
    ignore_changes = [set]
  }
}
