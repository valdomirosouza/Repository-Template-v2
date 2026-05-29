# Frontend module — IRSA role + Helm release for the Next.js operator UI.
# Spec: specs/system/architecture.md
# ADR:  ADR-0006 (Deployment Strategy), ADR-0008 (Secrets Management), ADR-0023 (Frontend)
#
# This module provisions:
#   1. An IAM role with IRSA trust for the frontend Kubernetes ServiceAccount
#   2. IAM policies: Secrets Manager read (OIDC client secret), CloudWatch Logs write
#   3. A Helm release deploying infrastructure/helm/frontend/

locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "frontend"
    Service     = "frontend"
  })

  service_account_namespace = var.namespace
  service_account_name      = var.service_account_name
}

# ── IRSA — IAM role bound to the K8s ServiceAccount ──────────────────────────

resource "aws_iam_role" "frontend" {
  name = "frontend-irsa-${var.environment}"

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
          "${var.oidc_provider_url}:sub" = "system:serviceaccount:${local.service_account_namespace}:${local.service_account_name}"
          "${var.oidc_provider_url}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = local.common_tags
}

# ── IAM policies ──────────────────────────────────────────────────────────────

resource "aws_iam_policy" "secrets_read" {
  name        = "frontend-secrets-read-${var.environment}"
  description = "Allow frontend to read OIDC client secret and other app secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = length(var.secrets_manager_arns) > 0 ? var.secrets_manager_arns : [
          "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:monorepo/${var.environment}/frontend/*"
        ]
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "frontend-cloudwatch-${var.environment}"
  description = "Allow frontend to write structured logs to CloudWatch"

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
      Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/monorepo/${var.environment}/frontend:*"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "secrets_read" {
  role       = aws_iam_role.frontend.name
  policy_arn = aws_iam_policy.secrets_read.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.frontend.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

# ── Helm release ──────────────────────────────────────────────────────────────

resource "helm_release" "frontend" {
  name      = "frontend"
  chart     = "${path.module}/../../../helm/frontend"
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
    value = aws_iam_role.frontend.arn
  }

  wait            = true
  timeout         = 300
  atomic          = true
  cleanup_on_fail = true

  lifecycle {
    ignore_changes = [
      # Image tag is managed by the CD pipeline, not Terraform
      set
    ]
  }
}
