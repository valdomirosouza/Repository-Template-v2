# Spec: Agentic Maturity Self-Assessment

**Status:** Approved
**Issue:** #17 | **ADR:** ADR-0040
**Owner:** AI Governance Lead | **Last updated:** 2026-06-05

---

## 1. Purpose

Provide a machine-checkable definition of the four Gartner agentic maturity levels so
that teams cannot falsely claim a higher maturity than they have achieved ("agent-washing").
The `make agentic-maturity-check` target evaluates the live repository configuration
and emits a structured maturity report.

---

## 2. Maturity Levels and Machine-Checkable Criteria

### Level 1 — Assistance

The agent acts as a smart conversational tool; humans decide and execute.

| Criterion               | Check                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| `harness_mode = solo`   | Read `settings.harness_mode`                                          |
| `autonomy_level = NONE` | All `autonomous-mode-*.yaml` flags `defaultVariant: "off"` or `false` |
| No tool registry        | `infrastructure/agent-tools/tools.yaml` absent or empty               |

### Level 2 — Automation

Discrete routine workflows; humans approve each sequential step.

| Criterion                     | Check                                                 |
| ----------------------------- | ----------------------------------------------------- |
| HITL gateway active           | `src/agents/hitl_gateway.py` present                  |
| At least one tool in registry | `infrastructure/agent-tools/tools.yaml` has ≥ 1 entry |
| Unit test coverage ≥ 80%      | `.coverage` report or `make test-unit-python` passes  |
| Audit logger present          | `src/guardrails/audit_logger.py` present              |

### Level 3 — Augmentation

Simple multi-step workflows by agent clusters with HITL oversight.

| Criterion                             | Check                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------- |
| `harness_mode = full`                 | `settings.harness_mode == "full"`                                         |
| FeedbackLearner active (passive mode) | `src/agents/feedback_learner.py` present AND `learning-mode` flag present |
| SubAgentRegistry has ≥ 1 agent        | `src/agents/harness/sub_agent_registry.py` present                        |
| SessionCheckpoint present             | `src/agents/harness/session_checkpoint.py` present                        |

### Level 4 — Autonomy

Long-horizon goals, context graphs, full governance prerequisites met.

| Criterion                    | Check                                                          |
| ---------------------------- | -------------------------------------------------------------- |
| `learning-mode = active`     | `learning-mode.yaml` `defaultVariant: "active"`                |
| Context graph reachable      | `src/agents/context_graph.py` present                          |
| `autonomy-tier-ready = true` | `autonomy-tier-ready.yaml` `defaultVariant: "true"`            |
| Governance council sign-off  | `governance-council-approved` label applied to the enabling PR |

---

## 3. Output Format

```
=== Agentic Maturity Assessment ===
Date: 2026-06-05
Repository: Repository-Template-v2

Current maturity level: AUGMENTATION (Level 3)

✅ Criteria met for ASSISTANCE (Level 1)
✅ Criteria met for AUTOMATION (Level 2)
✅ Criteria met for AUGMENTATION (Level 3)

Missing for AUTONOMY (Level 4):
  ✗ learning-mode not set to active (currently: passive)
  ✗ context_graph.py not found
  ✗ autonomy-tier-ready flag is false

Gartner compliance coverage: 75% → target 92% after all waves complete
```

---

## 4. CI Integration

The `agentic-maturity-check` step runs in `ci.yml` as an informational, non-blocking
step. Its output is posted as a PR annotation. It does not fail the build.

---

## 5. Related

- `scripts/agentic_maturity_check.py` — implementation
- `docs/adr/ADR-0040-agentic-maturity-model.md`
- `Makefile` — `agentic-maturity-check` target
