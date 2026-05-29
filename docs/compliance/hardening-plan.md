# Security & Resilience Hardening Plan

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-29
> **Reviewer role:** Senior Enterprise Architect
> **Maturity baseline:** CMMI Level 3–4 across most domains (see assessment below)

This plan translates the findings from the 2026-05-29 maturity assessment into a sequenced
delivery roadmap. Waves are ordered by **risk reduction per unit of effort**, not by ease.
Each wave closes specific REM-NNN items and maps to ISO 27001 / SOC 2 controls.

---

## Maturity Baseline (2026-05-29)

| Domain                  | Level           | Key finding                                                      |
| ----------------------- | --------------- | ---------------------------------------------------------------- |
| Secrets & SAST          | **4 — Managed** | detect-secrets + per-language SAST, all CI-blocking              |
| Supply Chain            | **4 — Managed** | SBOM+Cosign, Trivy, SHA-pinned actions, SLSA L2                  |
| Encryption              | **3 — Defined** | AES-256-GCM at rest, Redis TLS; key rotation still manual        |
| Input/Injection Defense | **4 — Managed** | Injection guard, PII filter, parameterized queries, sandbox      |
| AuthN/AuthZ             | **3 — Defined** | JWT + RBAC + audit identity; no MFA/OIDC, single-service model   |
| Container/K8s Hardening | **3 — Defined** | Non-root, distroless, securityContexts; no NetworkPolicy/mTLS    |
| Fault Tolerance         | **3 — Defined** | Circuit breakers + retries on LLM/DB; Kafka consumer edges weak  |
| Graceful Degradation    | **3–4**         | In-memory fallbacks well-wired with production guards            |
| **Idempotency / DLQ**   | **2 — Partial** | DLQ metric exists but no implementation; auto-commit risk        |
| Observability / SLO     | **4 — Managed** | OTel, golden signals, SLOs, error-budget policy, runbooks        |
| Governance / Compliance | **4 — Managed** | REM register, ISO matrix, blocking gates; CODEOWNERS placeholder |

**Weakest links:** the DLQ/offset-commit gap (silent message loss) and mTLS gap (plaintext lateral
traffic). These anchor the sequencing.

---

## Wave A — Critical: Runtime Integrity

**Target:** ≤ 1 sprint · **Branch pattern:** `security/REM-012-*`
**Goal:** eliminate silent failure modes on the critical request path.

### REM-012 — DLQ + Safe Kafka Offset Commit ✅ (this wave)

| Attribute    | Value                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------ |
| Severity     | **Critical**                                                                               |
| Risk         | Silent message loss OR infinite poison-message reprocessing                                |
| Root cause   | `enable_auto_commit=True` commits offset before processing completes; no retry or DLQ path |
| ISO controls | ISO 8.16 (monitoring), ISO 8.6 (capacity)                                                  |
| SOC 2        | CC7.2 (anomalous activity monitoring), CC9 (risk mitigation)                               |

**Changes:**

- Set `enable_auto_commit=False`; commit offset only after `_handle()` completes (success or DLQ)
- Add configurable retry loop inside `_handle()` with exponential backoff (`kafka_consumer_max_retries`)
- After exhausting retries, publish original envelope to `domain.request.dlq` topic, increment
  `DLQ_MESSAGES_COUNTER`, set request status to `failed`, then commit offset
- Register `domain.request.dlq` channel in AsyncAPI spec and `services.yaml`
- Update `RequestConsumer.__init__` to accept `broker: EventBrokerProtocol`
- Wire broker in `src/api/rest/main.py` lifespan
- New runbook: `docs/sre/runbooks/dlq-accumulating.md`
- Spec update: `specs/system/request-pipeline.md` (elevate DLQ from P5 to implemented)

**New config keys:**

```
kafka_dlq_topic = "domain.request.dlq"
kafka_consumer_max_retries = 3
kafka_consumer_retry_backoff_seconds = 1.0
```

### REM-013 — Consumer Heartbeat + Task-Hang Detection ✅ (this wave)

| Attribute    | Value                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------------ |
| Severity     | **Critical**                                                                                           |
| Risk         | A hung `async for` consumer fails silently — no liveness signal; pod appears healthy while queue grows |
| Root cause   | No metric updated by the consumer loop; runbooks reference an alert that doesn't exist                 |
| ISO controls | ISO 8.16 (event logging and monitoring)                                                                |
| SOC 2        | CC7.2 (anomalous activity), CC4.1 (continuous monitoring)                                              |

**Changes:**

- Add `CONSUMER_HEARTBEAT_TIMESTAMP` Gauge to `src/observability/metrics.py`
- Update gauge in `run()` after each committed message (epoch timestamp)
- Alert rule: `time() - consumer_heartbeat_timestamp_seconds > 300 AND kafka_consumer_lag > 0`
  fires only when there are queued messages AND the consumer hasn't committed in 5 minutes,
  avoiding false positives during genuine idle periods

---

## Wave B — High: Observability Closure

**Target:** ≤ 1 sprint · **Branch pattern:** `security/REM-014-*`
**Goal:** make SLOs and circuit breakers actually page someone.

### REM-014 — Prometheus Alerting Rules

| Attribute  | Value                                                                                                                 |
| ---------- | --------------------------------------------------------------------------------------------------------------------- |
| Severity   | **High**                                                                                                              |
| Risk       | SLO burn-rate alerts and circuit-breaker state exist only as runbook references; no actual Prometheus rule fires them |
| Root cause | No `*.rules.yml` files committed; `LLMTokenBudgetExceeded90Percent` not wired to PagerDuty                            |

**Changes:**

- Commit `infrastructure/prometheus/alerts.rules.yml` with rules for:
  - SLO burn-rate (fast 1h @14.4×, slow 6h @6.0×) per SLO tier
  - `ConsumerStale` (heartbeat + lag guard, from REM-013)
  - `CircuitBreakerOpen` gauge per client (LLM, DB) — requires adding `circuit_breaker_state` Gauge to `src/shared/retry.py`
  - `LLMTokenBudgetExceeded90Percent` wired to PagerDuty (closes REM-002)
- Add Prometheus rule file to `infrastructure/prometheus/` and reference in `docker-compose.yml`

### Closes REM-002 — LLM Token Budget Alert

Wired as part of REM-014 alerting rules. The 90% threshold gauge already exists
(`LLM_TOKEN_BUDGET`); only the alerting rule and notification channel are missing.

---

## Wave C — Medium: Network Trust Boundary

**Target:** ≤ 2 sprints · **Blocked on:** cloud/cluster infrastructure
**Goal:** close lateral-movement risk.

### REM-003 — mTLS + Kubernetes NetworkPolicies

| Attribute    | Value                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------ |
| Severity     | **Medium-High**                                                                                  |
| Risk         | Plaintext Kafka/internal pod traffic — eavesdropping and lateral movement after perimeter breach |
| ISO controls | ISO 5.14/8.20, SOC 2 CC6.7                                                                       |
| Blocker      | ADR-0007 (Service Mesh) is _Proposed_, not _Accepted_; needs real cluster                        |

**Changes:**

- Advance ADR-0007 from _Proposed_ to _Accepted_; select Istio or Linkerd
- Add default-deny `NetworkPolicy` manifests per namespace (`infrastructure/k8s/network-policies/`)
- Enable mTLS in mesh or implement app-level TLS for Kafka/Redis inter-service calls
- Add Trivy IaC/config scan (`--scanners config`) to `ci.yml` build job to catch missing
  `securityContext` regressions in Helm/K8s manifests

### REM-011 — SLSA L3: OIDC + Admission Verification (remainder of REM-007)

| Attribute | Value                                                                                    |
| --------- | ---------------------------------------------------------------------------------------- |
| Severity  | **Medium**                                                                               |
| Blocker   | Needs real cloud OIDC role + Kubernetes cluster with Kyverno/cosign admission controller |

**Changes (when infra is provisioned):**

- Replace long-lived `REGISTRY_USERNAME/PASSWORD` with OIDC workload identity
- Add Kyverno policy that rejects pods whose images lack a valid cosign attestation
- Replace `curl | sh` Syft/Cosign installs with pinned binary downloads

### REM-004 — Shift DAST Left

| Attribute     | Value                                                                              |
| ------------- | ---------------------------------------------------------------------------------- |
| Severity      | **Medium**                                                                         |
| Current state | OWASP ZAP runs only in `staging-check.yml`; not in CI against ephemeral test stack |

**Changes:**

- Add OWASP ZAP baseline scan job to `ci.yml`, running against the ephemeral test stack
  that is already up for integration tests

---

## Wave D — Medium: Governance Closure

**Target:** Before first enterprise engagement · **Blocked on:** named individuals
**Goal:** unblock ~22 "Partial" ISO controls.

### REM-009 — Real CODEOWNERS + DPO-Approved DPIA

| Attribute     | Value                                                                        |
| ------------- | ---------------------------------------------------------------------------- |
| Severity      | **High (enterprise gate)**                                                   |
| Current state | CODEOWNERS uses placeholder `@org/*` teams; DPIA is Draft                    |
| Impact        | ~22 ISO 27001 controls remain "Partial" — cannot be audited as "Implemented" |

**Changes:**

- Replace `@org/*` placeholders with real GitHub usernames/teams
- DPO reviews and signs off on `docs/privacy/dpia.md` (status: Draft → Approved)
- Once done: flip ~22 control-matrix rows from ⚠️ Partial to ✅ Implemented

---

## Wave E — Low: Operational Resilience Depth

**Target:** Ongoing backlog · **No blockers**

| Item                      | Description                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| Redis HA                  | Configure Redis Sentinel or Cluster; implement reconnection backoff on client startup           |
| Key-rotation job          | Automate `DB_ENCRYPTION_KEY` rotation (the `enc:v1:` versioned format supports it); add runbook |
| Per-user rate limiting    | Upgrade slowapi key function from per-IP to per-JWT-subject; add tenant-level quotas            |
| HITL queue overflow       | Define overflow policy beyond the hard `hitl_max_pending_requests=500` cap                      |
| HTTP security headers     | Add `SecurityHeadersMiddleware` with HSTS, CSP, X-Frame-Options, X-Content-Type-Options         |
| CodeQL / Semgrep          | Add to CI for deeper SAST coverage beyond Bandit                                                |
| DB pool saturation metric | Add `db_pool_acquired` / `db_pool_available` Gauges to `ResilientDBPool`                        |
| Container image digests   | Pin Python base image to a patch-level digest for reproducible builds                           |

---

## Delivery Conventions

Each wave is delivered as **one branch / one PR** following the existing SDD + PR governance gates:

- Branch name: `security/REM-NNN-<short-description>`
- PR title: `security(resilience): <description> (REM-NNN)`
- CHANGELOG updated under `[Unreleased]`
- Spec updated or written before code (SDD §2 step 1)
- REM register row moved from Open → Done in the same PR
- ISO control matrix rows flipped in the same PR

**Blocked items** (Waves C/D requiring cloud infra or named people) are tracked as open REM rows
and should be re-evaluated each quarter as the deployment environment matures.
