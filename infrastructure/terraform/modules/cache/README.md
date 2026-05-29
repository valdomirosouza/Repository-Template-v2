# `cache`

Provisions an AWS ElastiCache **Redis 7** replication group with TLS in transit (port 6380), KMS at-rest
encryption, and automatic backups — for caching and session/HITL state.

## Resources

- `aws_elasticache_subnet_group.main`
- `aws_elasticache_parameter_group.main`
- `aws_elasticache_replication_group.main`
- `aws_kms_key.cache`

Locals: `common_tags` (merges `tags`, `Environment`, `ManagedBy`, `Module`).

## Inputs

| Name                 | Type           | Default             | Description                                                           |
| -------------------- | -------------- | ------------------- | --------------------------------------------------------------------- |
| `environment`        | `string`       | _required_          | Deployment environment (`staging` \| `production`; also used in dev). |
| `cluster_id`         | `string`       | _required_          | ElastiCache cluster identifier.                                       |
| `vpc_id`             | `string`       | _required_          | VPC ID.                                                               |
| `subnet_ids`         | `list(string)` | _required_          | Private subnet IDs for the cache subnet group.                        |
| `security_group_ids` | `list(string)` | _required_          | Security group IDs to attach to the cache cluster.                    |
| `node_type`          | `string`       | `"cache.t4g.small"` | ElastiCache node type.                                                |
| `num_cache_nodes`    | `number`       | `1`                 | Number of cache nodes (use ≥2 for HA).                                |
| `redis_version`      | `string`       | `"7.1"`             | Redis engine version.                                                 |
| `tags`               | `map(string)`  | `{}`                | Additional tags applied to all resources.                             |

## Outputs

| Name               | Description                                                            |
| ------------------ | ---------------------------------------------------------------------- |
| `primary_endpoint` | Redis primary endpoint address (TLS, port 6380).                       |
| `port`             | Redis port (TLS-only: 6380).                                           |
| `redis_url`        | Connection URL for the `REDIS_URL` env var (`rediss://` enforces TLS). |
| `kms_key_arn`      | ARN of the KMS key used for at-rest encryption.                        |

## Usage

```hcl
module "cache" {
  source = "../../modules/cache"

  environment        = "production"
  cluster_id         = "monorepo-production-redis"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.networking.sg_data_id]
  node_type          = "cache.r7g.large"
  num_cache_nodes    = 3
}
```

> TLS + at-rest encryption are enforced per ADR-0019 (`rediss://` in production).
