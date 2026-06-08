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
| F8  | Stale `uv.lock`: `template-service` pinned at 2.10.2 while `pyproject`/`version.txt` are 2.12.2 — every `uv run` rewrites it   | Low      | dependency lockfile          | ✅ Fixed — [#138][138]  |
| F9  | `make lint-python` (ruff `src/ tests/`, no format-check) is narrower than CI (`ruff check .` + `ruff format --check .`)        | Low      | dev tooling / CI parity      | ✅ Fixed — [#141][141]  |
| F10 | Release PR blocked: version-sync step pushes with `GITHUB_TOKEN`, which de-triggers required CI checks (RFC-0014 regression)   | Medium   | release pipeline             | 📋 Filed — [#148][148]  |

[130]: https://github.com/valdomirosouza/Repository-Template-v2/issues/130
[131]: https://github.com/valdomirosouza/Repository-Template-v2/issues/131
[132]: https://github.com/valdomirosouza/Repository-Template-v2/issues/132
[133]: https://github.com/valdomirosouza/Repository-Template-v2/issues/133
[138]: https://github.com/valdomirosouza/Repository-Template-v2/issues/138
[141]: https://github.com/valdomirosouza/Repository-Template-v2/issues/141
[148]: https://github.com/valdomirosouza/Repository-Template-v2/issues/148

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

## F8 — stale `uv.lock` (FIXED) — [#138][138]

The committed `uv.lock` pinned the editable `template-service` package at **2.10.2** while
`pyproject.toml` / `version.txt` were at **2.12.2**. Any `uv run` / `uv sync` rewrote that line
back to 2.12.2, so the drift kept reappearing as a phantom diff that had to be reverted (twice
during #128 and #136). Likely cause: a prior version bump updated `version.txt` + `pyproject.toml`
but did not re-run `uv lock`.

**Fix.** Ran `uv lock` to refresh the lockfile — a one-line change (`template-service 2.10.2 ->
2.12.2`; all 135 packages otherwise unchanged) — so the lockfile matches the released version and
no longer drifts.

## F9 — `make lint-python` is narrower than CI (FIXED) — [#141][141]

Adding `make verify-f7-hook` (#140) tripped CI Lint twice even though `make lint-python` passed
locally. Root cause: `make lint-python` ran `ruff check src/ tests/` with **no** `ruff format
--check`, while the CI lint job runs `ruff check .` **and** `ruff format --check .` repo-wide. So
any Python outside `src/`/`tests/` (`.claude/`, `scripts/`, `scaffold/`) and any formatting drift
anywhere passed locally but failed CI — a round-trip trap only seen after pushing.

**Fix.** Aligned `make lint-python` with CI: `ruff check .` + `ruff format --check .` (mypy +
detect-secrets unchanged), and widened `make format-python` to `ruff format .` so the formatter
covers everything the checker checks. Local lint is now authoritative for the ruff gates.

## F10 — release PR de-triggered by the version-sync push (filed) — [#148][148]

Surfaced releasing 2.12.3 (#137 was un-mergeable, including by `--admin`). The release-please
PR's head was the **version-sync commit** authored by `github-actions[bot]`; because
`GITHUB_TOKEN` pushes do not trigger workflows, `ci.yml`'s `pull_request` checks never re-ran on
that head, so the branch ruleset reported "9 of 9 required status checks are expected" and refused
the merge. Same class as RFC-0014 (the `RELEASE_PLEASE_TOKEN` fix), re-introduced by the
`Sync version files` step in `release.yml` pushing with `GITHUB_TOKEN`.

**Workaround used this cycle:** close + reopen the PR (re-triggers CI as a real user) → wait for
green → `--admin` merge. Released 2.12.3 successfully.

**Proposed fix (tracked in [#148][148]):** push the version-sync commit with `RELEASE_PLEASE_TOKEN`
so it triggers CI; or fold the sync into the release-please commit; or make the version files
release-please-managed (`extra-files`).
