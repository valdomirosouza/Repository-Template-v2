# ADR-0063 — Brownfield Terraform reconciliation (extend existing modules, do not fork)

**Status:** Accepted
**Date:** 2026-06-09
**Authors:** Valdomiro Souza

---

## Context

SPEC-INFRA-001 targets the full AWS production platform (Aurora PostgreSQL, EKS, ALB/NLB,
ElastiCache, MSK) across 3 AZs via immutable Terraform. The Spec-as-PR review (finding H2) showed
the spec was written **greenfield against a brownfield repo**: `infrastructure/terraform/` already
ships `environments/{dev,staging,production}` and modules `networking`, `database`, `cache`,
`message-broker`, `kubernetes`, `observability`, `api-gateway`, `vector-db`, … Building the spec's
proposed new module names (`network`, `rds-postgres`, `eks`, `msk-kafka`, …) would have produced a
**parallel, conflicting tree**. Three concrete divergences exist against the target:

- `database` is a single `aws_db_instance` on **PostgreSQL 16.3** (target: Aurora 17 cluster, ADR-0062).
- `message-broker` authenticates with **SASL/SCRAM** (target: TLS-in-transit + **IAM** auth).
- No read members / cluster resources exist yet.

A reconciliation decision is needed so the spec **completes the existing IaC** rather than forking it.

## Decision

**Extend the existing modules in place; do not author a parallel tree.** The role labels in
SPEC-INFRA-001 §7/§8 map onto the existing module names (`network`→`networking`,
`rds-postgres`→`database`, `eks`→`kubernetes`, `elasticache-redis`→`cache`,
`msk-kafka`→`message-broker`). The three divergences are resolved as:

1. **`database` → Aurora PostgreSQL 17 cluster** (ADR-0062): rewrite from `aws_db_instance` to
   `aws_rds_cluster` + 3 `aws_rds_cluster_instance`. Because **data migration is a non-goal**
   (SPEC-INFRA-001 §3), provision **fresh at PG 17** — no in-place 16→17 major-version upgrade.
   **RDS/Aurora Blue/Green Deployments** is the documented runbook reserved for any _future_
   data-bearing cutover.
2. **`message-broker` SASL/SCRAM → IAM auth (SASL/IAM)**: drop the SCRAM secret +
   `aws_msk_scram_secret_association`; enable `client_authentication.sasl.iam`; bind **per-topic
   least-privilege IAM** to the EKS workloads' **IRSA** roles. TLS-in-transit is unchanged.
3. **State discipline:** any change that retains data is performed with **`terraform state mv`**,
   **never** destroy-recreate. Managed-service perpetual diffs are handled with a **reviewed**
   `lifecycle.ignore_changes` allow-list (SPEC-INFRA-001 AC-03), not a silently-growing one.

## Consequences

- **Positive:** one authoritative IaC tree (no fork); existing CI/Checkov/CODEOWNERS/governance
  continue to apply; the platform spec consolidates rather than duplicates.
- **Negative / effort:** the `database` module is a non-trivial rewrite (instance → cluster); MSK
  client configuration changes (SCRAM creds → IAM/IRSA) require coordinated app-side updates; a
  new `postgres17`-family / Aurora cluster parameter group replaces `postgres16`.
- **Risk:** module-name discipline must hold during implementation (reviewers reject any new
  `rds-postgres`/`eks`/`network` modules). Tracked in SPEC-INFRA-001 §1.5 / §13.

## Alternatives

- **Fork into a new parallel module set** (the as-written spec) — **rejected**: two trees, drift,
  duplicated governance, eventual reconciliation debt.
- **In-place PG 16→17 major upgrade** — rejected as unnecessary (no data to preserve, §3) and
  riskier than a fresh provision; retained only as the future data-bearing runbook.
- **Keep MSK SASL/SCRAM** (amend FR-06) — viable fallback, but IAM auth removes the shared secret
  and aligns with IRSA least-privilege (NFR-04), so SCRAM is demoted to fallback only.
- **MSK mTLS via ACM Private CA** — rejected (≈$400/mo CA + client-cert lifecycle overhead).

## References

- `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md` (§1.5 reconciliation; §15.7 decision; §3 non-goals)
- ADR-0062 (Aurora PostgreSQL — the `database` target this reconciles to)
- ADR-0027 (ISO-27001 change management — CAB-gated apply), ADR-0029 (DevSecOps/IaC scanning)
- `infrastructure/terraform/modules/{database,message-broker,networking,…}` (the existing tree)
