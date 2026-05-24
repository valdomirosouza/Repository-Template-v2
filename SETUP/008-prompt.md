# Prompt 008 — Infrastructure + Skills

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Sections: Repository Structure →
> `infrastructure/`, `skills/`; Section 3 SRE Journey; Section 13 FinOps).
> Skip any file that already exists with real content.

---

## Task

Create all infrastructure monitoring files, deploy scripts, and skills files
with **real, substantive content**.

---

## Part A — Infrastructure Monitoring

### `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`

Prometheus alerting rules for the four Golden Signals.
Use standard `PrometheusRule` structure with `groups:` and `rules:`.

Include alert rules for:

**Traffic:**

- `HighRequestRate`: request rate > 2× baseline for 5 minutes (warning)
- `ZeroRequestRate`: request rate = 0 for 3 minutes on a healthy service (critical)

**Error Rate:**

- `HighErrorRate`: 5xx rate > 1% of total requests for 5 minutes (warning)
- `CriticalErrorRate`: 5xx rate > 5% for 2 minutes (critical) — SLO blocker
- `AgentActionErrorRate`: agent action error rate > 0.5% for 5 minutes (warning)

**Saturation:**

- `HighCPUUsage`: CPU > 80% for 10 minutes (warning)
- `HighMemoryUsage`: memory > 85% for 10 minutes (warning)
- `KafkaConsumerLagHigh`: consumer lag > 10000 messages for 5 minutes (warning)
- `LLMTokenBudgetNearing`: token usage > 80% of monthly budget (warning)

**Latency:**

- `HighP99Latency`: p99 latency > 500ms for 5 minutes (warning)
- `CriticalP99Latency`: p99 latency > 2000ms for 2 minutes (critical)
- `HITLApprovalTimeout`: HITL request pending > 240s (warning — 60s before SLO breach)

Each rule must have: `alert` name, `expr` (PromQL), `for` duration,
`labels` (severity), `annotations` (summary, description, runbook_url).

---

### `infrastructure/monitoring/grafana/dashboards/golden-signals.json`

Grafana dashboard JSON for the Golden Signals overview panel.
Structure as a valid Grafana dashboard JSON with:

- `title`: "Golden Signals Overview"
- `uid`: "golden-signals-v1"
- `tags`: ["sre", "golden-signals"]
- Panel rows:
  1. **Traffic** — time series: requests/s by service and status code
  2. **Error Rate** — time series: 5xx rate %; stat panel showing current error rate
  3. **Saturation** — gauges: CPU %, memory %, Kafka consumer lag, LLM token budget %
  4. **Latency** — time series: p50 / p95 / p99 per service
- Template variables: `service`, `environment` (staging / production)
- Time range default: last 1 hour, refresh: 30s
- Include `__requires__` and `__inputs__` sections for portability

Use realistic Grafana JSON structure (schema version 36+). Use placeholder
datasource `${datasource}` for the Prometheus source.

---

### `infrastructure/monitoring/grafana/dashboards/sre-overview.json`

Grafana SRE overview dashboard JSON. Include:

- `title`: "SRE Overview — SLO & Error Budget"
- `uid`: "sre-overview-v1"
- `tags`: ["sre", "slo", "error-budget"]
- Panels:
  1. **SLO Status** — stat panels per service showing current SLO compliance (%)
  2. **Error Budget Remaining** — gauge panels per service (green > 50%, yellow 10–50%, red < 10%)
  3. **Burn Rate** — time series: 1h and 6h burn rates with threshold lines
  4. **HITL Metrics** — stat panels: approvals/rejections today, avg approval latency
  5. **Agent Action Errors** — time series: agent error rate over 24h
- Template variables: `service`, `window` (1h / 6h / 24h / 30d)

Use the same Grafana JSON structure as the golden-signals dashboard.

---

### `infrastructure/monitoring/opentelemetry/otel-collector.yaml`

OpenTelemetry Collector configuration. Include:

- `receivers:` — otlp (grpc port 4317, http port 4318), prometheus
- `processors:` — batch (timeout 5s, max 1000 spans), memory_limiter
  (check_interval 1s, limit_mib 512), resource (add service.environment attribute)
- `exporters:` — jaeger (endpoint placeholder), prometheusremotewrite
  (endpoint placeholder), logging (loglevel: warn)
- `service.pipelines:` — traces (otlp → batch → jaeger),
  metrics (otlp + prometheus → batch → prometheusremotewrite),
  logs (otlp → batch → logging)
- `extensions:` — health_check (port 13133), pprof, zpages

---

### `infrastructure/scripts/deploy/deploy.sh`

Deploy script supporting canary, blue-green, and rolling strategies.
Bash script with:

- `set -euo pipefail`
- Argument parsing: `--strategy`, `--env`, `--version`, `--service`
- Pre-deploy health check function: verify current pods healthy before proceeding
- Deploy functions:
  - `deploy_canary()`: helm upgrade with canary weight, monitoring window,
    Golden Signals check, progressive promotion (5% → 25% → 100%)
  - `deploy_blue_green()`: deploy to inactive slot, smoke test, switch traffic,
    keep old slot for rollback window
  - `deploy_rolling()`: standard helm upgrade with maxUnavailable=0
- `check_golden_signals()`: query Prometheus for error rate and p99 latency;
  return non-zero exit code if SLO thresholds breached
- `run_smoke_tests()`: call `smoke-test.sh` and fail deploy if tests fail
- Auto-rollback on any step failure: trap ERR → call `rollback.sh`
- Structured log output (JSON lines) for all deploy events
- Exit codes: 0 success, 1 deploy failed, 2 smoke test failed, 3 SLO breach

---

### `infrastructure/scripts/deploy/rollback.sh`

Automated rollback script. Bash with `set -euo pipefail`.

- Argument parsing: `--env`, `--service`, `--revision` (optional; defaults to previous)
- `get_previous_revision()`: `helm history` to find last successful revision
- `execute_rollback()`: `helm rollback <release> <revision> --wait`
- Post-rollback smoke test: call `smoke-test.sh`
- Golden Signals monitoring: 10-minute window after rollback
- Notification: send structured event to monitoring (webhook placeholder)
- Log all actions as JSON lines with timestamp, action, outcome
- Exit codes: 0 success, 1 rollback failed, 2 smoke test failed post-rollback

---

### `infrastructure/scripts/deploy/smoke-test.sh`

Post-deploy smoke test script. Bash with `set -euo pipefail`.

- Argument parsing: `--env`, `--base-url`
- Health check: `GET /health` → expect 200 with `{"status":"ok"}`
- Readiness check: `GET /ready` → expect 200
- API smoke: `GET /v1/status` → expect 200 with non-empty response body
- HITL gateway check: verify HITL endpoint responds (does not require approval,
  just checks connectivity)
- Metrics check: verify Prometheus metrics endpoint returns data
- Timeout per check: 10 seconds; retry up to 3 times with 5s backoff
- Exit 0 if all checks pass; exit 1 with descriptive error if any check fails
- Output: JSON summary of all checks with pass/fail and response time

---

## Part B — Skills Catalog (`skills/`)

### `skills/README.md`

Enterprise skills catalog. Include:

- What skills are (reusable Claude Code instruction sets for recurring domain tasks)
- How to activate a skill (referenced in `CLAUDE.md` skill activation table)
- **Full catalog table:**

| Skill             | Path                                          | Domain      | Activation trigger                |
| ----------------- | --------------------------------------------- | ----------- | --------------------------------- |
| Golden Signals    | `skills/sre/golden-signals.md`                | SRE         | Observability, SLO, on-call work  |
| PRR               | `skills/sre/prr.md`                           | SRE         | Pre-production readiness review   |
| CUJ               | `skills/sre/cuj.md`                           | SRE         | Critical user journey design      |
| AI Guardrails     | `skills/ai/guardrails.md`                     | AI Safety   | Agent or guardrail implementation |
| PII               | `skills/privacy/pii.md`                       | Privacy     | Any data handling code            |
| LGPD              | `skills/privacy/lgpd.md`                      | Privacy     | Brazilian data subjects           |
| GDPR              | `skills/privacy/gdpr.md`                      | Privacy     | EU data subjects                  |
| RFC Process       | `skills/change-management/rfc-process.md`     | Change Mgmt | Normal/Emergency changes          |
| Deploy & Rollback | `skills/change-management/deploy-rollback.md` | Change Mgmt | Deploy or rollback operations     |

---

### `skills/sre/golden-signals.md`

SRE Golden Signals skill. Include:

- The four signals: Traffic, Error Rate, Saturation, Latency — definitions
- How to read the Golden Signals dashboard (`infrastructure/monitoring/grafana/dashboards/golden-signals.json`)
- PromQL expressions for each signal
- Alert thresholds and when to escalate
- When a signal breach means SLO is at risk
- Step-by-step on-call triage using Golden Signals
- Link to runbooks for each signal type

---

### `skills/sre/prr.md`

PRR skill. Include:

- When a PRR is required (before every production deploy)
- How to complete the PRR checklist (`docs/sre/prr/prr-checklist.yaml`)
- How to get sign-offs from each required approver
- Common PRR blockers and how to resolve them
- How to document PRR completion in the PR

---

### `skills/sre/cuj.md`

CUJ skill. Include:

- What a CUJ is and why it matters for SLO design
- How to identify and document a new CUJ using `docs/sre/cuj/CUJ-001-*.md` as template
- How to define SLO targets for a CUJ (latency + availability)
- How to create the Grafana dashboard for a CUJ
- How to write E2E tests that validate the CUJ happy path

---

### `skills/ai/guardrails.md`

AI Guardrails skill. Include:

- The five mandatory guardrails and their files (from `specs/ai/guardrails.md`)
- How to use `pii_filter.py`: interception points, masking tokens, testing with synthetic data
- How to use `prompt_injection_guard.py`: what it checks, how it rejects,
  how to write unit tests using placeholder tokens (never real payloads)
- How to use `audit_logger.py`: event format, immutability requirement
- HITL gateway integration: when to route through it, approval timeout behaviour
- Checklist before merging any change to `src/guardrails/`

---

### `skills/privacy/pii.md`

PII skill. Include:

- L1–L4 classification levels and examples
- How to classify a new data field (decision flowchart in text form)
- How to add a new field to `docs/privacy/pii-inventory.md`
- How to implement masking for a new field in `pii_filter.py`
  (use synthetic examples only: `fake@example.com`, `[EMAIL]` token)
- Mandatory three-point masking: pre-LLM, pre-log, pre-broker-publish
- How to write unit tests for PII masking using synthetic data
- DPO notification requirement for new L1 or L2 fields

---

### `skills/privacy/lgpd.md`

LGPD skill. Include:

- Key obligations: lawful basis (Art. 7), data subject rights (Art. 18),
  DPO designation (Art. 41), RIPD requirement (Art. 38), breach notification
- How to determine if a processing activity requires a RIPD
- How to complete the RIPD template (`docs/privacy/ripd/ripd-v1.md`)
- Data subject rights implementation checklist (access, correction, deletion, portability)
- Breach notification procedure (ANPD notification requirements)

---

### `skills/privacy/gdpr.md`

GDPR skill. Include:

- Key obligations: lawful basis (Art. 6), special categories (Art. 9),
  data subject rights (Arts. 15–22), DPIA (Art. 35), breach notification (Art. 33–34),
  cross-border transfers (Chapter V)
- How to determine if a DPIA is required (high-risk processing criteria)
- How to complete the DPIA template (`docs/privacy/dpia/dpia-v1.md`)
- Cross-border transfer mechanism selection (SCCs, adequacy decision)
- 72-hour breach notification checklist

---

### `skills/change-management/rfc-process.md`

RFC Process skill. Include:

- When to file an RFC (Normal and Emergency change triggers)
- How to complete `docs/change-management/RFC-TEMPLATE.md`
- CAB submission requirements and timeline
- How to get approvals (Tech Lead, Security Lead, CAB)
- Emergency change abbreviated process
- How to reference the RFC in PR description and CHANGELOG

---

### `skills/change-management/deploy-rollback.md`

Deploy and Rollback skill. Include:

- How to run `infrastructure/scripts/deploy/deploy.sh` with correct parameters
- Canary deploy steps and Golden Signals monitoring window
- How to trigger a manual rollback via `rollback.sh`
- How to verify rollback success using `smoke-test.sh`
- When to escalate from automated to manual rollback
- Post-rollback checklist: incident opened, stakeholders notified, post-mortem scheduled

---

### Validation

After creating all files, confirm:

- All 3 infrastructure monitoring files exist and are valid YAML/JSON
- All 3 deploy scripts are executable Bash with `set -euo pipefail`
- `skills/README.md` catalog table lists all 9 skills
- All 9 skill files exist with substantive guidance content
- `infrastructure/scripts/deploy/deploy.sh` contains canary, blue-green,
  and rolling deploy functions
