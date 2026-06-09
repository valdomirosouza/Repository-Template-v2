# ADR-0062 — Aurora PostgreSQL as the platform RDBMS (vs RDS Multi-AZ + read replicas)

**Status:** Accepted
**Date:** 2026-06-09
**Authors:** Valdomiro Souza

---

## Context

SPEC-INFRA-001 (AWS production platform, immutable Terraform IaC) requires a PostgreSQL 17
data tier that is **highly available across 3 AZs** and provides **read scaling**. The original
spec phrasing ("Multi-AZ primary + 2 read replicas across 3 AZs, writer survives AZ loss, readers
serve traffic") **conflated two different AWS mechanisms**, which the Spec-as-PR review flagged as a
correctness error (finding H1):

- **RDS Multi-AZ (instance)** maintains a hidden **synchronous standby** that is **auto-promoted**
  on primary failure (the writer endpoint follows it). The standby is **not readable**.
- **RDS read replicas** are **asynchronous**, are **not** auto-promoted, and promoting one is a
  manual, endpoint-changing operation. They scale reads; they are **not** an HA failover target.

So "Multi-AZ + 2 read replicas" delivers HA _and_ read-scaling only by treating two unrelated
features as one — and the acceptance criterion "forcing a failover keeps the writer serving" is
satisfied by the standby, **not** by the replicas. A model is needed where the read members are
_also_ failover targets, with low lag and stable endpoints.

The repo's existing `infrastructure/terraform/modules/database` is a single `aws_db_instance` on
PostgreSQL 16.3 with no replicas (see ADR-0063 for the brownfield reconciliation).

## Decision

Adopt **Amazon Aurora PostgreSQL 17** (cluster) as the platform RDBMS:

1. Provision an `aws_rds_cluster` + **3 `aws_rds_cluster_instance`** members (1 writer + 2 readers),
   one per AZ across the 3 us-east-1 AZs, over Aurora's **shared cluster storage**.
2. **Readers are first-class failover targets** — on writer failure Aurora auto-promotes a reader
   (~30 s) and the **cluster writer endpoint** follows it; applications read via the **cluster
   reader endpoint** (AWS load-balances across readers). This resolves H1 by construction: HA and
   read-scaling are the _same_ mechanism, with **sub-second `AuroraReplicaLag`**.
3. Storage encrypted with a customer-managed **KMS** key; **RDS-managed master password**
   (`manage_master_user_password`, never in Terraform state); automated backups + PITR; **Aurora
   I/O-Optimized** for steady workloads.
4. Cross-region DR (if ever needed) is **Aurora Global Database** — out of scope for SPEC-INFRA-001
   (single region), recorded as the documented exit path.

## Consequences

- **Positive:** native HA-with-readable-failover-targets; sub-second replica lag; clean
  reader/writer cluster endpoints that make the FR-10 app-deploy contract trivial; fast failover
  (~30 s); storage auto-scaling; backtrack/fast-clone available.
- **Negative / cost:** Aurora runs ~15–25 % above equivalent RDS instances plus I/O charges
  (mitigated by I/O-Optimized) — reflected in the SPEC-INFRA-001 §15.1 cost envelope. Aurora is
  **not byte-for-byte vanilla PostgreSQL** (rare extension/version gaps) and carries mild lock-in.
- **Migration:** the existing `database` module is rewritten from `aws_db_instance` to
  `aws_rds_cluster` + instances; since data migration is a non-goal (SPEC-INFRA-001 §3) this is a
  **fresh provision at PG 17**, not a live cutover (see ADR-0063).
- Drives FR-02, AC-04 (`describe-db-clusters`), AC-09 (`failover-db-cluster`), and the §10
  `AuroraReplicaLag` SLO in SPEC-INFRA-001.

## Alternatives

- **RDS Multi-AZ DB cluster** (1 writer + **2 readable standbys**, semi-sync) — vanilla PostgreSQL,
  readers _are_ failover targets, ~35 s failover. **Documented runner-up**: choose this if Aurora's
  cost or non-vanilla nature is a hard blocker. Rejected as primary because it is **rigid** (fixed
  instance classes r6gd/r5b/r6id, io1/io2 storage only, **capped at exactly 2 readers** — no further
  read scaling).
- **RDS Multi-AZ instance + N async read replicas** (the original spec model) — **rejected**: the
  H1 conflation; replicas are not failover targets and need manual promotion.
- **Self-managed PostgreSQL on EC2** — rejected (SPEC-INFRA-001 §3 non-goal; operational burden).

## References

- `specs/infrastructure/SPEC-INFRA-001-aws-platform-terraform.md` (§15.8 decision; FR-02; AC-04/09)
- ADR-0063 (brownfield Terraform reconciliation — the `database` module rewrite + state discipline)
- ADR-0018 (encryption at rest), ADR-0019 (TLS), ADR-0004 (observability stack)
- AWS docs: Aurora PostgreSQL, Aurora endpoints & failover, RDS Multi-AZ DB clusters
