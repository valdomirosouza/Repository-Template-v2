# RBAC Matrix

> **Owner:** Security Lead + Tech Lead · **Status:** Living standard · **Last updated:** 2026-06-14
> The single place that maps **roles → what they may approve, change, and run** across this repository
> and its runtime. It consolidates the access rules already scattered across CODEOWNERS, the file
> ownership table (CLAUDE.md §8), the persona ceilings (§9.1), and the autonomy levels (§0.1), so
> access control is reviewable in one artefact. Implements OWASP A01 (Broken Access Control) at the
> governance layer. This closes the P1 "RBAC matrix" item of the repository improvement plan (Wave 5).

## Scope

Two access planes, kept deliberately separate:

1. **Repository / change-control plane** — who may approve PRs and changes to governed paths. Enforced
   by `.github/CODEOWNERS` + branch protection (ADR-0071) + the `pr-governance` / `cab-check` gates.
2. **Runtime / agent plane** — what an actor or an autonomous agent may _do_ at run time. Enforced by
   `src/agents/hitl_gateway.py`, autonomy feature flags (`src/shared/feature_flags.py`), and persona
   ceilings (`.claude/personas/`).

A role's repository rights never imply runtime rights, and vice-versa.

## 1. Repository / change-control plane

Roles are GitHub teams referenced in `.github/CODEOWNERS` (replace `@your-org/*` placeholders before
first use). "Required approver" = path needs this team's review before merge.

| Governed path                                                           | Required approver(s)                           | Source of truth                   |
| ----------------------------------------------------------------------- | ---------------------------------------------- | --------------------------------- |
| `docs/adr/`                                                             | Tech Lead                                      | §8 — binding decisions            |
| `specs/`                                                                | Product Owner + Tech Lead                      | §8                                |
| `docs/privacy/`                                                         | DPO / Privacy team                             | §8                                |
| `docs/sre/`                                                             | SRE Lead                                       | §8                                |
| `.github/workflows/`                                                    | DevOps Lead                                    | §8                                |
| `src/guardrails/`                                                       | Security Lead (AI-Safety review)               | §8 — weakening guardrails blocked |
| `src/agents/hitl_gateway.py`, `src/agents/hitl_store.py`                | Security **and** AI Governance (dual approval) | §8, §14.1                         |
| `src/shared/feature_flags.py`, `infrastructure/feature-flags/`          | AI Governance Lead                             | §8, ADR-0015                      |
| `src/*`, `services/*`, `infrastructure/*` (financial paths, **if SOX**) | ≥ 2 approvers; author ≠ sole approver          | §10 — segregation of duties       |
| Production deploy (normal / emergency change)                           | CAB (`cab-check` job) + RFC_ID                 | §11, ADR-0027                     |

**Separation of duties:** for SOX-in-scope financial write paths, the code author must not be the sole
approver of their own PR (§10). Enforced by requiring ≥ 2 CODEOWNERS on the paths above.

## 2. Runtime / agent plane

The agent's authority is bounded by the **autonomy level** (feature-flag driven) and routed through
the **HITL gateway** for any real-world action. Evaluated `FULL > MEDIUM_RISK > LOW_RISK > TESTS_ONLY

> READ_ONLY > NONE`; default `NONE` (every action requires HITL).

| Autonomy level   | May act autonomously on                            | Still requires HITL                            | Flag / governance                                         |
| ---------------- | -------------------------------------------------- | ---------------------------------------------- | --------------------------------------------------------- |
| `NONE` (default) | nothing                                            | all real-world actions                         | —                                                         |
| `READ_ONLY`      | reads / queries                                    | any write or side-effect                       | —                                                         |
| `TESTS_ONLY`     | run tests in sandbox                               | code exec outside `sandbox_executor.py`        | ADR-0016                                                  |
| `LOW_RISK`       | low-risk actions below `hitl_risk_threshold` (0.4) | anything ≥ threshold                           | feature flag                                              |
| `MEDIUM_RISK`    | medium-risk actions                                | actions at risk ≥ 0.7 (human-review threshold) | feature flag                                              |
| `FULL` (HOTL)    | high-risk actions autonomously                     | — (human monitors, can override)               | `autonomous-mode` flag — **ADR-0015 governance sign-off** |

Invariants (CLAUDE.md §3.3, binding regardless of level):

- **All** agent actions with real-world effects route through `hitl_gateway.py`.
- Agent-generated code executes **only** in `src/agents/sandbox_executor.py` without explicit HITL.
- Agents never get permissions beyond `specs/ai/guardrails.md`; every action is audit-logged
  (`guardrails/audit_logger.py`, immutable).
- Enabling/modifying any autonomy flag is itself a governance event → escalate (§14.1).

## 3. Human personas (non-engineering operators)

Personas (`.claude/personas/`) restrict the default contract; they may only **narrow**, never grant
beyond `CLAUDE.md` (§9.1). Each declares `role`, `autonomy_ceiling`, `skills_to_load`,
`prohibited_paths`.

| Persona        | Autonomy ceiling | Prohibited paths (illustrative) | File                                 |
| -------------- | ---------------- | ------------------------------- | ------------------------------------ |
| Legal Reviewer | `LOW_RISK`       | code & infra paths              | `.claude/personas/legal-reviewer.md` |
| Ops Analyst    | `MEDIUM_RISK`    | guardrails, feature flags       | `.claude/personas/ops-analyst.md`    |

A persona's ceiling caps the runtime plane (§2) for that session even if a flag would otherwise allow
more. The persona's `prohibited_paths` cap the repository plane (§1).

## Review cadence

- **Quarterly access review** of privileged access to prod secrets and DB encryption keys (§10,
  `docs/sox/access-review.md` when SOX-applicable).
- Re-confirm CODEOWNERS teams exist and map to current staff each quarter.
- Any new role, persona, or autonomy flag is added here in the same PR that introduces it.

## Gaps & target state

- **No machine check** that this matrix matches CODEOWNERS yet. Target: a `scripts/governance/` check
  that fails CI when a governed path in §1 lacks a matching CODEOWNERS rule (sibling to
  `check_traceability.py`).
- **Placeholder teams.** CODEOWNERS ships with `@your-org/*` placeholders (Wave 1 / P0 #1); this
  matrix is only enforceable once they are replaced with real GitHub teams.

---

## Related

- `.github/CODEOWNERS` — repository-plane enforcement · ADR-0071 (branch protection as code)
- `src/shared/feature_flags.py` · `infrastructure/feature-flags/` — autonomy levels (ADR-0015)
- `src/agents/hitl_gateway.py` · `guardrails/audit_logger.py` · `specs/ai/guardrails.md`
- `.claude/personas/` — persona ceilings (§9.1)
- CLAUDE.md §3.2 (OWASP A01), §3.3 (AI governance), §8 (file ownership), §10 (SOX SoD), §14 (escalation)
