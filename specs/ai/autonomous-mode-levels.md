# Spec: Granular Autonomy Levels

**ID:** SPEC-autonomous-mode-levels
**Status:** Accepted
**Version:** 1.0.0
**Date:** 2026-05-26
**Authors:** Tech Lead, AI Governance Lead
**ADR:** ADR-0015-feature-flag-strategy.md (revision)
**GitHub Issue:** required before merge

---

## 1. Problem

The existing `autonomous-mode` flag is binary: either all agent actions bypass HITL
or none do. This is too coarse — a developer may safely grant read-only autonomy
without wanting to enable full write/deploy autonomy. Risk tolerance varies by
action type and risk score, not by a single global toggle.

---

## 2. Solution

Replace the single boolean flag with **five graduated autonomy levels**, evaluated in
order from most to least permissive. Each level is an independent OpenFeature flag.
The `get_autonomy_level(action_type, risk_score)` function evaluates all enabled flags
and returns the highest applicable level for that combination.

The existing `autonomous-mode` flag and `is_autonomous_mode_enabled()` are preserved
for backward compatibility.

---

## 3. Autonomy Levels

| Level         | Flag                          | Condition                         | HITL Behaviour                                    |
| ------------- | ----------------------------- | --------------------------------- | ------------------------------------------------- |
| `FULL`        | `autonomous-mode-full`        | Any action, any risk              | No HITL (requires governance approval — ADR-0015) |
| `MEDIUM_RISK` | `autonomous-mode-medium-risk` | `risk_score ≤ 0.7`                | HOTL (monitor, no block)                          |
| `LOW_RISK`    | `autonomous-mode-low-risk`    | `risk_score < 0.3`                | No HITL                                           |
| `TESTS_ONLY`  | `autonomous-mode-tests-only`  | `action_type` ∈ test actions      | No HITL for test generation/execution             |
| `READ_ONLY`   | `autonomous-mode-read-only`   | `action_type` ∈ read-only actions | No HITL for read-only operations                  |
| `NONE`        | —                             | Default (all flags disabled)      | HITL required for all actions                     |

**Evaluation order:** FULL → MEDIUM_RISK → LOW_RISK → TESTS_ONLY → READ_ONLY → NONE.
First matching enabled level wins.

---

## 4. Action type sets

### Read-only actions (eligible for READ_ONLY level)

`read_file`, `search_code`, `list_files`, `get_status`, `read_spec`, `read_adr`

### Test actions (eligible for TESTS_ONLY level)

`generate_test`, `run_test`, `check_coverage`, `lint_check`

These sets are extended by adding entries to `settings.autonomy_read_only_action_types`
and `settings.autonomy_test_action_types` — no code change required.

---

## 5. Risk thresholds

| Setting                          | Default | Meaning                                                |
| -------------------------------- | ------- | ------------------------------------------------------ |
| `autonomy_low_risk_threshold`    | `0.3`   | risk_score below this → eligible for LOW_RISK          |
| `autonomy_medium_risk_threshold` | `0.7`   | risk_score at or below this → eligible for MEDIUM_RISK |

---

## 6. Flag defaults

All five granular flags default to `DISABLED`. Enabling any flag above `READ_ONLY`
requires AI Governance Lead approval and must be recorded in an ADR or governance ticket.
`FULL` additionally requires dual approval (AI Governance + Security Lead) per ADR-0015.

---

## 7. Acceptance criteria

- [ ] `get_autonomy_level()` returns `FULL` only when `autonomous-mode-full` is enabled
- [ ] `get_autonomy_level()` returns `MEDIUM_RISK` for `risk_score ≤ 0.7` with flag enabled
- [ ] `get_autonomy_level()` returns `LOW_RISK` only for `risk_score < 0.3` with flag enabled
- [ ] `get_autonomy_level()` returns `TESTS_ONLY` only for test action types with flag enabled
- [ ] `get_autonomy_level()` returns `READ_ONLY` only for read-only action types with flag enabled
- [ ] `get_autonomy_level()` returns `NONE` when all flags are disabled
- [ ] `is_autonomous_mode_enabled()` unchanged — no breaking change to callers
- [ ] Unit test coverage ≥ 80%
