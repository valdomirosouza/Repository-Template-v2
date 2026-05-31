# Skill: OWASP Top 10 Enforcement

## Purpose

Ensure all API endpoints, authentication flows, and data handling paths address every
OWASP Top 10 control. Integrates with DAST (OWASP ZAP) in the staging pipeline.

## When to Activate

- Any new REST API endpoint implementation
- Any authentication or authorization change
- Any data handling or storage change
- Any dependency upgrade touching security-sensitive libraries
- Before every staging → production promotion

## Control Checklist

Run this checklist before every PR involving API endpoints, auth, or data handling.

### A01 — Broken Access Control

- [ ] Every endpoint validates resource ownership (user can only access their own resources).
- [ ] No IDOR: IDs are opaque UUIDs, not sequential integers exposed in URLs.
- [ ] RBAC enforced via middleware; roles defined in `specs/security/threat-model.md`.
- [ ] Directory traversal prevented; no user-controlled file paths.

### A02 — Cryptographic Failures

- [ ] TLS 1.2+ on all external endpoints; `rediss://` for Redis (ADR-0019).
- [ ] AES-256-GCM for data at rest (ADR-0018); no MD5 or SHA-1 anywhere.
- [ ] Secrets never in environment variables in plaintext — use secret manager references.
- [ ] JWT signed with RS256 (asymmetric); short expiry (≤ 15 min access token).

### A03 — Injection

- [ ] All DB queries use SQLAlchemy parameterized queries; no string concatenation.
- [ ] `prompt_injection_guard.py` active for all LLM calls.
- [ ] XML/JSON inputs validated against schema before processing.
- [ ] Shell commands use `subprocess` with argument lists, never `shell=True`.

### A04 — Insecure Design

- [ ] Threat model (`specs/security/threat-model.md`) reviewed for any new component.
- [ ] Rate limiting on all public endpoints (configured in `src/api/rest/middleware.py`).
- [ ] Fail-secure defaults: deny by default, allow by explicit rule.

### A05 — Security Misconfiguration

- [ ] Swagger UI disabled in production (`app_env != production` gate in `main.py`).
- [ ] No default credentials; `Settings.reject_placeholder_secrets` enforced.
- [ ] HTTP security headers present: HSTS, X-Frame-Options, CSP, X-Content-Type-Options.
- [ ] Trivy container scan: zero CRITICAL CVEs before promotion to staging.

### A06 — Vulnerable and Outdated Components

- [ ] OWASP dep-check (Java) / pip-audit (Python) / nancy (Go) in CI — zero CRITICAL findings.
- [ ] Base image pinned to digest (not tag) in Dockerfile.
- [ ] Dependency updates via Dependabot; auto-merge only for patch-level non-security.

### A07 — Identification and Authentication Failures

- [ ] JWT validation on every protected route; no bearer token bypass paths.
- [ ] Refresh token rotation on every use; single-use enforcement via Redis.
- [ ] Brute-force protection: account lockout after 5 failed attempts (configurable).
- [ ] MFA enforced for all production access (infra, secrets, deployment).

### A08 — Software and Data Integrity Failures

- [ ] Cosign-signed container images; signatures verified on every deploy (`cosign verify`).
- [ ] SBOM generated on every build (Syft CycloneDX); hash stored in change-log.
- [ ] CI pipeline uses pinned action versions (SHA-pinned, not tag-pinned).
- [ ] No `pickle.loads()` or `eval()` on untrusted input (enforced in CLAUDE.md §3.2).

### A09 — Security Logging and Monitoring Failures

- [ ] Every 4xx/5xx logged with: timestamp, `request_id`, endpoint, status_code, `user_id` (masked).
- [ ] No PII in logs (`pii_filter.py` enforced before every log write).
- [ ] Alert on anomalous error rates (`golden-signals.yaml` PrometheusRule).
- [ ] Audit log covers all authentication events and privileged actions.

### A10 — Server-Side Request Forgery (SSRF)

- [ ] No user-controlled URLs in server-side HTTP calls.
- [ ] Outbound allow-list enforced in network policy (`infrastructure/k8s/`).
- [ ] Internal metadata endpoints (169.254.169.254) blocked at network layer.

## DAST Integration (OWASP ZAP)

Full scan runs in `cd-staging.yml` as a blocking gate after smoke tests:

```yaml
- name: OWASP ZAP Full Scan
  uses: zaproxy/action-full-scan@v0.10.0
  with:
    target: "http://staging.internal/api"
    rules_file_name: ".zap/rules.tsv"
    cmd_options: "-I"
  env:
    ZAP_AUTH_HEADER: "Authorization"
    ZAP_AUTH_HEADER_VALUE: ${{ secrets.ZAP_API_TOKEN }}
```

ZAP scan reports archived in `docs/security/zap-reports/YYYY-MM-DD.html`.

## OWASP LLM Top 10 (AI Agents module)

When `src/agents/` is active, also verify — covered in full by `skills/ai/guardrails.md`:

| LLM Risk               | Control                                                | Location                     |
| ---------------------- | ------------------------------------------------------ | ---------------------------- |
| LLM01 Prompt Injection | `prompt_injection_guard.py` — never disable            | `src/guardrails/`            |
| LLM02 Insecure Output  | `sanitize_llm_output()` before render/execute          | `src/guardrails/`            |
| LLM06 Sensitive Info   | `pii_filter.py` before every LLM call                  | `src/guardrails/`            |
| LLM08 Excessive Agency | HITL gateway + feature flag autonomy levels            | `src/agents/hitl_gateway.py` |
| LLM09 Overreliance     | Evaluator validates output; risk score threshold ≥ 0.7 | `src/agents/harness/`        |
