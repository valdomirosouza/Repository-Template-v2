# `message-broker`

Provisions an **Amazon MSK** (Managed Streaming for Apache Kafka) cluster with SASL/SCRAM authentication, TLS
encryption, KMS at-rest encryption, CloudWatch broker logging, and SCRAM credentials in AWS Secrets Manager.

## Resources

- `random_password.kafka_password` → `aws_secretsmanager_secret.kafka` + `aws_secretsmanager_secret_version.kafka`
- `aws_kms_key.msk` + `aws_kms_alias.msk`
- `aws_security_group.msk`
- `aws_msk_cluster.main`, `aws_msk_configuration.main`, `aws_msk_scram_secret_association.main`
- `aws_cloudwatch_log_group.msk`

## Inputs

| Name                         | Type           | Default            | Description                                                                        |
| ---------------------------- | -------------- | ------------------ | ---------------------------------------------------------------------------------- |
| `name_prefix`                | `string`       | _required_         | Prefix for all resource names.                                                     |
| `vpc_id`                     | `string`       | _required_         | VPC for the MSK cluster.                                                           |
| `subnet_ids`                 | `list(string)` | _required_         | Private subnet IDs — one broker per subnet.                                        |
| `allowed_security_group_ids` | `list(string)` | _required_         | SG IDs allowed to connect to brokers.                                              |
| `kafka_version`              | `string`       | `"3.7.x"`          | Apache Kafka version.                                                              |
| `broker_instance_type`       | `string`       | `"kafka.m5.large"` | EC2 instance type for broker nodes.                                                |
| `broker_volume_size_gb`      | `number`       | `100`              | EBS volume size per broker (GiB).                                                  |
| `default_replication_factor` | `number`       | `3`                | `default.replication.factor`. Must be ≤ broker count (use 2 for 2-broker staging). |
| `min_insync_replicas`        | `number`       | `2`                | `min.insync.replicas`. Must be < replication factor.                               |
| `tags`                       | `map(string)`  | `{}`               | Additional tags applied to all resources.                                          |

## Outputs

| Name                           | Description                                                                         |
| ------------------------------ | ----------------------------------------------------------------------------------- |
| `bootstrap_brokers_sasl_scram` | SASL/SCRAM bootstrap endpoints (comma-separated). Use as `KAFKA_BOOTSTRAP_SERVERS`. |
| `cluster_arn`                  | ARN of the MSK cluster.                                                             |
| `cluster_name`                 | Name of the MSK cluster.                                                            |
| `credentials_secret_arn`       | ARN of the Secrets Manager secret with the Kafka SASL/SCRAM credentials.            |
| `security_group_id`            | Security group ID attached to the brokers.                                          |
| `zookeeper_connect_string`     | ZooKeeper connection string (legacy — prefer bootstrap brokers).                    |

## Usage

```hcl
module "message_broker" {
  source = "../../modules/message-broker"

  name_prefix                = "monorepo-production"
  vpc_id                     = module.networking.vpc_id
  subnet_ids                 = module.networking.private_subnet_ids
  allowed_security_group_ids = [module.networking.sg_app_id]

  broker_instance_type       = "kafka.m5.large"
  broker_volume_size_gb      = 500
  default_replication_factor = 3
  min_insync_replicas        = 2
}
```

> Not provisioned in `dev`. Keep `default_replication_factor` ≤ the number of subnets/brokers, or the apply fails.
