# Terraform Infrastructure

Infrastructure-as-Code for the multi-language monorepo, targeting **AWS**. The layout follows the standard
root-module / reusable-module split:

```
infrastructure/terraform/
├── environments/            # Root modules — one per environment (you run terraform here)
│   ├── dev/                 # Local state, single-AZ, no stateful data services
│   ├── staging/             # S3 remote state, 2-AZ, full stack
│   └── production/          # S3 remote state, 3-AZ HA, hardened
└── modules/                 # Reusable building blocks (never run directly)
    ├── networking/          # VPC, subnets, NAT, security groups
    ├── kubernetes/          # EKS cluster, node group, OIDC provider (IRSA)
    ├── database/            # RDS PostgreSQL 16
    ├── cache/               # ElastiCache Redis 7 (TLS)
    ├── message-broker/      # Amazon MSK (Kafka, SASL/SCRAM)
    ├── vector-db/           # OpenSearch Serverless (vector search / RAG)
    ├── observability/       # CloudWatch log groups + Golden-Signal alarms + SNS
    ├── api-gateway/         # IRSA role + Helm release (FastAPI core)
    ├── domain-service/      # IRSA role + Helm release (Java/Spring Boot)
    ├── event-worker/        # IRSA role + Helm release (Go Kafka consumer)
    └── frontend/            # IRSA role + Helm release (Next.js operator UI)
```

> **Conventions used by every module**
>
> - All resources are AWS. Region defaults to `us-east-1`.
> - Every module accepts a `tags` map merged into a `common_tags` local (`Environment`, `ManagedBy=terraform`, `Module`).
> - Secrets (DB, Kafka SASL) are generated with the `random` provider and stored in **AWS Secrets Manager** — never in state outputs.
> - At-rest encryption uses **AWS KMS** (cache, MSK, EKS secrets). In-transit uses TLS (Redis `rediss://` port 6380, MSK TLS, RDS).
> - Service modules (`api-gateway`, `domain-service`, `event-worker`, `frontend`) provision an **IRSA** IAM role + a `helm_release`; the Kubernetes workload itself lives in `infrastructure/helm/<service>/`.

---

## Prerequisites

| Tool           | Version                                                        |
| -------------- | -------------------------------------------------------------- |
| Terraform      | `>= 1.9`                                                       |
| AWS CLI        | v2, authenticated (`aws sts get-caller-identity` must succeed) |
| kubectl / helm | for post-apply inspection                                      |

**Required providers** (pinned identically across all environments):

| Provider               | Version   |
| ---------------------- | --------- |
| `hashicorp/aws`        | `~> 5.0`  |
| `hashicorp/helm`       | `~> 2.13` |
| `hashicorp/kubernetes` | `~> 2.30` |
| `hashicorp/random`     | `~> 3.6`  |
| `hashicorp/tls`        | `~> 4.0`  |

The `helm` and `kubernetes` providers authenticate against the EKS cluster created by the `kubernetes` module
(via `data.aws_eks_cluster` + `data.aws_eks_cluster_auth`). Because of this, the **cluster must exist before the
service modules apply** — see [Bootstrapping](#bootstrapping-a-fresh-environment).

---

## Quick Start

```bash
cd infrastructure/terraform/environments/dev   # or staging / production

terraform init                                 # download providers + configure backend
terraform plan  -var="image_tag=<git-sha>"
terraform apply -var="image_tag=<git-sha>"
```

Common input variables (declared in each environment's `main.tf`):

| Variable        | Default     | Notes                                                                                  |
| --------------- | ----------- | -------------------------------------------------------------------------------------- |
| `aws_region`    | `us-east-1` | Target region                                                                          |
| `image_tag`     | `latest`    | Container image tag deployed via Helm — pass the build SHA                             |
| `db_secret_arn` | `""`        | **dev only** — RDS isn't provisioned in dev, so supply an external DB secret if needed |

### Bootstrapping a fresh environment

The `helm`/`kubernetes` providers can't authenticate until the EKS cluster exists. On the **first** apply of an
empty environment, create the cluster before the workloads:

```bash
terraform apply -target=module.networking -target=module.kubernetes
terraform apply                 # now the cluster data sources resolve; deploy everything else
```

Subsequent applies just use `terraform apply`.

### Remote state

`dev` uses **local state**. `staging` and `production` use an **S3 backend with DynamoDB locking**:

```hcl
backend "s3" {
  bucket         = "your-org-terraform-state"      # ← create + rename before first use
  key            = "monorepo/<env>/terraform.tfstate"
  region         = "us-east-1"
  encrypt        = true
  dynamodb_table = "terraform-state-lock"
}
```

Create the bucket and lock table once (manually or in a separate bootstrap stack) before `terraform init` in
staging/production.

---

## Environments

All three environments wire the same module catalog; they differ in sizing, AZ count, state backend, observability
thresholds, and whether the stateful data services are provisioned.

| Aspect                     | dev                   | staging                                         | production                                                                    |
| -------------------------- | --------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------- |
| State backend              | local                 | S3 + DynamoDB lock                              | S3 + DynamoDB lock                                                            |
| VPC CIDR                   | `10.2.0.0/16`         | `10.1.0.0/16`                                   | `10.0.0.0/16`                                                                 |
| Availability Zones         | 1 (`us-east-1a`)      | 2 (`a`,`b`)                                     | 3 (`a`,`b`,`c`)                                                               |
| EKS node type              | `t3.medium`           | `m6i.large`                                     | `m6i.xlarge`                                                                  |
| EKS desired/min/max        | 1 / 1 / 2             | 2 / 1 / 5                                       | 3 / 3 / 20                                                                    |
| Cache node type × count    | `cache.t4g.micro` × 1 | `cache.t4g.small` × 1                           | `cache.r7g.large` × 3                                                         |
| **Database (RDS)**         | ❌ not provisioned    | `db.t3.medium`, 20 GB, single-AZ, 7-day backups | `db.r8g.large`, 100 GB, **Multi-AZ**, **deletion protection**, 30-day backups |
| **Message broker (MSK)**   | ❌ not provisioned    | 2 brokers, RF=2, minISR=1                       | 3 brokers, RF=3, minISR=2                                                     |
| Vector DB (OpenSearch)     | ✅                    | ✅                                              | ✅                                                                            |
| Log retention              | 7 d                   | 30 d                                            | 90 d                                                                          |
| Alarm error-rate threshold | 5.0 %                 | 1.0 %                                           | 0.5 %                                                                         |
| Alarm P99 latency          | 1000 ms               | 500 ms                                          | 300 ms                                                                        |

**Module wiring order** (dependencies are implicit via output references unless noted):
`networking` → `kubernetes` → `cache` → (`database`, `message_broker` in staging/prod) → service modules
(`api_gateway`, `domain_service`, `event_worker`, `frontend`) → `observability` (one instance per service) →
`vector_db`.

`domain_service` consumes `module.database.secret_arn`; `event_worker` consumes `module.message_broker.cluster_arn`.
In dev, where those data services are absent, `domain_service` uses `var.db_secret_arn` and `event_worker` runs
without MSK access.

### Environment outputs

`staging` / `production` expose:
`cluster_endpoint`, `redis_url` (sensitive), `db_endpoint`, `db_secret_arn`, `kafka_bootstrap_brokers` (sensitive),
`kafka_client_iam_policy_arn`, `vector_db_endpoint`, `vector_db_arn`, and the four `*_irsa_role_arn` +
four `obs_*_sns_arn` values.
`dev` exposes the same set minus the database and Kafka outputs.

---

## Modules

Reusable modules are referenced from environments as `source = "../../modules/<name>"`. Every module's `tags`
input is optional (`{}`); inputs without a default are **required**.

### `networking`

Provisions a VPC with public/private subnets across the given AZs, an internet gateway, one NAT gateway per public
subnet, route tables, and three layered security groups (ingress → app → data).

| Input                  | Type         | Default                                          | Description                        |
| ---------------------- | ------------ | ------------------------------------------------ | ---------------------------------- |
| `environment`          | string       | _required_                                       | `dev` \| `staging` \| `production` |
| `vpc_cidr`             | string       | `10.0.0.0/16`                                    | CIDR block for the VPC             |
| `public_subnet_cidrs`  | list(string) | `["10.0.1.0/24","10.0.2.0/24","10.0.3.0/24"]`    | One per AZ                         |
| `private_subnet_cidrs` | list(string) | `["10.0.11.0/24","10.0.12.0/24","10.0.13.0/24"]` | One per AZ                         |
| `availability_zones`   | list(string) | _required_                                       | AZs to deploy into                 |
| `tags`                 | map(string)  | `{}`                                             | Extra tags                         |

**Outputs:** `vpc_id`, `public_subnet_ids`, `private_subnet_ids`, `sg_ingress_id` (HTTP/HTTPS from internet),
`sg_app_id` (port 8000 from ingress), `sg_data_id` (Postgres 5432 / Redis 6380 / Kafka 9092 from app).

### `kubernetes`

Provisions an EKS cluster with a managed node group, KMS envelope encryption of Kubernetes Secrets, IAM roles for
the control plane and nodes, and an **OIDC provider for IRSA**.

| Input                 | Type         | Default         | Description                                  |
| --------------------- | ------------ | --------------- | -------------------------------------------- |
| `environment`         | string       | _required_      | `staging` \| `production` (also used in dev) |
| `cluster_name`        | string       | _required_      | EKS cluster name                             |
| `kubernetes_version`  | string       | `1.31`          | Kubernetes version                           |
| `vpc_id`              | string       | _required_      | VPC for the cluster                          |
| `private_subnet_ids`  | list(string) | _required_      | Subnets for the node group                   |
| `node_instance_types` | list(string) | `["m6i.large"]` | Managed node group instance types            |
| `node_desired_size`   | number       | `2`             | Desired worker count                         |
| `node_min_size`       | number       | `1`             | Min worker count                             |
| `node_max_size`       | number       | `10`            | Max worker count                             |
| `tags`                | map(string)  | `{}`            | Extra tags                                   |

**Outputs:** `cluster_name`, `cluster_endpoint`, `cluster_ca_certificate` (sensitive), `cluster_oidc_issuer`,
`kms_key_arn`, `oidc_provider_arn`, `oidc_provider_url` (no `https://` prefix — feed both into service modules).

### `database`

Provisions an RDS PostgreSQL 16 instance with automated backups, enhanced monitoring, a dedicated security group,
and master credentials in Secrets Manager.

| Input                        | Type         | Default        | Description                       |
| ---------------------------- | ------------ | -------------- | --------------------------------- |
| `name_prefix`                | string       | _required_     | Prefix for resource names         |
| `vpc_id`                     | string       | _required_     | VPC for the instance              |
| `subnet_ids`                 | list(string) | _required_     | Private subnets (≥2 for Multi-AZ) |
| `allowed_security_group_ids` | list(string) | _required_     | SGs allowed on port 5432          |
| `engine_version`             | string       | `16.3`         | PostgreSQL version                |
| `instance_class`             | string       | `db.t3.medium` | RDS instance class                |
| `allocated_storage_gb`       | number       | `20`           | Initial storage (GiB)             |
| `max_allocated_storage_gb`   | number       | `100`          | Autoscaling max (GiB; 0 = off)    |
| `multi_az`                   | bool         | `false`        | Standby replica — `true` in prod  |
| `deletion_protection`        | bool         | `false`        | `true` in prod                    |
| `backup_retention_days`      | number       | `7`            | Backup retention                  |
| `db_name`                    | string       | `appdb`        | Initial database name             |
| `db_username`                | string       | `appuser`      | Master username                   |
| `tags`                       | map(string)  | `{}`           | Extra tags                        |

**Outputs:** `endpoint`, `host`, `port`, `db_name`, `secret_arn` (Secrets Manager — contains `DATABASE_URL`),
`security_group_id`.

### `cache`

Provisions an ElastiCache Redis 7 replication group with TLS in transit (port 6380), KMS at-rest encryption, and
automatic backups.

| Input                | Type         | Default           | Description                                  |
| -------------------- | ------------ | ----------------- | -------------------------------------------- |
| `environment`        | string       | _required_        | `staging` \| `production` (also used in dev) |
| `cluster_id`         | string       | _required_        | Cluster identifier                           |
| `vpc_id`             | string       | _required_        | VPC ID                                       |
| `subnet_ids`         | list(string) | _required_        | Private subnets                              |
| `security_group_ids` | list(string) | _required_        | SGs to attach                                |
| `node_type`          | string       | `cache.t4g.small` | Node type                                    |
| `num_cache_nodes`    | number       | `1`               | Node count (≥2 for HA)                       |
| `redis_version`      | string       | `7.1`             | Redis version                                |
| `tags`               | map(string)  | `{}`              | Extra tags                                   |

**Outputs:** `primary_endpoint`, `port` (6380, TLS-only), `redis_url` (`rediss://` — use as `REDIS_URL`),
`kms_key_arn`.

### `message-broker`

Provisions an Amazon MSK (Kafka) cluster with SASL/SCRAM auth, TLS, KMS encryption, CloudWatch broker logs, and
SCRAM credentials in Secrets Manager.

| Input                        | Type         | Default          | Description                                         |
| ---------------------------- | ------------ | ---------------- | --------------------------------------------------- |
| `name_prefix`                | string       | _required_       | Prefix for resource names                           |
| `vpc_id`                     | string       | _required_       | VPC for the cluster                                 |
| `subnet_ids`                 | list(string) | _required_       | Private subnets (one broker per subnet)             |
| `allowed_security_group_ids` | list(string) | _required_       | SGs allowed to reach brokers                        |
| `kafka_version`              | string       | `3.7.x`          | Kafka version                                       |
| `broker_instance_type`       | string       | `kafka.m5.large` | Broker instance type                                |
| `broker_volume_size_gb`      | number       | `100`            | EBS per broker (GiB)                                |
| `default_replication_factor` | number       | `3`              | Must be ≤ broker count (use 2 for 2-broker staging) |
| `min_insync_replicas`        | number       | `2`              | Must be < replication factor                        |
| `tags`                       | map(string)  | `{}`             | Extra tags                                          |

**Outputs:** `bootstrap_brokers_sasl_iam` (use as `KAFKA_BOOTSTRAP_SERVERS`), `cluster_arn`, `cluster_name`,
`kafka_client_iam_policy_arn` (attach to the IRSA role), `kms_key_arn`, `security_group_id`.

### `vector-db`

Provisions an Amazon OpenSearch Serverless collection for vector search / RAG (opt-in AI Agents component,
ADR-0010) with encryption, network, and data-access security policies.

| Input                    | Type         | Default    | Description                                                 |
| ------------------------ | ------------ | ---------- | ----------------------------------------------------------- |
| `name_prefix`            | string       | _required_ | Prefix for resource names                                   |
| `allowed_principal_arns` | list(string) | _required_ | IAM principals granted read/write (e.g. service IRSA roles) |
| `tags`                   | map(string)  | `{}`       | Extra tags                                                  |

**Outputs:** `collection_endpoint`, `collection_arn`, `dashboard_endpoint`.

### `observability`

Provisions CloudWatch log groups (app / audit / agent), an SNS alerts topic, and Golden-Signal metric alarms
(high error rate, high P99 latency, zero traffic, high CPU, HITL approval timeout). Instantiated **once per
service** in each environment. The audit log group keeps 365-day retention for LGPD/GDPR.

| Input                      | Type         | Default    | Description                                         |
| -------------------------- | ------------ | ---------- | --------------------------------------------------- |
| `name_prefix`              | string       | _required_ | Prefix for resource names                           |
| `service_name`             | string       | _required_ | Monitored service (used in alarm + log group names) |
| `log_retention_days`       | number       | `30`       | App/agent log retention                             |
| `alarm_actions_arns`       | list(string) | `[]`       | Extra SNS/Lambda targets on alarm                   |
| `error_rate_threshold`     | number       | `1.0`      | Error-rate (%) for HighErrorRate alarm              |
| `p99_latency_threshold_ms` | number       | `500`      | P99 ms for HighLatency alarm                        |
| `tags`                     | map(string)  | `{}`       | Extra tags                                          |

**Outputs:** `app_log_group_name`, `audit_log_group_name`, `agent_log_group_name`, `sns_topic_arn`
(subscribe email/PagerDuty/Slack here), `alarm_arns`.

### Service modules — `api-gateway`, `domain-service`, `event-worker`, `frontend`

These four share the same shape: an **IRSA IAM role** scoped to the service's Kubernetes ServiceAccount plus a
`helm_release` deploying `infrastructure/helm/<service>/`. They differ only in the extra IAM policies attached.

**Shared inputs** (all four):

| Input                  | Type        | Default     | Description                                |
| ---------------------- | ----------- | ----------- | ------------------------------------------ |
| `environment`          | string      | _required_  | Deployment environment                     |
| `oidc_provider_arn`    | string      | _required_  | From `module.kubernetes.oidc_provider_arn` |
| `oidc_provider_url`    | string      | _required_  | From `module.kubernetes.oidc_provider_url` |
| `aws_account_id`       | string      | _required_  | Scopes IAM ARNs                            |
| `aws_region`           | string      | _required_  | Scopes IAM ARNs                            |
| `namespace`            | string      | `default`   | K8s namespace                              |
| `service_account_name` | string      | `<service>` | K8s ServiceAccount name                    |
| `helm_chart_version`   | string      | `0.1.0`     | Chart version                              |
| `helm_values_file`     | string      | _required_  | Env-specific values override path          |
| `image_tag`            | string      | `latest`    | Container image tag                        |
| `tags`                 | map(string) | `{}`        | Extra tags                                 |

**Shared outputs** (all four): `irsa_role_arn`, `irsa_role_name`, `helm_release_status`, `helm_release_version`.

**Module-specific inputs / IAM:**

| Module           | Extra input                                                    | Extra IAM granted                                                                                                                              |
| ---------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `api-gateway`    | `cluster_name` (required), `secrets_manager_arns` (list, `[]`) | Secrets Manager read + CloudWatch Logs write                                                                                                   |
| `domain-service` | `db_secret_arn` (required)                                     | Secrets Manager read (DB creds + encryption key) + CloudWatch Logs write                                                                       |
| `event-worker`   | `msk_cluster_arn` (string, `""`), `dlq_sqs_arn` (string, `""`) | MSK connect/read/write _(if `msk_cluster_arn` set)_, SQS DLQ send _(if `dlq_sqs_arn` set)_, Secrets Manager read (SASL), CloudWatch Logs write |
| `frontend`       | `secrets_manager_arns` (list, `[]`)                            | Secrets Manager read (OIDC client secret) + CloudWatch Logs write                                                                              |

---

## Common Operations

```bash
# Validate / format the whole tree
terraform -chdir=environments/<env> fmt -recursive
terraform -chdir=environments/<env> validate

# Inspect a single resource graph node
terraform -chdir=environments/<env> state list
terraform -chdir=environments/<env> output

# Roll a new image to an environment
terraform -chdir=environments/<env> apply -var="image_tag=$(git rev-parse --short HEAD)"

# Tear down (dev only — staging/prod have deletion protection on RDS)
terraform -chdir=environments/dev destroy
```

> **Production guardrails:** the RDS `database` module sets `deletion_protection = true` and `multi_az = true` in
> production. A `terraform destroy` will fail on the database until protection is manually disabled — this is
> intentional. Coordinate any production teardown through the change-management process (`skills/change-management/`).

## Conventions & Governance

- **Secrets never leave Secrets Manager.** Modules output ARNs, not secret values. Consumers read them at runtime
  via IRSA. TLS/encryption settings follow ADR-0018 (at-rest) and ADR-0019 (`rediss://` in production).
- **IRSA over node IAM.** Every workload gets a least-privilege role bound to its ServiceAccount via the cluster
  OIDC provider; nothing relies on broad node-instance permissions.
- **The Helm chart is the source of truth for the workload**; these modules only provision the AWS-side IAM and
  trigger the release. Chart contents live under `infrastructure/helm/<service>/`.
- Changes under `infrastructure/feature-flags/` and HITL/agent infrastructure carry additional governance review
  (see root `CLAUDE.md` §8).
