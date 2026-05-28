variable "name_prefix" {
  type        = string
  description = "Prefix for all resource names."
}

variable "allowed_principal_arns" {
  type        = list(string)
  description = "IAM principal ARNs (roles/users) granted read/write access to the collection."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Additional tags applied to all resources."
}
