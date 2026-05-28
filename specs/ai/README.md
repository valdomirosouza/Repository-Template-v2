# AI Agents Module — Specs

> **Scope:** These specs apply **only** when the AI Agents Module is enabled for your project.
> If your project does not use AI agents, autonomous workflows, or LLM-based pipelines,
> you can ignore this entire directory.
>
> To enable the AI Agents Module, follow the activation checklist in
> [`docs/optional-extensions/ai-agents/README.md`](../../docs/optional-extensions/ai-agents/README.md).

---

## Specs in this directory

| Spec                                                   | Description                                            |
| ------------------------------------------------------ | ------------------------------------------------------ |
| [agent-design.md](agent-design.md)                     | Perception → Reason → Act agent architecture           |
| [agent-memory.md](agent-memory.md)                     | Vector store + semantic memory (pgvector, ADR-0017)    |
| [autonomous-mode-levels.md](autonomous-mode-levels.md) | Autonomy level progression (NONE → FULL, ADR-0015)     |
| [feedback-loop.md](feedback-loop.md)                   | Agent self-improvement and evaluator feedback loop     |
| [guardrails.md](guardrails.md)                         | PII filter, prompt injection guard, action limits      |
| [harness-design.md](harness-design.md)                 | Multi-agent harness: Planner/Generator/Evaluator       |
| [hitl-hotl.md](hitl-hotl.md)                           | Human-in-the-Loop / Human-on-the-Loop model (ADR-0011) |
| [hitl-notification.md](hitl-notification.md)           | HITL approval notification and timeout handling        |
| [sandbox-execution.md](sandbox-execution.md)           | Agent sandbox execution policy (ADR-0016)              |

## Related ADRs

ADR-0010, ADR-0011, ADR-0014, ADR-0016, ADR-0017 — all in `docs/adr/` under the **AI Agents Module** group.
