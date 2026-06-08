# `/deliver` dry-run findings & follow-ups

Findings surfaced while validating the two-mode (`dry-run` | `code`) `/deliver` skill against
`specs/system/SPEC-LGS-001-log-based-golden-signals.md` on 2026-06-08 (full 15-phase DRY-RUN).
This is a living list — check items off as they are fixed or filed as issues.

| ID  | Finding                                                                                                                        | Severity | Owner area                   | Status                  |
| --- | ------------------------------------------------------------------------------------------------------------------------------ | -------- | ---------------------------- | ----------------------- |
| F1  | DRY-RUN validation targets mutate **tracked** files                                                                            | Medium   | `/deliver` skill             | ✅ Fixed in this change |
| F2  | DoR checklist count drift: gate says "8 criteria", `DEFINITION_OF_READY.md` lists 13                                           | Low      | `phase-gates.yaml` / process | 📋 Filed — [#130][130]  |
| F3  | Phase-14 gate references `smoke-test.yml` which doesn't exist as a standalone workflow                                         | Low      | `phase-gates.yaml` id=14     | 📋 Filed — [#131][131]  |
| F4  | Phase-6 gate requires a manual `CHANGELOG [Unreleased]` edit, contradicting release-please ownership (RFC-0012)                | Low      | `phase-gates.yaml` id=6      | 📋 Filed — [#132][132]  |
| F5  | Local supply-chain tooling absent (`trivy`/`checkov`/`bandit`/`pip-audit`/`syft`/`cosign`) — Phase 9 SAST/SCA/SBOM are CI-only | Info     | environment                  | ⬜ Expected / no action |
| F6  | `make sbom`/`make doctor`/`make smoke` need infra (`syft`, Docker, `.env`) — Phase 9/11 evidence partial locally               | Info     | environment                  | ⬜ Expected / no action |
| F7  | `/deliver` + `phase-executor` grant unscoped `Bash`; push/merge/deploy/flag prohibitions are prose-only, not tool-enforced     | Medium   | skill/agent permissions      | 📋 Filed — [#133][133]  |

[130]: https://github.com/valdomirosouza/Repository-Template-v2/issues/130
[131]: https://github.com/valdomirosouza/Repository-Template-v2/issues/131
[132]: https://github.com/valdomirosouza/Repository-Template-v2/issues/132
[133]: https://github.com/valdomirosouza/Repository-Template-v2/issues/133

## F1 — DRY-RUN validation targets mutate tracked files (FIXED)

**What happened.** Running the repo's own validation targets as dry-run evidence had tracked-tree
side effects, violating the DRY-RUN "no real side-effects" invariant:

- `make lint-python` → `detect-secrets scan --baseline .secrets.baseline` rewrites the baseline's
  `generated_at` timestamp even when no secrets change.
- `make test-unit-python` / `make lint-python` → `uv run` auto-corrected pre-existing `uv.lock`
  drift (`template-service` `2.10.2` → `2.12.2`) on first invocation.

Both were tracked files; the run left the working tree dirty until the orchestrator restored them.

**Fix (this change).** The DRY-RUN contract in `.claude/skills/deliver/SKILL.md` and
`.claude/agents/phase-executor.md` now requires **snapshot-and-restore of the tracked tree around
validation**: capture `git status --porcelain` before phase execution, and after the run revert
**only the delta** — tracked files that were clean at baseline but were dirtied by the run — with
`git checkout -- <path>` (plus removing new untracked artefacts written outside the sandbox).
Pre-existing dirty files and the gitignored `reports/<SLUG>/` sandbox are never touched. This makes
DRY-RUN provably side-effect-free on the tracked tree.

## F2–F4 — `phase-gates.yaml` / process drift (filed follow-ups)

These are pre-existing inconsistencies in the gate definitions, **out of scope** for the skill
change (no scope creep — CLAUDE.md §3.4). Each is a small, independent fix, now tracked as its own
issue:

- **F2** ([#130][130]) — reconcile the "8 criteria" wording in `phase-gates.yaml` id=3
  `exit_criteria` with the 13 bullets now in `docs/process/DEFINITION_OF_READY.md` (or update the
  DoR doc).
- **F3** ([#131][131]) — fix the `ci_checks: [smoke-test.yml]` reference in `phase-gates.yaml`
  id=14; the smoke check is `make smoke` / a job in `ci.yml`, not a standalone `smoke-test.yml`
  workflow.
- **F4** ([#132][132]) — Phase-6 `required_artifacts: [CHANGELOG.md]` (manual `[Unreleased]`)
  contradicts release-please ownership (RFC-0012; the manual CHANGELOG gate was removed from
  pr-governance). Update id=6 to reflect that conventional-commit titles, not manual edits, drive
  the changelog.

## F5–F6 — environment gaps (informational)

Expected when running locally without the full stack / CI tooling. The affected phases (9, 11)
correctly recorded these as evidence gaps rather than failing the phase. No action required; they
are asserted by CI (`ci.yml` `test-security`, `trivy`, `checkov`; `cd-staging` ZAP).

## F7 — Bash grant is unscoped (defence-in-depth follow-up) — [#133][133]

Surfaced by the code-review of the two-mode change. Both `.claude/skills/deliver/SKILL.md` and
`.claude/agents/phase-executor.md` declare an unscoped `Bash`/`Write`/`Edit` tool set. The
critical invariants — never autonomously `git push`/merge/tag/release/deploy or change a flag —
are enforced **only by prose instruction**, not at the tool-permission layer. CODE mode (which
writes the real tree) widens the blast radius of the same grant, so a single instruction-following
lapse or spec/output-borne prompt injection could issue `git push` or a deploy with nothing below
the model to stop it.

**Out of scope for this change** (a prose edit can't fix a permission gap). Proper fix is
defence-in-depth at the harness layer — e.g. a `PreToolUse` hook or a `settings.json` deny-rule
blocking `git push`, `gh pr merge`, `helm upgrade`, `make deploy-*`, and feature-flag writes
during a `/deliver` run. Tracked in [#133][133]; candidate for an `update-config` change.
