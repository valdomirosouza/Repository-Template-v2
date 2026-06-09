variable "name_prefix" {
  type        = string
  description = "Prefix for all resource names."
}

variable "vpc_id" {
  type        = string
  description = "VPC in which to place the Aurora cluster."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the DB subnet group (3 AZs for the writer + 2 readers)."
}

variable "availability_zones" {
  type        = list(string)
  default     = []
  description = "AZs to spread cluster instances across (one per AZ). Empty = let AWS choose."
}

variable "allowed_security_group_ids" {
  type        = list(string)
  description = "Security group IDs allowed to connect to PostgreSQL on port 5432."
}

variable "engine_version" {
  type        = string
  default     = "17.4"
  description = "Aurora PostgreSQL engine version (17.x)."
  validation {
    condition     = can(regex("^17\\.", var.engine_version))
    error_message = "engine_version must be an Aurora PostgreSQL 17.x version (SPEC-INFRA-001 FR-02)."
  }
}

variable "cluster_parameter_group_family" {
  type        = string
  default     = "aurora-postgresql17"
  description = "Aurora cluster parameter group family. Must match the engine major version."
}

variable "instance_class" {
  type        = string
  default     = "db.r6g.large"
  description = "Aurora cluster instance class (applies to writer and readers)."
}

variable "reader_count" {
  type        = number
  default     = 2
  description = "Number of reader instances (writer is always 1). Default 2 = 3 instances across 3 AZs (FR-02)."
  validation {
    condition     = var.reader_count >= 0 && var.reader_count <= 15
    error_message = "reader_count must be between 0 and 15 (Aurora max 15 replicas)."
  }
}

variable "storage_type" {
  type        = string
  default     = "aurora-iopt1"
  description = "Aurora storage type: 'aurora-iopt1' (I/O-Optimized, ADR-0062 §15.1) or 'aurora' (standard)."
  validation {
    condition     = contains(["aurora", "aurora-iopt1"], var.storage_type)
    error_message = "storage_type must be 'aurora' or 'aurora-iopt1'."
  }
}

variable "kms_key_arn" {
  type        = string
  default     = null
  description = "Customer-managed KMS key ARN for storage + master-secret encryption (ADR-0018). Null = the module creates a dedicated CMK (never the AWS-managed aws/rds key)."
}

variable "deletion_protection" {
  type        = bool
  default     = false
  description = "Prevent accidental cluster deletion. Set true in production."
}

variable "backup_retention_days" {
  type        = number
  default     = 7
  description = "Automated backup retention period in days (PITR window)."
}

variable "db_name" {
  type        = string
  default     = "appdb"
  description = "Name of the initial database."
}

variable "db_username" {
  type        = string
  default     = "appuser"
  description = "Master username for the cluster (password is RDS-managed in Secrets Manager)."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags applied to all resources."
}

# ── Deprecated (instance-only) variables ──────────────────────────────────────
# Retained as no-ops so existing environment callers continue to validate during
# the brownfield Aurora migration (ADR-0063 extend-not-fork). Aurora manages
# storage on shared cluster volumes and HA via reader auto-failover, so these
# have no effect and should be removed from callers once the cutover lands.

variable "allocated_storage_gb" {
  type        = number
  default     = 0
  description = "DEPRECATED (Aurora manages storage automatically; no effect). Remove from callers."
}

variable "max_allocated_storage_gb" {
  type        = number
  default     = 0
  description = "DEPRECATED (Aurora manages storage automatically; no effect). Remove from callers."
}

variable "multi_az" {
  type        = bool
  default     = true
  description = "DEPRECATED (Aurora HA is provided by reader auto-failover across AZs; no effect). Remove from callers."
}
