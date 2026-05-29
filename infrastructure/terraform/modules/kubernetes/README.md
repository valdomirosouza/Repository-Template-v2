# `kubernetes`

Provisions an AWS EKS cluster with a managed node group, KMS envelope encryption of Kubernetes Secrets, IAM roles
for the control plane and worker nodes, and an **OIDC provider for IRSA** (IAM Roles for Service Accounts).

## Resources

- `aws_iam_role.cluster` + `aws_iam_role_policy_attachment.cluster_policy` (`AmazonEKSClusterPolicy`)
- `aws_eks_cluster.main` (encryption config, control-plane logging, VPC config)
- `aws_kms_key.eks` (envelope encryption of Secrets)
- `aws_iam_role.node` + attachments (`AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`)
- `aws_eks_node_group.main` (autoscaling managed node group)
- `aws_iam_openid_connect_provider.eks` (IRSA)
- Data source: `tls_certificate.eks` (cluster OIDC thumbprint). Locals: `common_tags`.

## Inputs

| Name                  | Type           | Default         | Description                                    |
| --------------------- | -------------- | --------------- | ---------------------------------------------- |
| `environment`         | `string`       | _required_      | Deployment environment.                        |
| `cluster_name`        | `string`       | _required_      | EKS cluster name.                              |
| `kubernetes_version`  | `string`       | `"1.31"`        | Kubernetes version for the EKS cluster.        |
| `vpc_id`              | `string`       | _required_      | VPC ID for the cluster.                        |
| `private_subnet_ids`  | `list(string)` | _required_      | Private subnet IDs for node groups.            |
| `node_instance_types` | `list(string)` | `["m6i.large"]` | EC2 instance types for the managed node group. |
| `node_desired_size`   | `number`       | `2`             | Desired number of worker nodes.                |
| `node_min_size`       | `number`       | `1`             | Minimum number of worker nodes.                |
| `node_max_size`       | `number`       | `10`            | Maximum number of worker nodes.                |
| `tags`                | `map(string)`  | `{}`            | Additional tags applied to all resources.      |

## Outputs

| Name                     | Description                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------- |
| `cluster_name`           | EKS cluster name.                                                                     |
| `cluster_endpoint`       | EKS cluster API endpoint.                                                             |
| `cluster_ca_certificate` | Base64-encoded cluster CA certificate (sensitive).                                    |
| `cluster_oidc_issuer`    | OIDC issuer URL for IRSA.                                                             |
| `kms_key_arn`            | ARN of the KMS key used for Secrets encryption.                                       |
| `oidc_provider_arn`      | ARN of the IAM OIDC provider — feed into service modules for IRSA trust.              |
| `oidc_provider_url`      | OIDC provider URL without `https://` prefix — used in IRSA `StringEquals` conditions. |

## Usage

```hcl
module "kubernetes" {
  source = "../../modules/kubernetes"

  environment        = "production"
  cluster_name       = "monorepo-production"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  node_instance_types = ["m6i.xlarge"]
  node_desired_size  = 3
  node_min_size      = 3
  node_max_size      = 20
}
```

> The `oidc_provider_arn` / `oidc_provider_url` outputs are consumed by every service module to build IRSA trust
> policies. This module must apply before the service modules — see the top-level README's bootstrapping note.
