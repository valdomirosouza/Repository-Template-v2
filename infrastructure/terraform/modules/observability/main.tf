# Observability module — CloudWatch log groups, SNS alerting, Golden Signal alarms.
#
# Spec: specs/system/architecture.md (Observability)
# ADR:  ADR-0004 (Observability Stack)
#
# Alarms mirror the Prometheus alert rules in
# infrastructure/monitoring/prometheus/rules/golden-signals.yaml.

# ── CloudWatch log groups ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "app" {
  name              = "/app/${var.name_prefix}/${var.service_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "audit" {
  name              = "/app/${var.name_prefix}/${var.service_name}/audit"
  retention_in_days = 365 # audit logs: 1-year minimum for compliance (LGPD/GDPR)
  tags              = merge(var.tags, { DataClassification = "audit" })
}

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/app/${var.name_prefix}/${var.service_name}/agent"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# ── SNS topic for alarm notifications ─────────────────────────────────────────

resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-${var.service_name}-alerts"
  tags = var.tags
}

# ── Golden Signal alarms ──────────────────────────────────────────────────────
# These alarms target metrics emitted by the application via the OTel Collector
# → CloudWatch EMF (Embedded Metric Format). Adjust namespace to match your
# OTel Collector cloudwatchlogs exporter configuration.

locals {
  metric_namespace = "TemplateMono/${var.service_name}"
  alarm_actions    = concat(var.alarm_actions_arns, [aws_sns_topic.alerts.arn])
}

resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.name_prefix}-${var.service_name}-HighErrorRate"
  alarm_description   = "HTTP error rate exceeded ${var.error_rate_threshold}% — Golden Signal: Errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = var.error_rate_threshold

  metric_query {
    id          = "error_rate"
    expression  = "100 * errors / MAX([errors, 1])"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      namespace   = local.metric_namespace
      metric_name = "http_requests_total"
      period      = 60
      stat        = "Sum"
      dimensions  = { status = "5xx" }
    }
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "high_p99_latency" {
  alarm_name          = "${var.name_prefix}-${var.service_name}-HighP99Latency"
  alarm_description   = "P99 request latency exceeded ${var.p99_latency_threshold_ms}ms — Golden Signal: Latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.p99_latency_threshold_ms

  metric_name = "http_request_duration_ms"
  namespace   = local.metric_namespace
  period      = 60
  # Percentiles must use extended_statistic, not statistic (which only accepts
  # SampleCount/Average/Sum/Minimum/Maximum) — SPEC-LGS-001 G-02 tail-latency.
  extended_statistic = "p99"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "zero_traffic" {
  alarm_name          = "${var.name_prefix}-${var.service_name}-ZeroTraffic"
  alarm_description   = "No requests received for 5 minutes — Golden Signal: Traffic"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 5
  threshold           = 0
  treat_missing_data  = "breaching"

  metric_name = "http_requests_total"
  namespace   = local.metric_namespace
  period      = 60
  statistic   = "Sum"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.name_prefix}-${var.service_name}-HighCPU"
  alarm_description   = "Pod CPU utilisation exceeded 80% — Golden Signal: Saturation"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 80

  metric_name = "pod_cpu_utilization"
  namespace   = "ContainerInsights"
  period      = 60
  statistic   = "Average"
  dimensions  = { ClusterName = var.name_prefix, Namespace = "default" }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "hitl_approval_timeout" {
  alarm_name          = "${var.name_prefix}-${var.service_name}-HITLApprovalTimeout"
  alarm_description   = "HITL requests waiting > 50 min — operator action required"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 3000 # 50 min in seconds

  metric_name = "hitl_wait_seconds"
  namespace   = local.metric_namespace
  period      = 60
  statistic   = "Maximum"

  alarm_actions = local.alarm_actions
  tags          = var.tags
}
