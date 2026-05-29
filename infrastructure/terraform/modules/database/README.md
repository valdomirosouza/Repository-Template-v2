# `database`

Provisions an AWS RDS **PostgreSQL 16** instance with automated backups, enhanced monitoring, a dedicated security
group, and master credentials stored in AWS Secrets Manager (never in Terraform state).

## Resources

- `random_password.db` → `aws_secretsmanager_secret.db` + `aws_secretsmanager_secret_version.db`
- `aws_security_group.db` (port 5432 from `allowed_security_group_ids`)
- `aws_db_subnet_group.main`, `aws_db_parameter_group.main`
- `aws_db_instance.main`
- `aws_iam_role.rds_enhanced_monitoring` + `aws_iam_role_policy_attachment.rds_enhanced_monitoring`

## Inputs

| Name                         | Type           | Default          | Description                                                   |
| ---------------------------- | -------------- | ---------------- | ------------------------------------------------------------- |
| `name_prefix`                | `string`       | _required_       | Prefix for all resource names.                                |
| `vpc_id`                     | `string`       | _required_       | VPC in which to place the RDS instance.                       |
| `subnet_ids`                 | `list(string)` | _required_       | Private subnet IDs for the DB subnet group (≥2 for Multi-AZ). |
| `allowed_security_group_ids` | `list(string)` | _required_       | SG IDs allowed to connect on port 5432.                       |
| `engine_version`             | `string`       | `"16.3"`         | PostgreSQL engine version.                                    |
| `instance_class`             | `string`       | `"db.t3.medium"` | RDS instance class.                                           |
| `allocated_storage_gb`       | `number`       | `20`             | Initial storage allocation (GiB).                             |
| `max_allocated_storage_gb`   | `number`       | `100`            | Max storage for autoscaling (GiB; 0 = disabled).              |
| `multi_az`                   | `bool`         | `false`          | Enable Multi-AZ standby replica. Set `true` in production.    |
| `deletion_protection`        | `bool`         | `false`          | Prevent accidental deletion. Set `true` in production.        |
| `backup_retention_days`      | `number`       | `7`              | Automated backup retention (days).                            |
| `db_name`                    | `string`       | `"appdb"`        | Name of the initial database.                                 |
| `db_username`                | `string`       | `"appuser"`      | Master username.                                              |
| `tags`                       | `map(string)`  | `{}`             | Additional tags applied to all resources.                     |

## Outputs

| Name                | Description                                                                  |
| ------------------- | ---------------------------------------------------------------------------- |
| `endpoint`          | RDS instance endpoint (`host:port`).                                         |
| `host`              | RDS instance hostname.                                                       |
| `port`              | RDS instance port.                                                           |
| `db_name`           | Name of the initial database.                                                |
| `secret_arn`        | ARN of the Secrets Manager secret containing `DATABASE_URL` and credentials. |
| `security_group_id` | Security group ID attached to the RDS instance.                              |

## Usage

```hcl
module "database" {
  source = "../../modules/database"

  name_prefix                = "monorepo-production"
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.networking.sg_app_id]

  instance_class        = "db.r8g.large"
  allocated_storage_gb  = 100
  multi_az              = true
  deletion_protection   = true
  backup_retention_days = 30
}
```

> Not provisioned in `dev` — the dev environment supplies an external `db_secret_arn` instead.
