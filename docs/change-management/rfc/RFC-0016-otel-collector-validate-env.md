# RFC-0016 — Fix OTel Collector config validation (inject placeholder envs)

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead, SRE Lead
> **Related Issue:** #122 · **Related RFC:** RFC-0015 (surfaced it) · **Related ADR:** ADR-0043–0046 (OTel)
> **Change type:** Normal

---

## 1. Context

`.github/workflows/ci-otel-collector-lint.yml` → "Validate OTel Collector configuration" fails:

```
failed to get config: cannot resolve the configuration:
expanding ${env:PROMETHEUS_REMOTE_WRITE_TOKEN}: expected convertable to string value type, got <nil>
```

`infrastructure/monitoring/opentelemetry/otel-collector.yaml` references five `${env:...}` values
(`SERVICE_ENVIRONMENT`, `DEPLOYMENT_REGION`, `JAEGER_ENDPOINT`, `PROMETHEUS_REMOTE_WRITE_ENDPOINT`,
`PROMETHEUS_REMOTE_WRITE_TOKEN`) injected at deploy time. The validate step injects none, and
`otelcol-contrib:0.104.0` errors on an unset `${env}` (it does not treat missing as empty). This
is pre-existing; it surfaced when the workflow was re-triggered during RFC-0015.

Fixing the env resolution then revealed a **second, latent config bug** the lint had never been
able to reach: the `tail_sampling` processor declared `policies[0]` with `type: or` + an
`and_sub_policy` block — but **tail_sampling has no `or` policy type** (`otelcol validate`:
`'policies[0]' has invalid keys: or`). Top-level tail_sampling policies are already implicitly
**OR'd**, so the intended "sample error traces OR HITL-rejected decisions" was mis-modelled.

## 2. Decision

Two-part fix:

1. **Env resolution:** pass **non-secret placeholder** env vars to the `docker run … validate`
   step for all five refs, so otelcol resolves them and structurally validates the **real,
   unmodified** config. The config keeps its `${env:...}` refs **required at runtime** (no
   in-config defaults) on purpose — a missing secret (`PROMETHEUS_REMOTE_WRITE_TOKEN`) should
   **fail fast** in production rather than silently send an empty `Bearer`. Placeholders are
   validation-only and never leave CI.
2. **tail_sampling fix:** replace the invalid `or` policy with two top-level policies
   (`error-status` via `status_code`, `hitl-rejected` via `string_attribute`). Because top-level
   policies are OR'd, this preserves the original intent (sample either category at 100%) using a
   valid schema.

## 3. Alternatives Considered

| Option                                               | Pros                                                                 | Cons                                                                                                                             | Why rejected                 |
| ---------------------------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| A (proposed) — placeholder envs in the validate step | Validates the real config; keeps runtime fail-fast; no config change | Local `otelcol validate` still needs envs                                                                                        | —                            |
| B — in-config `${env:VAR:-default}` defaults         | Validates anywhere incl. local                                       | Empty default for the **secret token** trades prod fail-fast for a silent empty Bearer; empty endpoints can fail validate anyway | Weakens the runtime contract |
| C — leave `continue-on-error` and ignore             | No work                                                              | A real broken-config gate stays red/meaningless                                                                                  | Defeats the lint             |

## 4. Impact

| Area           | Impact                                                                                |
| -------------- | ------------------------------------------------------------------------------------- |
| CI             | "Validate OTel Collector configuration" goes green; the lint becomes meaningful again |
| Runtime / prod | None — config unchanged; envs still required at deploy time                           |
| Security       | None — placeholders are dummy, validation-only                                        |

## 5. Rollout / Rollback

Merge → the next run validates green. Rollback = revert the PR (CI-only, no state).

---

_Approved by:_ _(signatures go here after CAB review)_
