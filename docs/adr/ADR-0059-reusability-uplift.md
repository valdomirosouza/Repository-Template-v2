# ADR-0059 — Reusability Uplift (progressive adoption UX)

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

---

## Context

An engineering review (`reusability-uplift-v2.0.0.md`) found adoption friction that made
the template hard to pick up despite its enterprise depth: 8+ manual setup steps,
mandatory full stack (incl. Kafka) on first run, CI blockers on day zero, contradictory
toolchain versions across configs, an ambiguous LLM key variable, no automated upstream
sync, and no explicit instructions for AI coding agents.

The goal is **progressive adoption** — simple for a solo developer on day one, still fully
mature for a regulated team on day ninety — **without weakening** governance, security,
privacy, observability, AI safety, HITL/HOTL, SDD, ADR practice, or DevSecOps gates.

## Decision

Implement the uplift as nineteen improvements, grouped as:

- **Init automation:** `make template-init` (idempotent placeholder/version/.env init),
  `scripts/check-template-placeholders.sh`, the CI `setup_status` gate, and the
  `template-init.yml` first-push workflow.
- **Progressive profiles:** `docker-compose` `profiles:` + `make setup-minimal`/
  `setup-core`/`setup-full`, `make smoke`, and `COMPOSE_PROJECT_NAME`/port isolation.
- **Toolchain hygiene:** runtime version alignment (Python 3.13 / Java 21 / Go 1.24 /
  Node 22) + `make check-versions`, and `LLM_API_KEY` canonicalisation behind
  `AI_AGENTS_ENABLED`.
- **Self-service tooling:** `make doctor`, `make new-service … REGISTER=true`,
  `docs/troubleshooting.md`, and CI workflow/README reconciliation.
- **Governance & DX:** split PR templates, `AGENTS.md`, the `template-sync.yml` workflow,
  the README restructure, and this ADR.

### Reconciliations with the existing repository

The recommendation predated several merged ADRs; where it conflicted, the existing
controls win (per the recommendation's own "do not weaken governance / ADR practice"
constraint):

1. **`version.txt` is kept** (the recommendation said delete it). ADR-0057 already made
   `version.txt` the single source of truth, enforced by `ci-version-check.yml`. The
   "single version source" goal is therefore already met; deletion would break the gate
   and the release process. We added the requested `make version` UX target instead, and
   `template-init` resets the version in `version.txt` **and** `pyproject.toml` + README.
2. **CI is not fragmented.** `ci-frontend.yml`/`ci-go.yml`/`ci-java.yml` already exist;
   Python and AI-safety gates live in the green monolithic `ci.yml`. We reconciled the
   README CI table to reality and added `paths:` filters rather than splitting a working
   pipeline.
3. **The uplift ADR is ADR-0059, not ADR-0031** — ADR-0031 is already taken
   (agent-onboarding-protocol).
4. **CI `setup_status` detects initialisation from the repo** (presence of placeholders),
   because `.env` is gitignored and never present in CI, so the recommendation's
   `grep SETUP_COMPLETE .env` could not work there.
5. **Template workflows use `gh`** (not `peter-evans/create-pull-request`) to match the
   repo's gh-based, SHA-pinned convention, and are guarded to never run on the source
   template.

## Consequences

**Positive:** much lower time-to-first-success; no Docker required for the minimal tier;
fresh "Use this template" clones don't fail CI on day zero; consistent toolchain; safe
multi-instance local dev; AI agents have explicit guardrails; upstream changes flow via
reviewable PRs.

**Negative / maintenance:** the init and sync scripts/workflows are new surfaces to
maintain; `template-sync` may open occasional false-positive PRs; `make setup` now
defaults to the lighter core profile (the original full-stack behaviour is `setup-full`).

## Implementation (file manifest)

- Scripts: `scripts/check-versions.sh`, `check-template-placeholders.sh`, `doctor.sh`,
  `smoke.sh`, `template-init.sh`, `new-service.sh`.
- Workflows: `.github/workflows/template-init.yml`, `template-sync.yml`; `ci.yml` setup gate.
- Compose/env: `docker-compose.yml` profiles + port params; `.env.example` AI/LLM,
  `PROFILE`, `COMPOSE_PROJECT_NAME`, port overrides.
- Docs: `AGENTS.md`, `docs/troubleshooting.md`, `scaffold/README.md`,
  `.github/PULL_REQUEST_TEMPLATE/*`, README restructure, SETUP/CUSTOMISING/CONTRIBUTING
  updates, this ADR.
- Makefile: `check-versions`, `check-placeholders`, `doctor`, `version`, `template-init`/
  `init`, `setup-minimal`/`setup-core`/`setup-observability`/`setup-full`,
  `infra-down-core`/`infra-down-full`, `smoke`, enhanced `new-service`.

**Supersedes / extends:** none. Complements ADR-0057 (version SoT) and ADR-0002 (stack).
