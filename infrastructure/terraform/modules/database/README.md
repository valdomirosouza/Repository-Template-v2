# `database`

Provisions an **Amazon Aurora PostgreSQL 17** cluster (1 writer + `reader_count` readers, one per AZ)
with automated backups, enhanced monitoring, Performance Insights, a dedicated security group, a
customer-managed CMK for encryption at rest, and **RDS-managed master credentials** in AWS Secrets
Manager (the password is never written to Terraform state).

Spec: SPEC-INFRA-001 FR-02 · ADR-0062 (Aurora), ADR-0063 (brownfield reconciliation), ADR-0018 (encryption).

## Resources

- `aws_kms_key.db` (created unless `kms_key_arn` is supplied — encryption never falls back to `aws/rds`)
- `aws_security_group.db` (port 5432 from `allowed_security_group_ids`)
- `aws_db_subnet_group.main`, `aws_rds_cluster_parameter_group.main`
- `aws_rds_cluster.main` + `aws_rds_cluster_instance.main` (count = `1 + reader_count`)
- `aws_iam_role.rds_enhanced_monitoring` + `aws_iam_role_policy_attachment.rds_enhanced_monitoring`

## Inputs

| Name                             | Type           | Default                 | Description                                                                    |
| -------------------------------- | -------------- | ----------------------- | ------------------------------------------------------------------------------ |
| `name_prefix`                    | `string`       | _required_              | Prefix for all resource names.                                                 |
| `vpc_id`                         | `string`       | _required_              | VPC in which to place the Aurora cluster.                                      |
| `subnet_ids`                     | `list(string)` | _required_              | Private subnet IDs for the DB subnet group (≥2 AZs).                           |
| `availability_zones`             | `list(string)` | `[]`                    | AZs to spread cluster instances across (one per AZ). Empty = AWS chooses.      |
| `allowed_security_group_ids`     | `list(string)` | _required_              | SG IDs allowed to connect on port 5432.                                        |
| `engine_version`                 | `string`       | `"17.4"`                | Aurora PostgreSQL 17.x engine version.                                         |
| `cluster_parameter_group_family` | `string`       | `"aurora-postgresql17"` | Cluster parameter group family (must match the engine major).                  |
| `instance_class`                 | `string`       | `"db.r6g.large"`        | Instance class for writer and readers.                                         |
| `reader_count`                   | `number`       | `2`                     | Reader instances (writer is always 1). `2` ⇒ 3 instances across 3 AZs (FR-02). |
| `storage_type`                   | `string`       | `"aurora-iopt1"`        | `aurora-iopt1` (I/O-Optimized) or `aurora` (standard).                         |
| `kms_key_arn`                    | `string`       | `null`                  | CMK ARN for storage + master-secret encryption. `null` ⇒ module creates a CMK. |
| `deletion_protection`            | `bool`         | `false`                 | Prevent accidental cluster deletion. Set `true` in production.                 |
| `backup_retention_days`          | `number`       | `7`                     | Automated backup retention / PITR window (days).                               |
| `db_name`                        | `string`       | `"appdb"`               | Name of the initial database.                                                  |
| `db_username`                    | `string`       | `"appuser"`             | Master username (password is RDS-managed in Secrets Manager).                  |
| `tags`                           | `map(string)`  | `{}`                    | Additional tags applied to all resources.                                      |

> **Deprecated (no-op) inputs** retained for the brownfield cutover: `allocated_storage_gb`,
> `max_allocated_storage_gb`, `multi_az`. Aurora manages storage on shared cluster volumes and HA via
> reader auto-failover, so these have no effect — remove them from callers.

## Outputs

| Name                               | Description                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------------- |
| `cluster_writer_endpoint`          | Writer endpoint — follows the writer on failover (FR-02).                       |
| `cluster_reader_endpoint`          | Reader endpoint — load-balances across reader instances.                        |
| `port`                             | Cluster port.                                                                   |
| `db_name`                          | Name of the initial database.                                                   |
| `username`                         | Master username (combine with the secret password to compose `DATABASE_URL`).   |
| `master_user_secret_arn`           | ARN of the RDS-managed master secret. Contains **only** `{username, password}`. |
| `kms_key_arn`                      | ARN of the customer-managed CMK used for encryption at rest.                    |
| `cluster_arn`                      | ARN of the Aurora cluster.                                                      |
| `cluster_identifier`               | Identifier of the Aurora cluster.                                               |
| `security_group_id`                | Security group ID attached to the cluster.                                      |
| `secret_arn` / `endpoint` / `host` | Compatibility aliases (ARN/host shape) for existing callers — see note below.   |

> **`DATABASE_URL` contract (changed from RDS).** The RDS-managed secret holds **only**
> `{username, password}` — there is no ready `url`/`host`/`port`/`dbname` key, because the master
> password is never readable in Terraform and a full DSN cannot be assembled here. Consumers must
> compose `DATABASE_URL` at runtime from `username` + the password in `master_user_secret_arn` +
> `cluster_writer_endpoint` + `port` + `db_name`. Code reading the legacy `url`/`dbname` keys must be
> updated.

## Usage

```hcl
module "database" {
  source = "../../modules/database"

  name_prefix                = "monorepo-production"
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.networking.sg_app_id]

  instance_class        = "db.r8g.large"
  availability_zones    = ["us-east-1a", "us-east-1b", "us-east-1c"]
  reader_count          = 2
  deletion_protection   = true
  backup_retention_days = 30
}
```

> Not provisioned in `dev` — the dev environment supplies an external `db_secret_arn` instead.
