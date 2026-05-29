output "app_log_group_name" {
  description = "CloudWatch log group name for application logs."
  value       = aws_cloudwatch_log_group.app.name
}

output "audit_log_group_name" {
  description = "CloudWatch log group name for audit logs (1-year retention)."
  value       = aws_cloudwatch_log_group.audit.name
}

output "agent_log_group_name" {
  description = "CloudWatch log group name for agent/harness logs."
  value       = aws_cloudwatch_log_group.agent.name
}

output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic. Subscribe email/PagerDuty/Slack here."
  value       = aws_sns_topic.alerts.arn
}

output "alarm_arns" {
  description = "ARNs of all CloudWatch metric alarms created by this module."
  value = [
    aws_cloudwatch_metric_alarm.high_error_rate.arn,
    aws_cloudwatch_metric_alarm.high_p99_latency.arn,
    aws_cloudwatch_metric_alarm.zero_traffic.arn,
    aws_cloudwatch_metric_alarm.high_cpu.arn,
    aws_cloudwatch_metric_alarm.hitl_approval_timeout.arn,
  ]
}
