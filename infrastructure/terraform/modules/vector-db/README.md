# `vector-db`

Provisions an **Amazon OpenSearch Serverless** collection for vector search, powering semantic search and RAG
(retrieval-augmented generation) for the optional AI Agents components (ADR-0010).

## Resources

- `aws_opensearchserverless_security_policy.encryption`
- `aws_opensearchserverless_security_policy.network`
- `aws_opensearchserverless_access_policy.main`
- `aws_opensearchserverless_collection.vectors`

## Inputs

| Name                     | Type           | Default    | Description                                                            |
| ------------------------ | -------------- | ---------- | ---------------------------------------------------------------------- |
| `name_prefix`            | `string`       | _required_ | Prefix for all resource names.                                         |
| `allowed_principal_arns` | `list(string)` | _required_ | IAM principal ARNs (roles/users) granted read/write to the collection. |
| `tags`                   | `map(string)`  | `{}`       | Additional tags applied to all resources.                              |

## Outputs

| Name                  | Description                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `collection_endpoint` | OpenSearch Serverless collection endpoint for vector operations. |
| `collection_arn`      | ARN of the OpenSearch Serverless collection.                     |
| `dashboard_endpoint`  | OpenSearch Dashboards endpoint.                                  |

## Usage

```hcl
module "vector_db" {
  source = "../../modules/vector-db"

  name_prefix = "monorepo-production"
  allowed_principal_arns = [
    module.api_gateway.irsa_role_arn,
    module.domain_service.irsa_role_arn,
  ]
}
```

> Opt-in component. If the project doesn't use AI agents / RAG, this module can be omitted from the environment.
