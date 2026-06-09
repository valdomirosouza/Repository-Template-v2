variable "name_prefix" {
  type        = string
  description = "Prefix for all resource names."
}

variable "vpc_id" {
  type        = string
  description = "VPC for the MSK cluster."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs — one broker node is placed per subnet."
}

variable "allowed_security_group_ids" {
  type        = list(string)
  description = "Security group IDs allowed to connect to Kafka brokers."
}

variable "kafka_version" {
  type        = string
  default     = "3.7.x"
  description = "Apache Kafka version for the MSK cluster."
}

variable "broker_instance_type" {
  type        = string
  default     = "kafka.m5.large"
  description = "EC2 instance type for MSK broker nodes."
}

variable "broker_volume_size_gb" {
  type        = number
  default     = 100
  description = "EBS volume size per broker in GiB."
}

variable "default_replication_factor" {
  type        = number
  default     = 3
  description = "Kafka default.replication.factor. Must be ≤ number of broker nodes. Use 2 for 2-broker staging clusters."
}

variable "min_insync_replicas" {
  type        = number
  default     = 2
  description = "Kafka min.insync.replicas. Must be < default_replication_factor to allow leader election."
}

variable "client_topics" {
  type        = list(string)
  default     = ["*"]
  description = "Topic name patterns the IRSA client may read/write (per-topic least-privilege, FR-06). Default '*' = all topics in this cluster only."
}

variable "client_consumer_groups" {
  type        = list(string)
  default     = ["*"]
  description = "Consumer-group name patterns the IRSA client may join (least-privilege, FR-06). Default '*' = all groups in this cluster only."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags applied to all resources."
}
