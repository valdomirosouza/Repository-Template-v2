---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-INFRA-001
title: AWS Production Platform — multi-AZ data + compute + streaming, provisioned by immutable Terraform IaC
version: 0.2.0
status: draft # draft | in-review | approved | implemented | superseded
owner: valdomirosouza
created: 2026-06-08
source: >-
  Platform request — stand up the full production cloud footprint (RDS PostgreSQL 17 + 2 read
  replicas, EKS, load balancers, Redis, Kafka) across 3 Availability Zones in us-east-1 (N.
  Virginia), provisioned automatically and reproducibly via Terraform following Immutable
  Infrastructure best practices.
deployment_topology: monorepo-services # IaC lives in this monorepo under infrastructure/terraform/ (§1.4)
governing_adrs:
  [
    ADR-0003,
    ADR-0004,
    ADR-0012,
    ADR-0018,
    ADR-0019,
    ADR-0020,
    ADR-0026,
    ADR-0027,
    ADR-0029,
  ]
new_adrs_required:
  [
    immutable-infrastructure-terraform,
    aws-three-az-region-topology,
    terraform-remote-state-management,
    managed-services-selection-rds-msk-elasticache,
    brownfield-terraform-reconciliation,
    rds-availability-model-multiaz-vs-aurora,
  ]
related_specs:
  [
    specs/k8s/probe-strategy.md,
    specs/security/threat-model.md,
    specs/privacy/db-encryption-at-rest.md,
    specs/compliance/iso27001-change-management.md,
  ]
slo_ref: docs/sre/slo/slo.yaml
---

# SPEC-INFRA-001 — AWS Production Platform (Immutable Terraform IaC)

> **One-line scope.** A reproducible, version-controlled AWS production platform — **RDS
> PostgreSQL 17 (Multi-AZ primary + 2 read replicas), EKS, Application/Network load balancers,
> ElastiCache for Redis, and MSK (Kafka)** — spread across **3 Availability Zones in `us-east-1`**
> and provisioned end-to-end by **Terraform** under **Immutable Infrastructure** discipline (no
> manual changes; replace-don't-mutate; remote state; plan-in-CI, apply behind a CAB gate).

<!-- Every numbered section is mandatory; (gate) sections are checked by docs/process/gates/phase-gates.yaml.
     This is an INFRASTRUCTURE spec — §8 maps to Terraform module contracts and §9 to the resource/state
     model rather than a REST API. No code is written until status: approved (CLAUDE.md §2). -->

## How `/deliver` reads this spec (section → phase)

| Spec section                                         | Feeds /deliver phase(s)                  | Gate it satisfies                                |
| ---------------------------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| §1 Context, §2 Goals, §3 Non-Goals, §4 Consumers     | 0 Intake · 1 Conception                  | problem/value/risk recorded                      |
| §5 FR, §6 NFR                                        | 2 Discovery · 4 Specification            | discovery + nfr; FR→AC traceability              |
| §6 NFR, §11 Governance/Security                      | 2 Discovery · 9 Security & DevSecOps     | data classification; threat & IaC scan review    |
| §7 Architecture, §14 ADR Impact, `new_adrs_required` | 5 Architecture                           | ADR(s) authored & accepted                       |
| §8 Terraform module contracts (gate)                 | 4 Specification · 6 Development          | contract-driven IaC (module inputs/outputs)      |
| §9 Resource & State model                            | 6 Development · 9 Security               | state safety; encryption/IAM safety              |
| §10 Golden Signals & SLO (gate)                      | 11 Observability & Operational Readiness | SLOs + PRR                                       |
| §11 Governance/Security (gate)                       | 9 DevSecOps                              | STRIDE; Checkov/tfsec; least-privilege           |
| §12 Acceptance Criteria (gate)                       | 8 Testing · all phases                   | **becomes the dry-run evidence in FINAL-REPORT** |
| §13 Risks, §15 Open Questions                        | every phase boundary                     | surfaced as HITL items                           |

> **Delivery:** once `status: approved`, this spec is built with
> `/deliver code iac specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md` — the IaC
> language maps to `infrastructure/terraform/`, validated by `terraform fmt/validate` + Checkov.

---

## 1. Context & Problem

### 1.1 Problem statement

The repo already carries a **partial** Terraform footprint under `infrastructure/terraform/`
(modules `networking`, `database`, `cache`, `message-broker`, `kubernetes`, `observability`,
`api-gateway`, `vector-db`, … and `environments/{dev,staging,production}`), but it is **incomplete
and divergent** from this platform's target: the `database` module is a **single** `aws_db_instance`
on **PostgreSQL 16.3** with **no read replicas**, and `message-broker` authenticates with
**SASL/SCRAM**, not TLS. So the real problem is not "nothing exists" — it is that the footprint is
**partial, version-divergent, and not yet the codified production platform**: every environment can
drift, multi-AZ recovery is unrehearsed, PG 17 + read-scaling is missing, and there is no single
authoritative spec. The cost of leaving it: failed audits (ISO 27001 change control), long MTTR,
configuration drift, and an inability to rebuild on demand. **This spec consolidates and completes
the existing tree into the production platform** (see §1.5 for the brownfield reconciliation).

### 1.2 Research / product question

Can the entire production platform be expressed as **versioned Terraform** such that the full
multi-AZ footprint is created (or rebuilt from zero) **automatically, identically, and safely** —
with no manual mutation — and every change flows through plan → review → CAB-gated apply?

### 1.3 Why now / motivation

The application platform (this monorepo) is ready to run on managed AWS services; provisioning is
the gating prerequisite. Doing it as Immutable IaC now avoids accruing manual, undocumented
infrastructure debt that becomes impossible to untangle later, and gives us tested DR and
reproducible non-prod environments from day one.

### 1.4 Deployment topology decision _(decided)_

**`monorepo-services`.** The Terraform lives in this repo under `infrastructure/terraform/`
(alongside the existing `infrastructure/` tree), reusing the repo's CI/CD, DevSecOps gates
(Checkov, SHA-pinned actions, SBOM), CODEOWNERS, and ISO-27001 change management. A standalone
infra repo was rejected — it would fork governance and break the single-pane Spec-as-PR flow.

### 1.5 Brownfield reconciliation _(decided — extend, do not fork)_

This spec **extends the existing `infrastructure/terraform/` modules in place; it does not author a
parallel tree.** Use the **existing module names** (`networking`, `database`, `cache`,
`message-broker`, `kubernetes`, `observability`, …) — the names in §7/§8 are role labels that map
onto them, not new modules. Three concrete deltas are resolved as explicit, ADR-backed decisions
(`new_adrs_required: brownfield-terraform-reconciliation`):

| Delta              | Existing today                              | Target (this spec)                                 | Decision                                                                                                                  |
| ------------------ | ------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| PostgreSQL version | `database` → **16.3** (`postgres16` family) | **17** (FR-02) → new `postgres17` parameter family | In-place major-version upgrade **or** blue/green via snapshot-restore — pick at the CAB gate; **not** a destroy/recreate. |
| Read replicas      | single `aws_db_instance.main`, **none**     | **+2** `replicate_source_db` read replicas (FR-02) | Net-new resources added to the `database` module.                                                                         |
| MSK authentication | `message-broker` → **SASL/SCRAM**           | **TLS** mutual-auth (FR-06)                        | Either keep SASL/SCRAM (then amend FR-06) **or** migrate to TLS — an ADR decision with a client-config migration step.    |

State for any in-place change is **moved with `terraform state mv`**, never destroyed. Until these
deltas are decided, building this spec is **blocked** (carried as an open item in §15).

## 2. Goals & Success Metrics

| ID   | Goal                                  | Measure of success                                                                                                                                                                                         |
| ---- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G-01 | Entire platform provisioned from code | `terraform apply` from an empty account stands up 100% of §7 resources; **zero** console-created resources                                                                                                 |
| G-02 | Highly available across 3 AZs         | HA = **RDS Multi-AZ standby** (auto-failover), ElastiCache Multi-AZ failover, MSK 3-broker quorum, EKS nodes across 3 AZs. The **2 RDS read replicas are read-scaling, not HA** (async, manual promotion). |
| G-03 | Immutable & drift-free                | `terraform plan` on a deployed environment is **empty** (no drift); changes ship as replacements, not in-place edits, for breaking attributes                                                              |
| G-04 | Reproducible & recoverable            | A second (staging) environment is created from the **same modules** with only a tfvars change; full rebuild ≤ 2h                                                                                           |
| G-05 | Secure by construction                | Encryption at rest (KMS) + TLS in transit on every data store; **zero** Checkov CRITICAL/HIGH; no public data-plane endpoints                                                                              |
| G-06 | Cost-attributed & bounded             | Every resource carries the cost-allocation tag set (§11/ADR-0020); a documented monthly cost envelope per environment                                                                                      |

## 3. Non-Goals / Out of Scope

- **Application workloads** — Helm charts / K8s Deployments for the app services (separate specs;
  this spec delivers the _cluster and data plane_, not what runs on them).
- **Multi-region / active-active DR** — single region (`us-east-1`), multi-AZ only. Cross-region
  replication and failover are future work (§13).
- **CI/CD runner infrastructure** and developer tooling accounts.
- **Data migration** from any existing database into the new RDS.
- **Self-managed Kafka/Redis/Postgres on EC2** — this spec uses AWS **managed** services (MSK,
  ElastiCache, RDS); the managed-vs-self-hosted decision is recorded as a new ADR (§14).
- **FinOps optimization** (savings plans, rightsizing automation) beyond baseline tagging + envelope.

## 4. Consumers & Personas

| Consumer                         | Need from this system                                                                             |
| -------------------------------- | ------------------------------------------------------------------------------------------------- |
| Platform / DevOps engineer       | `terraform plan`/`apply` to create & evolve the platform; versioned, reviewable modules           |
| Application services (this repo) | A PostgreSQL endpoint, Redis endpoint, Kafka bootstrap brokers, and an EKS cluster to deploy onto |
| SRE / on-call                    | Multi-AZ HA, CloudWatch golden signals, runbooks, and tested AZ-failure behaviour                 |
| Security / compliance owner      | Evidence of encryption, least-privilege IAM, no public exposure, IaC scan results, change records |
| Release Manager / CAB            | A `terraform plan` artifact to approve before any production `apply` (ISO 27001, ADR-0027)        |

## 5. Functional Requirements

<!-- One testable statement per row; each FR traces to an AC in §12. -->

| ID    | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| FR-01 | Provision a **VPC** in `us-east-1` spanning **3 AZs** (`us-east-1a/b/c`) with public + private (app) + isolated (data) subnet tiers per AZ, an internet gateway, route tables, **one NAT gateway per AZ in prod** (a single shared NAT allowed in non-prod for cost), and **VPC endpoints** for S3/ECR/Secrets Manager/STS (keep EKS pulls + secret fetches off the NAT/egress path — cost + A10 allow-list).                                                                                                                                                                                                                  |
| FR-02 | Provision **RDS PostgreSQL 17** with **two distinct mechanisms**: (a) **HA** via `multi_az = true` — a synchronous hidden standby in a second AZ that **auto-promotes** on primary failure (same endpoint); (b) **read-scaling** via **2 asynchronous read replicas** in the remaining AZs (separate reader endpoints, replica lag, **no automatic promotion** — a manual/runbook operation). Storage **encrypted with a customer-managed KMS key**; automated backups + PITR enabled. _(Decision deferred to §15: stay RDS Multi-AZ, or adopt **Aurora PostgreSQL** where reader instances are themselves failover targets.)_ |
| FR-03 | Provision an **EKS** cluster (control plane + managed node groups) with worker nodes **balanced across the 3 AZs**; private API endpoint; IRSA (IAM Roles for Service Accounts) enabled.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| FR-04 | Provision **load balancing**: an internet-facing **ALB** (via the AWS Load Balancer Controller / ingress) for HTTP(S), and an **NLB** where L4/static-IP is required; TLS terminated with ACM certs.                                                                                                                                                                                                                                                                                                                                                                                                                           |
| FR-05 | Provision **ElastiCache for Redis** (cluster/replication group) with nodes across **3 AZs**, **Multi-AZ automatic failover**, **encryption in transit (TLS) and at rest** (ADR-0019).                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| FR-06 | Provision **Amazon MSK (Kafka)** with **brokers across 3 AZs**, encryption at rest (KMS) + TLS in transit + in-cluster encryption, and a private bootstrap endpoint.                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| FR-07 | Use **RDS-managed master passwords** (`manage_master_user_password = true`) so RDS owns rotation and the credential never enters Terraform state; store other generated secrets (MSK/Redis auth) in **AWS Secrets Manager** (SecureString). **Never** output secrets to logs. Note: `sensitive = true` only redacts CLI/output — it does **not** encrypt state; that is the SSE-KMS backend's job (NFR-09).                                                                                                                                                                                                                    |
| FR-08 | Manage **Terraform remote state** in an encrypted **S3 backend** with **DynamoDB state locking**, versioning, and per-environment state isolation.                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| FR-09 | Apply a **consistent tag set** to every taggable resource: `environment`, `owner`, `cost-center`, `managed-by=terraform`, `spec=SPEC-INFRA-001` (ADR-0020 cost allocation).                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| FR-10 | Expose stable **module outputs**: VPC/subnet IDs, RDS writer + reader endpoints, EKS cluster name/OIDC, Redis primary endpoint, MSK bootstrap brokers — for app deploys to consume (§8).                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| FR-11 | Enforce **least-privilege security groups**: data stores (RDS/Redis/MSK) reachable **only** from the EKS node/pod security groups; **no** public ingress to any data-plane service.                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| FR-12 | Be **environment-parameterised** (`dev`/`staging`/`prod` via tfvars) so the same modules build any environment with differing sizing — no copy-paste of resource definitions.                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | **Immutable infrastructure — scoped honestly by tier.** _Compute_ (EKS node groups, launch templates, AMIs): strictly immutable — changes ship as **replacement** (new launch template / blue-green), never in-place, versioned Bottlerocket/MNG images, no SSH/manual mutation. _Stateful managed services_ (RDS/MSK/ElastiCache): changed via **controlled managed operations** (in-place modify with maintenance window, or **snapshot-restore / blue-green**), **never console mutation** — true destroy-recreate would lose data, so "immutable" here means _no out-of-band change_, not _recreate-on-every-change_ (see §13). |
| NFR-02 | **Pinned & reproducible:** Terraform `required_version` pinned; all providers and modules pinned to exact versions in `.terraform.lock.hcl`; no version ranges.                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| NFR-03 | **Encryption everywhere:** at rest via customer-managed **KMS** (RDS, MSK, ElastiCache, EBS, S3 state); in transit via **TLS 1.2+** (rediss://, MSK TLS, RDS SSL `require`) — aligns ADR-0018/0019.                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| NFR-04 | **Least-privilege IAM:** scoped roles/policies; **IRSA** for in-cluster AWS access; no wildcard `*` actions on resources; no long-lived access keys in code.                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| NFR-05 | **Multi-AZ availability:** every stateful tier tolerates the loss of **1 AZ** with **automatic** failover — **RDS Multi-AZ standby** (auto-promoted), ElastiCache Multi-AZ failover, MSK 3-broker quorum (RF=3/minISR=2), EKS nodes spread by AZ. The **read replicas do not count toward this** — they are async and not auto-promoted (FR-02).                                                                                                                                                                                                                                                                                    |
| NFR-06 | **Observability:** CloudWatch metrics/alarms + Container Insights for EKS; RDS/MSK/ElastiCache enhanced monitoring; logs shipped; golden-signal alarms (§10). Structured, no secrets in logs.                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| NFR-07 | **DevSecOps gate:** `terraform fmt -check`, `terraform validate`, and **Checkov** (and/or tfsec) run in CI on every change; **zero CRITICAL/HIGH** unsuppressed (ADR-0029); SHA-pinned GitHub Actions; a plan-time **SBOM/inventory** of provisioned resource types.                                                                                                                                                                                                                                                                                                                                                                |
| NFR-08 | **Config via variables:** all environment-specific values are tfvars/variables with documented defaults; **no** hardcoded account IDs, ARNs, AMIs, or secrets in module bodies.                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| NFR-09 | **State safety:** remote state encrypted (SSE-KMS) + locked (DynamoDB); state never committed to git; sensitive outputs flagged `sensitive = true`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| NFR-10 | **Cost envelope:** a documented expected monthly cost per environment; tags enable per-`cost-center` allocation (ADR-0020); non-prod sized down.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

## 7. Architecture

Single region **`us-east-1`**, three Availability Zones (`a`/`b`/`c`). One VPC, three subnet tiers
per AZ. Managed services for every stateful component; EKS for compute. Provisioned by composable,
versioned Terraform modules with remote state.

```
                         AWS Account · Region us-east-1
┌──────────────────────────────────────────────────────────────────────────────┐
│  VPC 10.0.0.0/16                                                               │
│                                                                                │
│   AZ us-east-1a            AZ us-east-1b            AZ us-east-1c               │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐             │
│  │ public  /24  │ NAT-a  │ public  /24  │ NAT-b  │ public  /24  │ NAT-c       │
│  │  ALB / NLB ◄─┼────────┼── (internet-facing, ACM TLS) ────────┼──► clients  │
│  ├──────────────┤        ├──────────────┤        ├──────────────┤             │
│  │ app(private) │        │ app(private) │        │ app(private) │   EKS nodes  │
│  │  EKS nodes   │        │  EKS nodes   │        │  EKS nodes   │   (3 AZ MNG) │
│  ├──────────────┤        ├──────────────┤        ├──────────────┤             │
│  │ data(isolated)        │ data(isolated)        │ data(isolated)             │
│  │  RDS primary │◄──repl──│ RDS replica1 │        │ RDS replica2 │  PG 17       │
│  │  Redis node  │  (MAZ)  │  Redis node  │  (MAZ) │  Redis node  │  ElastiCache │
│  │  MSK broker1 │         │  MSK broker2 │        │  MSK broker3 │  Kafka       │
│  └──────────────┘        └──────────────┘        └──────────────┘             │
│                                                                                │
│  KMS (CMKs) · Secrets Manager · CloudWatch · IAM (IRSA) · ACM                  │
└──────────────────────────────────────────────────────────────────────────────┘
  Terraform state: S3 (SSE-KMS, versioned) + DynamoDB lock — per environment
```

> **On the diagram:** "RDS primary / replica1 / replica2" shows the **read-scaling** layout. HA is
> provided **additionally** by the Multi-AZ **hidden synchronous standby** (not drawn, in a second
> AZ) which auto-promotes on primary failure — the replicas do **not** perform that role (FR-02).

**Module decomposition — extends the existing tree (§1.5), does not fork it.** The role labels
below map onto the **existing** modules under `infrastructure/terraform/modules/` (keep their
names): `network`→**`networking`** (VPC, subnets, NAT, routes, **VPC endpoints**) ·
`rds-postgres`→**`database`** (primary + **Multi-AZ standby** + 2 read replicas + KMS + params) ·
`eks`→**`kubernetes`** (cluster, MNG, IRSA, addons) · `loadbalancing` (ALB controller IAM, NLB,
ACM) · `elasticache-redis`→**`cache`** · `msk-kafka`→**`message-broker`** · plus `kms`, `secrets`,
`iam`, **`observability`**, and a `remote-state` bootstrap. Composed per environment under
`environments/<env>/`. Event topology aligns with **ADR-0003** (async streaming via Kafka); any
deviation is a new ADR (§14).

## 8. Terraform Module Contracts _(gate: contract-driven IaC)_

<!-- The "interface" of an IaC change is each module's input variables and output values. These are
     the contract app deploys and other modules depend on — generate/validate, don't hand-drift. -->

| Module              | Key inputs (variables)                                                                                                                                                           | Key outputs                                                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `network`           | `cidr`, `azs=[a,b,c]`, `env`, tags                                                                                                                                               | `vpc_id`, `public_subnet_ids`, `app_subnet_ids`, `data_subnet_ids`                                |
| `rds-postgres`      | `engine_version=17`, `instance_class`, `multi_az=true` (HA standby), `replica_count=2` (read-scaling), `manage_master_user_password=true`, `kms_key_arn`, `subnet_ids`, `sg_ids` | `writer_endpoint` (HA, stable across failover), `reader_endpoints[]`, `port`, `master_secret_arn` |
| `eks`               | `cluster_version`, `node_groups{az→size}`, `subnet_ids`, `irsa=true`                                                                                                             | `cluster_name`, `cluster_endpoint`, `oidc_provider_arn`, `node_security_group_id`                 |
| `loadbalancing`     | `cluster_name`, `acm_cert_arn`, `public_subnet_ids`                                                                                                                              | `alb_controller_role_arn`, `nlb_arn` (if used)                                                    |
| `elasticache-redis` | `node_type`, `replicas`, `multi_az=true`, `transit_encryption=true`, `at_rest_encryption=true`, `subnet_ids`                                                                     | `primary_endpoint`, `reader_endpoint`, `auth_secret_arn`                                          |
| `msk-kafka`         | `kafka_version`, `broker_count=3`, `broker_instance_type`, `kms_key_arn`, `subnet_ids`, `encryption_in_transit=TLS`                                                              | `bootstrap_brokers_tls` (clients need only this in KRaft mode)                                    |

Outputs of FR-10 are the **stable contract** app-deploy specs (and the EKS workloads) consume;
breaking an output is a versioned, reviewed change.

## 9. Resource & State Model

### 9.1 Resources (managed at boundaries)

VPC + subnets/route tables/NAT/IGW · RDS DB instance (primary) + 2 read-replica instances + subnet
group + parameter group + KMS key · EKS cluster + managed node groups + OIDC provider + addons
(VPC-CNI, CoreDNS, kube-proxy, EBS-CSI) · ElastiCache replication group + subnet group · MSK
cluster + configuration · ALB controller IAM + NLB + ACM cert · Secrets Manager secrets · KMS
CMKs · IAM roles/policies · CloudWatch alarms/log groups · security groups.

### 9.2 State convention _(define once; all environments agree)_

Remote backend `s3://<org>-tfstate-<account>/<env>/<region>/terraform.tfstate`, **SSE-KMS**,
**versioned**, **DynamoDB lock table** `terraform-locks`. One state per environment; modules are
shared and pinned. State is **never** committed to git (NFR-09).

### 9.3 Retention

RDS automated backups + PITR (7-day prod / 1-day non-prod) plus a monthly manual snapshot kept 1
year; MSK + ElastiCache daily snapshots, 7-day retention; S3 state versioning retains prior states;
CloudWatch log retention 90 d (prod) / 30 d (non-prod). See §15 for the (illustrative) resolved
values — re-confirm at the cost/compliance gate for a real run.

### 9.4 Governance/response metadata

Every resource is tagged (FR-09) so cost, owner, and the governing spec are queryable from the AWS
console/Cost Explorer; the `terraform plan` JSON is the change artifact attached to the CAB record.

## 10. Golden Signals & SLO Definitions _(gate: observability)_

These are the **platform-plane** signals this spec owns (per ADR-0004 Observability Stack).
Application-plane request signals (ALB 5xx, `TargetResponseTime` per service) belong to the
workloads that run on the platform — **out of scope** here (§3) and owned by the app specs.

| Signal     | Derivation (platform infra)                                                                                                      | Exposed as               |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| Traffic    | MSK `BytesIn/Out`; RDS connections; Redis ops/sec; NAT `BytesOut`; ALB `ActiveFlowCount`                                         | throughput/conn counts   |
| Latency    | RDS read/write latency; **RDS `ReplicaLag`** (read-replica freshness); Redis latency; ALB `TargetResponseTime` (infra view only) | P50 / P95 / P99          |
| Error      | RDS failed connections + failover events; MSK under-replicated/offline partitions; ElastiCache failovers; unhealthy-host count   | error_rate / event count |
| Saturation | RDS CPU/FreeableStorage/IOPS; EKS node CPU/mem + pod headroom; Redis evictions/memory; MSK disk; **NAT GW throughput**           | saturation_pct, headroom |

SLO targets recorded in `docs/sre/slo/slo.yaml` (e.g. RDS availability ≥ 99.95%, ElastiCache ≥
99.9%, MSK under-replicated-partitions = 0, **read-replica lag < N s**). CloudWatch alarms page on
breach; an AZ-failure test (§12 AC-09) validates the multi-AZ standby SLO. PRR ≥ 90% before
production promotion.

## 11. Governance, Privacy & Security _(gate: threat & IaC scan review)_

| Concern                             | Control in this spec                                                                                                                                                                                                           | Maps to                                 |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| Human oversight (change gate)       | Production `terraform apply` requires a CAB-approved RFC; plan reviewed in PR                                                                                                                                                  | ADR-0027                                |
| Data classification / PII           | The platform _stores_ app data (may be L1–L4); encryption + access controls enforced here, classification owned by the data-handling specs                                                                                     | ADR-0012, ADR-0018, specs/privacy/      |
| Auditability (change trail)         | All changes via git PR + `terraform plan` artifact; **account CloudTrail**; tagged resources. _(SOX audit-log immutability per ADR-0026 applies only if this platform later hosts a financial-data path — not asserted here.)_ | ADR-0027 (ISO-27001); ADR-0026 (if SOX) |
| Authn / abuse (network exposure)    | No public data-plane ingress; least-privilege SGs (FR-11); private EKS API; **WAFv2 on the ALB** (§15.4)                                                                                                                       | specs/security/threat-model.md          |
| Cost envelope                       | Mandatory cost tags (FR-09); documented monthly envelope per env (G-06). _ADR-0020 is reused for its **tagging/allocation discipline**, not its LLM-budget mechanism._                                                         | ADR-0020 (tagging discipline)           |
| Pipeline security (IaC scan / SBOM) | `terraform fmt/validate` + **Checkov/tfsec** in CI, zero CRITICAL/HIGH; SHA-pinned actions; resource-inventory artifact                                                                                                        | ADR-0029                                |

**STRIDE over the untrusted boundaries** (internet→ALB, and the Terraform state/apply pipeline):
ALB is the only internet-facing surface (TLS + optional WAF); data stores are isolated-subnet +
SG-scoped (Spoofing/Tampering/Info-disclosure mitigated); state is encrypted + locked + access-
controlled (Tampering/EoP); apply is least-privilege via a scoped CI role (EoP). No `src/agents/`
or `src/guardrails/` surface → Phase 10 (AI Safety) is **N/A** for this spec.

## 12. Acceptance Criteria _(gate: dry-run validation)_

<!-- Each observable & runnable; these become the dry-run evidence in /deliver's FINAL-REPORT. -->

| ID    | Acceptance criterion                                                                                                                                                                                                                                                                                                                                       |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC-01 | `terraform fmt -check` and `terraform validate` pass for every module and environment.                                                                                                                                                                                                                                                                     |
| AC-02 | **Checkov/tfsec** scan reports **zero** CRITICAL/HIGH findings (or each is documented + risk-accepted).                                                                                                                                                                                                                                                    |
| AC-03 | `terraform plan` from an empty state proposes the full §7 footprint; a second `plan` on the applied state is **empty modulo a documented `lifecycle.ignore_changes` allow-list** (managed services emit known perpetual diffs — the allow-list is reviewed, not silently growing).                                                                         |
| AC-04 | `aws rds describe-db-instances` shows PostgreSQL **17** with **`MultiAZ=true`** (HA standby) on the primary, **plus 2 read replicas** (`ReadReplicaDBInstanceIdentifiers`), each in a distinct AZ, all `StorageEncrypted=true` with the CMK. (Standby and replicas are verified as **separate** facts.)                                                    |
| AC-05 | EKS worker nodes are present in **all 3 AZs**; the cluster API endpoint is **private**; IRSA OIDC provider exists.                                                                                                                                                                                                                                         |
| AC-06 | ElastiCache Redis has **Multi-AZ automatic failover**, `TransitEncryptionEnabled=true`, `AtRestEncryptionEnabled=true`, nodes across 3 AZs.                                                                                                                                                                                                                |
| AC-07 | MSK cluster has **3 brokers across 3 AZs**, encryption-in-transit = TLS, encryption-at-rest with the CMK; bootstrap-brokers-TLS endpoint resolves.                                                                                                                                                                                                         |
| AC-08 | No data-plane service (RDS/Redis/MSK) is reachable from `0.0.0.0/0`; security groups allow only the EKS node/pod SG.                                                                                                                                                                                                                                       |
| AC-09 | **AZ-failure drill:** `reboot-db-instance --force-failover` (or simulated AZ loss) keeps the **writer endpoint** serving within the RDS Multi-AZ RTO via the **standby** (replicas play no part); Redis/MSK remain available. A separate documented **read-replica promotion runbook** is exercised (replicas are NOT auto-promoted) and its RTO recorded. |
| AC-10 | The **same modules** build a `staging` environment from a different tfvars file with no module edits, and a **timed full rebuild completes ≤ 2 h** (validates G-04).                                                                                                                                                                                       |
| AC-11 | Every provisioned resource carries the mandatory tag set (`environment`, `owner`, `cost-center`, `managed-by=terraform`, `spec=SPEC-INFRA-001`).                                                                                                                                                                                                           |
| AC-12 | No secret appears in `terraform output`, state, or CI logs in plaintext; the **RDS master password is RDS-managed** (`manage_master_user_password`, absent from state) and Redis/MSK credentials resolve from Secrets Manager.                                                                                                                             |
| AC-13 | _(traces FR-04)_ An **internet-facing ALB** exists with an **ACM cert** and an HTTPS listener terminating **TLS 1.2+**; where L4 is required an **NLB** is present; the AWS Load Balancer Controller IRSA role is bound.                                                                                                                                   |
| AC-14 | _(traces FR-10)_ Every §8 module **output resolves non-empty** (`terraform output` for `writer_endpoint`, `reader_endpoints`, `cluster_name`, `oidc_provider_arn`, Redis `primary_endpoint`, `bootstrap_brokers_tls`) — the app-deploy contract is satisfiable.                                                                                            |

## 13. Risks & Limitations

- **Single region.** `us-east-1` only — a full-region outage is not covered. Documented exit path:
  cross-region read-replica + Route53 failover (future ADR). Record as an explicit consequence,
  not a silent assumption.
- **Managed-service constraints.** RDS read replicas are asynchronous (replica lag under write
  bursts); MSK/ElastiCache patching windows can cause brief failovers — surface in runbooks.
- **Cost.** A 3-AZ managed footprint (RDS Multi-AZ + 2 replicas, MSK 3-broker, ElastiCache MAZ,
  EKS, NAT×3) is non-trivial; non-prod must be sized down and the envelope tracked (G-06/ADR-0020).
- **Stateful "immutability" is bounded (NFR-01).** Compute is genuinely immutable (node groups
  replaced); data stores are **not** recreated on change — they use in-place managed ops or
  snapshot-restore/blue-green. The claim is "no out-of-band mutation," not "recreate every change."
- **Read replicas are not HA (FR-02/NFR-05).** They are async (lag under write bursts) and **not
  auto-promoted** — writer-HA is the Multi-AZ standby alone. Adopting **Aurora** (where readers are
  failover targets) is the open alternative (§15).
- **Brownfield migration risk (§1.5).** Extending the existing `database` (PG 16.3, single instance,
  SASL/SCRAM MSK) into the PG-17 + read-replica + TLS target involves a major-version upgrade and an
  auth migration — done via `terraform state mv` / snapshot-restore, **never** destroy-recreate;
  perpetual-diff `ignore_changes` lists must be reviewed (AC-03), not silently grown.
- **Apply blast radius.** A bad `apply` can affect production; mitigated by plan-in-PR + CAB gate +
  per-environment state isolation + targeted applies.

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0003 (async/Kafka), ADR-0004 (observability stack — §10 platform signals),
  ADR-0012 (PII masking — data the platform stores), ADR-0018 (encryption at rest), ADR-0019
  (Redis TLS + value encryption), ADR-0020 (cost-allocation **tagging discipline**, not its LLM
  budget), ADR-0026 (SOX audit-log immutability — _only if_ a financial path lands here),
  ADR-0027 (ISO-27001 change management), ADR-0029 (DevSecOps/IaC scanning).
- **Adds** (authored in Phase 5): `immutable-infrastructure-terraform` (replace-not-mutate,
  tier-scoped), `aws-three-az-region-topology` (VPC/subnet/AZ design), `terraform-remote-state-
management` (S3+DynamoDB backend, isolation, locking), `managed-services-selection-rds-msk-
elasticache` (managed vs self-hosted + exit paths), **`brownfield-terraform-reconciliation`**
  (extend-not-fork; PG-16→17 + SCRAM→TLS migration plan; `state mv` discipline — §1.5), and
  **`rds-availability-model-multiaz-vs-aurora`** (HA-standby vs read-replicas; the Aurora option).
- **Produces:** Terraform modules + environments under `infrastructure/terraform/`,
  `.terraform.lock.hcl` (pinned), a Checkov policy/baseline, module input/output docs, a
  resource-inventory/SBOM artifact, runbook stubs (RDS failover, AZ loss, state recovery), and
  `slo.yaml` entries for the platform golden signals.

## 15. Open Questions

<!-- Resolved at a HITL gate, not assumed. /deliver lists these as open-HITL items. -->

> ⚠️ **Illustrative example values — this is a template/demo spec.** The six items below carry
> **fake, plausible** answers to show a fully-resolved spec; they are **not** real production
> decisions. A real run must re-decide each at the §11 CAB gate and replace these figures.

1. **Instance sizing & cost envelope** _(resolved — example)_: **RDS** `db.r6g.2xlarge` primary
   (Multi-AZ) + `db.r6g.xlarge` ×2 replicas, gp3 500 GB; **EKS** `m6i.2xlarge` managed nodes, 2/AZ
   (6 baseline) autoscaling 6–15; **MSK** `kafka.m5.large` ×3, 1 TB/broker; **Redis**
   `cache.r6g.xlarge`, 1 primary + 2 replicas. Cost envelope (example): **prod ≈ \$6,500/mo**,
   **staging ≈ \$1,800/mo**, **dev ≈ \$700/mo**. (Figures fabricated for the example.)
2. **MSK mode** _(resolved — example)_: **KRaft** (no ZooKeeper) on **provisioned** MSK (not
   Serverless) — predictable cost and broker-level tuning at the expected throughput.
3. **Backup/retention windows** _(resolved — example)_: RDS **PITR 7 days** (prod) / 1 day
   (non-prod); automated snapshots 7 d + a **monthly manual snapshot kept 1 year**; MSK & Redis
   daily snapshots, 7-day retention; CloudWatch logs **90 d** (prod) / 30 d (non-prod).
4. **WAF on the ALB** _(resolved — example)_: **Yes — AWS WAFv2** web ACL on the internet-facing
   ALB in prod (AWS managed rule groups: Common, SQLi, Known-Bad-Inputs + a rate-based rule).
5. **Multi-account strategy** _(resolved — example)_: **Separate AWS accounts per environment**
   under **AWS Organizations + Control Tower** (`dev`/`staging`/`prod` + a central logging
   account); environments isolated by account, not just VPC.
6. **Terraform execution** _(resolved — example)_: **GitHub Actions with OIDC-assumed IAM role**
   (no long-lived keys) — `plan` on PR, `apply` on merge gated by environment protection + a
   CAB-approved RFC (ADR-0027); reuses the repo's existing OIDC/SHA-pinned-actions posture.

> 🔴 **Genuinely open — these BLOCK `status: approved` (not example-fillable; real decisions):**

7. **Brownfield deltas (§1.5).** (a) PG **16.3 → 17**: in-place major-version upgrade vs blue/green
   snapshot-restore? (b) MSK **SASL/SCRAM → TLS** mutual-auth (FR-06) vs keep SCRAM (amend FR-06)?
   Each needs an ADR + a client-config migration step. **Until decided, the build is blocked.**
8. **RDS availability model (FR-02).** Stay **RDS Multi-AZ** (hidden standby + 2 manual-promotion
   read replicas) or adopt **Aurora PostgreSQL** (reader instances are failover targets, cluster
   reader/writer endpoints)? Drives AC-04/AC-09 and the §10 replica-lag SLO.

## 16. References

- AWS Well-Architected Framework (Reliability, Security, Cost pillars); AWS Multi-AZ patterns for
  RDS, MSK, ElastiCache, EKS.
- HashiCorp Terraform — module composition, remote state (S3 + DynamoDB locking), provider/version
  pinning, immutable-infrastructure guidance.
- Repo: `infrastructure/terraform/` (existing tree), `specs/k8s/probe-strategy.md`,
  `specs/security/threat-model.md`, ADR-0003/0018/0019/0020/0027/0029, `docs/sre/slo/slo.yaml`.
