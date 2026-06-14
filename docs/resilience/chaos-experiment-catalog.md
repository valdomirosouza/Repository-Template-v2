# Chaos Experiment Catalog

> **Owner:** SRE Lead | **Status:** Living catalog
> The experiments below **already exist** as Chaos Toolkit definitions in `tests/chaos/experiments/`
> and are exercised by the game-day playbook (`tests/chaos/runbooks/game-day-playbook.md`, CHAOS-001).
> This catalog is the human-readable index: each experiment's hypothesis, fault, blast radius, and
> pass/fail criteria, cross-linked to the policy (ADR-0075) and the YAML it runs from.

**Policy (ADR-0075):** every fallback is classified **degrade-open** (availability over the
dependency) or **fail-closed** (integrity over availability), and every fallback ships a chaos
experiment. Classification changes only via a new ADR.

**Run the smoke suite:** `uv run pytest tests/chaos/test_resilience_smoke.py -m chaos` (in-process,
gates PRs, no Docker/k8s). YAML validity is checked by `tests/chaos/test_experiments_valid.py`.

---

## Steady-state hypothesis (global)

During any single-dependency fault the platform must keep its invariants: **no data loss** (all
produced events consumed after recovery), **HITL approvals preserved** (no auto-approve on timeout),
**audit log intact**, **alerts fire within 2 minutes**, and **DLQ depth returns to 0** after recovery
(game-day pass criteria). RTO per the DR plan.

## Catalog

| Experiment (YAML)             | Fault injected                   | Classification  | Expected behaviour                                | Pass criteria                               |
| ----------------------------- | -------------------------------- | --------------- | ------------------------------------------------- | ------------------------------------------- |
| `redis-fallback-activation`   | Redis down                       | degrade-open    | `InMemoryHITLStore`/`InMemoryRequestStore` engage | service stays 2xx; no data loss on recovery |
| `broker-outage`               | Kafka down                       | degrade-open    | producers buffer; full replay on recovery         | zero event loss; DLQ→0 after recovery       |
| `db-audit-fallback-blocked`   | DB down in prod                  | **fail-closed** | startup/refuse to proceed (no InMemory audit)     | service fails closed; audit integrity kept  |
| `kill-agent`                  | Kill agent pod                   | degrade-open    | reschedule; recover within RTO                    | RTO ≤ 15 min; HITL approvals preserved      |
| `network-partition`           | Agent ↔ broker partition         | degrade-open    | circuit breaker opens; DLQ; recovery              | circuit breaker fires; no loss on heal      |
| `hitl-store-degradation`      | HITL store fault                 | degrade-open    | fallback store; approvals preserved               | no auto-approval; approvals intact          |
| `llm-api-timeout`             | LLM provider timeout             | degrade-open    | retry w/ backoff; circuit breaker; degraded mode  | no crash; circuit breaker state correct     |
| `agent-context-overflow`      | Context token overflow           | degrade-open    | bounded handling; no runaway                      | graceful handling; no unbounded loop        |
| `evaluator-disagreement`      | Evaluator/generator disagreement | degrade-open    | self-reflection loop bounded                      | bounded iterations; no infinite retry       |
| `prompt-injection-under-load` | Injection attempts under load    | fail-closed\*   | injection guard holds under load                  | guard blocks; no leakage (abuse-case tie)   |

\* Injection resistance is an integrity guarantee (the guard must never be bypassed — CLAUDE.md §3.3).

## Per-experiment fields (in the YAML)

Each `tests/chaos/experiments/*.yaml` defines: steady-state hypothesis, method (fault injection),
rollback, and probes. Pass/fail thresholds are enforced by the game-day playbook
(`tests/chaos/runbooks/game-day-playbook.md`). Resilience signals come from
`infrastructure/monitoring/prometheus/rules/resilience-alerts.yaml` (`circuit_breaker_state`,
consumer staleness, DLQ depth).

## Blast radius & cadence

- **Blast radius:** smoke experiments run in-process (no infra impact). Full experiments target a
  non-prod environment; never inject faults into production without an approved game-day plan.
- **Cadence:** weekly automated (`.github/workflows/chaos-schedule.yml`) + quarterly full-team
  game-day rotating the RB-002 scenarios.
- **Adding a fallback?** Ship a new experiment here + in `tests/chaos/experiments/` and classify it in
  ADR-0075 (degrade-open vs fail-closed) — this is the policy rule, not optional.

---

## Related

- `tests/chaos/experiments/` · `tests/chaos/runbooks/game-day-playbook.md` (CHAOS-001)
- ADR-0075 (fallback classification) · `src/shared/retry.py` (circuit breaker)
- `docs/resilience/dr-plan.md` · `infrastructure/monitoring/prometheus/rules/resilience-alerts.yaml`
