# RFC-0003 — Exclude governance/contract artifacts from auto-merge eligibility

> **Status:** Under Review
> **Date:** 2026-06-07
> **Author(s):** @valdomirosouza
> **Reviewers:** DevOps Lead (owner of `.github/workflows/`), Tech Lead
> **Related Issue:** #77
> **Related Spec:** `specs/compliance/iso27001-change-management.md`
> **Related RFC:** RFC-0001, RFC-0002 (auto-merge behaviour)
> **Change type:** Normal

---

## 1. Context

The `auto-merge` workflow (`.github/workflows/auto-merge.yml`, REM-005) auto-approves and
merges PRs it classifies as docs-only. Its eligibility check matches `docs/*|*.md|*.markdown`.

That glob also matches **governance and contract artifacts** which AGENTS.md §2 says require
team sign-off:

- `CLAUDE.md` — the authoritative behavioral contract (changes need team sign-off).
- `AGENTS.md` — the cross-tool agent contract.
- `docs/adr/**` — Architecture Decision Records, binding decisions of record (append-only,
  AGENTS.md §6).

This was observed in PR #76, where a `CLAUDE.md` §4 change auto-merged as "low-risk docs."
The change was authorized, but the workflow should not _classify_ contract/decision changes
as routine — that conflates "is a Markdown file" with "is low-risk."

## 2. Proposed Change

In the eligibility `case` in `.github/workflows/auto-merge.yml`, add a governance-sensitive
pattern **ahead of** the docs glob so it takes precedence, and mark those PRs ineligible:

```yaml
case "$f" in
  CLAUDE.md|AGENTS.md|docs/adr/*)       # governance/contract — never auto-merge (RFC-0003)
    echo "::notice::Governance/contract change requires human review: $f"; ineligible=1 ;;
  docs/*|*.md|*.markdown) ;;            # ordinary documentation
  *) echo "::notice::Non-docs change requires review: $f"; ineligible=1 ;;
esac
```

Effect: a PR touching any of these paths is **not auto-merge eligible** and waits for explicit
human review. Ordinary docs (guides, runbooks, READMEs other than the contracts, RFCs) still
auto-merge. No change to merge method (RFC-0002) or branch preservation (RFC-0001).

## 3. Alternatives Considered

| Option                                                         | Pros                                                           | Cons                                                       | Why rejected                       |
| -------------------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------- |
| A (proposed) — exclude `CLAUDE.md`, `AGENTS.md`, `docs/adr/**` | Contract + decisions always reviewed; ordinary docs still fast | Slightly more manual merges for ADRs                       | —                                  |
| B — exclude only `CLAUDE.md` + `AGENTS.md`                     | Minimal friction                                               | ADRs (binding decisions) would still auto-merge unreviewed | Decisions of record deserve review |
| C — exclude nothing (status quo)                               | Simplest                                                       | Behavioral contract auto-merges as routine docs            | Conflicts with AGENTS.md §2        |
| D — disable auto-merge entirely                                | No misclassification                                           | Loses fast-path for genuine docs                           | Throws out the benefit             |

## 4. Impact Assessment

| Area            | Impact   | Notes                                                               |
| --------------- | -------- | ------------------------------------------------------------------- |
| API contracts   | None     | CI-only change                                                      |
| Database schema | None     | —                                                                   |
| PII / Privacy   | None     | —                                                                   |
| Security        | Positive | Contract/decision changes can no longer merge without human review  |
| Performance     | None     | —                                                                   |
| Observability   | None     | —                                                                   |
| Feature flags   | None     | —                                                                   |
| Developer flow  | Minor    | ADR/contract PRs require a human approval; ordinary docs unaffected |

## 5. Rollout Plan

1. Merge this PR to `main` after DevOps Lead approval (this PR itself touches `.github/workflows/`, so it is already non-eligible and requires human review — the desired behaviour, demonstrated on itself).
2. No deploy step — Actions uses the updated workflow on the next eligible PR.
3. Smoke test: open a trivial `CLAUDE.md` (or `docs/adr/`) docs PR and confirm auto-merge logs `Governance/contract change requires human review` and does **not** auto-approve; confirm an ordinary docs PR still auto-merges.

## 6. Rollback Plan

Revert this PR — restores the prior eligibility globs. No data or irreversible state involved.

## 7. Timeline

| Milestone               | Target date        |
| ----------------------- | ------------------ |
| RFC approved            | 2026-06-07         |
| Implementation complete | 2026-06-07         |
| Staging deploy          | n/a (CI workflow)  |
| Production deploy       | on merge to `main` |

## 8. Open Questions

- [ ] Should other contract-like paths (e.g. `.github/CODEOWNERS`, `specs/**`) also be excluded? `specs/**` is non-`.md`-only and already requires review via the non-docs branch; CODEOWNERS is non-docs. Out of scope for now.

---

_Approved by:_ _(signatures go here after CAB review)_
