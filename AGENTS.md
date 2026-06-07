# AGENTS.md — Instructions for AI Coding Agents

This file is the contract for AI coding agents (Claude Code, Copilot, Cursor, etc.)
working in this repository. It keeps agents from accidentally weakening governance,
leaking secrets, or bypassing CI gates. Claude Code users: `CLAUDE.md` is the deeper,
authoritative behavioural contract — read it too.

## 1. Repository orientation

This is a multi-language enterprise monorepo template (Python/FastAPI core; optional
Java, Go, Next.js services; opt-in AI agents). It practises **Spec-Driven Development
(SDD)**: no code without a referenced spec. Source-of-truth files:

- `CLAUDE.md` — behavioural contract · `services.yaml` — service catalog
- `version.txt` — canonical version (ADR-0057) · `docs/adr/` — binding decisions
- `specs/` — feature/system specs · `docs/process/WORKFLOW.md` — 15-phase lifecycle

## 2. Files that must not be edited casually

| File / directory                | Why                                                           |
| ------------------------------- | ------------------------------------------------------------- |
| `docs/adr/`                     | ADRs are decisions of record; append/supersede, never rewrite |
| `specs/`                        | Specs are reviewed before the code they describe              |
| `src/guardrails/`               | Weakening guardrails requires AI Safety review                |
| `src/agents/hitl_gateway.py`    | HITL controls require ADR amendment (dual approval)           |
| `.github/workflows/`            | Pipeline changes require an RFC                               |
| `CLAUDE.md`                     | Behavioural contract — changes need team sign-off             |
| `infrastructure/feature-flags/` | Flag/autonomy changes need governance approval (ADR-0015)     |

## 3. Required workflow before code changes

1. Read the linked spec before writing any implementation.
2. Check whether an ADR already covers the decision; if not, propose one.
3. Run `make doctor` before starting.
4. Run `make lint-python` and `make test-unit-python` before pushing.
5. Reference the spec in every module docstring you write.

**Task sizing — the 2-skill budget (ADR-0060).** Every task loads **at most 2 repo
skills** (`skills/<domain>/<name>.md`). Treat that budget as the _test_ for whether a task
is atomic: list the skills the task needs to finish — if it would need a 3rd, the task is
too big, so **split it at the skill boundary** instead of loading more. One task = one
reviewable artifact; declare bindings under `## Skills — load before executing`.
`CLAUDE.md` and repo context are ambient and never count. Full rule: CLAUDE.md §4.

## 4. How to choose a setup profile

Pick the smallest tier that fits and see `SETUP.md`: `make setup-minimal` (no Docker —
deps + unit tests), `make setup-core` (PostgreSQL + Redis + observability), or
`make setup-full` (full enterprise stack). Then `make smoke`.

## 5. What AI agents must never do

- Do not commit or log real secrets, tokens, or PII.
- Do not set `HITL_ENABLED=false` or `autonomous-mode=on` without an explicit user
  instruction and a governance sign-off reference.
- Do not modify `src/guardrails/` without an AI Safety review comment in the PR.
- Do not add `--no-verify` to git commands.
- Do not weaken SAST rules or add `# nosec` / `# noqa` suppressions without justification.
- Do not remove or alter existing ADRs — mark superseded ones as `Superseded`.
- Do not write code that references a spec that does not exist yet.

## 6. How to update ADRs

ADRs are **append-only**. Create a new ADR for a new decision. To change a past
decision, add a new ADR and mark the old one `Status: Superseded by ADR-NNNN` — never
edit the original rationale. Add every new ADR to `docs/adr/README.md`.

## 7. Validation commands (run before pushing)

```bash
make doctor
make lint-python
make test-unit-python
make check-placeholders
```

See also: [`CLAUDE.md`](CLAUDE.md) · [`SETUP.md`](SETUP.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/troubleshooting.md`](docs/troubleshooting.md)
