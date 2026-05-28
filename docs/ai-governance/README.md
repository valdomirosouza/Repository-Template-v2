# AI Governance

> **AI Agents Module dependency.** This directory is only relevant when the AI Agents Module
> is enabled for your project. If your project does not include AI agents, autonomous workflows,
> or LLM pipelines, you can delete this entire directory.
>
> For the activation and removal checklist see:
> [`docs/optional-extensions/ai-agents/README.md`](../optional-extensions/ai-agents/README.md)

---

## Documents in this directory

| Document                                           | Purpose                                                       |
| -------------------------------------------------- | ------------------------------------------------------------- |
| [model-card.md](model-card.md)                     | LLM model card — capabilities, limitations, intended use      |
| [eu-ai-act-compliance.md](eu-ai-act-compliance.md) | EU AI Act risk classification and compliance evidence         |
| [nist-ai-rmf.md](nist-ai-rmf.md)                   | NIST AI Risk Management Framework alignment                   |
| [autonomy-boundaries.md](autonomy-boundaries.md)   | Documented autonomy boundaries per agent type and environment |

## Governance contacts

| Role               | Responsibility                                       |
| ------------------ | ---------------------------------------------------- |
| AI Governance Lead | Owns this directory; approves all AI-related changes |
| DPO                | Reviews PII exposure in LLM inputs/outputs           |
| Security Lead      | Reviews guardrails and sandbox configuration         |

All documents in this directory require review by the AI Governance Lead before changes are merged.
