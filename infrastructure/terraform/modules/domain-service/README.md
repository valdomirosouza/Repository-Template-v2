# `domain-service`

Provisions an **IRSA** IAM role for the domain-service (Java/Spring Boot) ServiceAccount with Secrets Manager read
(DB credentials + encryption key) and CloudWatch Logs write access, then deploys the workload via a Helm release of
`infrastructure/helm/domain-service/`.

## Resources

- `aws_iam_role.domain_service` — IRSA role trusted by the EKS OIDC provider
- `aws_iam_policy.db_secrets_read` — Secrets Manager read for DB credentials and encryption key
- `aws_iam_policy.cloudwatch_logs` — CloudWatch Logs write
- `aws_iam_role_policy_attachment.db_secrets_read`, `aws_iam_role_policy_attachment.cloudwatch_logs`
- `helm_release.domain_service`

Locals: `common_tags`.

## Inputs

| Name                   | Type          | Default            | Description                                                |
| ---------------------- | ------------- | ------------------ | ---------------------------------------------------------- |
| `environment`          | `string`      | _required_         | Deployment environment.                                    |
| `oidc_provider_arn`    | `string`      | _required_         | IAM OIDC provider ARN (output of the `kubernetes` module). |
| `oidc_provider_url`    | `string`      | _required_         | IAM OIDC provider URL without `https://` prefix.           |
| `aws_account_id`       | `string`      | _required_         | AWS account ID.                                            |
| `aws_region`           | `string`      | _required_         | AWS region.                                                |
| `namespace`            | `string`      | `"default"`        | Kubernetes namespace.                                      |
| `service_account_name` | `string`      | `"domain-service"` | Kubernetes ServiceAccount name.                            |
| `db_secret_arn`        | `string`      | _required_         | Secrets Manager ARN for the PostgreSQL credentials secret. |
| `helm_chart_version`   | `string`      | `"0.1.0"`          | Helm chart version.                                        |
| `helm_values_file`     | `string`      | _required_         | Path to the environment-specific values override file.     |
| `image_tag`            | `string`      | `"latest"`         | Container image tag to deploy.                             |
| `tags`                 | `map(string)` | `{}`               | Additional tags applied to all AWS resources.              |

## Outputs

| Name                   | Description                                                |
| ---------------------- | ---------------------------------------------------------- |
| `irsa_role_arn`        | IAM role ARN for the domain-service ServiceAccount (IRSA). |
| `irsa_role_name`       | IAM role name for the domain-service ServiceAccount.       |
| `helm_release_status`  | Status of the domain-service Helm release.                 |
| `helm_release_version` | Deployed chart version.                                    |

## Usage

```hcl
module "domain_service" {
  source = "../../modules/domain-service"

  environment       = "production"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  db_secret_arn     = module.database.secret_arn
  helm_values_file  = "infrastructure/helm/domain-service/values-production.yaml"
  image_tag         = var.image_tag
}
```

> In `dev` (no RDS), pass an external secret via `db_secret_arn = var.db_secret_arn`.
