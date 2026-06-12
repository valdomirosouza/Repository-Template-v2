# ADR-0074 — Automated Dependency & Digest Update Policy (Renovate)

**Status:** Accepted
**Date:** 2026-06-12
**Authors:** Valdomiro Souza
**Milestone:** v2.16.0 — Governance Enforcement Hardening (Track C)
**Relates to:** [ADR-0029](ADR-0029-devsecops-pipeline-security.md) (DevSecOps / SCA), [ADR-0072](ADR-0072-versioned-security-control-matrices.md) (control matrices)

---

## Context

The container `Dockerfile` intentionally uses a floating `python:3.13-slim` base to pick up OS
security patches, noting that digest pinning "should be done with a bot such as Renovate." That
trade-off — floating-for-patches vs digest-pinned-for-reproducibility — is real, but leaving the
resolution as _guidance_ means it is never actually done: the base image is unpinned, and there is
no automation raising controlled update PRs.

This week independently confirmed the cost of un-automated dependency hygiene: the Java services
were pinned to a stale Spring Boot (3.4.5) carrying 40+ CVEs (several CVSS 9.8) until a manual bump
— exactly the drift Renovate exists to prevent. A secure enterprise template should _demonstrate_
the bot-driven strategy, not merely recommend it.

## Decision

**Base images are pinned by digest; automation maintains digests and versions across ecosystems.**

1. **Renovate configuration** (`renovate.json`) manages: Docker base-image **digests**, GitHub
   Actions **SHAs**, and the Python / Java / Go / Node ecosystems.
2. **Digest-pinned bases:** `Dockerfile` `FROM` lines are pinned by digest; the floating-tag
   security-patch benefit is preserved by **Renovate raising update PRs** (pin + automated bump),
   not by an unpinned tag. Floating tags outside Renovate-managed PRs are prohibited.
3. **Update PRs run the full gate suite** (SCA, Trivy, tests) before merge — automation proposes,
   the gates + a human dispose.
4. **Version unification:** the same change resolves the pre-existing Python version drift (pin
   one — **3.13** — and align `pyproject.toml`, CI `python-version`, and `Dockerfile`), so the
   ecosystem speaks one version.

## Consequences

### Positive

- Reproducible, digest-pinned builds **and** timely patches — the bot dissolves the
  floating-vs-pinned trade-off instead of forcing a choice.
- Stale-dependency CVE tails (the Spring Boot 3.4.5 situation) are surfaced as routine update PRs
  rather than discovered during an incident or a manual audit.
- Action-SHA + ecosystem coverage complements the existing SHA-pinning gate and SLSA posture.

### Negative / Trade-offs

- Renovate raises PR volume; grouping + a sensible schedule (in `renovate.json`) keeps it
  manageable. Update PRs still pass through the full required-check suite (ADR-0071).

### Neutral

- Adopters supply their own Renovate/Mend app installation; the config is the template default.

## Alternatives Considered

- **Leave digest pinning as documented guidance** — rejected: it is the current state, and it
  produced the stale-Spring-Boot exposure.
- **Dependabot instead of Renovate** — acceptable; Renovate chosen for richer digest + grouping
  support. Either satisfies this ADR's intent; the config artifact differs.

## References

- `improvements-2026-06-12-2021.md` backlog P1 #8 · `reports/STRENGTHENING-PLAN.md` W3-1
- `governance-enforcement-hardening-v1.0.0.md` W3-T1 (ADR-0070-as-proposed → renumbered 0074)
- [ADR-0029](ADR-0029-devsecops-pipeline-security.md)
