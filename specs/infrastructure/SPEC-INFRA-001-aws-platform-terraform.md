---
# ─────────────────────────────────────────────────────────────────────────
# SPEC METADATA  (machine-readable header — /deliver and CI read this block)
# ─────────────────────────────────────────────────────────────────────────
id: SPEC-INFRA-001
title: AWS Production Platform — multi-AZ data + compute + streaming, provisioned by immutable Terraform IaC
version: 0.1.0
status: draft # draft | in-review | approved | implemented | superseded
owner: valdomirosouza
created: 2026-06-08
source: >-
  Platform request — stand up the full production cloud footprint (RDS PostgreSQL 17 + 2 read
  replicas, EKS, load balancers, Redis, Kafka) across 3 Availability Zones in us-east-1 (N.
  Virginia), provisioned automatically and reproducibly via Terraform following Immutable
  Infrastructure best practices.
deployment_topology: monorepo-services # IaC lives in this monorepo under infrastructure/terraform/ (§1.4)
governing_adrs: [ADR-0003, ADR-0018, ADR-0019, ADR-0020, ADR-0027, ADR-0029]
new_adrs_required:
  [
    immutable-infrastructure-terraform,
    aws-three-az-region-topology,
    terraform-remote-state-management,
    managed-services-selection-rds-msk-elasticache,
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

There is no codified, reproducible production cloud footprint. Standing up data, compute, caching,
and streaming by hand (or with drift-prone, half-documented scripts) is slow, error-prone, and
**not auditable** — every environment differs, recovery from a region/AZ event is unrehearsed, and
there is no single source of truth for what is deployed. The cost of not solving it: failed audits
(ISO 27001 change control), long MTTR, configuration drift, and an inability to rebuild the
platform on demand. This is the "big issue" the spec resolves.

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

## 2. Goals & Success Metrics

| ID   | Goal                                  | Measure of success                                                                                                                            |
| ---- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| G-01 | Entire platform provisioned from code | `terraform apply` from an empty account stands up 100% of §7 resources; **zero** console-created resources                                    |
| G-02 | Highly available across 3 AZs         | RDS primary + 2 replicas, EKS node groups, MSK brokers, and ElastiCache nodes each span 3 distinct AZs                                        |
| G-03 | Immutable & drift-free                | `terraform plan` on a deployed environment is **empty** (no drift); changes ship as replacements, not in-place edits, for breaking attributes |
| G-04 | Reproducible & recoverable            | A second (staging) environment is created from the **same modules** with only a tfvars change; full rebuild ≤ 2h                              |
| G-05 | Secure by construction                | Encryption at rest (KMS) + TLS in transit on every data store; **zero** Checkov CRITICAL/HIGH; no public data-plane endpoints                 |
| G-06 | Cost-attributed & bounded             | Every resource carries the cost-allocation tag set (§11/ADR-0020); a documented monthly cost envelope per environment                         |

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

| ID    | Requirement                                                                                                                                                                                                    |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | Provision a **VPC** in `us-east-1` spanning **3 AZs** (`us-east-1a/b/c`) with public + private (app) + isolated (data) subnet tiers per AZ, one **NAT gateway per AZ**, an internet gateway, and route tables. |
| FR-02 | Provision **RDS PostgreSQL 17**: a **Multi-AZ** primary plus **2 read replicas** placed in the other two AZs; storage **encrypted with a customer-managed KMS key**; automated backups + PITR enabled.         |
| FR-03 | Provision an **EKS** cluster (control plane + managed node groups) with worker nodes **balanced across the 3 AZs**; private API endpoint; IRSA (IAM Roles for Service Accounts) enabled.                       |
| FR-04 | Provision **load balancing**: an internet-facing **ALB** (via the AWS Load Balancer Controller / ingress) for HTTP(S), and an **NLB** where L4/static-IP is required; TLS terminated with ACM certs.           |
| FR-05 | Provision **ElastiCache for Redis** (cluster/replication group) with nodes across **3 AZs**, **Multi-AZ automatic failover**, **encryption in transit (TLS) and at rest** (ADR-0019).                          |
| FR-06 | Provision **Amazon MSK (Kafka)** with **brokers across 3 AZs**, encryption at rest (KMS) + TLS in transit + in-cluster encryption, and a private bootstrap endpoint.                                           |
| FR-07 | Store all generated secrets (DB master credential, MSK/Redis auth) in **AWS Secrets Manager** (or SSM Parameter Store, SecureString); **never** output secrets to Terraform state in plaintext or to logs.     |
| FR-08 | Manage **Terraform remote state** in an encrypted **S3 backend** with **DynamoDB state locking**, versioning, and per-environment state isolation.                                                             |
| FR-09 | Apply a **consistent tag set** to every taggable resource: `environment`, `owner`, `cost-center`, `managed-by=terraform`, `spec=SPEC-INFRA-001` (ADR-0020 cost allocation).                                    |
| FR-10 | Expose stable **module outputs**: VPC/subnet IDs, RDS writer + reader endpoints, EKS cluster name/OIDC, Redis primary endpoint, MSK bootstrap brokers — for app deploys to consume (§8).                       |
| FR-11 | Enforce **least-privilege security groups**: data stores (RDS/Redis/MSK) reachable **only** from the EKS node/pod security groups; **no** public ingress to any data-plane service.                            |
| FR-12 | Be **environment-parameterised** (`dev`/`staging`/`prod` via tfvars) so the same modules build any environment with differing sizing — no copy-paste of resource definitions.                                  |

## 6. Non-Functional Requirements

| ID     | Requirement                                                                                                                                                                                                                                                                                  |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | **Immutable infrastructure:** changes to breaking attributes ship as **replacement** (e.g. new node-group launch template, blue/green), never in-place mutation; nodes use versioned, immutable images (EKS managed node groups / Bottlerocket); no SSH/manual changes to running resources. |
| NFR-02 | **Pinned & reproducible:** Terraform `required_version` pinned; all providers and modules pinned to exact versions in `.terraform.lock.hcl`; no version ranges.                                                                                                                              |
| NFR-03 | **Encryption everywhere:** at rest via customer-managed **KMS** (RDS, MSK, ElastiCache, EBS, S3 state); in transit via **TLS 1.2+** (rediss://, MSK TLS, RDS SSL `require`) — aligns ADR-0018/0019.                                                                                          |
| NFR-04 | **Least-privilege IAM:** scoped roles/policies; **IRSA** for in-cluster AWS access; no wildcard `*` actions on resources; no long-lived access keys in code.                                                                                                                                 |
| NFR-05 | **Multi-AZ availability:** every stateful tier tolerates the loss of **1 AZ** with automatic failover; RDS Multi-AZ, ElastiCache automatic failover, MSK 3-broker quorum, EKS nodes spread by AZ.                                                                                            |
| NFR-06 | **Observability:** CloudWatch metrics/alarms + Container Insights for EKS; RDS/MSK/ElastiCache enhanced monitoring; logs shipped; golden-signal alarms (§10). Structured, no secrets in logs.                                                                                                |
| NFR-07 | **DevSecOps gate:** `terraform fmt -check`, `terraform validate`, and **Checkov** (and/or tfsec) run in CI on every change; **zero CRITICAL/HIGH** unsuppressed (ADR-0029); SHA-pinned GitHub Actions; a plan-time **SBOM/inventory** of provisioned resource types.                         |
| NFR-08 | **Config via variables:** all environment-specific values are tfvars/variables with documented defaults; **no** hardcoded account IDs, ARNs, AMIs, or secrets in module bodies.                                                                                                              |
| NFR-09 | **State safety:** remote state encrypted (SSE-KMS) + locked (DynamoDB); state never committed to git; sensitive outputs flagged `sensitive = true`.                                                                                                                                          |
| NFR-10 | **Cost envelope:** a documented expected monthly cost per environment; tags enable per-`cost-center` allocation (ADR-0020); non-prod sized down.                                                                                                                                             |

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

**Module decomposition** (each a versioned, single-responsibility Terraform module under
`infrastructure/terraform/modules/`, composed per environment under
`infrastructure/terraform/environments/<env>/`):

`network` (VPC, subnets, NAT, routes) · `rds-postgres` (primary + replicas + KMS + params) ·
`eks` (cluster, managed node groups, IRSA, addons) · `loadbalancing` (ALB controller IAM, NLB,
ACM) · `elasticache-redis` · `msk-kafka` · `kms`, `secrets`, `iam`, `observability`, and a
`remote-state` bootstrap. Network and event topology align with **ADR-0003** (async streaming via
Kafka); any deviation is recorded as a new ADR (§14).

## 8. Terraform Module Contracts _(gate: contract-driven IaC)_

<!-- The "interface" of an IaC change is each module's input variables and output values. These are
     the contract app deploys and other modules depend on — generate/validate, don't hand-drift. -->

| Module              | Key inputs (variables)                                                                                              | Key outputs                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `network`           | `cidr`, `azs=[a,b,c]`, `env`, tags                                                                                  | `vpc_id`, `public_subnet_ids`, `app_subnet_ids`, `data_subnet_ids`                |
| `rds-postgres`      | `engine_version=17`, `instance_class`, `replica_count=2`, `kms_key_arn`, `subnet_ids`, `sg_ids`, `multi_az=true`    | `writer_endpoint`, `reader_endpoints[]`, `port`, `secret_arn`                     |
| `eks`               | `cluster_version`, `node_groups{az→size}`, `subnet_ids`, `irsa=true`                                                | `cluster_name`, `cluster_endpoint`, `oidc_provider_arn`, `node_security_group_id` |
| `loadbalancing`     | `cluster_name`, `acm_cert_arn`, `public_subnet_ids`                                                                 | `alb_controller_role_arn`, `nlb_arn` (if used)                                    |
| `elasticache-redis` | `node_type`, `replicas`, `multi_az=true`, `transit_encryption=true`, `at_rest_encryption=true`, `subnet_ids`        | `primary_endpoint`, `reader_endpoint`, `auth_secret_arn`                          |
| `msk-kafka`         | `kafka_version`, `broker_count=3`, `broker_instance_type`, `kms_key_arn`, `subnet_ids`, `encryption_in_transit=TLS` | `bootstrap_brokers_tls`, `zookeeper_or_kraft_endpoint`                            |

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

RDS automated backups + PITR (e.g. 7-day retention prod / 1-day non-prod); MSK + ElastiCache
snapshots per environment; S3 state versioning retains prior states; CloudWatch log retention set
per log group (e.g. 30–90 days). Final values are open (§15) pending cost/compliance review.

### 9.4 Governance/response metadata

Every resource is tagged (FR-09) so cost, owner, and the governing spec are queryable from the AWS
console/Cost Explorer; the `terraform plan` JSON is the change artifact attached to the CAB record.

## 10. Golden Signals & SLO Definitions _(gate: observability)_

| Signal     | Derivation (infra)                                                          | Exposed as                     |
| ---------- | --------------------------------------------------------------------------- | ------------------------------ |
| Traffic    | ALB `RequestCount`; MSK `BytesIn/Out`; RDS connections; Redis ops/sec       | per-service request/throughput |
| Latency    | ALB `TargetResponseTime`; RDS read/write latency; Redis latency             | P50 / P95 / P99                |
| Error      | ALB 5xx rate; RDS failed connections; MSK under-replicated partitions       | error_rate                     |
| Saturation | RDS CPU/FreeableMemory/storage; EKS node CPU/mem; Redis evictions; MSK disk | saturation_pct, headroom       |

SLO targets recorded in `docs/sre/slo/slo.yaml` (e.g. RDS availability ≥ 99.95%, ALB availability
≥ 99.9%, MSK under-replicated-partitions = 0). CloudWatch alarms page on breach; an AZ-failure
test (§12 AC-09) validates the multi-AZ SLO. PRR ≥ 90% before production promotion.

## 11. Governance, Privacy & Security _(gate: threat & IaC scan review)_

| Concern                             | Control in this spec                                                                                                                       | Maps to                            |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------- |
| Human oversight (change gate)       | Production `terraform apply` requires a CAB-approved RFC; plan reviewed in PR                                                              | ADR-0027                           |
| Data classification / PII           | The platform _stores_ app data (may be L1–L4); encryption + access controls enforced here, classification owned by the data-handling specs | ADR-0012, ADR-0018, specs/privacy/ |
| Auditability (immutable trail)      | All changes via git PR + `terraform plan` artifact; CloudTrail on the account; tagged resources                                            | ADR-0026, ADR-0027                 |
| Authn / abuse (network exposure)    | No public data-plane ingress; least-privilege SGs (FR-11); private EKS API; WAF on ALB (open §15)                                          | specs/security/threat-model.md     |
| Cost envelope                       | Mandatory cost tags (FR-09); documented monthly envelope per env (G-06)                                                                    | ADR-0020                           |
| Pipeline security (IaC scan / SBOM) | `terraform fmt/validate` + **Checkov/tfsec** in CI, zero CRITICAL/HIGH; SHA-pinned actions; resource-inventory artifact                    | ADR-0029                           |

**STRIDE over the untrusted boundaries** (internet→ALB, and the Terraform state/apply pipeline):
ALB is the only internet-facing surface (TLS + optional WAF); data stores are isolated-subnet +
SG-scoped (Spoofing/Tampering/Info-disclosure mitigated); state is encrypted + locked + access-
controlled (Tampering/EoP); apply is least-privilege via a scoped CI role (EoP). No `src/agents/`
or `src/guardrails/` surface → Phase 10 (AI Safety) is **N/A** for this spec.

## 12. Acceptance Criteria _(gate: dry-run validation)_

<!-- Each observable & runnable; these become the dry-run evidence in /deliver's FINAL-REPORT. -->

| ID    | Acceptance criterion                                                                                                                                                    |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC-01 | `terraform fmt -check` and `terraform validate` pass for every module and environment.                                                                                  |
| AC-02 | **Checkov/tfsec** scan reports **zero** CRITICAL/HIGH findings (or each is documented + risk-accepted).                                                                 |
| AC-03 | `terraform plan` from an empty state proposes the full §7 footprint; a second `plan` on the applied state is **empty** (no drift).                                      |
| AC-04 | `aws rds describe-db-instances` shows a **Multi-AZ** PostgreSQL **17** primary **+ 2 read replicas**, each in a distinct AZ, all `StorageEncrypted=true` with the CMK.  |
| AC-05 | EKS worker nodes are present in **all 3 AZs**; the cluster API endpoint is **private**; IRSA OIDC provider exists.                                                      |
| AC-06 | ElastiCache Redis has **Multi-AZ automatic failover**, `TransitEncryptionEnabled=true`, `AtRestEncryptionEnabled=true`, nodes across 3 AZs.                             |
| AC-07 | MSK cluster has **3 brokers across 3 AZs**, encryption-in-transit = TLS, encryption-at-rest with the CMK; bootstrap-brokers-TLS endpoint resolves.                      |
| AC-08 | No data-plane service (RDS/Redis/MSK) is reachable from `0.0.0.0/0`; security groups allow only the EKS node/pod SG.                                                    |
| AC-09 | **AZ-failure drill:** forcing an RDS failover (or simulating loss of one AZ) keeps the writer endpoint serving within the RDS Multi-AZ RTO; Redis/MSK remain available. |
| AC-10 | The **same modules** build a `staging` environment from a different tfvars file with no module edits (G-04).                                                            |
| AC-11 | Every provisioned resource carries the mandatory tag set (`environment`, `owner`, `cost-center`, `managed-by=terraform`, `spec=SPEC-INFRA-001`).                        |
| AC-12 | No secret appears in `terraform output`, state, or CI logs in plaintext; DB/Redis/MSK credentials resolve from Secrets Manager.                                         |

## 13. Risks & Limitations

- **Single region.** `us-east-1` only — a full-region outage is not covered. Documented exit path:
  cross-region read-replica + Route53 failover (future ADR). Record as an explicit consequence,
  not a silent assumption.
- **Managed-service constraints.** RDS read replicas are asynchronous (replica lag under write
  bursts); MSK/ElastiCache patching windows can cause brief failovers — surface in runbooks.
- **Cost.** A 3-AZ managed footprint (RDS Multi-AZ + 2 replicas, MSK 3-broker, ElastiCache MAZ,
  EKS, NAT×3) is non-trivial; non-prod must be sized down and the envelope tracked (G-06/ADR-0020).
- **Stateful blue/green limits.** True immutability is straightforward for compute (node groups)
  but data stores are replaced via managed failover/restore, not recreate — document the
  reconcile path so "immutable" is honest for stateful tiers.
- **Apply blast radius.** A bad `apply` can affect production; mitigated by plan-in-PR + CAB gate +
  per-environment state isolation + targeted applies.

## 14. ADR & Dependency Impact

- **Reuses:** ADR-0003 (async/Kafka strategy), ADR-0018 (encryption at rest), ADR-0019 (Redis TLS
  - value encryption), ADR-0020 (FinOps cost allocation), ADR-0027 (ISO 27001 change management),
    ADR-0029 (DevSecOps pipeline security / IaC scanning).
- **Adds** (authored in Phase 5): `immutable-infrastructure-terraform` (the immutability
  discipline + replace-not-mutate policy), `aws-three-az-region-topology` (the VPC/subnet/AZ
  design), `terraform-remote-state-management` (S3+DynamoDB backend, isolation, locking),
  `managed-services-selection-rds-msk-elasticache` (managed vs self-hosted decision + exit paths).
- **Produces:** Terraform modules + environments under `infrastructure/terraform/`,
  `.terraform.lock.hcl` (pinned), a Checkov policy/baseline, module input/output docs, a
  resource-inventory/SBOM artifact, runbook stubs (RDS failover, AZ loss, state recovery), and
  `slo.yaml` entries for the platform golden signals.

## 15. Open Questions

<!-- Resolved at a HITL gate, not assumed. /deliver lists these as open-HITL items. -->

1. **Instance sizing & cost envelope** per environment (RDS class, EKS node types/counts, MSK
   broker type, Redis node type) — needs a cost/CAB decision before prod apply.
2. **MSK mode** — ZooKeeper vs **KRaft**, and provisioned vs **MSK Serverless** — which fits the
   throughput + cost profile?
3. **Backup/retention windows** (RDS PITR days, snapshot cadence, log retention) — compliance-driven.
4. **WAF on the ALB** — required for the internet-facing surface, or deferred?
5. **Multi-account strategy** — single account with environments by tag/VPC, or separate AWS
   accounts per environment (org/Control Tower)?
6. **Terraform execution** — Terraform Cloud / Atlantis / GitHub Actions OIDC role — which runs the
   gated `apply`?

## 16. References

- AWS Well-Architected Framework (Reliability, Security, Cost pillars); AWS Multi-AZ patterns for
  RDS, MSK, ElastiCache, EKS.
- HashiCorp Terraform — module composition, remote state (S3 + DynamoDB locking), provider/version
  pinning, immutable-infrastructure guidance.
- Repo: `infrastructure/terraform/` (existing tree), `specs/k8s/probe-strategy.md`,
  `specs/security/threat-model.md`, ADR-0003/0018/0019/0020/0027/0029, `docs/sre/slo/slo.yaml`.
