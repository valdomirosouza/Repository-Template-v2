# Prompt 004 — Privacy Documentation + AI Governance Documentation

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section 9 — AI Governance, Section 10 — Data Privacy).
> Skip any file that already exists with real content.

---

## Task

Create all privacy and AI governance documentation files with **real, substantive content**.

---

## Part A — Privacy Documentation (`docs/privacy/`)

### `docs/privacy/pii-inventory.md`

PII fields catalogue and classification. Include:

- Introduction: purpose of this inventory and who maintains it (DPO)
- Classification table with columns: Field Name, Classification Level, Examples,
  Storage Location, Masking Rule, Retention Period, Legal Basis

Populate with representative rows covering:

- L1 Critical: national ID numbers (CPF/SSN), health/medical data, biometric data,
  financial account numbers — rule: encrypt at rest and in transit, never in logs,
  never sent to LLM unmasked
- L2 Sensitive: full name, email address, phone number, IP address, physical address,
  date of birth — rule: mask in all logs, pseudonymise for analytics
- L3 Internal: username, user ID, session token, device ID, internal correlation IDs —
  rule: allowed in internal audit logs, masked in external/third-party logs
- L4 Public: declared job title, public organisation name, public profile URL —
  rule: no special handling required

Include a section on masking token format: `[FIELD_TYPE]`
(e.g., `[EMAIL]`, `[CPF]`, `[NAME]`, `[IP]`, `[PHONE]`).

Include a mandatory pre-release checklist:

- All new PII fields added to this inventory before merging
- Masking rule confirmed and implemented in `src/guardrails/pii_filter.py`
- DPO review obtained for any new L1 or L2 field

---

### `docs/privacy/data-retention-policy.md`

Data retention rules per data type. Include:

- Policy statement and regulatory basis (LGPD Art. 16, GDPR Art. 5(1)(e))
- Retention schedule table:

| Data Type                             | Hot Retention             | Warm Retention       | Cold/Archive                        | Deletion Method                    | Owner              |
| ------------------------------------- | ------------------------- | -------------------- | ----------------------------------- | ---------------------------------- | ------------------ |
| Operational logs (masked PII)         | 30 days                   | 90 days              | Not retained                        | Automated lifecycle rule           | SRE                |
| Audit logs (anonymised agent actions) | 90 days                   | 1 year               | Not retained                        | Automated purge                    | Security Lead      |
| Agent action history                  | 90 days active            | —                    | 30-day soft-delete then hard-delete | Automated + manual                 | Engineering        |
| User account data                     | Active duration           | 30 days post-closure | —                                   | User-initiated or automated expiry | Product            |
| Backup snapshots                      | 30 days rolling           | —                    | —                                   | Automated rotation                 | SRE                |
| LLM interaction logs (anonymised)     | 30 days                   | —                    | —                                   | Automated purge                    | AI Governance Lead |
| DPIA / RIPD documents                 | Indefinite (legal record) | —                    | —                                   | DPO manual review                  | DPO                |

- Implementation requirements: lifecycle rules must be configured in all storage systems
  (object storage, databases, log aggregators) before production release
- Quarterly review process: DPO reviews retention rules against regulatory changes
- Deletion verification: automated monthly report confirming purges executed

---

### `docs/privacy/data-processing-register.md`

Register of Processing Activities (RoPA) — GDPR Art. 30 template. Include:

- Introduction and legal basis for maintaining this register
- Controller details section (placeholder fields)
- Processing activities table with columns:
  - Activity Name
  - Purpose
  - Legal Basis (GDPR / LGPD)
  - Data Categories (reference PII levels from pii-inventory.md)
  - Data Subjects
  - Recipients / Third-Party Processors
  - Third Countries (cross-border transfers)
  - Retention Period
  - Technical and Organisational Measures
  - DPIA Required (Yes/No)
  - DPIA Reference

Populate with representative rows:

- User authentication and session management
- AI agent action processing
- Observability and log collection
- Analytics and reporting
- Third-party LLM API calls

Include a maintenance section: updated before every production release that introduces
a new processing activity; DPO signs off.

---

### `docs/privacy/dpia/dpia-v1.md`

Data Protection Impact Assessment — GDPR Art. 35 template. Include:

- **Section 1 — Description of Processing**
  - Name and version of the processing activity
  - Controller and DPO details
  - Purpose and legal basis
  - Data subjects and categories of personal data processed
  - Recipients and third-party processors
  - Cross-border transfers (Y/N, mechanism)
  - Retention period

- **Section 2 — Necessity and Proportionality**
  - Is processing necessary for the stated purpose?
  - Is data minimisation applied? How?
  - Are data subject rights mechanisms in place?

- **Section 3 — Risk Assessment**
  - Risk identification table: Risk | Likelihood (1–3) | Impact (1–3) | Risk Score | Mitigation | Residual Risk
  - Cover risks: unauthorised access, data breach, PII exposure via LLM, excessive retention,
    rights not fulfilled

- **Section 4 — Measures to Address Risks**
  - Technical measures (encryption, masking, access control, audit logging)
  - Organisational measures (training, DPO oversight, incident response)

- **Section 5 — Consultation and Approval**
  - DPO consulted: [Date] [Name]
  - DPO opinion: [Approved / Approved with conditions / Not approved]
  - Supervisory authority consultation required: [Y/N]
  - Sign-off date and version

---

### `docs/privacy/ripd/ripd-v1.md`

Relatório de Impacto à Proteção de Dados Pessoais — LGPD Art. 38 template. Include:

- **Seção 1 — Identificação**
  - Nome da atividade de tratamento
  - Controlador e Encarregado (DPO)
  - Data e versão

- **Seção 2 — Descrição do Tratamento**
  - Finalidade do tratamento
  - Base legal (Art. 7 ou Art. 11 da LGPD)
  - Dados pessoais tratados (referência ao pii-inventory.md)
  - Titulares dos dados
  - Operadores e suboperadores (terceiros)
  - Transferência internacional (S/N, mecanismo)

- **Seção 3 — Necessidade e Proporcionalidade**
  - Tratamento é necessário para a finalidade declarada?
  - Medidas de minimização de dados adotadas
  - Mecanismos para exercício dos direitos dos titulares (acesso, correção,
    exclusão, portabilidade)

- **Seção 4 — Avaliação de Riscos**
  - Tabela de riscos: Risco | Probabilidade | Impacto | Score | Mitigação | Risco Residual
  - Cobrir: acesso não autorizado, violação de dados, exposição de PII via LLM,
    retenção excessiva, direitos não atendidos

- **Seção 5 — Medidas de Mitigação**
  - Medidas técnicas e organizacionais adotadas

- **Seção 6 — Aprovação**
  - Encarregado consultado: [Data] [Nome]
  - Parecer do Encarregado: [Aprovado / Aprovado com condições / Não aprovado]
  - Data de aprovação e versão

---

## Part B — AI Governance Documentation (`docs/ai-governance/`)

### `docs/ai-governance/model-card.md`

Model Card template following Google / Hugging Face format. Include all required
fields from Section 9 of the reference document:

- **Model Details:** provider/version/API endpoint (placeholder), intended use cases,
  out-of-scope uses
- **Training Data (if fine-tuned):** data sources, date range, known biases
- **Performance:** benchmark results, evaluation methodology
- **Ethical Considerations:** known failure modes, bias assessment summary
  (link to `docs/ai-governance/bias-audit.md`), autonomy level (HITL/HOTL with ADR link)
- **Privacy:** data sent to model (fields, classification), PII handling policy
  (masked / not sent), data retention at provider (link to DPA)
- **Monitoring:** metrics tracked in production, drift detection approach, retraining trigger
- **Changelog:** version history of the model in this system

---

### `docs/ai-governance/eu-ai-act-compliance.md`

EU AI Act compliance checklist covering Arts. 9, 12, 13, and 14. Include:

- System risk classification (High-Risk / Limited Risk / Minimal Risk) with reasoning
- **Art. 9 — Risk Management System:**
  - [ ] Risk management process documented and implemented
  - [ ] Residual risks identified and mitigated
  - [ ] Testing performed throughout lifecycle
- **Art. 12 — Record-Keeping:**
  - [ ] Automatic logging of system events enabled
  - [ ] Logs retained for at minimum the period specified in retention policy
  - [ ] Audit trail covers all autonomous decisions
- **Art. 13 — Transparency:**
  - [ ] Users informed they are interacting with an AI system
  - [ ] System capabilities and limitations documented in model card
  - [ ] Instructions for use provided to deployers
- **Art. 14 — Human Oversight:**
  - [ ] HITL controls implemented for all high-consequence actions (`hitl_gateway.py`)
  - [ ] HOTL monitoring active for autonomous flows
  - [ ] Override mechanism available to authorised operators at all times
  - [ ] Persons responsible for oversight identified and trained
- Status column for each item: Compliant / In Progress / Not Started / Not Applicable
- Evidence / reference column pointing to implementing files or documents

---

### `docs/ai-governance/nist-ai-rmf.md`

NIST AI Risk Management Framework (AI RMF 1.0) mapping. Include:

- Overview of the four core functions: Govern, Map, Measure, Manage
- For each function, a table mapping framework sub-categories to this system's
  implementing controls:

**GOVERN:** AI risk governance structure, policies, roles

- Roles and responsibilities defined (link to CODEOWNERS)
- AI governance policies documented (link to `docs/ai-governance/`)
- Risk tolerance defined (link to `docs/sre/slo/slo.yaml`)

**MAP:** AI risk context and identification

- Use cases documented (link to `specs/ai/agent-design.md`)
- Stakeholders and impacted groups identified
- Third-party AI components inventoried (link to model card)

**MEASURE:** Risk analysis and assessment

- Bias audit process defined (link to `docs/ai-governance/bias-audit.md`)
- Performance metrics defined (link to `src/observability/metrics.py`)
- DPIA / RIPD completed before production

**MANAGE:** Risk treatment and monitoring

- HITL/HOTL controls operational (link to ADR-0011, `hitl_gateway.py`)
- Guardrails active in production (link to `src/guardrails/`)
- Incident response plan for AI failures (link to `docs/runbooks/agent-failure.md`)
- Continuous monitoring via Golden Signals (link to Grafana dashboard)

---

### `docs/ai-governance/autonomy-boundaries.md`

HITL / HOTL boundary definitions. Include:

- **Purpose:** define exactly which agent actions require human approval (HITL) vs.
  which run autonomously under human monitoring (HOTL)
- **HITL — Requires Human Approval Before Execution:**
  - Any write operation to production data stores
  - Any external API call with side effects (payments, notifications, provisioning)
  - Any action affecting more than N records (threshold defined per agent in `config.py`)
  - Any action flagged as HIGH or CRITICAL risk by the risk scorer
  - Any action outside the agent's documented scope in `specs/ai/agent-design.md`
- **HOTL — Autonomous with Monitoring:**
  - Read-only data retrieval and classification
  - Internal scoring and routing decisions
  - Draft generation (output reviewed before delivery)
  - Metric collection and aggregation
- **Escalation rules:** conditions under which HOTL automatically escalates to HITL
  (anomaly score threshold, consecutive error rate, novel input category)
- **Approval timeout:** HITL requests expire after `HITL_APPROVAL_TIMEOUT_SECONDS`
  (configured in `.env`); expired requests are rejected, not auto-approved
- **Audit requirement:** every HITL approval and rejection is logged immutably
  via `guardrails/audit_logger.py`
- **Quarterly review:** boundaries reviewed by AI Governance Lead and DPO each quarter

---

### Validation

After creating all files, confirm:

- All 9 files listed above exist with substantive content
- `docs/privacy/pii-inventory.md` contains all four classification levels (L1–L4)
- `docs/privacy/dpia/dpia-v1.md` contains all six sections
- `docs/privacy/ripd/ripd-v1.md` contains all six sections in Portuguese
- `docs/ai-governance/eu-ai-act-compliance.md` covers Arts. 9, 12, 13, and 14
- `docs/ai-governance/autonomy-boundaries.md` defines both HITL and HOTL tiers
