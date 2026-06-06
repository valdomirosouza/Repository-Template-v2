# ADR-0057 — Repository Hygiene: Version Single-Source-of-Truth, Reference Integrity & Generated Context Graph

**Status:** Accepted
**Date:** 2026-06-06
**Authors:** Valdomiro Souza

---

## Context

The directive (§6–§7) flagged three low-severity but compounding hygiene gaps that
create ambiguity for agents and contributors:

- **P2-1 — Ambiguous version references.** `version.txt` and `pyproject.toml` could
  drift, and user-facing docs (README) carried a hard-coded version (`2.4.0`) that
  lagged the real release (`2.6.0`). An agent reading the README would infer the
  wrong contract version.

- **P2-2 — Stale repository references.** Several user-facing files still pointed at
  `Repository-Template` (the pre-rename name) instead of `Repository-Template-v2`,
  producing broken badges, a broken "Use this template" command, and a wrong
  upstream remote in the customization guide.

- **P1-8 — No generated context graph.** Agents had to read many documents at
  session start to understand the repo. `src/agents/context_graph.py` is a _runtime
  session_ goal-graph — a different concern; there was no static repo-structure map.

## Decision

### P2-1 — Version single-source-of-truth + CI check

`version.txt` is authoritative. A new `scripts/check_version_consistency.py` (run by
`ci-version-check.yml` and `make check-version`) fails CI when:

- `pyproject.toml` `version` ≠ `version.txt`, or
- `README.md`'s `**Version:**` line ≠ `version.txt`.

`CLAUDE.md` carries an independent _behavioral-contract_ version and is deliberately
**not** coupled to the framework release version. The README version was corrected to
`2.6.0`.

### P2-2 — Reference integrity

Corrected stale `Repository-Template` → `Repository-Template-v2` in user-facing files
(README badges + "Use this template" command, CUSTOMISING upstream remote).
**Historical references are preserved**: CHANGELOG CI-run URLs and version-compare
links record events that occurred under the old name and are left untouched.

### P1-8 — Generated context graph

A new `scripts/generate_context_graph.py` (`make gen-context-graph`,
`ci-context-graph.yml`) emits `.agent/context-graph.json` — a compact
(`< 50 KB`) map for agent session bootstrap:

| Section     | Content                                                            |
| ----------- | ------------------------------------------------------------------ |
| `specs`     | each spec → implementation files that reference it (`Spec:` lines) |
| `adrs`      | ADR id/title → files affected (`ADR-NNNN` references)              |
| `skills`    | skill file → trigger domain                                        |
| `services`  | `services.yaml` entries (apis, topics)                             |
| `tools`     | tool catalog risk policy (risk, hitl, reversible, …)               |
| `features`  | per-feature lifecycle state (`docs/product/FEAT-*/state.yaml`)     |
| `checksums` | sha256 (truncated) of key governance files for drift detection     |

The mapping is **derived** from `Spec:`/`ADR:` references already present in source
docstrings, so it stays accurate without a separate registry. The artifact is
gitignored (it is derived, not source); CI regenerates it on relevant changes and
enforces the size budget.

## Consequences

### Positive

- One authoritative version; CI blocks drift between `version.txt`, `pyproject.toml`, and the README.
- Badges, the template-clone command, and the upstream remote resolve correctly.
- Agents bootstrap from a single ~21 KB JSON instead of reading dozens of files.
- The context graph's checksums let an agent detect when a governance file changed since the graph was generated.

### Negative / Trade-offs

- The version check is intentionally narrow (README + pyproject); it does not scan every doc for version-like strings (too noisy). Other docs may still drift, caught only by review.
- The context graph is regenerated, not committed — consumers must run `make gen-context-graph` (or pull the CI artifact) to get a fresh copy.
- The spec→impl mapping relies on `Spec:`/`ADR:` docstring conventions; a file that omits them won't be linked.

### Neutral

- `scripts/**` are exempted from the `T201` (print) lint rule — they are CLI tools whose output is `print`, consistent with the existing `scaffold/scaffold.py` exemption and the "no print() in src/" intent.
- CLAUDE.md's contract version remains independent by design.

## Alternatives Considered

**Reuse `src/agents/context_graph.py` for the bootstrap map:** Rejected — that class
models a _runtime session_ (goals, decisions, constraints), not repository structure.
Conflating them would overload one abstraction.

**Commit `.agent/context-graph.json`:** Rejected — a derived artifact in git would
churn on every relevant change and invite merge conflicts. Gitignored + CI-regenerated
keeps it fresh without noise.

**Auto-rewrite all `Repository-Template` references:** Rejected — historical CHANGELOG
links and CI-run URLs are accurate records of the past and must not be rewritten.

---

## References

- ADR-0041 — Context graph (runtime session)
- ADR-0030 — RTK / token efficiency (bootstrap context budget)
- `scripts/generate_context_graph.py`, `scripts/check_version_consistency.py`
- Directive: `Agentic-SDLC-Repository-Improvement-Directive.md` §6–§7 (P2-1, P2-2, P1-8)
- Issue: #47
