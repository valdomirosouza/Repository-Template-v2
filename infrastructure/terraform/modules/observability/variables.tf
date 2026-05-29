variable "name_prefix" {
  type        = string
  description = "Prefix for all resource names."
}

variable "service_name" {
  type        = string
  description = "Name of the monitored service (used in alarm names and log groups)."
}

variable "log_retention_days" {
  type        = number
  default     = 30
  description = "CloudWatch log group retention period in days."
}

variable "alarm_actions_arns" {
  type        = list(string)
  default     = []
  description = "ARNs of SNS topics or Lambda functions to notify on alarm state changes."
}

variable "error_rate_threshold" {
  type        = number
  default     = 1.0
  description = "HTTP error rate (%) that triggers the HighErrorRate alarm."
}

variable "p99_latency_threshold_ms" {
  type        = number
  default     = 500
  description = "P99 latency in milliseconds that triggers the HighLatency alarm."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags applied to all resources."
}
