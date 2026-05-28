variable "name_prefix" {
  type        = string
  description = "Prefix for all resource names."
}

variable "vpc_id" {
  type        = string
  description = "VPC in which to place the RDS instance."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the DB subnet group (minimum 2 for Multi-AZ)."
}

variable "allowed_security_group_ids" {
  type        = list(string)
  description = "Security group IDs allowed to connect to PostgreSQL on port 5432."
}

variable "engine_version" {
  type        = string
  default     = "16.3"
  description = "PostgreSQL engine version."
}

variable "instance_class" {
  type        = string
  default     = "db.t3.medium"
  description = "RDS instance class."
}

variable "allocated_storage_gb" {
  type        = number
  default     = 20
  description = "Initial storage allocation in GiB."
}

variable "max_allocated_storage_gb" {
  type        = number
  default     = 100
  description = "Maximum storage for autoscaling in GiB (0 = disabled)."
}

variable "multi_az" {
  type        = bool
  default     = false
  description = "Enable Multi-AZ standby replica. Set true in production."
}

variable "deletion_protection" {
  type        = bool
  default     = false
  description = "Prevent accidental deletion. Set true in production."
}

variable "backup_retention_days" {
  type        = number
  default     = 7
  description = "Automated backup retention period in days."
}

variable "db_name" {
  type        = string
  default     = "appdb"
  description = "Name of the initial database."
}

variable "db_username" {
  type        = string
  default     = "appuser"
  description = "Master username for the database."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags applied to all resources."
}
