# `observability`

Provisions CloudWatch log groups (application / audit / agent), an SNS alerts topic, and Golden-Signal metric
alarms for one service. Instantiate **once per service** in each environment.

## Resources

- `aws_cloudwatch_log_group.app` — application logs (`log_retention_days`)
- `aws_cloudwatch_log_group.audit` — audit logs (**365-day** retention for LGPD/GDPR)
- `aws_cloudwatch_log_group.agent` — agent/harness logs
- `aws_sns_topic.alerts` — alarm notification topic
- `aws_cloudwatch_metric_alarm.high_error_rate` — HTTP error-rate (metric-query based)
- `aws_cloudwatch_metric_alarm.high_p99_latency` — P99 request latency
- `aws_cloudwatch_metric_alarm.zero_traffic` — zero-traffic detection
- `aws_cloudwatch_metric_alarm.high_cpu` — pod CPU (ContainerInsights namespace)
- `aws_cloudwatch_metric_alarm.hitl_approval_timeout` — HITL wait time

Locals: `metric_namespace = "TemplateMono/${var.service_name}"`, `alarm_actions` (`alarm_actions_arns` + SNS topic).

## Inputs

| Name                       | Type           | Default    | Description                                                  |
| -------------------------- | -------------- | ---------- | ------------------------------------------------------------ |
| `name_prefix`              | `string`       | _required_ | Prefix for all resource names.                               |
| `service_name`             | `string`       | _required_ | Monitored service (used in alarm names and log groups).      |
| `log_retention_days`       | `number`       | `30`       | App/agent log group retention (days).                        |
| `alarm_actions_arns`       | `list(string)` | `[]`       | Extra SNS topics / Lambdas to notify on alarm state changes. |
| `error_rate_threshold`     | `number`       | `1.0`      | HTTP error rate (%) that triggers the HighErrorRate alarm.   |
| `p99_latency_threshold_ms` | `number`       | `500`      | P99 latency (ms) that triggers the HighLatency alarm.        |
| `tags`                     | `map(string)`  | `{}`       | Additional tags applied to all resources.                    |

## Outputs

| Name                   | Description                                                        |
| ---------------------- | ------------------------------------------------------------------ |
| `app_log_group_name`   | CloudWatch log group name for application logs.                    |
| `audit_log_group_name` | CloudWatch log group name for audit logs (1-year retention).       |
| `agent_log_group_name` | CloudWatch log group name for agent/harness logs.                  |
| `sns_topic_arn`        | ARN of the SNS alerts topic. Subscribe email/PagerDuty/Slack here. |
| `alarm_arns`           | ARNs of all CloudWatch metric alarms created by this module.       |

## Usage

```hcl
module "obs_api_gateway" {
  source = "../../modules/observability"

  name_prefix              = "monorepo-production"
  service_name             = "api-gateway"
  log_retention_days       = 90
  error_rate_threshold     = 0.5
  p99_latency_threshold_ms = 300
  tags                     = local.obs_tags
}
```
