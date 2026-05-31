# ADR-0030: RTK Token Efficiency Integration

**Status:** Accepted
**Date:** 2026-05-31
**Author:** Valdomiro Souza
**Spec:** RTK-001 (`specs/tooling/rtk-token-efficiency.md`)

---

## Context

Claude Code sessions in this monorepo were consuming 80,000–120,000 tokens per
30-minute session due to verbose output from pytest, git, docker, ruff, and make targets.
This adds latency and cost, and compresses useful context out of the context window.

RTK (Rust Token Killer, https://github.com/rtk-ai/rtk, 54.7k ⭐) is a CLI proxy that
filters command output before it reaches the LLM, saving 60–90% of tokens on common
dev commands via a transparent `PreToolUse` hook in Claude Code.

The existing ADR sequence (ADR-0026–ADR-0029) covers SOX, ISO 27001, DORA, and
DevSecOps pipeline security. This ADR governs the developer-tooling decision only.

---

## Decision

- Install RTK as a **developer tool only** — not a build dependency, not in Dockerfile,
  not in CI pipelines.
- Add `.rtk/filters.toml` at the repo root with project-specific filters for make,
  alembic, trivy, helm, terraform, uv, pre-commit, cosign, and syft.
- Add `skills/token-efficiency/` skill group (3 skills) as the usage contract for
  Claude Code operators working in this repository.
- Add §13 Token Efficiency Rules to `CLAUDE.md` as an inviolable behavioral contract
  for every Claude Code session.

---

## Consequences

**Positive:**

- Estimated 60–80% reduction in tokens per session (~120k → ~25k tokens/30 min).
- Shorter Claude Code response latency — smaller context window = faster inference.
- Lower API cost per session with no change to developer workflow.
- RTK tee mode saves full unfiltered output on failure; no information is lost.

**Neutral:**

- Requires one-time per-developer install (`brew install rtk && rtk init -g`).
  Not enforced in CI — purely opt-in per machine.
- `rtk discover --since 7` should be run weekly to surface commands with 0% savings
  that need new entries in `.rtk/filters.toml`.

**Risk:**

- RTK `PreToolUse` hook applies to Bash tool calls only. Claude Code built-in tools
  (Read, Grep, Glob) bypass it. Mitigated by CLAUDE.md §13.3 which mandates preferring
  shell equivalents for large files and codebase searches.

---

## Alternatives Considered

| Alternative                   | Reason rejected                                          |
| ----------------------------- | -------------------------------------------------------- |
| Manual prompt discipline only | Not enforceable — no behavioral contract for Claude Code |
| Context window summarization  | Reactive, loses information already consumed             |
| Smaller model for tool calls  | Degrades quality; RTK preserves full model quality       |

---

## References

- RTK repository: https://github.com/rtk-ai/rtk
- RTK documentation: https://www.rtk-ai.app/guide
- Spec: `specs/tooling/rtk-token-efficiency.md`
- Skills: `skills/token-efficiency/`
- Filter config: `.rtk/filters.toml`
