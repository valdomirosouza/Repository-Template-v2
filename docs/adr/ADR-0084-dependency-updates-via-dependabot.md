# ADR-0084 — Dependency & Digest Updates via Dependabot (supersedes ADR-0074)

**Status:** Accepted
**Date:** 2026-06-17
**Authors:** Valdomiro Souza
**Supersedes:** [ADR-0074](ADR-0074-automated-dependency-digest-policy.md)
**Relates to:** [ADR-0029](ADR-0029-devsecops-pipeline-security.md) (DevSecOps / SCA), [ADR-0072](ADR-0072-versioned-security-control-matrices.md) (control matrices)

---

## Context

[ADR-0074](ADR-0074-automated-dependency-digest-policy.md) selected **Renovate** and rested on a
`renovate.json` "template default" — but that file was never added, and Renovate was never adopted.
The dependency-update tool that is actually implemented and operating is **Dependabot**
(`.github/dependabot.yml`), expanded by **RFC-0015** to cover all six ecosystems in the monorepo:
`pip`, `github-actions`, `npm`, `gomod`, `maven`, and `docker`. RFC-0015 explicitly kept Renovate
out of scope.

The 2026-06-16 ADR/RFC audit (#327) flagged the contradiction: an `Accepted` ADR mandates a tool
that does not run, while the running tool has no ratifying ADR. Carrying a decision that conflicts
with the operating reality is a governance liability — exactly the drift the audit exists to close.

## Decision

**Ratify Dependabot as the canonical dependency- and digest-update mechanism; supersede ADR-0074.**

1. **All six ecosystems** are managed via `.github/dependabot.yml` (verified present); minor/patch
   updates are grouped per ecosystem, majors stay individual for review (RFC-0015).
2. **Container base-image digest pinning** — the original ADR-0074 intent — is satisfied by
   Dependabot's `docker` ecosystem: pin base images by `@sha256:<digest>` and Dependabot raises PRs
   to bump the pinned digest, preserving reproducibility **and** patch currency.
3. **GitHub Actions SHA-pins** are kept current by Dependabot's `github-actions` ecosystem and
   enforced by `scripts/governance/check_action_pins.sh` (RFC-0015).
4. **Patch/minor auto-merge** for Dependabot PRs is handled per RFC-0020.
5. **No `renovate.json` is added.** ADR-0074 (Renovate) is superseded by this ADR.

## Consequences

### Positive

- The ADR record now matches the operating reality; no net-new tooling or migration.
- Dependabot is already integrated with the repo's auto-merge (RFC-0020) and pin gate (RFC-0015).

### Negative / Trade-offs

- Dependabot lacks some Renovate features (richer grouping, custom managers, dashboard). Accepted
  for current needs; a future ADR can revisit if those become necessary.

### Neutral

- The floating-vs-pinned base-image trade-off ADR-0074 raised is resolved in favour of **pinned
  digests with Dependabot-driven bumps**, getting both reproducibility and OS-patch currency.

## Alternatives Considered

- **Adopt Renovate (ADR-0074 as written)** — rejected: net-new churn and a migration off a working
  Dependabot setup, for no current functional gain. Reconsider only if a concrete Renovate-only
  capability is required.

## References

- `.github/dependabot.yml` · RFC-0015 (supply-chain hardening — Dependabot expansion) · RFC-0020
  (Dependabot patch/minor auto-merge)
- [ADR-0029](ADR-0029-devsecops-pipeline-security.md) · [ADR-0074](ADR-0074-automated-dependency-digest-policy.md) (superseded)
