# Threat Model — STRIDE Analysis

**Status:** Approved | **Owner:** Security Lead | **Last updated:** 2026-05-28
**Method:** STRIDE | **Scope:** API Gateway + AI Agents Module
**ADR references:** ADR-0008 (Secrets), ADR-0011 (HITL), ADR-0012 (PII), ADR-0016 (Sandbox), ADR-0018 (DB Encryption), ADR-0019 (Redis TLS)

---

## System Boundary

```
Internet ──▶ Ingress (nginx, TLS) ──▶ FastAPI (rate-limited)
                                           │
                           ┌───────────────┼───────────────┐
                           ▼               ▼               ▼
                        PostgreSQL       Redis           Kafka
                        (encrypted)      (TLS, encrypted) (plaintext cluster-internal)
                                           │
                                     AgentOrchestrator
                                           │
                                     HITLGateway ──▶ Operator UI
                                           │
                                     SandboxExecutor (Docker, network=none)
                                           │
                                     LLM Provider (Anthropic API, external)
```

**Trust boundaries:** Internet ↔ Ingress; App pod ↔ Data layer; App pod ↔ LLM provider; Sandbox ↔ App pod.

---

## STRIDE Analysis

### S — Spoofing

| Threat                                                                            | Component            | Likelihood | Impact   | Controls                                                                                                                                         | Residual |
| --------------------------------------------------------------------------------- | -------------------- | ---------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| Unauthenticated API calls                                                         | FastAPI routers      | Medium     | High     | JWT bearer token (`SECRET_KEY`, HS256); `Settings.reject_placeholder_secrets` blocks deploy without real key                                     | Low      |
| Agent identity spoofing — a compromised agent claims a different `agent_id`       | `AgentOrchestrator`  | Low        | Medium   | `agent_id` is set at orchestrator init from trusted config; not user-controlled; audit log records every action against the declared id          | Low      |
| HITL operator impersonation — forged `decided_by` field in `/v1/hitl/{id}/decide` | `hitl.py` router     | Medium     | High     | JWT bearer auth + `hitl-operator` role; `approver_id` taken from token subject — not from request body; audit-logged (REM-001 ✅ Done, ADR-0048) | Low      |
| LLM provider impersonation                                                        | `AnthropicLLMClient` | Low        | Critical | TLS + official SDK; no custom CA; SDK validates Anthropic server cert                                                                            | Low      |

### T — Tampering

| Threat                                                                  | Component                      | Likelihood | Impact   | Controls                                                                                                    | Residual |
| ----------------------------------------------------------------------- | ------------------------------ | ---------- | -------- | ----------------------------------------------------------------------------------------------------------- | -------- |
| Prompt injection — user input overrides agent instructions              | `prompt_injection_guard.py`    | High       | High     | Structural detection + reject on match; SHA256 logged, raw input discarded; see `specs/ai/guardrails.md` §2 | Low      |
| Spec tampering — attacker modifies `specs/` to expand agent permissions | Git repository                 | Low        | Critical | CODEOWNERS + branch protection on `main`; CI validates spec paths exist (governance job)                    | Low      |
| Audit log tampering                                                     | `audit_logger.py` / PostgreSQL | Low        | Critical | Append-only storage; `AuditLogger` has no delete path; DB user has INSERT only on audit table               | Low      |
| Redis HITL payload tampering                                            | `HITLRedisStore`               | Low        | High     | AES-256-GCM encryption at rest (ADR-0019); TLS in transit; any bit-flip fails GCM authentication            | Low      |
| Sandbox escape — agent-generated code modifies host filesystem          | `sandbox_executor.py`          | Low        | Critical | Docker `network=none`, tmpfs volume, CPU/memory cap, stdout size limit; `docker-compose.sandbox.yml`        | Low      |

### R — Repudiation

| Threat                                | Component         | Likelihood | Impact | Controls                                                                                             | Residual |
| ------------------------------------- | ----------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------------- | -------- |
| Agent denies executing an action      | `audit_logger.py` | Low        | High   | Immutable audit trail with `agent_id`, `action_type`, timestamp, and `trace_id` on every action      | Low      |
| Operator denies HITL decision         | HITL gateway      | Low        | High   | `decided_by` + timestamp written to immutable audit log on every decision                            | Low      |
| No attribution for autonomous actions | Feedback loop     | Low        | Medium | `action_type` + `result` + `trace_id` on every Prometheus metric emission; full decision tree logged | Low      |

### I — Information Disclosure

| Threat                                                                   | Component                                   | Likelihood | Impact   | Controls                                                                                                                                                                                                                                       | Residual |
| ------------------------------------------------------------------------ | ------------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| PII sent to LLM provider                                                 | `pii_filter.py`                             | Medium     | Critical | Mandatory PII masking before every LLM call; `test_pii_leakage.py` enforces L1–L4 coverage; DPIA documents transfer basis                                                                                                                      | Low      |
| PII in log streams                                                       | `logger.py`                                 | Medium     | High     | `mask_dict()` called before every structured log write; ruff lint catches `print()` in `src/`                                                                                                                                                  | Low      |
| Secret exposure in error responses                                       | FastAPI exception handlers                  | Low        | High     | Exception handlers return opaque `error_code` only; stack traces suppressed in `app_env=production` (Swagger disabled)                                                                                                                         | Low      |
| LLM response contains training data from other users                     | Anthropic API                               | Low        | High     | DPA with Anthropic confirms no training on customer data; PII masked before prompt                                                                                                                                                             | Low      |
| Unencrypted DB columns                                                   | PostgreSQL                                  | Low        | Critical | L1/L2 columns use `EncryptedField` (AES-256-GCM, ADR-0018); `DB_ENCRYPTION_KEY` from Vault                                                                                                                                                     | Low      |
| SSRF — server-side request to cloud metadata / internal host (OWASP A10) | outbound HTTP boundary (`feedback_loop.py`) | Low        | Critical | `src/shared/url_allowlist.py` blocks non-http(s) schemes + metadata/link-local endpoints at every HTTP-client boundary, and enforces `settings.outbound_url_allowlist` when set; `check_outbound_urls.py` CI gate fails any unguarded boundary | Low      |

### D — Denial of Service

| Threat                                                         | Component           | Likelihood | Impact | Controls                                                                                                          | Residual |
| -------------------------------------------------------------- | ------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------- | -------- |
| Request flood overwhelming the API                             | FastAPI             | High       | Medium | `slowapi` rate limiter (60 req/min per IP); nginx `limit-rps: 20` at ingress; HPA scales on CPU                   | Low      |
| LLM API cost exhaustion                                        | `llm_client.py`     | Medium     | High   | Monthly token budget gauge; `LLMTokenBudgetExceeded90Percent` alert; circuit breaker after 5 consecutive failures | Medium   |
| Agent semaphore starvation — all slots occupied by slow agents | `asyncio.Semaphore` | Low        | Medium | Hard cap `max_concurrent_agents=20`; `AgentSemaphoreSaturation` alert at >10 waiting                              | Low      |
| Kafka consumer lag spiral                                      | `RequestConsumer`   | Low        | High   | `KafkaConsumerLagHigh` alert at 10k messages; DLQ routes unprocessable messages                                   | Low      |
| HITL store overflow                                            | `InMemoryHITLStore` | Low        | High   | `hitl_max_pending_requests=500` hard cap; Redis-backed in production                                              | Low      |

### E — Elevation of Privilege

| Threat                                              | Component                  | Likelihood | Impact   | Controls                                                                                                                           | Residual |
| --------------------------------------------------- | -------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Attacker enables FULL autonomy via feature flag API | `feature_flags.py` / flagd | Low        | Critical | `flagd` config stored in `infrastructure/feature-flags/`; changes require ADR-0015 governance sign-off; `CODEOWNERS` on flag files | Low      |
| Agent self-modifies its autonomy level              | `AgentOrchestrator`        | Low        | Critical | Autonomy level read from feature flags at runtime; not writable by agent; HITL gateway enforces level at every action              | Low      |
| Sandbox process escalates to host                   | `sandbox_executor.py`      | Very Low   | Critical | Docker `--user nonroot`, read-only root FS, `seccomp` default profile, `network=none`                                              | Low      |
| HITL decision forged to approve a rejected action   | `hitl_gateway.py`          | Low        | Critical | Decision is recorded in immutable audit log before execution; re-submission of same request ID is idempotent and re-audited        | Low      |

---

## Remediations Required Before Production

| ID      | Threat                           | Action                                                                                                          | Owner         | Priority |
| ------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------- | -------- |
| REM-001 | HITL operator impersonation      | ✅ **Done** — JWT bearer auth + `hitl-operator` role; `approver_id` from token subject (`src/api/rest/auth.py`) | Security Lead | ✅ Done  |
| REM-002 | LLM cost exhaustion              | Wire `LLMTokenBudgetExceeded90Percent` alert to PagerDuty                                                       | SRE Lead      | P1       |
| REM-003 | Kafka plaintext cluster-internal | Enable mTLS between pods (service mesh, ADR-0007)                                                               | DevOps Lead   | P1       |
| REM-004 | No DAST in CI pipeline           | Add OWASP ZAP or Nuclei scan to `ci.yml`                                                                        | DevSecOps     | P2       |

---

## Review Cadence

This threat model must be re-reviewed on:

- Any new external integration (new LLM provider, external API)
- Any change to the trust boundary (new endpoint, new data store)
- Annually as a standing review
