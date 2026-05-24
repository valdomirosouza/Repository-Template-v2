# Prompt 006 — Specs (Spec-Driven Development)

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section "SPECS — SDD").
> Skip any file that already exists with real content.

---

## Task

Create all spec files under `specs/` with **real, substantive content**.
Specs are the authoritative source of truth — code is never written without a
referenced spec. Every spec must be actionable and implementable.

---

### `specs/README.md`

Spec hierarchy and ownership table. Include:

- What specs are and why SDD requires them to precede implementation
- Spec lifecycle: Draft → Review → Approved → Implemented → Deprecated
- Spec hierarchy: system specs govern domain specs, domain specs govern feature specs
- Naming convention: `specs/<domain>/<name>.md`
- **Ownership table:**

| Spec Path                          | Owner         | Reviewer      | Status   |
| ---------------------------------- | ------------- | ------------- | -------- |
| `specs/system/vision.md`           | Product Owner | Tech Lead     | Approved |
| `specs/system/architecture.md`     | Tech Lead     | SRE Lead      | Approved |
| `specs/system/async-event-flow.md` | Tech Lead     | DevOps Lead   | Approved |
| `specs/ai/agent-design.md`         | AI Lead       | Tech Lead     | Approved |
| `specs/ai/hitl-hotl.md`            | AI Lead       | Security Lead | Approved |
| `specs/ai/guardrails.md`           | Security Lead | AI Lead       | Approved |
| `specs/privacy/pii-inventory.md`   | DPO           | Tech Lead     | Approved |
| `specs/privacy/data-retention.md`  | DPO           | SRE Lead      | Approved |
| `specs/privacy/dpia-ripd.md`       | DPO           | Legal         | Approved |

- How to reference a spec in a PR (required field in PR template)
- How to update a spec: minor changes by owner; major changes require new ADR

---

### `specs/system/vision.md`

Product vision and goals template. Include:

- **Problem statement:** what problem does this system solve?
- **Vision statement:** one sentence describing the desired future state
- **Goals and success metrics:** 3–5 measurable goals with KPIs
- **Non-goals:** explicit list of what this system does NOT do
- **Target users / personas:** who uses this system and what are their core jobs-to-be-done
- **Key constraints:** technical, regulatory (LGPD/GDPR), operational
- **Strategic alignment:** how this system supports organisational objectives
- **Risks:** top 3–5 strategic risks and mitigation strategies

---

### `specs/system/architecture.md`

High-level architecture template. Include:

- **Architecture principles:** (e.g., async-first, privacy-by-design, defence-in-depth,
  observable-by-default, HITL for consequential actions)
- **Component diagram description:** describe the major components and their relationships
  (API Gateway → Agent Service → HITL Gateway → Message Broker → Consumers)
- **Technology stack table:**

| Layer              | Technology                                    | ADR Reference      |
| ------------------ | --------------------------------------------- | ------------------ |
| API (sync)         | FastAPI                                       | ADR-0002           |
| API (async)        | Apache Kafka + AsyncAPI 2.6                   | ADR-0003, ADR-0005 |
| Agent framework    | Custom (Perception→Reason→Act)                | ADR-0010           |
| LLM provider       | Configurable via `LLM_PROVIDER` env           | ADR-0010           |
| Observability      | OpenTelemetry + Prometheus + Grafana + Jaeger | ADR-0004           |
| Secrets management | Vault / AWS Secrets Manager                   | ADR-0008           |
| Caching            | Redis (L2) + Vector DB (L3 semantic)          | ADR-0009           |
| Deployment         | Kubernetes + Helm + canary/blue-green         | ADR-0006           |

- **Data flow:** describe how data moves from ingestion to processing to storage,
  highlighting where PII masking is applied
- **Integration boundaries:** external systems this architecture integrates with
- **Quality attributes:** reliability targets, scalability approach, security posture

---

### `specs/system/async-event-flow.md`

Async event flow design. Include:

- **Principle:** async-first for high-volume / latency-tolerant flows;
  sync (REST/gRPC) only for health checks, HITL approvals, direct user queries
- **Event topology:**

| Event                   | Producer      | Consumer(s)         | Schema | Retention |
| ----------------------- | ------------- | ------------------- | ------ | --------- |
| `domain.created`        | API service   | Processor, Audit    | Avro   | 7 days    |
| `domain.updated`        | API service   | Processor, Notifier | Avro   | 7 days    |
| `agent.action.proposed` | Agent service | HITL Gateway        | Avro   | 7 days    |
| `agent.action.approved` | HITL Gateway  | Agent service       | Avro   | 7 days    |
| `agent.action.executed` | Agent service | Audit, Notifier     | Avro   | 7 days    |

- **Delivery guarantees:** at-least-once with idempotent consumers
- **Schema evolution rules:** backward/forward compatible; Avro union types
- **Dead Letter Queue (DLQ):** configuration and monitoring requirements
- **PII handling in events:** masked at producer before publish (reference ADR-0012)
- **Trace propagation:** W3C TraceContext injected into message headers
- **Observability:** consumer lag threshold (Golden Signal: Saturation)

---

### `specs/ai/agent-design.md`

Agent architecture spec. Include:

- **Architecture pattern:** Perception → Reason → Act loop
  - Perception: inputs received (user query, tool results, memory retrieval)
  - Reason: LLM call with system prompt, tools, and conversation history
  - Act: tool invocation or response generation — routes through HITL gateway
    if action has real-world effect
- **Agent components:**
  - `agent.py`: core loop; `tools.py`: external integrations; `prompts.py`: prompt templates
  - `hitl_gateway.py`: mandatory interception for consequential actions
  - `guardrails/`: validation at input (pii_filter, prompt check) and output
- **Tool design principles:** each tool has a name, description, input schema,
  output schema, and risk classification (Read / Write / External)
- **Memory architecture:** short-term (conversation window) + long-term (vector store RAG)
- **Multi-agent coordination:** orchestrator pattern
  (`src/agents/orchestrator/orchestrator.py`)
- **Error handling:** tool failure → retry with backoff → fallback → HITL escalation
- **Token budget:** per-agent budget defined in `config.py`; alert when 80% consumed
- **Observability requirements:** one span per agent action, one span per LLM call

---

### `specs/ai/hitl-hotl.md`

Human oversight model spec. Include:

- **Definitions:** HITL and HOTL (reference ADR-0011)
- **Classification criteria:** what makes an action HITL vs HOTL
  (real-world effect, irreversibility, data scope, risk score)
- **HITL implementation requirements:**
  - Request format sent to approver (action type, parameters, risk score, context)
  - Approval interface: REST endpoint `/v1/hitl/requests/{id}/approve|reject`
  - Timeout behaviour: reject on expiry; never auto-approve
  - Audit: every decision logged with approver identity, timestamp, and rationale
- **HOTL implementation requirements:**
  - Override interface available in ops dashboard at all times
  - Automatic escalation triggers (anomaly threshold, error rate, novel input)
  - Monitoring: HOTL agent metrics visible in Grafana agent-performance dashboard
- **Compliance mapping:** EU AI Act Art. 14 controls; NIST AI RMF Manage function
- **Testing requirements:** HITL approval flow covered by `tests/integration/test_hitl_gateway.py`
  and `tests/e2e/test_hitl_approval_flow.py`

---

### `specs/ai/guardrails.md`

Technical guardrails spec. Include:

- **Purpose:** define all mandatory safety controls applied to AI agent inputs and outputs
- **Guardrail inventory:**

| Guardrail           | File                        | Stage         | OWASP LLM Risk | Blocking                             |
| ------------------- | --------------------------- | ------------- | -------------- | ------------------------------------ |
| Input validation    | `pii_filter.py`             | Pre-LLM call  | LLM06          | Yes                                  |
| Input validation    | `prompt_injection_guard.py` | Pre-LLM call  | LLM01          | Yes                                  |
| Output validation   | `output_validator.py`       | Post-LLM call | LLM02          | Yes                                  |
| Action scope limits | `action_limits.py`          | Pre-Act step  | LLM08          | Yes                                  |
| Immutable audit log | `audit_logger.py`           | Every action  | LLM09          | Yes (write failure = action blocked) |

- **Implementation requirements per guardrail:**
  - PII filter: mask L1–L4 fields using replacement tokens before any LLM call or log write
  - Input validation: detect and reject structurally malformed inputs using
    pattern-based rules; log rejection with reason; never expose rejection details to caller
  - Output validation: schema check, length check, prohibited-content category check
  - Action limits: per-agent rate limits and scope limits configurable in `config.py`
  - Audit logger: append-only writes; includes action type, agent ID, user context
    (anonymised), timestamp, outcome, approver (for HITL)
- **Guardrail failure behaviour:** any guardrail failure blocks the action and logs
  the event — never silently swallowed
- **Testing requirements:** each guardrail has unit tests in `tests/unit/guardrails/`

---

### `specs/privacy/pii-inventory.md`

PII fields and classification spec (authoritative source for `docs/privacy/pii-inventory.md`).
Include:

- Classification scheme (L1–L4) with definitions
- Full field inventory table: Field | Level | Examples | Masking Token | Source Systems
- Mandatory interception points: pre-LLM, pre-log, pre-broker-publish
- Synthetic data standard for tests: format requirements for fake data
  (e.g., `fake@example.com`, `000.000.000-00` for CPF, `192.0.2.x` for IP)
- Review cadence: updated before any PR that introduces a new personal data field

---

### `specs/privacy/data-retention.md`

Retention rules and LGPD/GDPR alignment spec. Include:

- Retention schedule (mirror `docs/privacy/data-retention-policy.md` — this spec is
  the authoritative source; the doc is a rendered view)
- Implementation requirements: lifecycle rules in object storage, database TTLs,
  log aggregator retention policies
- Verification: monthly automated report confirming purges executed
- Legal references: LGPD Art. 16, GDPR Art. 5(1)(e), GDPR Art. 17 (right to erasure)

---

### `specs/privacy/dpia-ripd.md`

DPIA and RIPD process spec. Include:

- When a DPIA/RIPD is required (new processing activity, changed data categories,
  new third-party processor, new cross-border transfer)
- Process: identify → describe → assess → mitigate → DPO review → approve → deploy
- Roles: who conducts it (engineering + DPO), who approves (DPO), who signs off (DPO)
- Templates: `docs/privacy/dpia/dpia-v1.md` and `docs/privacy/ripd/ripd-v1.md`
- CI gate: no production deploy without DPO sign-off on current DPIA/RIPD versions
- Versioning: new version created for every significant change to the processing activity

---

### Validation

After creating all files, confirm:

- All 10 spec files exist with substantive content
- Every spec references at least one ADR where relevant
- `specs/README.md` ownership table lists all specs created
- `specs/ai/guardrails.md` lists all 5 guardrails with their file paths
- `specs/system/async-event-flow.md` includes the agent action event topology
