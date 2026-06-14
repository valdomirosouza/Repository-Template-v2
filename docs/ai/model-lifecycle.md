# Model Lifecycle Policy

> **Owner:** AI Governance Lead | **Status:** Living policy
> Governs how an LLM version enters, moves through, and leaves production use. It makes the rule in
> ADR-0051 + CLAUDE.md §3.2 operational: **never promote a model in `docs/dependency-manifest.yaml`
> without first passing `tests/model_contract/` against it.**

The active model is configured by `src/shared/config.py` (`llm_model`, default `claude-sonnet-4-6`)
and pinned in `docs/dependency-manifest.yaml` (primary `claude-sonnet-4-6`; backup
`claude-haiku-4-5-20251001`), which carries `behavioral_contract_version` and `last_contract_tested`.

---

## Lifecycle states

```
Candidate → Approved → Deprecated → Blocked
```

| State          | Meaning                                                               | Allowed in prod? |
| -------------- | --------------------------------------------------------------------- | ---------------- |
| **Candidate**  | Under evaluation; contract suite not yet green on this version        | No               |
| **Approved**   | Passed model-contract + eval gates; pinned in dependency-manifest     | Yes              |
| **Deprecated** | Superseded by a newer Approved model; kept for rollback               | Rollback only    |
| **Blocked**    | Failed a safety/contract gate or withdrawn upstream; must not be used | No               |

## Promotion checklist (Candidate → Approved)

- [ ] `tests/model_contract/` green against the new `model_id` (refusal, spec-adherence, PII non-leakage)
- [ ] Abuse-case suite green (`uv run pytest tests/abuse_cases/ -m abuse_case`) — never reduced (ADR-0050)
- [ ] Evaluator suite scores within threshold on the eval set (`docs/ai/eval-scorecard.md`)
- [ ] Prompts re-validated against the new model and re-pinned (`docs/ai/prompt-registry.md`)
- [ ] Cost/latency delta recorded (token cost p95, latency p99 — `specs/observability/agent-performance.md`)
- [ ] `docs/dependency-manifest.yaml` updated: `model_id`, `behavioral_contract_version`, `last_contract_tested`
- [ ] `docs/ai-governance/model-card.md` updated (capabilities/limits/intended use)
- [ ] Rollback path identified (previous Approved model id) and tested
- [ ] Change recorded; governance sign-off (AI Governance Lead)

`ci-model-contract.yml` runs the contract suite on any PR touching `docs/dependency-manifest.yaml`,
`specs/ai/**`, or `tests/model_contract/**` — so a promotion PR cannot merge with a red contract.

## Deprecation & rollback

- Mark the outgoing model **Deprecated** in `docs/dependency-manifest.yaml` (keep it for rollback).
- Rollback = re-pin `llm_model` to the last Approved/Deprecated id; no code change required.
- A model withdrawn upstream or failing a safety gate is moved to **Blocked** immediately.

## Behavioural contract

Each Approved model carries a `behavioral_contract_version`. Bump it when the contract suite itself
changes (new refusal class, new PII case). A model is only Approved against a specific contract
version — record both together.

## Cost & performance comparison (record per promotion)

| Dimension                 | Source                                                                    |
| ------------------------- | ------------------------------------------------------------------------- |
| Token cost p95            | `agent_cost_per_resolution_tokens` (`docs/ai/ai-observability-naming.md`) |
| Latency p99               | `llm_call_duration_seconds` / `agent_mttr_seconds`                        |
| Quality vs baseline       | evaluator dimensions (`docs/ai/eval-scorecard.md`)                        |
| Safety (refusals/leakage) | `tests/model_contract/`                                                   |

---

## Related

- ADR-0051 — model behavioural contracts · `tests/model_contract/`
- `docs/dependency-manifest.yaml` — pinned model versions
- `docs/ai/eval-scorecard.md` · `docs/ai/prompt-registry.md`
- `docs/ai-governance/model-card.md`
