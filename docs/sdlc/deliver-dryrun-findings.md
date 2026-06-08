# `/deliver` dry-run findings & follow-ups

Findings surfaced while validating the two-mode (`dry-run` | `code`) `/deliver` skill against
`specs/system/SPEC-LGS-001-log-based-golden-signals.md` on 2026-06-08 (full 15-phase DRY-RUN).
This is a living list — check items off as they are fixed or filed as issues.

| ID  | Finding                                                                                                                        | Severity | Owner area                   | Status                  |
| --- | ------------------------------------------------------------------------------------------------------------------------------ | -------- | ---------------------------- | ----------------------- |
| F1  | DRY-RUN validation targets mutate **tracked** files                                                                            | Medium   | `/deliver` skill             | ✅ Fixed in this change |
| F2  | DoR checklist count drift: gate says "8 criteria", `DEFINITION_OF_READY.md` lists 13                                           | Low      | `phase-gates.yaml` / process | ✅ Fixed — [#130][130]  |
| F3  | Phase-14 gate references `smoke-test.yml` which doesn't exist as a standalone workflow                                         | Low      | `phase-gates.yaml` id=14     | ✅ Fixed — [#131][131]  |
| F4  | Phase-6 gate requires a manual `CHANGELOG [Unreleased]` edit, contradicting release-please ownership (RFC-0012)                | Low      | `phase-gates.yaml` id=6      | ✅ Fixed — [#132][132]  |
| F5  | Local supply-chain tooling absent (`trivy`/`checkov`/`bandit`/`pip-audit`/`syft`/`cosign`) — Phase 9 SAST/SCA/SBOM are CI-only | Info     | environment                  | ⬜ Expected / no action |
| F6  | `make sbom`/`make doctor`/`make smoke` need infra (`syft`, Docker, `.env`) — Phase 9/11 evidence partial locally               | Info     | environment                  | ⬜ Expected / no action |
| F7  | `/deliver` + `phase-executor` grant unscoped `Bash`; push/merge/deploy/flag prohibitions are prose-only, not tool-enforced     | Medium   | skill/agent permissions      | ✅ Fixed — [#133][133]  |

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

## F2–F4 — `phase-gates.yaml` / process drift (FIXED)

These were pre-existing inconsistencies in the gate definitions, **out of scope** for the original
skill change but fixed in a dedicated follow-up. Each was corrected in both the machine-readable
`docs/process/gates/phase-gates.yaml` and its human-readable projection `docs/process/WORKFLOW.md`
(the header mandates the two stay in sync):

- **F2** ([#130][130]) — `phase-gates.yaml` id=3 `exit_criteria` and `WORKFLOW.md` no longer
  hard-code a criteria count (the DoR doc actually has 13, not 8); both now reference
  "all checklist criteria in `docs/process/DEFINITION_OF_READY.md`" so the count can't drift again.
- **F3** ([#131][131]) — id=14 `ci_checks` and `WORKFLOW.md` no longer reference the non-existent
  `smoke-test.yml` (nor `harness/smoke-test.yml`); they now point at the real post-deploy smoke:
  the `cd-staging.yml` smoke-test step → `infrastructure/scripts/deploy/smoke-test.sh`.
- **F4** ([#132][132]) — id=6 no longer requires a manual `CHANGELOG.md [Unreleased]` artifact
  (it is `[]` with a note that release-please generates the changelog from the Conventional-Commit
  PR title, RFC-0012); the matching `WORKFLOW.md` development step was reworded to match.

## F5–F6 — environment gaps (informational)

Expected when running locally without the full stack / CI tooling. The affected phases (9, 11)
correctly recorded these as evidence gaps rather than failing the phase. No action required; they
are asserted by CI (`ci.yml` `test-security`, `trivy`, `checkov`; `cd-staging` ZAP).

## F7 — Bash grant is unscoped (FIXED — harness hook) — [#133][133]

Surfaced by the code-review of the two-mode change. Both `.claude/skills/deliver/SKILL.md` and
`.claude/agents/phase-executor.md` declare an unscoped `Bash`/`Write`/`Edit` tool set. The
critical invariants — never autonomously `git push`/merge/tag/release/deploy or change a flag —
were enforced **only by prose instruction**, not at the tool-permission layer. CODE mode (which
writes the real tree) widens the blast radius of the same grant, so a single instruction-following
lapse or spec/output-borne prompt injection could issue `git push` or a deploy with nothing below
the model to stop it.

**Fix.** A `PreToolUse` guard — [`.claude/hooks/high-risk-action-guard.py`](../../.claude/hooks/high-risk-action-guard.py),
wired in `.claude/settings.json` and documented in `.claude/hooks/README.md` — now enforces this
at the harness layer for both `Bash` and `Edit`/`Write` tool calls:

- **Subagent context** (`agent_type` set, e.g. `phase-executor`) → **`deny`**: autonomous delivery
  runs are hard-blocked from `git push`, `gh pr merge`, `gh release create`,
  `helm upgrade|install|rollback`, `kubectl apply|delete|rollout`, `make deploy*`, `make rollback`,
  feature-flag writes, and edits to governance-controlled paths (`src/guardrails/`,
  `hitl_gateway.py`/`hitl_store.py`, `feature_flags.py`, `infrastructure/feature-flags/`).
- **Main session** → **`ask`**: the human confirms the high-risk action once.
- Safe / read-only commands defer to normal rules; the guard fails open on any parse error.

This makes the "stop at every human gate" guarantee real, not just instructed.
