# ADR-0008 — Secrets Management

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead, Security Lead

---

## Context

The system handles secrets that must never appear in source code, container images,
or Kubernetes manifests:

- LLM API key (`LLM_API_KEY`)
- Database credentials (`DATABASE_URL`)
- JWT signing key (`SECRET_KEY`)
- Kafka SASL credentials
- Third-party integration tokens

CLAUDE.md rule 3.2 prohibits committing any secret. A secrets management system must
enforce this structurally, not by policy alone.

---

## Decision

Adopt **HashiCorp Vault** as the primary secrets store, with cloud-provider secret
managers (AWS Secrets Manager, GCP Secret Manager) as environment-specific fallbacks.

### Runtime secret injection

Secrets are injected at pod startup via the **Vault Agent Sidecar** (or Vault CSI driver
on managed Kubernetes). The application reads secrets from environment variables or
mounted files — never from Kubernetes Secrets directly.

### Development environments

Local development uses `.env` (gitignored, copied from `.env.example`).
`.env.example` contains only placeholder values — never real secrets.

### Secret rotation

- LLM API keys: rotate every 90 days via Vault's dynamic secrets engine
- Database credentials: rotate every 30 days via Vault database secrets engine
- JWT signing key: rotate every 180 days with a 24-hour overlap window for token validity

### Secret scanning

`detect-secrets` runs in `make lint` and as a pre-commit hook to catch accidental
secret commits before they reach the remote. Baseline: `.secrets.baseline`.

---

## Consequences

### Positive

- Application code never handles raw secret values — it reads from environment,
  which is populated by Vault Agent. No secrets in memory longer than needed.
- Vault audit log records every secret access — satisfies compliance audit requirements.
- Dynamic secrets (DB credentials) are short-lived — a compromised credential expires
  automatically without manual rotation.
- `.secrets.baseline` + pre-commit hook provides defence-in-depth against accidental commits.

### Negative / Trade-offs

- Vault adds a critical infrastructure dependency — must be HA-deployed (Vault cluster, not single node).
- Vault Agent sidecar adds latency to pod startup and consumes additional memory per pod.
- Teams must learn Vault policy language (HCL) for secret access control.

---

## Alternatives Considered

**Kubernetes Secrets only**
Rejected: base64-encoded, not encrypted at rest by default (requires additional etcd encryption config);
secrets visible in plain text to anyone with `kubectl get secret`; no audit log.

**Environment variables in CI/CD only**
Rejected: secrets baked into pipeline configuration are hard to rotate; no centralized audit;
not suitable for dynamic/short-lived credentials.

**AWS Parameter Store (SSM) only**
Rejected: cloud-vendor lock-in; no multi-cloud portability; less ergonomic dynamic secrets
compared to Vault's database secrets engine.
