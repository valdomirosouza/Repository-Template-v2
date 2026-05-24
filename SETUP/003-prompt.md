# Prompt 003 — Architecture Decision Records (ADRs) + Core Docs

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section "Repository Structure" → `docs/adr/`).
> Skip any file that already exists with real content.

---

## Task

Create all ADR files and core documentation files listed below with **real, substantive content**.

---

### `docs/adr/README.md`

ADR index and template. Include:

- What an ADR is and why this project uses them
- ADR lifecycle: Proposed → Accepted → Deprecated → Superseded
- ADR template (sections: Title, Status, Date, Context, Decision, Consequences, Alternatives Considered)
- Master index table with all ADRs ADR-0001 through ADR-0013:

| ADR      | Title                             | Status   | Date       |
| -------- | --------------------------------- | -------- | ---------- |
| ADR-0001 | Monorepo Structure and Governance | Accepted | 2026-05-24 |
| ADR-0002 | Technology Stack Selection        | Accepted | 2026-05-24 |
| ADR-0003 | Async API Strategy                | Accepted | 2026-05-24 |
| ADR-0004 | Observability Stack               | Accepted | 2026-05-24 |
| ADR-0005 | Message Broker Selection          | Accepted | 2026-05-24 |
| ADR-0006 | Deployment Strategy               | Accepted | 2026-05-24 |
| ADR-0007 | Service Mesh                      | Proposed | 2026-05-24 |
| ADR-0008 | Secrets Management                | Accepted | 2026-05-24 |
| ADR-0009 | Caching Strategy                  | Accepted | 2026-05-24 |
| ADR-0010 | Agent Framework Selection         | Accepted | 2026-05-24 |
| ADR-0011 | HITL/HOTL Human Oversight Model   | Accepted | 2026-05-24 |
| ADR-0012 | PII Masking Strategy              | Accepted | 2026-05-24 |
| ADR-0013 | Data Retention Policy             | Accepted | 2026-05-24 |

---

### `docs/adr/ADR-0001-monorepo-structure-and-governance.md`

First foundational ADR. Full structure:

- **Status:** Accepted
- **Context:** Need for a single repository strategy for an enterprise AI-powered system
  covering governance, DevSecOps, AI safety, and privacy compliance
- **Decision:** Adopt a monorepo with Spec-Driven Development (SDD), mandatory ADRs,
  HITL/HOTL controls, and privacy-by-design as first-class architectural concerns
- **Consequences (positive):** Single source of truth, unified CI/CD, shared guardrails,
  consistent governance across all components
- **Consequences (negative):** Larger clone size, requires discipline to avoid coupling
- **Alternatives Considered:** Polyrepo with shared packages (rejected: governance fragmentation)

---

### `docs/adr/ADR-0010-agent-framework-selection.md`

- **Status:** Accepted
- **Context:** Selecting a framework for building autonomous AI agents in this system.
  Requirements: tool use, multi-step reasoning, HITL integration point, observability hooks,
  Python-native, actively maintained
- **Decision:** Use a modular agent loop pattern (Perception → Reason → Act) implemented
  directly in `src/agents/`, with LLM calls abstracted behind a provider interface.
  No vendor lock-in on orchestration framework; integrate HITL gateway at the Act step.
- **Consequences:** Full control over agent lifecycle; requires more scaffolding than
  off-the-shelf frameworks; HITL integration is explicit and auditable
- **Alternatives Considered:** LangChain (rejected: heavy abstraction, difficult to audit);
  AutoGen (rejected: limited HITL control); CrewAI (rejected: immature enterprise controls)

---

### `docs/adr/ADR-0011-hitl-hotl-model.md`

- **Status:** Accepted
- **Context:** AI agents in this system can propose actions with real-world effects
  (data writes, API calls, notifications). Unreviewed autonomous actions carry legal,
  reputational, and safety risk. EU AI Act Arts. 13–14 require human oversight mechanisms.
- **Decision:** Two-tier oversight model:
  - **HITL (Human in the Loop):** all actions with real-world effects require explicit
    human approval before execution. Implemented in `src/agents/hitl_gateway.py`.
  - **HOTL (Human on the Loop):** monitoring and classification flows run autonomously;
    human can observe and override at any time via the ops dashboard.
- **Consequences:** Higher latency for HITL flows; significantly reduced risk of
  unintended autonomous actions; clear audit trail for every approved action
- **Alternatives Considered:** Fully autonomous (rejected: unacceptable risk, non-compliant
  with EU AI Act); fully manual (rejected: defeats purpose of automation)

---

### `docs/adr/ADR-0012-pii-masking-strategy.md`

- **Status:** Accepted
- **Context:** The system processes personal data subject to LGPD and GDPR.
  LLM providers receive API payloads; logs are shipped to third-party aggregators.
  Personal data must not appear in LLM calls, external logs, or broker events unmasked.
- **Decision:** Four-level PII classification (L1 Critical → L4 Public).
  `src/guardrails/pii_filter.py` runs at three mandatory interception points:
  1. Before every LLM API call
  2. Before every log write
  3. Before every broker event publish
     Masking uses replacement tokens (e.g., `[EMAIL]`, `[CPF]`, `[NAME]`) that preserve
     semantic structure without leaking personal data.
- **Consequences:** Slight processing overhead at each interception point; full
  LGPD/GDPR compliance for data minimisation; no personal data at rest in third-party systems
- **Alternatives Considered:** Opt-in masking (rejected: too error-prone); tokenisation
  vault (considered for future L1 data; deferred to ADR-0014)

---

### `docs/adr/ADR-0013-data-retention-policy.md`

- **Status:** Accepted
- **Context:** LGPD Art. 16 and GDPR Art. 5(1)(e) require personal data be retained
  no longer than necessary. System generates operational logs, audit logs, and agent
  action history containing or referencing personal data.
- **Decision:** Tiered retention policy automated via storage lifecycle rules:
  - Operational logs: 30 days hot / 90 days warm / deleted
  - Audit logs (anonymised): 1 year archived / deleted
  - Agent action history: 90 days active + 30 days soft-delete / hard-deleted
  - User data: per product requirement + user-initiated deletion
  - Backups: 30-day rotation
- **Consequences:** Automated compliance; data minimisation by default; requires
  lifecycle policies configured in all storage systems
- **Alternatives Considered:** Manual deletion processes (rejected: error-prone,
  non-compliant); indefinite retention (rejected: LGPD/GDPR violation)

---

### `docs/glossary.md`

Canonical glossary. Include every term used in the repository. Minimum entries:

| Term                 | Definition                                                                                                                     |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **ADR**              | Architecture Decision Record — a document capturing a significant architectural decision, its context, and its consequences    |
| **Agent**            | An autonomous software component that perceives inputs, reasons over them, and acts to achieve a goal                          |
| **Async API**        | An event-driven API defined using AsyncAPI 2.6, where producers and consumers communicate via a message broker                 |
| **CAB**              | Change Advisory Board — the governance body that reviews and approves Normal and Emergency changes                             |
| **CUJ**              | Critical User Journey — a key end-to-end user workflow with defined SLO targets                                                |
| **DPIA**             | Data Protection Impact Assessment — a GDPR Art. 35 risk assessment for high-risk data processing activities                    |
| **DPO**              | Data Protection Officer — the person responsible for overseeing LGPD/GDPR compliance                                           |
| **Error Budget**     | The permitted amount of downtime or error within an SLO window; 100% minus the SLO target                                      |
| **GDPR**             | General Data Protection Regulation (EU 2016/679) — EU data privacy law                                                         |
| **Golden Signals**   | The four key SRE metrics: Traffic, Error Rate, Saturation, Latency                                                             |
| **HITL**             | Human in the Loop — an oversight model requiring explicit human approval before an agent executes an action                    |
| **HOTL**             | Human on the Loop — an oversight model where an agent acts autonomously while a human monitors and retains override capability |
| **L1–L4**            | PII classification levels: L1 Critical, L2 Sensitive, L3 Internal, L4 Public                                                   |
| **LGPD**             | Lei Geral de Proteção de Dados (Lei 13.709/2018) — Brazil's data privacy law                                                   |
| **LLM**              | Large Language Model — a neural network model trained on large text corpora used for generation and classification             |
| **OWASP LLM Top 10** | A list of the ten most critical security risks specific to LLM-based applications                                              |
| **PII**              | Personally Identifiable Information — any data that can identify a natural person                                              |
| **PRR**              | Production Readiness Review — a mandatory checklist completed before every production deployment                               |
| **RAG**              | Retrieval-Augmented Generation — an LLM pattern that grounds responses in retrieved documents                                  |
| **RFC**              | Request for Change — a formal document proposing a Normal or Emergency change for CAB review                                   |
| **RIPD**             | Relatório de Impacto à Proteção de Dados — the LGPD Art. 38 equivalent of a DPIA                                               |
| **RoPA**             | Record of Processing Activities — the GDPR Art. 30 register of all data processing activities                                  |
| **SBOM**             | Software Bill of Materials — a formal inventory of all software components and their dependencies                              |
| **SDD**              | Spec-Driven Development — a practice where specifications are written and approved before any implementation begins            |
| **SLSA**             | Supply-chain Levels for Software Artifacts — a security framework for software supply chain integrity                          |
| **SLI**              | Service Level Indicator — a metric that measures a specific aspect of service performance                                      |
| **SLO**              | Service Level Objective — a target value or range for an SLI                                                                   |
| **SRE**              | Site Reliability Engineering — a discipline applying software engineering to operations and reliability                        |
| **Trace**            | A distributed trace — a record of a request's path through all services, collected via OpenTelemetry                           |

---

### `docs/repo-structure.md`

Annotated directory tree mirroring the full scaffold. For each top-level directory include:

- One-line purpose annotation
- Key files within it and their roles
- Who owns it (role)
- Link to the relevant spec or ADR where applicable

Cover all directories: `docs/`, `specs/`, `src/`, `tests/`, `infrastructure/`,
`.github/`, `harness/`, `skills/`, `.devcontainer/`.

---

### Validation

After creating all files, confirm:

- All ADRs listed in `docs/adr/README.md` index table have a corresponding file
- `docs/glossary.md` contains at least all terms listed above
- `docs/repo-structure.md` covers all top-level directories
