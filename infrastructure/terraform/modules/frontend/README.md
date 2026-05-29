# `frontend`

Provisions an **IRSA** IAM role for the frontend (Next.js operator UI, incl. HITL approval UI) ServiceAccount with
Secrets Manager read (OIDC client secret) and CloudWatch Logs write access, then deploys the workload via a Helm
release of `infrastructure/helm/frontend/`.

## Resources

- `aws_iam_role.frontend` — IRSA role trusted by the EKS OIDC provider
- `aws_iam_policy.secrets_read` — Secrets Manager `GetSecretValue` / `DescribeSecret`
- `aws_iam_policy.cloudwatch_logs` — CloudWatch Logs `CreateLogGroup` / `CreateLogStream` / `PutLogEvents` / `DescribeLogStreams`
- `aws_iam_role_policy_attachment.secrets_read`, `aws_iam_role_policy_attachment.cloudwatch_logs`
- `helm_release.frontend`

Locals: `common_tags`, `service_account_namespace`, `service_account_name`.

## Inputs

| Name                   | Type           | Default      | Description                                                               |
| ---------------------- | -------------- | ------------ | ------------------------------------------------------------------------- |
| `environment`          | `string`       | _required_   | Deployment environment.                                                   |
| `oidc_provider_arn`    | `string`       | _required_   | IAM OIDC provider ARN (output of the `kubernetes` module).                |
| `oidc_provider_url`    | `string`       | _required_   | IAM OIDC provider URL without `https://` prefix.                          |
| `aws_account_id`       | `string`       | _required_   | AWS account ID — scopes IAM ARNs.                                         |
| `aws_region`           | `string`       | _required_   | AWS region — scopes IAM ARNs.                                             |
| `namespace`            | `string`       | `"default"`  | Kubernetes namespace.                                                     |
| `service_account_name` | `string`       | `"frontend"` | Kubernetes ServiceAccount name.                                           |
| `secrets_manager_arns` | `list(string)` | `[]`         | Secrets Manager ARN prefixes the pod may read (OIDC client secret, etc.). |
| `helm_chart_version`   | `string`       | `"0.1.0"`    | Helm chart version (from `Chart.yaml`).                                   |
| `helm_values_file`     | `string`       | _required_   | Path to the environment-specific values override file.                    |
| `image_tag`            | `string`       | `"latest"`   | Container image tag to deploy.                                            |
| `tags`                 | `map(string)`  | `{}`         | Additional tags applied to all AWS resources.                             |

## Outputs

| Name                   | Description                                          |
| ---------------------- | ---------------------------------------------------- |
| `irsa_role_arn`        | IAM role ARN for the frontend ServiceAccount (IRSA). |
| `irsa_role_name`       | IAM role name for the frontend ServiceAccount.       |
| `helm_release_status`  | Status of the frontend Helm release.                 |
| `helm_release_version` | Deployed chart version.                              |

## Usage

```hcl
module "frontend" {
  source = "../../modules/frontend"

  environment       = "production"
  oidc_provider_arn = module.kubernetes.oidc_provider_arn
  oidc_provider_url = module.kubernetes.oidc_provider_url
  aws_account_id    = data.aws_caller_identity.current.account_id
  aws_region        = var.aws_region
  helm_values_file  = "infrastructure/helm/frontend/values-production.yaml"
  image_tag         = var.image_tag
}
```
