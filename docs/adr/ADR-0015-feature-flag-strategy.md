# ADR-0015 — Feature Flag Strategy

**Status:** Accepted
**Date:** 2026-05-25
**Authors:** Tech Lead
**Supersedes:** —
**Superseded by:** —

---

## Context

The system requires a mechanism to enable or disable behaviours at runtime without
a full deployment. The primary use case is controlling `autonomous-mode` — whether
agents act without human-in-the-loop approval (HITL) or require it. Secondary use
cases include gradual rollout of new agent capabilities and kill-switch controls.

Requirements:

- **Vendor-neutral**: avoid hard lock-in to a SaaS provider
- **Local provider**: flags must work without external API calls (dev, test, air-gapped envs)
- **Audit trail**: flag evaluations should be loggable
- **Swap-friendly**: replacing the evaluation backend must not require application code changes

---

## Decision

Use **OpenFeature** (CNCF standard SDK) with **flagd** as the local evaluation backend.

**Why OpenFeature:**

- CNCF-graduated project — long-term support and broad ecosystem
- Provider interface abstracts the backend; swapping to LaunchDarkly, Unleash, or any
  other vendor requires only a provider change, not application code changes
- Python SDK (`openfeature-sdk`) is stable and well-maintained

**Why flagd:**

- Lightweight Go binary — runs as a sidecar or k8s Deployment
- Reads flag definitions from YAML/JSON files mounted as ConfigMaps — no external DB
- Supports OpenFeature remote evaluation protocol (OFREP) over HTTP
- Zero SaaS dependency — flags are fully self-hosted

**Fallback behaviour:**
When flagd is unavailable (local dev, unit tests without a provider configured), the
application falls back to `settings.autonomous_mode_enabled` from `config.py`. This
ensures the application remains functional without flagd running.

---

## Consequences

### Positive

- Provider-neutral: migrate to LaunchDarkly, Unleash, or GrowthBook without touching
  `src/shared/feature_flags.py` or callers
- Flags are version-controlled YAML files — changes go through PR review
- `InMemoryProvider` enables full unit testing without network calls
- flagd can be upgraded independently of the application

### Negative

- Adds `openfeature-sdk` as a runtime dependency
- flagd sidecar adds operational overhead (container, ConfigMap mount, health check)
- Remote evaluation adds ~1 ms latency per flag check (mitigated by flagd caching)

### Neutral

- Flag definitions live in `infrastructure/feature-flags/flags/` and are mounted as
  ConfigMaps in the k8s Deployment; changes require a ConfigMap update (no pod restart)

---

## Alternatives Considered

| Alternative          | Reason rejected                                               |
| -------------------- | ------------------------------------------------------------- |
| LaunchDarkly SaaS    | Vendor lock-in; requires external API key and internet access |
| Unleash self-hosted  | Requires PostgreSQL; heavier than flagd for the current scope |
| GrowthBook           | Focused on A/B testing; overkill for kill-switch use case     |
| Config env vars only | No runtime toggle; requires pod restart for every change      |

---

## Implementation Reference

- `src/shared/feature_flags.py` — `is_autonomous_mode_enabled()` (legacy) and `get_autonomy_level()` (graduated)
- `infrastructure/feature-flags/flags/autonomous-mode.yaml` — legacy flag definition
- `infrastructure/feature-flags/flagd.yaml` — k8s Deployment + Service for flagd
- `tests/unit/shared/test_feature_flags.py` — tests using `InMemoryProvider`

---

## Revision — Granular Autonomy Levels (2026-05-26)

**Motivation:** The single `autonomous-mode` boolean proved too coarse — teams needed to
grant read-only or test-only autonomy without enabling full write/deploy autonomy.

**Change:** Added five graduated flags evaluated in priority order by `get_autonomy_level()`.
The legacy `autonomous-mode` flag and `is_autonomous_mode_enabled()` are preserved unchanged.

| Flag                          | Default  | Condition              | Effect                           |
| ----------------------------- | -------- | ---------------------- | -------------------------------- |
| `autonomous-mode-full`        | DISABLED | Any                    | No HITL — dual approval required |
| `autonomous-mode-medium-risk` | DISABLED | `risk_score ≤ 0.7`     | HOTL monitoring                  |
| `autonomous-mode-low-risk`    | DISABLED | `risk_score < 0.3`     | No HITL                          |
| `autonomous-mode-tests-only`  | DISABLED | Test action types      | No HITL for tests                |
| `autonomous-mode-read-only`   | DISABLED | Read-only action types | No HITL for reads                |

**Spec:** `specs/ai/autonomous-mode-levels.md`
**Governance:** Enabling any flag above `read-only` requires AI Governance Lead approval.
`full` additionally requires Security Lead approval (dual approval unchanged from original ADR).
