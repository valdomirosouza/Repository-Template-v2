# Orphan Files and Folders Analysis

> **Type:** Report-only (no files moved or deleted by this document). **Issue:** #61
> **Date:** 2026-06-06 · **Scope:** full repository at the `main` tip after v2.10.0

## Executive Summary

The repository is in good governance health. A full scan surfaced **no tracked junk
artifacts** (no committed caches, `.bak`/`.old`/`.orig`, `.DS_Store`) and confirmed that
all `scripts/`, workflows, and infrastructure files are referenced and used. The only
genuine cleanup items are a small set of **stray prompt artifacts** in the repo root, one
**misplaced structure doc**, and a block of **dead Makefile targets** orphaned by the
v2.10.0 Reusability Uplift (Wave 6). None of the cleanup is urgent; all of it is low risk.

Per the controlling prompt's safety constraints, **this document recommends only** — the
actual moves and the dead-code removal are proposed as a **separate follow-up PR after
human review** (see _Suggested Pull Request Plan_).

## Methodology

For each candidate, we checked whether it is referenced by README, SETUP, CUSTOMISING,
CLAUDE, AGENTS, the Makefile, CI/CD workflows, Dockerfiles/compose, `pyproject.toml`,
`services.yaml`, k8s/monitoring configs, scripts, tests, docs, specs, and ADRs (via
`git grep` / `git ls-files`). An automated fan-out scan was run and then **independently
verified** — three of its findings were false positives and are corrected below. We
prefer conservative classifications when uncertain.

## Repository Areas Inspected

Root-level files · `docs/` (149 markdown files) · `src/` · `tests/` · `scripts/` (11) ·
`.github/workflows/` (26) · `.github/PULL_REQUEST_TEMPLATE/` · `infrastructure/` ·
`scaffold/` · `services/` · `specs/` · `docs/adr/` · `docs/quickstart/` · `.claude/` ·
Docker/devcontainer · Makefile · `services.yaml` · `mkdocs.yml`.

## Findings by Category

### Keep but Document

| Path                       | Type | Evidence                                                                                                                                                | Risk | Recommendation    | Reason                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MONOREPO-STRUCTURE-EN.md` | File | Referenced only by `CHANGELOG.md` (history) and `docs/change-management/README.md`; **not** in README or `mkdocs.yml` nav; 1071 lines, dated 2026-05-29 | Low  | Keep but Document | A comprehensive "ideal template structure" reference, but misplaced at root with an all-caps `-EN` name and almost no inbound links. Either link it from README as the canonical template-structure reference or move it under `docs/` (e.g. `docs/template-structure.md`) and update the 2 references. Distinct from `docs/repo-structure.md` (the short mkdocs Home for _this_ instance) — **not** a duplicate. |

### Move to deprecated/

| Path                                | Type | Evidence                                                            | Risk | Recommendation                                   | Reason                                                                                                            |
| ----------------------------------- | ---- | ------------------------------------------------------------------- | ---- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `claude-code-improvement-prompt.md` | File | Gitignored; in repo root; referenced only by `CHANGELOG.md` history | Low  | Move to `deprecated/`                            | Consumed prompt artifact from an earlier session; same class as the 12 prompts already archived to `deprecated/`. |
| `rtk-token-efficiency-prompt.md`    | File | Gitignored; in repo root; referenced only by `CHANGELOG.md` history | Low  | Move to `deprecated/`                            | Consumed prompt artifact (RTK setup); already implemented (ADR-0030, `.rtk/`).                                    |
| `scan.md`                           | File | Untracked; the input prompt for this very analysis                  | Low  | Move to `deprecated/` (after this report merges) | Consumed prompt; preserve for provenance like the others.                                                         |

### Delete Candidates

| Path                                                                                                                     | Type             | Evidence                                                                                                                                                                                                         | Risk       | Recommendation   | Reason                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Makefile` targets `_scaffold-python-$(NAME)`, `_scaffold-java-$(NAME)`, `_scaffold-go-$(NAME)`, `_scaffold-k8s-$(NAME)` | Makefile recipes | `git grep "_scaffold-"` shows **only their own definitions** — nothing invokes them. `new-service` was repointed to `scripts/new-service.sh` (which calls `scaffold/scaffold.py`) in the v2.10.0 uplift (Wave 6) | Low-Medium | Delete Candidate | Dead code. They also carry stale values (`go 1.23`, `com/yourorg`) that contradict the current toolchain (Go 1.24) and would mislead anyone who revived them. Remove the recipe block; the live path is `scripts/new-service.sh` → `scaffold/scaffold.py`. |

### Keep (no action — incl. corrections to the automated scan)

| Path                                                 | Type    | Evidence                                                                                                                                      | Risk | Recommendation | Reason                                                                                                                                                                                   |
| ---------------------------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/asdd_state.py`                              | File    | Referenced by **all 16** `.claude/agents/*.md` files and `tests/unit/process/test_asdd_state.py`                                              | Low  | **Keep**       | The automated scan flagged this as a delete-candidate ("zero references") — **false positive**. It is the shared-state store for the Agentic Spec-Driven Delivery agent system (v2.9.0). |
| `docs/repo-structure.md`                             | File    | `mkdocs.yml` nav "Home"                                                                                                                       | Low  | Keep           | Active. Not a duplicate of `MONOREPO-STRUCTURE-EN.md`.                                                                                                                                   |
| `docker-compose.sandbox.yml`                         | File    | Referenced by CUSTOMISING, ADR-0016, `specs/security/*`, `specs/ethics/*`                                                                     | Low  | Keep           | Agent sandbox-execution stack (active, governed).                                                                                                                                        |
| `scripts/*` (other 10)                               | Files   | All referenced by Makefile / CI workflows (`check_llm_budget`→`ci-model-contract.yml`, `generate_context_graph`→`ci-context-graph.yml`, etc.) | Low  | Keep           | All wired in.                                                                                                                                                                            |
| `docs/**` not in `mkdocs.yml` nav (~majority of 149) | Files   | mkdocs lists a curated nav; omitted docs are INFO-level (build passes `--strict`) and are cross-linked from other docs                        | Low  | Keep           | Intentional nav curation, not orphaning. Adding every reference doc to the nav is a stylistic choice, not a fix.                                                                         |
| `docs/security/zap-reports/`, `.claude/memory/`      | Folders | Documented placeholders (DAST output / agent memory), gitignored content                                                                      | Low  | Keep           | Intentional.                                                                                                                                                                             |
| `deprecated/`                                        | Folder  | Gitignored local archive created this session                                                                                                 | Low  | Keep           | Intentional archive.                                                                                                                                                                     |

## High-Risk Items Requiring Human Review

**None.** No high-risk items were found. All recommendations are Low / Low-Medium risk
and reversible (moves preserve files; the Makefile block is dead code with no callers).

## Recommended Deprecated Folder Structure

The existing `deprecated/` (flat, gitignored) already holds 12 archived prompts. For the
three additions, keep the flat layout (they are all root-level prompt artifacts):

```text
deprecated/
├── README.md                          # (new) provenance index — see below
├── claude-code-improvement-prompt.md  # ← moved from repo root
├── rtk-token-efficiency-prompt.md     # ← moved from repo root
├── scan.md                            # ← moved from repo root
└── … (12 previously-archived prompts)
```

Add `deprecated/README.md` recording, per item: original path, reason, date, replacement
(if any), and whether it is safe to delete later.

## Suggested Pull Request Plan

1. **PR 1 — report only (this document).** Adds `docs/repository-maintenance/orphan-files-analysis.md`. No file moves. _(This PR.)_
2. **PR 2 — controlled cleanup (after human review).**
   - Move `claude-code-improvement-prompt.md`, `rtk-token-efficiency-prompt.md`, `scan.md` → `deprecated/`.
   - Add `deprecated/README.md` provenance index.
   - Remove the dead `_scaffold-python/java/go/k8s-$(NAME)` Makefile recipes.
   - Decide `MONOREPO-STRUCTURE-EN.md`: link from README **or** move to `docs/template-structure.md` (+ update 2 references).

## Validation Checklist

- [x] No tracked cache/junk artifacts (`__pycache__`, `*.pyc`, `.DS_Store`, `*.bak/.old/.orig`).
- [x] Every `scripts/` file is referenced by Makefile/CI/docs.
- [x] Every `.github/workflows/*` is triggered/used; README CI references reconciled (v2.10.0).
- [x] `_scaffold-*` Makefile targets confirmed dead (no callers).
- [x] `asdd_state.py` confirmed in active use (corrects automated false positive).
- [x] `MONOREPO-STRUCTURE-EN.md` vs `docs/repo-structure.md` confirmed **not** duplicates.
- [x] PR 2 moves applied (approved 2026-06-06): 3 prompts archived to `deprecated/` + `deprecated/README.md` provenance index; dead `_scaffold-*` Makefile recipes removed; `MONOREPO-STRUCTURE-EN.md` → `docs/template-structure.md` (references + mkdocs nav updated).

## Final Recommendation

Proceed with **PR 2** (the low-risk cleanup above) after review. No deletions of
content occur — the prompt artifacts are archived to `deprecated/`, and only dead,
caller-less Makefile recipes are removed. Everything else is correctly placed and used.
