# `event-worker`

Provisions an **IRSA** IAM role for the event-worker (Go Kafka consumer) ServiceAccount, then deploys the workload
via a Helm release of `infrastructure/helm/event-worker/`. Grants MSK access, dead-letter-queue send, Secrets
Manager read (SASL credentials), and CloudWatch Logs write.

## Resources

- `aws_iam_role.event_worker` — IRSA role trusted by the EKS OIDC provider
- `aws_iam_policy.msk_access` — MSK Connect/DescribeCluster/Read/Write/Topic/Group **(created only if `msk_cluster_arn != ""`)**
- `aws_iam_policy.dlq_send` — SQS `SendMessage` / `GetQueueAttributes` **(created only if `dlq_sqs_arn != ""`)**
- `aws_iam_policy.secrets_read` — Secrets Manager read for Kafka SASL credentials
- `aws_iam_policy.cloudwatch_logs` — CloudWatch Logs write
- Conditional + unconditional `aws_iam_role_policy_attachment.*`
- `helm_release.event_worker`

Locals: `common_tags`.

## Inputs

| Name                   | Type          | Default          | Description                                                      |
| ---------------------- | ------------- | ---------------- | ---------------------------------------------------------------- |
| `environment`          | `string`      | _required_       | Deployment environment.                                          |
| `oidc_provider_arn`    | `string`      | _required_       | IAM OIDC provider ARN (output of the `kubernetes` module).       |
| `oidc_provider_url`    | `string`      | _required_       | IAM OIDC provider URL without `https://` prefix.                 |
| `aws_account_id`       | `string`      | _required_       | AWS account ID.                                                  |
| `aws_region`           | `string`      | _required_       | AWS region.                                                      |
| `namespace`            | `string`      | `"default"`      | Kubernetes namespace.                                            |
| `service_account_name` | `string`      | `"event-worker"` | Kubernetes ServiceAccount name.                                  |
| `msk_cluster_arn`      | `string`      | `""`             | MSK cluster ARN — grants the worker read/write access when set.  |
| `dlq_sqs_arn`          | `string`      | `""`             | SQS ARN for the dead-letter queue — grants send access when set. |
| `helm_chart_version`   | `string`      | `"0.1.0"`        | Helm chart version.                                              |
| `helm_values_file`     | `string`      | _required_       | Path to the environment-specific values override file.           |
| `image_tag`            | `string`      | `"latest"`       | Container image tag to deploy.                                   |
| `tags`                 | `map(string)` | `{}`             | Additional tags applied to all AWS resources.                    |

## Outputs

| Name                   | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| `irsa_role_arn`        | IAM role ARN for the event-worker ServiceAccount (IRSA). |
| `irsa_role_name`       | IAM role name for the event-worker ServiceAccount.       |
| `helm_release_status`  | Status of the event-worker Helm release.                 |
| `helm_release_version` | Deployed chart version.                                  |

## Usage

```hcl
module "event_worker" {
  source = "../../modules/event-worker"

  environment       = "production"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  msk_cluster_arn   = module.message_broker.cluster_arn
  dlq_sqs_arn       = ""
  helm_values_file  = "infrastructure/helm/event-worker/values-production.yaml"
  image_tag         = var.image_tag
}
```

> In `dev` (no MSK), leave `msk_cluster_arn` empty — the MSK policy/attachment are then skipped.
