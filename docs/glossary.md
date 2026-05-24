# Canonical Glossary

All terms used in this repository are defined here. When a term is ambiguous,
this glossary definition takes precedence over any other usage.

Maintained by: Tech Lead. Updated whenever a new term is introduced in specs or ADRs.

---

| Term                     | Definition                                                                                                                                                                                                        |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ADR**                  | Architecture Decision Record — a document capturing a significant architectural decision, its context, and its consequences. ADRs in `docs/adr/` are binding on implementation.                                   |
| **Agent**                | An autonomous software component that perceives inputs, reasons over them using an LLM, and acts to achieve a goal. Implemented using the Perception → Reason → Act loop pattern.                                 |
| **AsyncAPI**             | An open specification (v2.6) for describing event-driven APIs. Used in `docs/api/asyncapi/` to define event contracts as first-class API artifacts.                                                               |
| **Audit Log**            | An immutable, append-only record of all agent actions and decisions. Implemented in `src/guardrails/audit_logger.py`. Write failures block the associated action.                                                 |
| **Autonomy Boundary**    | The defined line between actions an agent may take autonomously (HOTL) and actions requiring human approval before execution (HITL). Documented in `docs/ai-governance/autonomy-boundaries.md`.                   |
| **CAB**                  | Change Advisory Board — the governance body that reviews and approves Normal and Emergency changes. Composition: Tech Lead, Security Lead, SRE Lead, DPO (for privacy changes).                                   |
| **Canary Deploy**        | A deployment strategy where a new version receives a small percentage of traffic (5% → 25% → 100%) while Golden Signals are monitored at each step. Auto-rollback on SLO breach.                                  |
| **CUJ**                  | Critical User Journey — a key end-to-end user workflow with defined SLO targets for availability and latency. Each CUJ has a dedicated spec file in `docs/sre/cuj/` and a Grafana dashboard.                      |
| **DPIA**                 | Data Protection Impact Assessment — a structured risk assessment required by GDPR Art. 35 before any high-risk personal data processing begins. Template at `docs/privacy/dpia/dpia-v1.md`.                       |
| **DPO**                  | Data Protection Officer — the person responsible for overseeing LGPD and GDPR compliance. Required approver for any change that introduces or modifies personal data processing.                                  |
| **DLQ**                  | Dead Letter Queue — a message broker queue that receives events that could not be processed by the primary consumer after all retry attempts. Monitored as a Golden Signal (Saturation).                          |
| **Error Budget**         | The permitted amount of unreliability within an SLO window, expressed as downtime minutes or request failures. Calculated as: (1 − SLO target) × window duration. Feature freeze when budget < 10%.               |
| **GDPR**                 | General Data Protection Regulation (EU 2016/679) — the EU data privacy law governing processing of personal data of EU residents.                                                                                 |
| **Golden Signals**       | The four key SRE observability metrics defined by Google SRE: Traffic, Error Rate, Saturation, and Latency. Dashboards in `infrastructure/monitoring/grafana/dashboards/golden-signals.json`.                     |
| **HITL**                 | Human in the Loop — an oversight model where an agent proposes an action and a human must explicitly approve it before execution. Implemented in `src/agents/hitl_gateway.py`. No auto-approval on timeout.       |
| **HOTL**                 | Human on the Loop — an oversight model where an agent acts autonomously while a human monitors with override capability. Used for read-only and low-risk agent operations.                                        |
| **L1–L4**                | PII classification levels: L1 Critical (CPF, health, biometric), L2 Sensitive (name, email, IP), L3 Internal (username, session token), L4 Public (declared role, org name). See `docs/privacy/pii-inventory.md`. |
| **LGPD**                 | Lei Geral de Proteção de Dados (Lei 13.709/2018) — Brazil's data privacy law governing processing of personal data of Brazilian residents.                                                                        |
| **LLM**                  | Large Language Model — a neural network trained on large text corpora, used in this system for generation, classification, and reasoning within the agent Reason step.                                            |
| **OTel / OpenTelemetry** | An open-source observability framework providing standardised APIs for traces, metrics, and logs. Bootstrap in `src/observability/otel_setup.py`.                                                                 |
| **PII**                  | Personally Identifiable Information — any data that can directly or indirectly identify a natural person. Classified L1–L4; masked at three interception points per ADR-0012.                                     |
| **PRR**                  | Production Readiness Review — a mandatory checklist completed and signed off by SRE Lead, Tech Lead, Security Lead, and DPO before every production deployment. Template at `docs/sre/prr/PRR-TEMPLATE.md`.       |
| **RAG**                  | Retrieval-Augmented Generation — an LLM pattern that retrieves relevant documents from a vector store and includes them in the LLM context to ground responses in factual data.                                   |
| **RFC**                  | Request for Change — a formal document proposing a Normal or Emergency change for review by the CAB. Template at `docs/change-management/RFC-TEMPLATE.md`.                                                        |
| **RIPD**                 | Relatório de Impacto à Proteção de Dados Pessoais — the LGPD Art. 38 equivalent of a DPIA. Required before any production release that introduces or changes personal data processing of Brazilian residents.     |
| **RoPA**                 | Record of Processing Activities — the GDPR Art. 30 register of all data processing activities maintained by the data controller. Template at `docs/privacy/data-processing-register.md`.                          |
| **SBOM**                 | Software Bill of Materials — a formal inventory of all software components, their versions, and their licences. Generated by Syft in CI and signed with Cosign.                                                   |
| **SDD**                  | Spec-Driven Development — the practice in this repository where a spec in `specs/` is written and approved before any implementation begins. No PR may be merged without a spec reference.                        |
| **SLSA**                 | Supply-chain Levels for Software Artifacts — a security framework for software supply chain integrity. Target: SLSA Level 2+ (provenance generated and signed in CI).                                             |
| **SLI**                  | Service Level Indicator — a quantitative measure of a specific aspect of service performance (e.g., percentage of requests returning non-5xx responses).                                                          |
| **SLO**                  | Service Level Objective — a target value or range for an SLI over a defined window (e.g., 99.9% availability over 30 days). Defined in `docs/sre/slo/slo.yaml`.                                                   |
| **SRE**                  | Site Reliability Engineering — the discipline of applying software engineering principles to operations, reliability, and scalability.                                                                            |
| **Trace**                | A distributed trace — a correlated record of a request's execution path across all services, collected via OpenTelemetry and stored in Jaeger. Every trace carries a `trace_id` propagated via W3C TraceContext.  |
