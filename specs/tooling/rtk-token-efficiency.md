# Spec: RTK Token Efficiency Integration

**Spec ID:** RTK-001  
**Version:** 1.0.0  
**Date:** 2026-05-31  
**Status:** Accepted  
**Author:** Valdomiro Souza  
**ADR:** ADR-0030

---

## 1. Problem Statement

Claude Code sessions in this monorepo consume 80,000–120,000 tokens per 30-minute session.
Primary sources of token bloat:

- `pytest` / `make test-*` → ~8,000 tokens raw per run (4–6x/session)
- `git status` / `git diff` → ~3,000 tokens raw (10–15x/session)
- `docker compose ps` / `docker ps` → ~900 tokens (5x/session)
- `ruff check` / `make lint-*` → ~3,000 tokens (3x/session)
- `cat` on large files → up to 40,000 tokens (20x/session)

This compresses useful context out of the window, increases latency, and raises API cost.

## 2. Solution

Integrate **RTK (Rust Token Killer)** — a CLI proxy (https://github.com/rtk-ai/rtk,
54.7k ⭐) that intercepts bash command output before it reaches the LLM context window.

RTK applies four strategies:

1. Smart filtering — removes boilerplate, ANSI codes, progress bars
2. Grouping — aggregates similar items (files by dir, errors by type)
3. Truncation — keeps signal, cuts repetition
4. Deduplication — collapses repeated log lines with counts

Integration point: Claude Code `PreToolUse` bash hook (via `rtk init -g`), which
transparently rewrites bash tool calls before Claude ever sees the output.

## 3. Scope

### In scope

- Developer tooling only — not a build dependency, not in Dockerfile or CI
- Project-level filter config (`.rtk/filters.toml`) for monorepo-specific tools
- Three-skill token-efficiency skill group (`skills/token-efficiency/`)
- CLAUDE.md §13 behavioral contract enforcing RTK usage
- ADR-0030 documenting the decision

### Out of scope

- CI/CD pipeline changes
- Docker image changes
- Any production code path

## 4. Token Savings Estimate

| Command pattern                   | Frequency/session | Raw tokens   | With RTK    | Saved     |
| --------------------------------- | ----------------- | ------------ | ----------- | --------- |
| `pytest` / `make test-python`     | 4–6×              | ~8,000       | ~800        | −90%      |
| `git status` / `git diff`         | 10–15×            | ~3,000       | ~600        | −80%      |
| `docker compose ps`               | 5×                | ~900         | ~180        | −80%      |
| `ruff check` / `make lint-python` | 3×                | ~3,000       | ~600        | −80%      |
| `ls` / `tree`                     | 10×               | ~2,000       | ~400        | −80%      |
| `kubectl` / `helm`                | 5×                | ~2,000       | ~400        | −80%      |
| `cat` (large files)               | 20×               | ~40,000      | ~12,000     | −70%      |
| **Session total**                 |                   | **~120,000** | **~25,000** | **~−79%** |

## 5. Custom Filters Required

RTK built-in filters do not natively cover this monorepo's tools. `.rtk/filters.toml`
adds project-specific filters for:

| Tool / Target                  | Coverage                    |
| ------------------------------ | --------------------------- |
| `make setup` / `make infra-*`  | Strip Docker/uv boilerplate |
| `make lint-*` / `make test-*`  | Violations only             |
| `alembic upgrade head`         | Target + errors only        |
| `trivy image`                  | CRITICAL/HIGH only          |
| `helm upgrade` / `helm diff`   | Changes + errors only       |
| `terraform plan` / `tofu plan` | Resource changes only       |
| `uv sync` / `uv install`       | Adds/removes only           |
| `pre-commit`                   | Failed hooks only           |
| `syft` / `cosign`              | One-line result             |

## 6. Skills Delivered

| Skill file                                       | Purpose                                 |
| ------------------------------------------------ | --------------------------------------- |
| `skills/token-efficiency/rtk-setup.md`           | One-time install per developer machine  |
| `skills/token-efficiency/rtk-commands.md`        | Command reference map for this monorepo |
| `skills/token-efficiency/rtk-context-hygiene.md` | Session discipline rules                |

## 7. Acceptance Criteria

- [ ] `skills/token-efficiency/` directory contains all three skill files
- [ ] `.rtk/filters.toml` present in repo root and parseable by RTK
- [ ] CLAUDE.md contains §13 Token Efficiency Rules
- [ ] Skill Activation Table in CLAUDE.md §4 contains three token-efficiency rows
- [ ] ADR-0030 created and accepted
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] After `rtk init -g` + restart: `rtk gain` shows > 0% savings within one session

## 8. References

- RTK repository: https://github.com/rtk-ai/rtk
- RTK documentation: https://www.rtk-ai.app/guide
- ADR-0030: `docs/adr/ADR-0030-rtk-token-efficiency.md`
