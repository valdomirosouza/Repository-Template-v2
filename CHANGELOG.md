# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Categories: `Added` | `Changed` | `Fixed` | `Security` | `Removed` | `Privacy` | `Deprecated`

Every entry must reference: Issue #, ADR # (if applicable), RFC # (if applicable).

---

## [Unreleased]

### Wave 12 — Python API Gateway Probe Tuning (K8s Probe Compliance)

#### Added

- `tests/unit/api/test_health.py` — `TestProbeCompliance` class: 3 explicit probe-contract tests verifying `/health` returns 200 regardless of dependency state and `/ready` returns 503 (not 500) on DB failure (Issue #21, specs/k8s/probe-strategy.md §3.1)

#### Changed

- `infrastructure/helm/api-gateway/values.yaml` — added `probes.startup` section (failureThreshold=30, periodSeconds=5, 150s window); bumped `terminationGracePeriodSeconds` 30→60 (HITL in-flight SLA, ADR-0011/ADR-0042); removed `initialDelaySeconds` from liveness and readiness (anti-pattern per K8S-001 spec)
- `infrastructure/helm/api-gateway/templates/deployment.yaml` — `startupProbe` is now fully values-driven via `{{ .Values.probes.startup.* }}`; removed hardcoded `failureThreshold`/`periodSeconds`; removed `initialDelaySeconds` from liveness and readiness
- `infrastructure/k8s/deployment.yaml` — startup probe `periodSeconds` 10→5; `terminationGracePeriodSeconds` 30→60; removed `initialDelaySeconds` from liveness and readiness

---

### Wave 11 — Go Event-Worker Health Server + startupProbe (K8s Probe Compliance)

#### Added

- `services/event-worker/internal/health/server.go` — dedicated HTTP health server on port 8081; atomic-bool ready state; `/healthz` (liveness) and `/readyz` (readiness) endpoints; isolated from Prometheus metrics port (Issue #20, specs/k8s/probe-strategy.md §3.3)
- `services/event-worker/internal/health/server_test.go` — 8 unit tests covering liveness always-200, readiness 503→200 lifecycle, concurrent access safety
- `infrastructure/helm/event-worker/values.yaml` — `probes.startup` section (failureThreshold=12, periodSeconds=5, 60s window); `service.healthPort: 8081`; removed `initialDelaySeconds` from liveness/readiness
- `specs/k8s/probe-strategy.md` — formal probe strategy spec (K8S-001) covering all three workloads, parameter reference table, canary gate requirements (Issue #20–#24, ADR-0042)

#### Changed

- `services/event-worker/cmd/event-worker/main.go` — wires `health.New()` + `health.Start(cfg.HealthPort)`; calls `SetReady(true)` after Kafka consumer group joins
- `services/event-worker/internal/config/config.go` — adds `HealthPort` field (default 8081, env `HEALTH_PORT`)
- `infrastructure/helm/event-worker/templates/deployment.yaml` — adds `startupProbe` on `/healthz:health`; moves all probes from `port: metrics` to `port: health` (8081); removes `initialDelaySeconds` anti-pattern

---

## [2.2.0] — 2026-06-05

### Wave 10 — Context Graph & Autonomy Tier (Agentic SDLC)

#### Added

- **`specs/ai/context-graph.md`** — Spec for the context graph: `GoalState` schema, `ContextGraph` API, `[CONTEXT_GRAPH]` prompt block format, Autonomy-tier prerequisites guard. Closes #18. ADR-0041.
- **`src/agents/context_graph.py`** — `ContextGraph` implementation: `add_sub_goal()`, `mark_complete()`, `mark_blocked()`, `add_constraint()`, `add_gathered_context()`, `add_decision()`, `to_prompt_block()`, `to_dict()` / `from_dict()` for PostgreSQL JSONB persistence. Closes #18.
- **`alembic/versions/0006_add_context_graph_table.py`** — Migration adding `agent_context_graphs` table with JSONB `graph_data` column and indexes on `session_id` and `status`. Closes #18.
- **`infrastructure/feature-flags/flags/autonomy-tier-ready.yaml`** — Guard flag (default: false); comments document all 3 prerequisites required before enabling. Closes #18.
- **`docs/adr/ADR-0041-context-graph-autonomy-tier.md`** — Decision record for the context graph and autonomy-tier prerequisites guard.
- **`tests/unit/agents/test_context_graph.py`** — 25 unit tests covering init, sub-goals, status transitions, constraints, gathered context, decisions, prompt block rendering, serialisation roundtrip, and `AutonomyPrerequisiteError`. All passing.

#### Changed

- **`src/shared/feature_flags.py`** — Add `AutonomyPrerequisiteError` (RuntimeError subclass) and `is_autonomy_tier_ready()`: checks `autonomy-tier-ready` flag then validates learning-mode=active and context_graph.py present; raises `AutonomyPrerequisiteError` if any prerequisite is unmet. Closes #18.

---

### Wave 9 — Agentic Maturity Self-Assessment (Agentic SDLC)

#### Added

- **`specs/ai/agentic-maturity-assessment.md`** — Machine-checkable criteria for the four Gartner maturity levels (Assistance/Automation/Augmentation/Autonomy) with per-level criterion tables and structured output format. Closes #17. ADR-0040.
- **`scripts/agentic_maturity_check.py`** — Self-contained stdlib-only script: evaluates file-system and flag configuration against the four maturity levels; emits a structured report with missing criteria and remediation hints. Current result: AUGMENTATION (Level 3, ~80% Gartner coverage). Closes #17.
- **`docs/adr/ADR-0040-agentic-maturity-model.md`** — Decision record for the anti-agent-washing maturity model.

#### Changed

- **`Makefile`** — Add `agentic-maturity-check` target: `python3 scripts/agentic_maturity_check.py`. Closes #17.
- **`.github/workflows/ci.yml`** — Add informational `agentic-maturity` job: runs on every PR, posts maturity report as a PR comment (non-blocking). Closes #17.

---

### Wave 8 — Governed Tool Registry (Agentic SDLC)

#### Added

- **`specs/ai/tool-registry.md`** — Spec for the governed tool registry: `ToolDefinition` schema, registry interface, permission check matrix, aggregate risk window (Gap T3). Closes #16. ADR-0039.
- **`src/agents/tool_registry.py`** — `ToolRegistry` singleton: `register()`, `get()`, `check_permission()`, `list_by_risk()`, `assert_registered()` (raises `UnregisteredToolError` for unregistered calls); module-level `default_tool_registry` with 3 starter tools. Closes #16.
- **`infrastructure/agent-tools/tools.yaml`** — Canonical tool catalog: `send-email` (high, HITL), `read-db-record` (low), `write-db-record` (medium, HITL), `post-webhook` (high, HITL), `generate-report` (low). Closes #16.
- **`docs/adr/ADR-0039-governed-tool-registry.md`** — Decision record for the governed tool registry.
- **`tests/unit/agents/test_tool_registry.py`** — 21 unit tests covering register, get, unregister, permission checks, list-by-risk, assert_registered, and default registry. All passing.

#### Changed

- **`src/guardrails/audit_logger.py`** — Add `log_tool_invocation(tool_name, session_id, payload_hash, risk_level, outcome)`: records metric, maintains 5-minute rolling risk-weight deque, returns `False` when aggregate exceeds threshold (Gap T3). `__init__` accepts `aggregate_risk_threshold` (default 3.0). Closes #16.
- **`src/observability/metrics.py`** — Add `AGENT_TOOL_INVOCATIONS` Counter (`agent_tool_invocations_total`, labels: `tool_name`, `risk_level`, `outcome`). Closes #16.

---

### Wave 7 — Learn Stage Feedback Loop (Agentic SDLC)

#### Added

- **`specs/ai/learn-stage.md`** — Spec for the Learn stage of the Perceive→Reason→Act→Learn cycle: `OutcomeFeedback` schema, `BiasReport`, learning modes (passive/active), governance guard, metrics. Closes #15. ADR-0038.
- **`src/agents/feedback_learner.py`** — `FeedbackLearner` implementation: `record()` stores HITL outcomes, `get_similar_precedents()` retrieves precedents by action type and payload hash, `build_precedents_block()` renders a `[PRECEDENTS]` prompt block in active mode, `get_bias_summary()` feeds `make agent-feedback-check`. Closes #15.
- **`infrastructure/feature-flags/flags/learning-mode.yaml`** — `learning-mode` feature flag (default: `passive`; `active` requires ADR-0038 sign-off). Closes #15.
- **`docs/adr/ADR-0038-learn-stage-feedback-loop.md`** — Decision record for the Learn stage.
- **`tests/unit/agents/test_feedback_learner.py`** — 21 unit tests covering record, precedent retrieval, block rendering, bias summary, and factory method.

#### Changed

- **`src/agents/orchestrator/orchestrator.py`** — Accept optional `FeedbackLearner`; inject precedents into Reason-stage LLM system prompt when `learning-mode=active`; call `record()` after successful action execution (approved outcome). Closes #15.
- **`src/agents/hitl_gateway.py`** — Accept optional `FeedbackLearner`; call `record()` after every `record_decision()` with the HITL outcome (approved or rejected). Closes #15.
- **`src/shared/feature_flags.py`** — Add `get_learning_mode()` function: reads `learning-mode` flag via OpenFeature SDK, falls back to `"passive"`. Closes #15.
- **`src/observability/metrics.py`** — Add `AGENT_LEARN_PRECEDENTS_INJECTED` Counter (`agent_learn_precedents_injected_total`, labels: `action_type`, `outcome_influenced`). Closes #15.

---

### Wave 6 — Gartner Governance Gate & Business Value (Agentic SDLC)

#### Added

- **`.github/workflows/governance-gate.yml`** — Blocking CI gate: PRs targeting `main` that touch `autonomous-mode*.yaml`, `autonomy-tier-ready.yaml`, or `hitl_gateway.py` require both `governance-council-approved` and `legal-reviewed` labels before merge. Closes #14. ADR-0037.
- **`harness/business-value-check.yml`** — Informational PR gate: checks that agent PRs answer all 6 mandatory Business Value questions; posts advisory comment if any are missing. Closes #14. ADR-0037.
- **`docs/governance/governance-labels.md`** — Label definitions, approval workflow, council composition, and escalation path for governance labels. Closes #14.
- **`docs/adr/ADR-0037-governance-gate-enforcement.md`** — Decision record for machine-enforced governance council approval gate.

#### Changed

- **`skills/sre/prr.md`** — Added "Business Value Gate" section with 6 mandatory ROI questions (baseline metric, measurable target, business sponsor, LLM cost budget, break-even timeline, 30/90/180-day success criteria). Addresses Gartner Gap G2.

---

## [2.1.0] — 2026-06-05

### Wave 5 — Personas & Expansion (Agentic SDLC)

#### Added

- **`docs/quickstart/non-engineer-automation.md`** — Step-by-step guide for product managers, legal, and ops to automate repetitive workflows without writing code; covers workflow spec, GitHub Issue submission, implementation review, and HITL approval. Closes #10.
- **`skills/data/data-pipeline.md`** — Data pipeline skill: Pandas/Polars ingestion patterns, PII classification for analytical datasets (L1–L4), OTel instrumentation, output validation, and synthetic-fixture testing conventions. Closes #10.
- **`skills/sdlc/new-language-extension.md`** — 5-step protocol for adding a language outside the default stack (Python/Java/Go/Node.js): ADR → scaffold → CI gates → skills entry → CLAUDE.md update. Closes #10.
- **`.claude/personas/legal-reviewer.md`** — Legal reviewer persona: `LOW_RISK` autonomy ceiling, permitted paths `docs/**` and `specs/**` only, privacy/compliance skill set. Closes #11.
- **`.claude/personas/ops-analyst.md`** — Ops analyst persona: `MEDIUM_RISK` autonomy ceiling, observability and data-pipeline skill set, permitted read-only commands. Closes #11.
- **`specs/automation/automation-spec-template.md`** — Plain-language automation spec template with sections for trigger, input, steps, output, guardrails (PII checklist), rollback, SLA, and HITL approval gate. Closes #11.
- **`docs/quickstart/self-service-automation.md`** — End-to-end guide: spec → GitHub Issue (`automation-request` label) → Claude scaffolds → PR review → HITL approval → HOTL promotion. Closes #11.

#### Changed

- **`CLAUDE.md §4`** — Added `skills/data/data-pipeline.md` row to the Core Skills Activation Table. Closes #10.
- **`CLAUDE.md §9`** — Added §9.1 Personas subsection: persona table, activation instructions, and constraint that personas may only restrict (never expand) default permissions. Closes #11.

#### Closed (already implemented in Wave 3)

- **Issue #12** — `docs/adr/ADR-0020-finops-cost-allocation.md` ROI model appendix (cost-per-task formula, net-new multiplier, metrics table, budget allocation) was delivered in Wave 3 as part of Issue #7. Closes #12.

### Wave 4 — CI Intelligence (Agentic SDLC)

#### Added

- **`.github/workflows/ci-ai-review.yml`** — Informational AI-assisted PR review: captures first 200 lines of diff, sends to Claude API, posts structured findings comment covering spec reference, guardrail preservation, test coverage, PII literals, and architecture rules. Gracefully skips if `ANTHROPIC_API_KEY` is absent. Closes #8.
- **`docs/adr/ADR-0035-ai-assisted-ci-review.md`** — Decision record for the AI-assisted CI review gate; includes path-to-blocking-gate criteria. Closes #8.
- **`skills/devsecops/agentic-cyber-defense.md`** — 6-section skill: 5-step automated response protocol, agent-readable finding format, GitHub Security Advisory creation, tool-specific remediation guidance (Bandit/Trivy/gosec), and escalation decision tree. Closes #9.
- **`docs/adr/ADR-0036-agentic-cyber-defense.md`** — Decision record for automated security advisory creation and `security_finding_total` metric integration. Closes #9.

#### Changed

- **`CLAUDE.md §4`** — Added two new rows to the Core Skills Activation Table: `skills/devsecops/agentic-cyber-defense.md` and `skills/sdlc/agent-onboarding.md`. Closes #8, #9.
- **`docs/adr/README.md`** — Added index entries for ADR-0031 through ADR-0036 (all Agentic SDLC ADRs from Waves 1–4).

### Wave 3 — Multi-Agent Infrastructure (Agentic SDLC)

#### Added

- **`specs/ai/sub-agent-specialization.md`** — Spec for pluggable sub-agent registry: `AgentConfig` schema, risk-level semantics, built-in specializations, observability contract. Closes #6.
- **`src/agents/harness/sub_agent_registry.py`** — `SubAgentRegistry` with `register`, `get`, `list_by_risk_level`, `all`, `unregister`; module-level `default_registry` pre-populated with `security-reviewer` (high) and `document-generator` (low). Closes #6.
- **`docs/adr/ADR-0032-sub-agent-specialization-registry.md`** — Decision record for sub-agent registry. Closes #6.
- **`tests/unit/agents/harness/test_sub_agent_registry.py`** — 19 unit tests for `SubAgentRegistry` (100% pass). Closes #6.
- **`infrastructure/monitoring/grafana/dashboards/agent-productivity.json`** — Grafana dashboard: session velocity, net-new/planned ratio, cycle time p50/p95, token cost per task, sub-agent latency/errors, session duration. Closes #7.

#### Changed

- **`src/observability/metrics.py`** — Added 5 new metrics: `agent_subtask_duration_seconds`, `agent_subtask_error_total` (Issue #6); `agent_session_tasks_total`, `agent_session_duration_seconds`, `agent_cycle_time_seconds` (Issue #7); plus `security_finding_total` (pre-emptive for Issue #9). Added helpers `record_subtask`, `record_session_task`, `record_cycle_time`. Closes #6, #7.
- **`docs/adr/ADR-0020-finops-cost-allocation.md`** — Added ROI model appendix: cost-per-task formula, net-new work multiplier, metrics table, budget allocation guidance for formerly non-viable work. Closes #7.

### Wave 2 — Agentic SDLC Core (Agentic SDLC)

#### Added

- **`skills/sdlc/agent-onboarding.md`** — 5-step machine-readable session bootstrap skill for Claude Code. Closes #4.
- **`CLAUDE_SESSION_INIT.md`** — Compact repo-specific session primer; loaded at every session start to orient the agent without reading the full codebase. Closes #4.
- **`docs/quickstart/agent-onboarding.md`** — Human guide for supervising and verifying agentic session bootstraps. Closes #4.
- **`docs/adr/ADR-0031-agent-onboarding-protocol.md`** — Decision record for the agent onboarding protocol. Closes #4.
- **`specs/ai/long-running-session.md`** — Spec for durable agent sessions: checkpoint format, resume protocol, failure taxonomy, `task_type` field. Closes #5.
- **`src/agents/harness/session_checkpoint.py`** — `SessionCheckpoint` class: Redis-backed (TTL=7d) with local JSON fallback; `save`, `resume`, `mark_step_complete`, `delete`. Closes #5.
- **`docs/adr/ADR-0033-long-running-agent-session-durability.md`** — Decision record for session checkpoint/resume strategy. Closes #5.
- **`docs/sre/runbooks/RB-005-agent-session-recovery.md`** — Runbook for inspecting, resuming, and force-deleting interrupted agent session checkpoints. Closes #5.
- **`tests/unit/agents/harness/test_session_checkpoint.py`** — Unit tests for `SessionCheckpoint` lifecycle (≥ 80% coverage). Closes #5.

#### Changed

- **`CLAUDE.md §2`** — Added "Agentic Session Bootstrap" pre-step (Pre-0a–0e) before the SDD Cycle; references `skills/sdlc/agent-onboarding.md` and §14 escalation. Closes #4.

### Wave 1 — Safety & Compliance (Agentic SDLC)

#### Added

- **`docs/adr/ADR-0034-agentic-escalation-protocol.md`** — Decision record for the mandatory in-session escalation protocol. Closes #3.
- **`docs/ai-governance/dual-use-registry.md`** — Append-only registry for dual-use risk assessments per `action_type`. Closes #1.
- **`specs/ethics/ethical-ai-principles.md §4`** — New "Dual-Use Risk Assessment" section with a six-question mandatory checklist (D-01–D-06) and mitigation registry format. Closes #1.
- **`CLAUDE.md §14`** — New "Agentic Escalation Protocol" section defining six hard escalation triggers, `[HITL-ESCALATE]` block format, and `[HITL-NOTE]` for near-miss acknowledgement. Closes #3.

#### Security

- **`SECURITY.md`** — Added dual-use exploitation as a reportable AI-specific security class; linked to the dual-use registry and ethical-ai-principles checklist. Closes #1.
- **`.github/workflows/ci.yml` (sbom job)** — Added SBOM component-count gate (fails on 0 components) and cosign attestation step for push events. Closes #2.

## [2.0.0] — 2026-06-05

### Added

- **Repository-Template-v2** — Initial release of the v2 generation of the enterprise monorepo template, published as a GitHub Template Repository (`is_template: true`).

### Changed

- Repository renamed from `Repository-Template` to `Repository-Template-v2`; remote origin updated accordingly.
- Version lineage reset to `2.0.0`; codebase based on `v1.26.19` of the original template.

## [1.26.19] — 2026-06-01

### Fixed

- **`pr-governance.yml`** — Added `\w+(docs):` scope exemption to the spec-reference check; `feat(docs):` and similar docs-scoped PRs do not require a product spec (same rationale as `\w+(ci):`). Fixes retroactive failure on PR #60.
- **`ci-go.yml`** — Updated `GO_VERSION` from `1.23` to `1.24`; fixed `golangci-lint`, `govulncheck`, and all `go test` commands to run inside the module directory via subshell `(cd "$dir" && ...)` — they were failing with `directory prefix does not contain main module` when invoked from the repo root; fixed coverage profile path to write to `$WORKSPACE` so the coverage threshold step can find the files; bumped Kafka integration service image to `cp-kafka:7.8.0`.
- **`ci-frontend.yml`** — Updated `NODE_VERSION` from `20` to `22`; removed `cache: pnpm` and `cache-dependency-path: .../pnpm-lock.yaml` from all three `setup-node` steps — `pnpm-lock.yaml` is not tracked in this repo (removed v1.26.3) so the cache step was failing with `specified paths were not resolved`.
- **`ci-java.yml`** — Replaced all `mvn ... -pl $(find services ...)` invocations with per-service `(cd "$dir" && mvn ...)` loops; Maven's `-pl` flag requires a parent `pom.xml` in the working directory which this repo does not have; bumped Kafka integration service image to `cp-kafka:7.8.0`.

## [1.26.18] — 2026-06-01

### Added

- **`SETUP.md`** — First-run onboarding checklist with 6 numbered steps; clearly flags the 3 CI-gate blockers (CODEOWNERS, image registry, `.env` secrets) that prevent every PR from merging until resolved. Closes #56.
- **`docs/quickstart/deploy-to-production.md`** — End-to-end production deployment guide: change classification (standard/normal/emergency), PRR pre-flight, canary rollout (5%→25%→100% with SLO gates), rollback procedure (`make rollback`, RTO < 1h), and post-deploy DORA/change-log verification. Linked from `docs/quickstart/README.md` and `README.md`. Closes #59.

### Removed

- **`docs/sbom.json`** — Removed from the repo; the file was auto-committed by the `sbom` CI job on every push, causing recurring SBOM-only patch releases (v1.26.12/15/16/17) and merge conflicts on every branch sync. The SBOM is still generated by Syft and uploaded as a 90-day workflow artifact on every build. The OCI attestation in `cd-staging.yml` remains the authoritative signed copy. Closes #58.
- **`stefanzweifel/git-auto-commit-action`** step removed from `ci.yml` sbom job (no longer needed).
- **`docs/sbom.json` exclusion** removed from `secret-scanning.yml` (file no longer exists).
- **`contents: write`** permission removed from the `sbom` job (downgraded to `read`).

### Fixed

- **GitHub Actions Node.js 24 upgrade** — Pinned all 6 actions running on deprecated Node.js 20 to their latest Node.js 24-compatible SHA releases ahead of the June 16 2026 forced migration: `codecov/codecov-action` v4.6.0→v6.0.1, `docker/build-push-action` v5.4.0→v7.2.0, `docker/setup-buildx-action` v3.9.0→v4.1.0, `actions/checkout` @v4→v6.0.2 (SHA-pinned), `actions/upload-artifact` @v4→v7.0.1 (SHA-pinned), `stefanzweifel/git-auto-commit-action` @v5→v7.1.0 (SHA-pinned). Closes #57.

### Changed

- **`README.md`** — Customisation table now prominently links to `SETUP.md` and labels the 3 CI-gate blockers with `[BLOCKER]` callouts.
- **`README.md`** — Updated language versions in "What you get" table and repo tree: Go 1.23→1.24, Node 20→22, Next.js 14→15, Spring Boot 3.3→3.4 (reflects v1.26.10 EOL upgrades).

## [1.26.17] — 2026-06-01

### Changed

- **`docs/sbom.json`** — Refreshed by CI Syft scan (auto-committed; reflects current dependency graph).

## [1.26.16] — 2026-06-01

### Changed

- **`docs/sbom.json`** — Refreshed by CI Syft scan (auto-committed; reflects current dependency graph).

## [1.26.15] — 2026-06-01

### Changed

- **`docs/sbom.json`** — Refreshed by CI Syft scan (auto-committed; reflects current dependency graph).

## [1.26.14] — 2026-06-01

### Fixed

- **`pr-governance.yml`** — Added `chore(release):` exemption to the issue-reference gate (PR #49); release version-bump PRs have no associated feature issue. Added `\w+(ci):` scope exemptions to both the issue-reference and spec-reference gates; CI maintenance PRs (`fix(ci):`, `chore(ci):`) require neither a feature issue nor a product spec.

## [1.26.13] — 2026-06-01

### Fixed

- **`pr-governance.yml`** — Added `chore(release):` title exemption to the issue-reference gate; release PRs are version bumps with no associated feature issue and were failing this check on every release (first caught in run [26756255904](https://github.com/valdomirosouza/Repository-Template/actions/runs/26756255904) for v1.26.12).

## [1.26.12] — 2026-06-01

### Changed

- **`docs/sbom.json`** — Refreshed by CI Syft scan (auto-committed; reflects current dependency graph).

## [1.26.11] — 2026-06-01

### Fixed

- **`secret-scanning.yml`** — Added `--exclude-files 'docs/sbom\.json'` to the detect-secrets scan command; Syft-generated SBOM content (hex hashes, UUIDs, SHA digests, CPE strings) was producing 48 false positives on every CI push.
- **`.secrets.baseline`** — Regenerated with the same exclusion filter; zero genuine new findings.

## [1.26.10] — 2026-06-01

### Changed

- **Go 1.23 → 1.24** (`services/event-worker/go.mod`, `event-worker/Dockerfile`, `scaffold/templates/go/Dockerfile`) — Go 1.23 reached EOL 2025-08-13. Closes #31.
- **Node.js 20 → 22** (`frontend/frontend/package.json` engines, `frontend/frontend/Dockerfile`, `scaffold/templates/frontend/Dockerfile`) — Node.js 20 LTS reached EOL 2026-04-30. Closes #32.
- **Spring Boot 3.3.5 → 3.4.5** (`services/domain-service/pom.xml`) — Spring Boot 3.3.x OSS support ended 2025-11-23. Closes #33.
- **Next.js 14.2.29 → 15.2.4** (`frontend/frontend/package.json` — `next` + `eslint-config-next`) — Next.js 14 reached EOL 2025-10-17. Closes #34.
- **Apache Kafka CP 7.7.0 → 7.8.0** (`docker-compose.yml`, `ci.yml` integration test service) — Kafka 3.7 community EOL ~2025-10. Closes #35.
- **Kubernetes 1.31 → 1.32** (`infrastructure/terraform/modules/kubernetes/variables.tf`) — K8s 1.31 community EOL 2025-10-28. Closes #36.
- **`docs/eol-inventory.yaml`** — Updated versions and statuses for all six upgraded components; zero EOL items remaining.

## [1.26.9] — 2026-06-01

### Fixed

- **`ci.yml` — `sbom` job** — Removed cosign install + attest steps; the `build` job uses `push: false` so no image exists in the registry for CI to sign. The job now only generates the SBOM with Syft and uploads it as a 90-day workflow artifact. Fixes CI failure in run [26752567193](https://github.com/valdomirosouza/Repository-Template/actions/runs/26752567193).
- **`cd-staging.yml` — `deploy-staging` job** — Added Syft SBOM generation from the pushed image + `cosign attest` immediately after the image push (where the image is actually in the registry). Updated `cosign verify-attestation` certificate identity to reference `cd-staging.yml`. Lowercased image name consistently across all new steps.

## [1.26.8] — 2026-06-01

### Fixed

- **`ci.yml` — `sbom` job** — Lowercased the image name in the `cosign attest` step using `tr '[:upper:]' '[:lower:]'`; `github.repository` contains uppercase letters (`Repository-Template`) which are invalid in OCI references and caused cosign to fail with `could not parse reference`. Matches the pattern already used in the `build` job. Fixes run [26751670496](https://github.com/valdomirosouza/Repository-Template/actions/runs/26751670496).

## [1.26.7] — 2026-06-01

### Added

- **`docs/eol-inventory.yaml`** — Quarterly EOL inventory covering 11 runtime/framework/infra components (Python, Java, Go, Node.js, FastAPI, Spring Boot, Next.js, PostgreSQL, Redis, Kafka, Kubernetes). Six components flagged `eol`; upgrade tracking issues: #31 #32 #33 #34 #35 #36.
- **`docs/sbom.json`** — CycloneDX SBOM placeholder; replaced automatically by CI on every push via Syft.
- **`ci.yml` — `sbom` job** — Generates a CycloneDX SBOM with Syft after `build`, uploads a 90-day workflow artifact, and attaches a keyless Cosign OCI attestation on push events. Closes PDR SBOM gap.
- **`cd-staging.yml` — cosign pre-flight** — `cosign verify-attestation` step added to `deploy-staging` before Helm upgrade; `id-token: write` permission added for keyless OIDC signing.

## [1.26.6] — 2026-06-01

### Added

- **`LICENSE`** — MIT License (Copyright 2026 Valdomiro Souza).
- **`.claude/skills/` (29 skill directories)** — Ported all skills from `skills/` to proper Claude Code slash-command format (`<name>/SKILL.md` with `name:` + `description:` frontmatter). Each skill is auto-discoverable and available as a `/skill-name` command. Replaced 21 flat `.md` files (not discoverable) with proper directories covering: AI (guardrails, harness), API, change management (CAB, deploy/rollback, RFC), compliance (ISO 27001, SOX), DevSecOps (OWASP, pipeline, secret scanning), domain modeling, testing, ethical AI, observability, privacy (data rights, GDPR, LGPD, PII), SDLC, SRE (capacity, CUJ, DORA, golden signals, incident, PRR), and token efficiency (RTK setup, commands, hygiene).
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.6`.

### Changed

- **`README.md`** — License badge updated from `Proprietary` to `MIT`.
- **`pyproject.toml`** — `license = {text = "MIT"}` added to `[project]` metadata.

### Removed

- 21 flat `.md` files from `.claude/skills/` (wrong format — replaced by proper skill directories above).

## [1.26.5] — 2026-06-01

- **`README.md`** — License badge updated from `Proprietary` to `MIT`.
- **`pyproject.toml`** — Added `license = {text = "MIT"}` to `[project]` metadata.

## [1.26.5] — 2026-06-01

### Added

- **`.claude/skills/run-repository-template/`** — Run skill for the FastAPI server: `smoke.sh` driver exercises 7 endpoints (health, ready, docs, metrics, HITL status, POST/GET requests) with no Docker required; `SKILL.md` documents the agent path, gotchas, and troubleshooting. All checks verified passing.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.5`.

## [1.26.4] — 2026-06-01

### Changed

- **`.secrets.baseline`** — Removed stale `frontend/frontend/pnpm-lock\\.yaml` entry from the `should_exclude_file` patterns array; the file was removed from git tracking in v1.26.3, making the filter entry obsolete.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.4`.

## [1.26.3] — 2026-06-01

### Changed

- **`.gitignore`** — Added patterns for Claude Code session prompt files (`*-improvement-prompt.md`, `*-token-efficiency-prompt.md`) and `frontend/frontend/pnpm-lock.yaml` (environment-specific lock file).
- **`docs/compliance/remediation-register.md`** — Deduplicated accumulated duplicate table sections (file had Open/Done tables repeated 3–4× from incremental edits); replaced instance-specific handle with generic placeholder; content and resolution details preserved.
- **`.github/workflows/secret-scanning.yml`** — Removed `--exclude-files 'frontend/frontend/pnpm-lock\.yaml'` exclusion (file no longer tracked).
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.3`.

### Removed

- **`frontend/frontend/pnpm-lock.yaml`** — Untracked from git (environment-specific; was causing 644 secret-scanner false positives; regenerated on `pnpm install`).

- **`frontend/frontend/pnpm-lock.yaml`** — Untracked from git (environment-specific; was causing secret-scanner false positives; regenerated on `pnpm install`).

## [1.26.2] — 2026-06-01

### Fixed

- **`.github/workflows/pr-governance.yml`** — `issue-referenced` job now exempts `docs:` type PR titles and adds a `no-issue` label escape hatch; previous behaviour caused every documentation-only PR to fail even when no issue was required.
- **`.github/workflows/` (13 files)** — Updated four GitHub Actions from Node.js 20 to Node.js 24 compatible versions ahead of the June 16 deprecation: `actions/checkout` v4.3.1→v6.0.2, `actions/setup-python` v5.6.0→v6.2.0, `actions/upload-artifact` v4.6.2→v7.0.1, `actions/github-script` v7.1.0→v9.0.0.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.2`.

## [1.26.1] — 2026-05-31

### Changed

- **`README.md`** — Updated ADR count (21→30), added `docs/governance/` to repo tree, added `skills/token-efficiency/` to skills tree, added ADR-0026–0030 to key decisions table.
- **`docs/adr/README.md`** — Added ADR-0026–0030 to the Core Architecture index table.
- **`mkdocs.yml`** — Added `sre/on-call-schedule.md`, `sre/deployment-strategy.md`, `sre/finops.md`, `sre/capacity-planning.md` to SRE nav; added new Governance section (team-topology, RACI matrix, owner onboarding).
- **`skills/README.md`** — Added three `token-efficiency/` skill rows (rtk-setup, rtk-commands, rtk-context-hygiene) to the skills catalog.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.1`.

## [1.26.0] — 2026-05-31

### Added

- **`docs/sre/finops.md`** — FinOps budget template and cost-allocation guide: cost centers, monthly budget table, required cost allocation tags, alert thresholds (70/90/100%), 15-item optimization checklist, chargeback/showback model, maturity self-assessment, and cost review cadence. Closes #22. Refs: FIN-001, ADR-0020.
- **`docs/sre/capacity-planning.md`** — Capacity planning template: baseline resource sizing per runtime (Python/Java/Go/Node), headroom rules with Prometheus alerts, horizontal vs vertical scaling decision matrix, HPA configuration template, per-service capacity worksheet, traffic growth model, load testing prerequisites, and quarterly review checklist. Closes #23. Refs: CAP-001.
- **`docs/governance/team-topology.md`** — Team topology guide: four team types (stream-aligned, enabling, platform, complicated-subsystem), three interaction modes, squad ownership map, Team API definition template, interaction mode map, RACI/CODEOWNERS sync rules, and customization guide. Closes #24. Refs: TT-001.
- **`specs/sre/finops.md`**, **`specs/sre/capacity-planning.md`**, **`specs/governance/team-topology.md`** — Specs FIN-001, CAP-001, TT-001.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.26.0`.

## [1.25.1] — 2026-05-31

### Fixed

- **`.github/workflows/secret-scanning.yml`** — YAML parse error: indented Python heredoc content inside `run: |` block so YAML block scalar is not terminated prematurely. Closes #17.
- **`.github/workflows/cd-production.yml`** — YAML parse errors in `deploy-canary` and `promote-canary-25` jobs: indented `python3 -c "..."` body lines to stay within YAML block scalar. Closes #18.
- **`.github/workflows/sbom.yml`** — Workflow file issue: moved `id-token: write` to workflow-level permissions; replaced `secrets.*` comparison in step `if:` with env-var pattern; guarded `cosign attest` with `if: vars.CONTAINER_REGISTRY != ''` so it skips gracefully when no registry is configured. Closes #19.
- **`.github/workflows/index-docs.yml`** — Postgres service container failed to start: added `|| 'dev-postgres'` fallback to `POSTGRES_PASSWORD` and both `DATABASE_URL` references so the workflow runs in repos without the secret configured. Closes #20.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.25.1`.

## [1.25.0] — 2026-05-31

### Added

- **`skills/token-efficiency/`** — Token-efficiency skill group: `rtk-setup.md` (one-time install), `rtk-commands.md` (monorepo command reference), `rtk-context-hygiene.md` (session discipline rules). Estimated 60–80% token reduction per Claude Code session. Refs: RTK-001, ADR-0030.
- **`.rtk/filters.toml`** — Project-level RTK filter config; covers make targets, alembic, trivy, helm, terraform, uv, pre-commit, syft, and cosign. Refs: RTK-001, ADR-0030.
- **`CLAUDE.md §13`** — Token Efficiency Rules: mandatory RTK usage contract for every Claude Code session. Refs: RTK-001, ADR-0030.
- **`docs/adr/ADR-0030-rtk-token-efficiency.md`** — ADR documenting RTK integration as a developer-only tool.
- **`specs/tooling/rtk-token-efficiency.md`** — Spec RTK-001 defining problem statement, solution, scope, and acceptance criteria.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.25.0`.

## [1.24.0] — 2026-05-31

### Added

- **`docs/sre/on-call-schedule.md`** — On-call schedule template covering rotation structure (primary/secondary/manager tiers), escalation policy with acknowledgement SLAs (P0 5 min → P3 next day), paging rules mapped to Prometheus alert severities, on-call responsibilities, handoff procedure with note template, post-incident action SLAs, onboarding checklist, and sustainability guidelines. Closes #14.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.24.0`.

## [1.23.1] — 2026-05-31

### Fixed

- **`.github/workflows/secret-scanning.yml`** — Added `frontend/frontend/pnpm-lock.yaml` to `--exclude-files` list; pnpm lock file hashes were generating 644 false-positive Base64 entropy findings. Closes #12.
- **`.secrets.baseline`** — Regenerated with pnpm-lock.yaml exclusion; reduced from 645 to 1 entry.
- **`.github/workflows/release.yml`** — Added `continue-on-error: true` to `release-please-action` step; workflow now degrades gracefully when the "Allow Actions to create PRs" GitHub repo setting is disabled (manual releases are used instead). Closes #12.
- **`.github/workflows/sbom.yml`** — Registry login step now conditional on `REGISTRY_USERNAME` and `REGISTRY_PASSWORD` secrets being set; SBOM generation no longer fails when registry credentials are not configured. Closes #12.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.23.1`.

## [1.23.0] — 2026-05-31

### Added

- **`docs/governance/raci-matrix.md`** — RACI matrix covering 7 process domains (SDLC, security, privacy, AI governance, change management, SRE, infrastructure) with 60+ process rows mapped to 8 roles (TL, PO, ENG, SEC, DPO, AIGOV, SRE, DEV) and validation rules. Closes #10.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.23.0`.

## [1.22.0] — 2026-05-31

### Added

- **`docs/sre/deployment-strategy.md`** — Deployment strategy guide: decision matrix (canary/blue-green/rolling/feature-flag/hotfix), per-strategy mechanics, DB migration rules, SLO gate configuration and per-service tuning, hotfix deploy path, feature flag hygiene, 6-factor risk scoring matrix, and DORA impact tracking. Closes #8. Refs: ADR-0027, ADR-0028.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.22.0`.

## [1.21.0] — 2026-05-31

### Added

- **`docs/compliance/dependency-policy.md`** — Dependency policy covering approved registries (Python/Java/Go/Node/containers/Actions), licence allowlist/blocklist, new-dependency approval process, version pinning requirements, update SLAs by CVE severity, SCA gate thresholds, and vendoring rules. Closes #7.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.21.0`.

### Fixed

- **`src/observability/dora_metrics.py`** — Replaced EN dash with hyphen in `dora_change_failure_rate` docstring (Ruff RUF001).
- **`.github/workflows/ci.yml`** — Docker image tag and Trivy `image-ref` now lowercased via `tr '[:upper:]' '[:lower:]'`; prevents build failure when repository name contains uppercase letters.

## [1.20.1] — 2026-05-31

### Changed

- **`docs/runbooks/README.md`** — Runbook index expanded with Alert → Runbook mapping (all 35 Prometheus alerts linked to their runbook) and Service → Runbook mapping (on-call quick reference by service and scenario).
- **`version.txt` / `pyproject.toml`** — Bumped to `1.20.1`.

## [1.20.0] — 2026-05-31

### Added

- **`docs/runbooks/RB-004-db-connection-failure.md`** — Incident response playbook for PostgreSQL connection failures: symptoms, pool exhaustion, crash recovery, disk-full, and escalation matrix.
- **`docs/runbooks/RB-005-kafka-consumer-lag.md`** — Incident response playbook for Kafka consumer lag: consumer pod down, slow consumer scale-out, poison-pill handling, schema mismatch, and DLQ verification.
- **`docs/runbooks/RB-006-auth-failure.md`** — Incident response playbook for JWT/auth failures: JWKS unreachability, key rotation gaps, clock skew, brute-force detection, and security escalation path.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.20.0`.

### Changed

- **`docs/runbooks/README.md`** — Runbook index expanded to all six runbooks (RB-001–RB-006) with owner and last-reviewed columns; RB-003 (HITL recovery) was previously missing from the index.

## [1.19.0] — 2026-05-31

### Added

- **`.github/ISSUE_TEMPLATE/feature_request.md`** — Feature request issue template with spec reference, acceptance criteria, ISO 27001 change type, pre-implementation checklist, and definition of done aligned with CLAUDE.md §2 SDD cycle.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.19.0`.

## [1.18.1] — 2026-05-31

### Changed

- **`.github/pull_request_template.md`** — Updated SDD step count (7 → 10), added ISO 27001 change type section with RFC_ID field, expanded PR checklist with SOX/ISO 27001/DORA/OWASP/DevSecOps compliance gates from CLAUDE.md §7, and referenced harness compliance check IDs. Refs: ADR-0027, ADR-0028, ADR-0029.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.18.1`.

## [1.18.0] — 2026-05-31

### Added

- **`docs/adr/ADR-0026-sox-audit-log-immutability.md`** — ADR for SOX-conditional three-layer immutable audit log strategy (PostgreSQL INSERT-only trigger + Kafka infinite retention + S3 cold storage). Refs: SPEC-sox-controls, ADR-0026.
- **`docs/adr/ADR-0027-iso27001-change-management.md`** — ADR for three-tier change classification (Standard/Normal/Emergency) enforced via GitHub PR labels and `cab-check` CI gate. Refs: SPEC-iso27001-change-management, ADR-0027.
- **`docs/adr/ADR-0028-dora-metrics.md`** — ADR for Prometheus-native DORA metrics instrumentation (four metrics, Pushgateway, Grafana dashboard, monthly report). Refs: SPEC-dora-metrics, ADR-0028.
- **`docs/adr/ADR-0029-devsecops-pipeline-security.md`** — ADR for DevSecOps pipeline hardening: Checkov IaC scan, OWASP ZAP DAST, SHA-pinned actions, Gitleaks CI, digest-pinned base images, least-privilege workflow permissions. Refs: ADR-0029.
- **`specs/compliance/sox-controls.md`** — SOX ITGC spec (CC1–CC7), audit event schema, retention policy, and acceptance criteria. Conditional on SEC-listed status.
- **`specs/compliance/iso27001-change-management.md`** — ISO 27001 A.12.1 change management spec: classification matrix, deploy/rollback flowcharts, CAB integration, evidence retention.
- **`specs/observability/dora-metrics.md`** — DORA metrics instrumentation spec: metric definitions, tier thresholds, Grafana panel spec, alerting rules, monthly report template.
- **`skills/compliance/sox.md`** — SOX compliance skill with ITGC checklist, application controls, and evidence artifact matrix. Conditional on SEC-listed status.
- **`skills/compliance/iso27001-change-management.md`** — ISO 27001 change management skill with deploy/rollback procedures and audit evidence matrix.
- **`skills/sre/dora-metrics.md`** — DORA metrics skill with Prometheus metric definitions, `cd-production.yml` integration snippet, and monthly report guidance.
- **`skills/devsecops/owasp-top10.md`** — OWASP Top 10 enforcement skill with per-control checklist (A01–A10), ZAP DAST integration, and OWASP LLM Top 10 cross-reference.
- **`skills/devsecops/pipeline-security.md`** — DevSecOps pipeline security skill: stage security map, GitHub Actions hardening, Checkov, Gitleaks, container hardening, SBOM+provenance workflow.
- **`src/observability/dora_metrics.py`** — Prometheus metric registrations for all four DORA metrics (`dora_deployments_total`, `dora_lead_time_seconds`, `dora_change_failure_rate`, `dora_mttr_seconds`). Refs: ADR-0028.
- **`infrastructure/monitoring/grafana/dora-metrics.json`** — Grafana dashboard with four DORA panels (Deployment Frequency, Lead Time p50/p90, Change Failure Rate gauge, MTTR p50/p90) and Elite threshold annotations. Refs: ADR-0028.
- **`docs/sox/access-review.md`** — Quarterly SOX access review template (CC7 evidence). Conditional on SEC-listed status.
- **`docs/change-log/SCHEMA.md`** — Append-only change-log entry schema (deploy and rollback events) for ISO 27001 A.12.1 and SOX CC5 audit evidence. Refs: ADR-0027.

### Changed

- **`CLAUDE.md`** — §3.2 Security Rules expanded with OWASP Top 10 and OWASP LLM Top 10 controls; §4 Skill Activation Table gains five new rows (SOX, ISO 27001 CM, DORA, OWASP Top 10, DevSecOps Pipeline); §7 PR Checklist gains eleven compliance gate items (SOX, ISO 27001, DORA, OWASP, DevSecOps); new §10 SOX Compliance Rules (conditional), §11 ISO 27001 Change Management Rules, and §12 DORA Metrics — Mandatory Tracking; ADR reference updated to ADR-0026–0029.
- **`harness/code-check.yml`** — Added `compliance_checks` block: SOX-01–03, ISO-CM-01–03, OWASP-A03/A08/A09, DSEC-01–03, DORA-01.
- **`harness/release-check.yml`** — Added `pre_release_compliance` block: REL-SOX-01, REL-ISO-01, REL-DORA-01, REL-OWASP-01, REL-SBOM-01.
- **`harness/staging-check.yml`** — Added `staging_compliance_gates` block: STG-DAST-01, STG-ROLLBACK-01, STG-DORA-01.
- **`.github/workflows/cd-production.yml`** — Added `cab-check` job (validates change-type label and RFC_ID before deploy); `emit-dora-event` job (pushes DORA metrics to Pushgateway after every deploy); `record-change-evidence` job (appends deploy record to `docs/change-log/`). Refs: ADR-0027, ADR-0028.
- **`.github/workflows/cd-staging.yml`** — Added `dast-scan` job (OWASP ZAP full scan as blocking gate after smoke tests; archives report to `docs/security/zap-reports/`). Refs: ADR-0029.
- **`docs/sre/slo/slo.yaml`** — Bumped to v1.2; added `dora_mttr_target_seconds: 3600` (DORA Elite MTTR target). Refs: ADR-0028.
- **`version.txt` / `pyproject.toml`** — Bumped to `1.18.0`.

## [1.17.7] — 2026-05-29

### Changed

- **README version badge** updated to `1.17.6`.

## [1.17.6] — 2026-05-29

### Changed

- **README** version badge corrected to `1.17.5`; `services.yaml` bolded and promoted to top
  of the minimum customisation table; glossary link added below the table; Alertmanager
  (port 9093) added to the infrastructure table; `autonomous-mode` verify command added to
  the Feature Flags section.
- **`docs/quickstart/python-backend.md`** Python version corrected from `3.12` to `3.13` in
  stack header and prerequisites table.
- **`.env.example`** header now points to `src/shared/config.py` as the authoritative
  reference for all available settings fields.
- **`CONTRIBUTING.md`** unimplemented "Container scan" quality gate removed from the blocking
  gates table.
- **`CLAUDE.md`** §4 skill table gains `incident-response` row; §2 Step 5 links to
  `docs/privacy/` for the DPIA/RIPD review process.
- **`docs/change-management/rfc/RFC-TEMPLATE.md`** created — structured RFC template covering
  status, context, alternatives, impact assessment, rollout/rollback plans, timeline, and
  open questions.
- **`.gitignore`** excludes `src/shared/generated/grpc/` (auto-generated gRPC stubs).

## [1.17.5] — 2026-05-29

### Changed

- **README version badge** updated from `1.17.0` to `1.17.4`.

## [1.17.4] — 2026-05-29

### Changed

- **`MONOREPO-STRUCTURE-EN.md` accuracy pass.** Synced the architectural reference document
  with the actual repository state: version header corrected (`2.0.0` → `1.17.3`), 19
  non-existent files removed from the directory tree, 7 paths/names corrected (threat-model
  location, tracer.py, proto filenames, k6 scripts, chaos experiments, CI workflows), and 9
  missing directories added (`docs/quickstart/`, `docs/compliance/`, `docs/governance/`,
  `services/`, `frontend/`, `scaffold/`, `infrastructure/k8s/`, plus root config files).

## [1.17.3] — 2026-05-29

### Removed

- **`docs/audit/expert-audit-2026-05-26.md` deleted.** Internal development audit containing
  construction-time tracking detail (REM-NNN references, fix commit hashes) irrelevant to
  template adopters. The `docs/audit/` folder is now empty and ready for adopter-owned audit
  records.

## [1.17.2] — 2026-05-29

### Removed

- **SETUP/ folder deleted.** The 14 Claude Code scaffolding prompts and their README were
  internal build artefacts used to construct this template from scratch. They are not needed
  by template adopters and have been removed to keep the repository clean.

## [1.17.1] — 2026-05-29

### Changed

- **Repository renamed** from `template-monorepo` to `Repository-Template`. All URLs, badges,
  template clone commands, pact metadata, and CHANGELOG comparison links updated accordingly.

- **Quick Start onboarding** (README). Consolidated the previous "Use this template",
  "End-to-end demo", and "5-step setup" sections into a single **Clone → Initial Setup → Code**
  flow. Added devcontainer alternative, `openssl rand -hex 32` hint for `SECRET_KEY`, direct
  links to API docs and observability UIs, and a minimum-customisation table.

- **CODEOWNERS** replaced single-owner placeholder with semantic team handles
  (`@your-org/platform-team`, `@your-org/tech-leads`, `@your-org/privacy-team`,
  `@your-org/ai-governance`, `@your-org/security-team`, `@your-org/sre-team`,
  `@your-org/devops-team`). HITL gateway now requires dual approval from two distinct teams.

- **CHANGELOG comparison links** extended from `v1.3.0` up to `v1.17.0` — all 27 released
  versions now have a working diff link.

- **7-step workflow enforcement (governance audit).** Closed enforcement gaps in the mandatory
  development cycle (CLAUDE.md §2): `pr-governance.yml` now has a blocking `issue-referenced`
  gate (Step 1 was entirely unenforced at CI level); `harness/doc-check.yml` gains
  `issue-referenced` and `workflow-compliance` gates; `pull_request_template.md` gains a
  Workflow Compliance section requiring Steps 1–3 to be ticked before merge.
  `bug_report.md` adds Referenced Spec field, Step 2 validation checklist, and Definition of
  Done; `change_request.md` marks spec reference required for all change types and adds Step 2
  checklist and Step 3 implementation plan section. `CLAUDE.md` adds ADR-0001–0025 row to the
  Key Layers table and clarifies §4 skill loading mechanism.

- **README version badge** corrected from `1.9.0` → `1.17.0`; `CLAUDE.md` version ref
  corrected from `v2.1.0` → `v2.1.1` in the Repository Structure table.

## [1.17.0] — 2026-05-29

This release delivers the full **five-wave security and resilience hardening programme**
(Waves A–E, PRs #27–#31) together with the compliance infrastructure, governance controls,
and CI hardening shipped in the preceding milestone. All changes are additive; no public
API or configuration keys were removed.

### Security

- **DLQ + safe Kafka offset commit (REM-012, Wave A).** `enable_auto_commit=False` on the
  request consumer — offsets committed only after `_handle()` completes. Retry loop
  (`kafka_consumer_max_retries=3`, exponential backoff) routes exhausted messages to
  `domain.request.dlq` via the injected broker; `DLQ_MESSAGES_COUNTER` incremented; request
  status set to `failed`. New config: `kafka_dlq_topic`, `kafka_consumer_max_retries`,
  `kafka_consumer_retry_backoff_seconds`. 35 unit tests. ISO 8.16, SOC 2 CC7.2/CC9.

- **Consumer heartbeat metric (REM-013, Wave A).** `CONSUMER_HEARTBEAT_TIMESTAMP` Gauge
  (epoch seconds) updated after every committed message. Alert:
  `time() - consumer_heartbeat_timestamp_seconds > 300 AND kafka_consumer_lag > 0`. ISO 8.16.

- **Prometheus alerting rules + Alertmanager/PagerDuty (REM-002, REM-014, Wave B).**
  `infrastructure/monitoring/prometheus/rules/resilience-alerts.yaml`: `CircuitBreakerOpen`,
  `CircuitBreakerHalfOpen`, `ConsumerStale`, `ConsumerLagCritical`. `CIRCUIT_BREAKER_STATE`
  Gauge emitted by `CircuitBreaker(name=...)` on CLOSED/HALF_OPEN/OPEN transitions. Two
  missing SLO burn-rate groups added (agent action success rate, event consumer DLQ proxy).
  Alertmanager service (`prom/alertmanager:v0.27.0`) wired; `severity=critical` routes to
  PagerDuty when `PAGERDUTY_INTEGRATION_KEY` is set (null receiver in local dev). ISO 8.16,
  SOC 2 CC7.2.

- **Network isolation — NetworkPolicy manifests + ADR-0007 Accepted: Istio (REM-003 Phase 1,
  Wave C).** Four `NetworkPolicy` manifests in `infrastructure/k8s/network-policies/`:
  default-deny-ingress, per-service ingress/egress (api-gateway, event-worker, domain-service),
  Prometheus scrape + Alertmanager egress, and `istio-peer-auth.yaml` (STRICT mTLS Phase 2 —
  requires cluster + Istio). Phase 1 enforced by CNI plugin without a mesh. `securityContext`
  (runAsNonRoot, readOnlyRootFilesystem, drop ALL capabilities) added to `agent-service` and
  `flagd` Deployments. ISO 5.14/8.20, SOC 2 CC6.7.

- **OWASP ZAP DAST shifted left (REM-004, Wave C).** New `dast` job in `ci.yml` runs ZAP
  baseline scan against the FastAPI app in in-memory mode (no backing services required).
  Fails on FAIL-level findings; WARN-level findings in uploaded artifact (30-day retention).
  `build` job now `needs: dast`. ISO 8.29, SOC 2 CC7.1.

- **Trivy IaC/config scan (Wave C).** New Trivy step (`scan-type: config`) in `build` job
  catches CRITICAL/HIGH misconfigurations in Helm templates, K8s manifests, and Dockerfiles
  (missing `securityContext`, privileged containers). Terraform stubs excluded via `skip-dirs`;
  `.trivyignore` documents accepted DS-0002 for the multi-stage builder. ISO 5.14/8.20, SOC 2 CC6.8.

- **CODEOWNERS governance closure (REM-009 partial, Wave D).** All `@org/*` placeholder teams
  replaced with `@valdomirosouza`; CI `governance` job now blocks re-introduction of `@org/`
  patterns. ISO control 5.2 (roles & responsibilities) updated to ✅ Implemented. DPIA
  Section 5 expanded with DPO sign-off checklist and GDPR Art. 36 consultation determination.
  ISO 5.2/5.31, SOC 2 CC5.2.

- **HTTP security headers on every response (Wave E).** `SecurityHeadersMiddleware`
  (`src/api/rest/security_headers.py`): `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()`,
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; form-action 'none'`.
  HSTS (2-year max-age, includeSubDomains, preload) in `APP_ENV=production` only. 5 unit tests.

- **Per-JWT-subject rate limiting (Wave E).** `_limiter.py` key function decodes Bearer token
  (without signature verification — intentionally, for bucketing only) and uses the JWT `sub`
  claim as the rate-limit key; falls back to IP for unauthenticated requests. Prevents a single
  IP from exhausting limits across multiple user accounts.

- **CodeQL SAST workflow (Wave E).** `.github/workflows/codeql.yml` runs Python
  `security-extended` queries on push/PR to main and weekly. Results surface in GitHub Security
  → Code scanning alerts.

- **HITL operator authentication (REM-001).** `POST /v1/hitl/requests/{id}/decision` now
  requires a JWT bearer token with the `hitl-operator` role; approver identity taken from the
  verified token subject (not the request body). Closes impersonation / audit-forgery gap.
  ISO 5.15/8.5, SOC 2 CC6.1.

- **Scoped auto-merge (REM-005).** `auto-merge.yml` limited to documentation-only PRs and
  Dependabot bumps; code/infra changes require human review.
  ISO 5.3/8.32, SOC 2 CC8.1.

- **Supply-chain hardening (REM-006, REM-007).** Trivy image CVE scan gates build on
  CRITICAL/HIGH with `ignore-unfixed`. All 17 GitHub Actions SHA-pinned to commit digests;
  least-privilege `permissions:` blocks on 10 workflows; signed SLSA build provenance added
  to `release.yml` (SLSA L2). ISO 5.21/8.7, SOC 2 CC9.

- **PR governance gates (REM-008, REM-010).** `.github/workflows/pr-governance.yml` enforces:
  Conventional-Commit PR title, CHANGELOG `[Unreleased]` entry, spec reference for product
  PRs, version.txt ↔ pyproject.toml consistency. All four gates merge-blocking on `main` with
  strict mode. ISO 5.36, SOC 2 CC5.

### Added

- `docs/compliance/hardening-plan.md` — five-wave hardening plan with severity, owners,
  blockers, ISO/SOC 2 control mappings.
- `docs/compliance/` package — ISO/IEC 27001:2022 Annex A control matrix (93 controls),
  SOC 2 Trust Services Criteria mapping, SLSA v1.0 assessment, remediation register.
- `docs/governance/owner-onboarding.md` — adopter playbook: GitHub Org, 7 required teams,
  CODEOWNERS migration, branch protection, DPO sign-off checklist.
- `docs/sre/runbooks/dlq-accumulating.md` — DLQ triage, root-cause playbooks, replay procedure.
- `docs/sre/runbooks/redis-ha.md` — Redis Sentinel HA setup, failover verification.
- `docs/sre/runbooks/db-key-rotation.md` — zero-downtime encryption key rotation procedure.
- `infrastructure/k8s/network-policies/` — 4 `NetworkPolicy` manifests + README.
- `infrastructure/monitoring/alertmanager/alertmanager.yml` — PagerDuty + null receiver.
- `infrastructure/monitoring/prometheus/rules/resilience-alerts.yaml` — 4 new alert rules.
- `src/api/rest/security_headers.py` — `SecurityHeadersMiddleware`.
- `src/api/rest/auth.py` — JWT bearer + role-based HITL operator authentication.
- `CIRCUIT_BREAKER_STATE` Gauge — per-client circuit breaker state (0/0.5/1.0).
- `CONSUMER_HEARTBEAT_TIMESTAMP` Gauge — consumer liveness.
- `DB_POOL_CONNECTIONS_ACQUIRED` / `DB_POOL_CONNECTIONS_AVAILABLE` Gauges — pool saturation.
- `redis_sentinel_enabled`, `redis_sentinel_master_name`, `redis_sentinel_hosts` config settings.
- `domain.request.dlq` Kafka channel in AsyncAPI spec and `services.yaml`.
- `alembic/versions/0004_create_requests.py` and `0005_create_hitl_archive.py`.
- `scaffold/` — service scaffolding system (`make new-service NAME=foo LANG=python|java|go`).
- Terraform module READMEs for all 11 infrastructure modules.
- `.github/workflows/codeql.yml` — CodeQL analysis.
- `.trivyignore` — documented accepted finding (DS-0002, builder stage).

### Changed

- `src/api/rest/_limiter.py` — rate-limit key upgraded from per-IP to per-JWT-subject.
- `CircuitBreaker` — accepts `name` parameter; emits `CIRCUIT_BREAKER_STATE` on transitions.
- `ResilientDBPool._call()` — emits pool saturation gauges after each successful query.
- `ResilientDBPool` defaults to `CircuitBreaker(name="db")`;
  `ResilientLLMClientWrapper` to `CircuitBreaker(name="llm")`.
- `RequestConsumer` — `enable_auto_commit=False`, retry loop, DLQ routing; now requires
  `broker: EventBrokerProtocol` parameter.
- `infrastructure/feature-flags/flagd.yaml`, `infrastructure/k8s/deployment.yaml` —
  `securityContext` added (runAsNonRoot, readOnlyRootFilesystem, capabilities drop ALL).
- `docs/adr/ADR-0007-service-mesh.md` — advanced from Proposed → Accepted: Istio.
- `docs/privacy/dpia/dpia-v1.md` — Section 5 DPO checklist + GDPR Art. 36 determination.
- `.github/CODEOWNERS` — all `@org/*` placeholders replaced with `@valdomirosouza`.

### Fixed

- `src/shared/llm_client.py` — `AttributeError` on `settings.anthropic_api_key` /
  `settings.anthropic_model` (correct fields: `llm_api_key` / `llm_model`).
- `src/observability/logger.py` — missing `StructuredLogger.debug()` method.
- `src/shared/broker.py` — `InMemoryBroker` gained `start()`/`stop()` no-ops to satisfy
  the `KafkaEventBroker` interface in the lifespan.
- `.github/workflows/ci.yml` — services.yaml schema check used bare `python3` instead of
  `uv run python`, causing `ModuleNotFoundError: No module named 'yaml'`.
- Various mypy-strict, ruff, and formatting fixes across `src/`.

## [1.15.0] — 2026-05-28

### Added

- **`tests/e2e/test_hitl_operator_ui.py`** — HITL operator E2E tests (Wave 10.1). Covers
  CUJ-002: HITL status endpoint reflecting queue depth, APPROVE decision removing request
  from queue, REJECT decision with valid rationale, short-rationale 422, unknown-ID 404,
  double-decision 404, and invalid decision enum 422. Uses FastAPI ASGI transport (no real
  server required); set `BASE_URL` to run against a live server. Marked `e2e`.
- **`tests/e2e/test_request_lifecycle.py`** — Request lifecycle E2E tests (Wave 10.2). Covers
  CUJ-001 and CUJ-003: 202 Accepted on submit, request_id in message, valid priority values,
  empty/oversized/invalid-priority 422, no-store 503, immediate status poll returning queued,
  unknown-ID 404, all contracted fields present, PII not echoed in response, submit latency
  < 500 ms, poll latency < 200 ms, 10 concurrent submissions all succeed with unique IDs.
  Marked `e2e`.
- **`tests/performance/k6/request-api-load.js`** — k6 load test for `POST /v1/requests`
  (Wave 10.3). Three scenarios: ramp-up (1→50 VUs over 2 min), sustained (50 VUs for 5 min),
  spike (200 VUs for 1 min). SLO-aligned thresholds: submit p99 < 500 ms, poll p99 < 200 ms,
  error rate < 0.5%. Handles 429 with Retry-After backoff. `handleSummary` prints a concise
  SLO pass/fail table.
- **`tests/performance/k6/hitl-decision-load.js`** — k6 load test for HITL decision endpoint
  (Wave 10.4). Two scenarios: operator baseline (5 concurrent operators, 3 min), operator surge
  (15 operators, 1 min). Seeds pending requests via the submission endpoint. 80/20 approve/reject
  split; tracks `decisions_submitted_total`, `approvals_total`, `rejections_total`. Thresholds:
  decision p95 < 300 ms, decision p99 < 500 ms.
- **`tests/performance/benchmarks/test_orchestrator_benchmarks.py`** — Orchestrator hot-path
  benchmarks (Wave 10.5). Uses `time.perf_counter_ns()` for microsecond-resolution measurement
  over 200–1 000 iterations. Covers: `mask_text` short/long (≤ 5/10 ms), `mask_dict` flat/nested/
  clean (≤ 5/10/2 ms), `RiskScorer.score` low/high/PII-tokens (≤ 2 ms each), monotonicity
  invariant (delete > read), `PromptInjectionGuard.check` clean/malicious/long-clean (≤ 5/5/10 ms),
  and full sync pipeline PII→injection→risk (≤ 12 ms). Marked `benchmark`.
- **`tests/contract/test_rest_pact_provider.py`** — Pact provider verification against the
  Wave 6.5 consumer contracts (Wave 10.6). 9 test classes (one per Pact interaction), each
  firing real HTTP requests through the FastAPI ASGI stack with direct store seeding for
  provider state setup. Includes a coverage-contract test that fails when a new Pact interaction
  lacks a provider test class. Marked `unit`.

### Changed

- **`pyproject.toml`** — Added two new pytest markers: `e2e` (full user journey; opt-in via
  `BASE_URL`) and `benchmark` (latency assertions against SLO thresholds). `--strict-markers`
  already enforced; new markers prevent spurious "unknown marker" warnings.

---

## [1.14.0] — 2026-05-28

### Added

- **`infrastructure/helm/domain-service/`** — Helm chart for the Java/Spring Boot domain-service
  (Wave 9.1). 9 files: Chart.yaml, values.yaml, values-staging.yaml, values-production.yaml,
  templates/\_helpers.tpl, deployment.yaml (Spring Actuator probes, readOnlyRootFilesystem,
  tmpfs volume, Prometheus annotations), service.yaml, serviceaccount.yaml (IRSA annotation
  support), hpa.yaml (CPU + memory metrics), pdb.yaml. Spring-specific: JAVA_OPTS JVM tuning,
  `/actuator/health/liveness` and `/actuator/health/readiness` probes, 60 s graceful drain.
- **`infrastructure/helm/event-worker/`** — Helm chart for the Go Kafka consumer (Wave 9.2).
  10 files: Chart.yaml, values.yaml, values-staging.yaml, values-production.yaml,
  templates/\_helpers.tpl, configmap.yaml (Kafka bootstrap, group ID, topics, timeouts),
  deployment.yaml (WORKER_ID injected from pod name via Downward API, metrics port only),
  service.yaml (metrics-only ClusterIP), serviceaccount.yaml, hpa.yaml (CPU + Kafka
  consumer lag via prometheus-adapter, conservative 600 s scale-down window), pdb.yaml.
- **`infrastructure/helm/frontend/`** — Helm chart for the Next.js frontend (Wave 9.3).
  11 files: Chart.yaml, values.yaml, values-staging.yaml, values-production.yaml,
  templates/_helpers.tpl, configmap.yaml (NEXT_PUBLIC_\* and server-side env vars; includes
  build-time warning comment), deployment.yaml (checksum annotation for ConfigMap-triggered
  rollouts, secretRef optional for pre-auth deployments), service.yaml, ingress.yaml
  (TLS + cert-manager), serviceaccount.yaml, hpa.yaml (CPU), pdb.yaml.
- **`infrastructure/terraform/modules/api-gateway/`** — Terraform application module for the
  api-gateway (Wave 9.4). main.tf (IRSA role with WebIdentity trust, Secrets Manager read
  policy scoped to `monorepo/{env}/api-gateway/*`, CloudWatch Logs write policy, Helm release
  with local chart path, `lifecycle.ignore_changes` for image tag), variables.tf (OIDC inputs,
  secrets ARNs, Helm values file path), outputs.tf (IRSA role ARN, Helm release status).
- **`infrastructure/terraform/modules/domain-service/`** — Terraform application module for
  the domain-service (Wave 9.5). Follows api-gateway pattern; adds db_secret_arn variable
  granting explicit Secrets Manager access to the PostgreSQL credential secret (ADR-0018).
- **`infrastructure/terraform/modules/event-worker/`** — Terraform application module for the
  event-worker (Wave 9.5). Adds optional MSK cluster access policy (kafka-cluster:\* actions)
  and optional SQS DLQ send policy; both conditioned on non-empty variable values so the
  module works without MSK in local/staging environments.

### Changed

- **`infrastructure/terraform/environments/staging/main.tf`** — Wired the three new
  application modules (api_gateway, domain_service, event_worker) into the staging environment.
  Added `data.aws_caller_identity.current` for account ID resolution, `db_secret_arn` and
  `image_tag` input variables, and IRSA role ARN outputs for all three services.

---

## [1.13.0] — 2026-05-28

### Added

- **`specs/security/rbac-model.md`** — HITL RBAC spec (Wave 8.1). Defines three roles
  (`hitl:operator`, `hitl:supervisor`, `hitl:auditor`), an action type permission matrix
  (operators cannot approve `deploy`, `database_write`, `delete_resource`, or `escalate_privilege`),
  JWT claim requirements (`sub` as `approver_id`, `roles` claim, `iss`/`aud` validation),
  enforcement points in api-gateway middleware and audit logger, and implementation status
  tracking for each deferred component. Addresses threat-model REM-001.
- **`specs/security/pentest-checklist.md`** — Pre-production penetration testing checklist
  (Wave 8.2). 50 items across 10 sections aligned with the STRIDE threat model: authentication
  (S), authorisation/privilege escalation (E), injection (T), data exposure (I), audit/repudiation
  (R), denial of service (D), dependency vulnerabilities (supply chain), infrastructure
  configuration, and OWASP LLM Top 10. Includes sign-off table for Security Lead PRR gate.

### Changed

- **`.github/workflows/ci-java.yml`** — OWASP Dependency-Check is now a **blocking gate**
  (Wave 8.3). Removed `continue-on-error: true`; added `-Ddependency-check.failBuildOnCVSS=7`
  (fails on CVSS ≥ 7.0, i.e. HIGH and CRITICAL). Suppression file (`dependency-check-suppressions.xml`)
  explicitly wired. Report artifact uploaded on every run for audit. False positives must be
  documented in the suppressions file with CVE ID and rationale.
- **`.github/workflows/ci-go.yml`** — Added `govulncheck` as a **blocking gate** in the
  `lint-go` job (Wave 8.4). Scans all Go service directories; fails on any reachable vulnerability
  in the Go vulnerability database. Call-graph analysis means only actually-called vulnerable
  code paths trigger a failure — not unreachable transitive dependencies.
- **`.github/workflows/ci-frontend.yml`** — Added `pnpm audit --audit-level=high` as a
  **blocking gate** in the `lint-frontend` job (Wave 8.5). Fails on HIGH or CRITICAL CVEs in
  any direct or transitive Node.js dependency. Runs before ESLint so the build fails fast on
  known-vulnerable packages.

---

## [1.12.0] — 2026-05-28

### Added

- **`docs/sre/runbooks/api-gateway-high-error-rate.md`** — Runbook (Wave 7.1). Five-step
  triage procedure covering error severity classification, root-cause branches (recent deploy,
  upstream dependency, LLM provider, resource exhaustion), containment, rollback, and
  post-incident checklist. References `skills/change-management/deploy-rollback.md`.
- **`docs/sre/runbooks/hitl-queue-backlog.md`** — Runbook (Wave 7.2). Covers operator
  unavailability, portal failure, action-type flood, and risk-scorer over-escalation. Includes
  governance-gated emergency drain procedure with required AI Governance Lead sign-off per
  ADR-0011.
- **`docs/sre/runbooks/kafka-consumer-lag.md`** — Runbook (Wave 7.3). Covers pod OOM,
  broker degradation, slow consumer, and poison-pill messages. Documents partition rebalance,
  poison-pill skip procedure (with data-loss declaration), and DLQ replay path.
- **`docs/sre/runbooks/redis-connection-failure.md`** — Runbook (Wave 7.4). Covers pod
  failure, network policy, TLS expiry, OOM, and auth failure. Documents production safety
  rules (in-memory fallback blocked), data-loss communication protocol, and
  GDPR/LGPD breach assessment trigger. ADR-0019.
- **`docs/sre/cuj/CUJ-002-hitl-decision-flow.md`** — HITL operator CUJ (Wave 7.5). SLO
  targets (p95 decision latency ≤ 300 s, queue depth ≤ 100, 100% audit write). Happy path,
  dependency table, failure scenarios, degraded path procedure, and test coverage map.
- **`docs/sre/cuj/CUJ-003-agent-autonomous-resolution.md`** — Autonomous resolution CUJ
  (Wave 7.6). SLO targets (≥ 80% autonomous rate, p95 ≤ 5 000 tokens, p99 ≤ 15 iterations).
  Full HOTL happy path, failure scenarios including runaway self-reflection, autonomy boundary
  enforcement note, and test coverage map.
- **`infrastructure/monitoring/prometheus/rules/slo-burn-rate.yaml`** — Multi-window SLO
  burn-rate alert rules (Wave 7.8). Covers: HITL availability fast/slow burn (1h/6h),
  HITL decision latency p95 warning/critical, HITL queue depth warning/critical, audit log
  write failure (hard invariant, fires immediately), autonomous resolution rate warning/critical,
  token cost p95 warning/critical, self-reflection iteration runaway, and API gateway
  availability fast/slow burn. All rules linked to runbooks.
- **`infrastructure/monitoring/grafana/dashboards/finops-cost-allocation.json`** — FinOps
  cost allocation dashboard (Wave 7.9). Nine panels: monthly budget utilisation gauge,
  estimated days until budget exhausted, total tokens stat, monthly budget stat, input/output
  token daily trend, real-time consumption rate vs sustainable rate, cost-per-resolution
  p50/p95/p99 table by action_type (with threshold colouring at 5k/10k), top-10 action types
  by total 30d cost, and burn-rate ratio vs 1.0× and 14.4× thresholds. ADR-0020.

### Changed

- **`docs/sre/slo/slo.yaml`** — Version bumped to 1.1; added two new service blocks
  (Wave 7.7): `hitl-system` (4 SLOs: availability, decision latency p95, queue depth, audit
  write) and `agent-autonomous` (3 SLOs: autonomous resolution rate, token cost p95,
  self-reflection iterations p99). All new SLOs carry multi-window burn-rate alert references
  and runbook pointers.

---

## [1.11.0] — 2026-05-28

### Added

- **`infrastructure/proto/domain_service.proto`** — gRPC service contract for the Java
  domain-service (Wave 6.1). Defines `DomainService` with four RPCs: `CreateEntity`,
  `GetEntity`, `ListEntities`, `UpdateEntityStatus`. Includes `EntityMessage`,
  `EntityStatus` enum, cursor-based pagination, and PII masking requirements per field.
  ADR-0021, ADR-0024.
- **`infrastructure/proto/event_worker.proto`** — gRPC service contract for the Go
  event-worker (Wave 6.2). Defines `EventWorkerService` with three RPCs: `PublishEvent`
  (ad-hoc replay/backfill), `GetEventStatus` (recent processing records), `DrainQueue`
  (maintenance drain before rolling restarts). ADR-0021, ADR-0024.
- **`docs/api/asyncapi/v2/migration-guide.md`** — AsyncAPI schema evolution guide (Wave 6.3).
  Documents backwards-compatible vs breaking change rules, dual-publish migration process,
  `x-stability` / `x-sunset-date` annotation schema, current v1 channel stability table,
  and v2 planning candidates. ADR-0024.
- **`docs/adr/ADR-0024-api-versioning-strategy.md`** — API versioning strategy ADR (Wave 6.4).
  Unifies versioning rules across REST (URL-major), AsyncAPI/Kafka (topic rename + dual-publish),
  and gRPC/Protobuf (field permanence + service-level deprecation). Includes consumer
  compatibility requirements and governance sign-off table.
- **`tests/contract/pacts/frontend-api_gateway.json`** — Pact v2 consumer contract file
  (Wave 6.5). Nine interactions covering `POST /v1/requests`, `GET /v1/requests/{id}` (queued,
  completed, not found), `GET /v1/hitl/status`, `POST /v1/hitl/requests/{id}/decision`
  (APPROVED, REJECTED, not found). Uses matching rules for type and regex.
- **`tests/contract/test_rest_pact_consumer.py`** — Provider-side REST contract tests (Wave 6.5).
  Validates that `RequestOut`, `RequestStatusResponse`, `HITLStatusResponse`, and `DecisionOut`
  Pydantic models satisfy the shapes declared in the Pact file. Includes cross-interaction
  invariants (Content-Type headers, synthetic UUID format). Runs as `unit` tests with no I/O.
  ADR-0022, ADR-0024.

### Changed

- **`docs/api/asyncapi/v1/asyncapi.yaml`** — Added `x-stability` and `x-sunset-date`
  extension annotations to all 10 channels (Wave 6.3). Eight channels marked `stable`;
  `agent.feedback.applied` and `agent.harness.state` marked `beta`. ADR-0024.

---

## [1.10.0] — 2026-05-28

### Added

- **`skills/domain/domain-modeling.md`** — Domain modeling skill (Wave 5.1). DDD tactical
  patterns (entities, value objects, aggregates, repositories, domain events) with reference
  examples from the Java domain-service and Python src/ layouts. Includes a new-concept
  checklist and anti-pattern table.
- **`skills/engineering/testing-strategy.md`** — Testing strategy skill (Wave 5.2). Test
  pyramid with directory→marker→infrastructure mapping, coverage requirements, AAA convention,
  fixture standards, contract/security/chaos layer guidance, and mutation testing targets.
  References ADR-0022.
- **`skills/ethics/ethical-ai-review.md`** — Ethical AI review skill (Wave 5.3). Pre-implementation
  checklist (Human Oversight, Transparency, Fairness, Privacy, Accountability, Safety), prohibited
  uses quick-reference, quarterly bias audit procedure, incident response steps, governance
  sign-off matrix, and EU AI Act article cross-reference. References `specs/ethics/ethical-ai-principles.md`.
- **`docs/adr/ADR-0022-testing-strategy.md`** — Testing strategy ADR (Wave 5.5). Documents test
  pyramid layers, 80% coverage threshold rationale, branch coverage decision, Pact consumer-driven
  contract testing selection, mutation testing tooling and targets, and multi-language coverage
  expectations.
- **`docs/adr/ADR-0023-frontend-architecture.md`** — Frontend architecture ADR (Wave 5.6).
  Documents Next.js 14 / App Router selection, rendering strategy per view type (SSR, ISR,
  client components, polling), API communication via generated TypeScript client, deferred
  authentication design (OIDC + next-auth), and Jest + Playwright test split.

### Changed

- **`pyproject.toml`** — Added `[tool.coverage.run]` (branch=true, source=src, omit list) and
  `[tool.coverage.report]` (fail_under=80, show_missing=true) sections (Wave 5.4). The 80%
  coverage threshold is now enforced locally on every `make test-unit-python` run, not only in
  the CI harness. ADR-0022.
- **`CLAUDE.md §4` Skill Activation Table** — Added three trigger rows (Wave 5.7):
  domain modeling → `skills/domain/domain-modeling.md`;
  testing strategy → `skills/engineering/testing-strategy.md`;
  ethical AI review → `skills/ethics/ethical-ai-review.md`.

---

## [1.9.1] — 2026-05-28

### Changed

- **`README.md`** — updated to reflect v1.9.0 state: version badge, Python 3.13, 21 ADRs,
  service scaffolds, Helm/Terraform IaC, agent alert rules, STRIDE/ethics/SDLC specs,
  contract tests, full repository structure, CI/CD canary CD table, and new Security section.

---

## [1.9.0] — 2026-05-28

### Added

- **`skills/sre/incident-response.md`** — Incident response skill (Wave 4.1). Severity levels (P0–P3), lifecycle (acknowledge → triage → mitigate → resolve → postmortem), HITL-specific incident procedure, and communication templates.
- **`skills/sre/capacity-planning.md`** — Capacity planning skill (Wave 4.1). Key capacity signals with Prometheus queries, HPA tuning guide, Little's Law sizing worksheet, and load testing guidance.
- **`skills/privacy/data-subject-rights.md`** — Data subject rights skill (Wave 4.1). GDPR/LGPD rights table with SLAs, step-by-step request handling, erasure SQL, downstream processor notification, and Art. 22 automated-decision compliance.
- **`skills/change-management/cab-process.md`** — CAB process skill (Wave 4.1). Change type classification, Normal change workflow, emergency hotfix path, CAB escalation procedure.
- **`infrastructure/monitoring/jaeger/jaeger-config.yaml`** and **`sampling-strategies.json`** — Jaeger collector config with sampling policy (Wave 4.3). HITL and request endpoints sampled at 100%; health/metrics at 0%.
- **`infrastructure/proto/harness_state.proto`** — Three new message types (Wave 4.5): `AgentContext`, `HITLRequestEnvelope` + `HITLDecisionEnvelope`, `AuditEventEnvelope`.

### Changed

- **`docs/dependency-manifest.yaml`** — updated date; added ADR-0020 and ADR-0021 to governance references (Wave 4.4).
- **`.github/workflows/ci.yml`** — advisory `.env.example` drift check against `Settings` fields (Wave 4.2).

---

## [1.8.0] — 2026-05-28

### Added

- **`specs/security/threat-model.md`** — STRIDE threat model (Wave 3.1). Full attack
  surface analysis across Spoofing, Tampering, Repudiation, Information Disclosure,
  DoS, and Elevation of Privilege. Includes 4 prioritised remediations required before
  production.
- **`specs/ethics/ethical-ai-principles.md`** — Ethical AI principles (Wave 3.2).
  Six core principles (Human Oversight, Transparency, Fairness, Privacy by Design,
  Accountability, Safety), prohibited use table, quarterly bias monitoring procedure,
  and ethical incident response playbook. Maps to EU AI Act Arts. 9–15 and LGPD Art. 20.
- **`specs/sdlc/development-lifecycle.md`** — Development lifecycle spec (Wave 3.3).
  Five-stage lifecycle (Spec → Implement → Verify → Stage → Produce) with explicit
  entry conditions, gate criteria, canary promotion thresholds, hotfix path, and
  Definition of Done.
- **`docs/adr/ADR-0020-finops-cost-allocation.md`** — FinOps ADR (Wave 3.4).
  Three-tier budget enforcement (80%/95%/100%), cost attribution by `action_type` via
  Prometheus, harness iteration caps, and resolution of the SessionMemory encryption
  deferral from ADR-0019.
- **`docs/adr/ADR-0021-agent-communication-protocol.md`** — Agent communication
  protocol ADR (Wave 3.5). Rationale for Protobuf over JSON/Avro for cross-process
  messages, boundary policy (dataclasses in-process / proto on wire), versioning
  strategy (field number permanence), PII masking invariant, and Kafka migration path.
- **`tests/contract/test_harness_contracts.py`** — Harness contract tests (Wave 3.6).
  32 tests across 8 classes covering `TaskBrief`, `SprintContract`, `GeneratorArtifact`,
  `EvaluatorScore`, `HarnessResult`, `PatchProposal`, `ExecutionSummary`, and three
  cross-boundary invariants (sprint_id propagation, task_id propagation,
  escalated-result-has-no-passing-score). All 32 pass.
- **`docs/adr/README.md`** — ADR-0020 and ADR-0021 added to the index.

---

## [1.7.0] — 2026-05-28

### Added

- **`infrastructure/helm/api-gateway/`** — Helm chart for the API Gateway (Wave 2.1).
  Parametrized templates for Deployment, Service, Ingress, HPA, PDB, and ServiceAccount.
  Separate `values-staging.yaml` and `values-production.yaml` overrides. Canary
  deployment toggle (`canary.enabled`, `canary.weight`) wired to CD workflows.
- **`infrastructure/monitoring/prometheus/rules/agent-alerts.yaml`** — Agent-specific
  Prometheus alert rules (Wave 2.2). Covers HITL queue depth, rejection rate, wait
  time, operator absence; feedback loop bias ceiling and stall; MTTD/MTTR SLOs;
  autonomous resolution rate; token cost per resolution; semaphore saturation; LLM
  latency and budget; Dead Letter Queue growth.
- **`infrastructure/terraform/modules/networking/`** — Terraform VPC module (Wave 2.5).
  VPC, public/private subnets, NAT gateway (one per AZ), route tables, and three
  security groups (ingress, app, data).
- **`infrastructure/terraform/modules/kubernetes/`** — Terraform EKS module (Wave 2.5).
  EKS cluster with KMS secrets encryption, managed node group, and IRSA-ready OIDC
  output.
- **`infrastructure/terraform/modules/cache/`** — Terraform ElastiCache Redis module
  (Wave 2.5). TLS-only (port 6380, `rediss://`), at-rest KMS encryption, parameter
  group enforcing ADR-0019.
- **`infrastructure/terraform/environments/staging/main.tf`** and
  **`infrastructure/terraform/environments/production/main.tf`** — Root environment
  modules wiring networking + kubernetes + cache with S3 remote state backend.

### Changed

- **`cd-staging.yml`**, **`cd-production.yml`** — fixed Helm chart path from
  `./infrastructure/helm/` to `./infrastructure/helm/api-gateway` and added
  per-environment `--values` flag (Wave 2.1).
- **`ci.yml`** — added `fail_ci_if_error: true` and `token` to the codecov upload step
  so a failed upload blocks the PR rather than silently passing (Wave 2.4).

---

## [1.6.0] — 2026-05-28

### Added

- **`services/domain-service/`** — Java 21 / Spring Boot 3.3 scaffold (Wave 1.1).
  Full CRUD REST API (`/v1/entities`), Kafka consumer for `request.created.v1`,
  producers for `domain.entity.{created,updated}.v1`, Flyway migration, JaCoCo ≥ 80%,
  Checkstyle, SpotBugs, OWASP dep-check, unit tests with MockMvc.
- **`services/event-worker/`** — Go 1.23 scaffold (Wave 1.2).
  Stateless Kafka consumer for entity domain events, publishes `event.processed.v1`,
  Prometheus metrics endpoint, air hot-reload, golangci-lint config, handler unit tests.
- **`frontend/frontend/`** — Next.js 14 / TypeScript scaffold (Wave 1.3).
  HITL approval queue UI (`/hitl`), typed API client over the API Gateway REST spec,
  `ApprovalCard` component with approve/reject flow, Jest unit tests, Playwright config,
  multi-stage Dockerfile, committed `pnpm-lock.yaml`.

### Changed

- **`.github/workflows/ci-go.yml`** — added `go mod tidy` step before unit tests so
  the scaffold works in CI without a pre-committed `go.sum`.

---

## [1.5.2] — 2026-05-28

### Changed

- **`CLAUDE.md`** (v2.1.0): expanded with missing commands and corrected architecture framing.
  - Architecture description corrected from "Python monorepo" to multi-language monorepo template (Python 3.13, Java/Spring Boot, Go, Node.js/Next.js).
  - Added Java, Go, and Frontend `make` targets with `SERVICE=`/`APP=` parameter pattern.
  - Added database migration commands (`alembic upgrade head`, `alembic revision --autogenerate`).
  - Added code generation targets (proto stubs, Avro/OpenAPI clients).
  - Added `make deploy-staging`, `make rollback`, and `make clean`.
  - Documented `services.yaml` as canonical service registry and its AsyncAPI contract requirement.
  - Documented pre-commit hooks (`.pre-commit-config.yaml`) and `harness/` PR gate specs.
  - Referenced `CUSTOMISING.md` for project adoption guidance.
  - Extended Key Layers table with `src/memory/`, `frontend/`, and `harness/` rows.
- **`.github/pull_request_template.md`**: improved for multi-language monorepo.
  - Per-language test commands (Python/Java/Go/Frontend) in checklist.
  - Per-language deploy command examples.
  - Added `services.yaml` checklist item for new services, ports, or Kafka topics.
  - Scoped HITL checklist item to _(AI Agents Module only)_.
  - Added footer referencing `harness/code-check.yml` CI gates.
- **`version.txt`**: corrected stale version (was `1.4.1`, now tracks `pyproject.toml`).

---

## [1.5.1] — 2026-05-28

### Changed

- **`docs/architecture.md`**: reframed to treat Agent Runtime and HITL/HOTL as opt-in.
  Added scope note, annotated Mermaid topology subgraph, marked sequence diagram as
  "with AI Agents Module enabled", split Key Module Map into Core and AI Agents Module
  sections, and added `Module` column to Infrastructure Fallback table.

---

## [1.5.0] — 2026-05-28

### Changed

- **Repository generalised from "Enterprise AI Monorepo" to "Enterprise Monorepo Template"**:
  AI/agent capabilities are now an explicit opt-in extension rather than a core assumption.
  - `README.md`, `pyproject.toml`, `MONOREPO-STRUCTURE-EN.md`: titles and descriptions updated
  - `CLAUDE.md §1`: identity reframed as generic enterprise engineer; AI governance role marked conditional
  - `CLAUDE.md §3.3`: AI Governance Rules wrapped with "only when AI Agents Module is enabled" gate
  - `CLAUDE.md §4`: Skill table split into Core Skills and AI Agents Module Skills (opt-in)
  - `CLAUDE.md §7–8`: PR checklist and file ownership table updated to mark AI-specific items conditional
  - `docs/adr/README.md`: ADR index split into "Core Architecture" and "AI Agents Module (opt-in)" groups
  - `specs/system/architecture.md`: Principle 5 (HITL) reframed as conditional on AI Agents Module
  - `src/api/rest/main.py`: FastAPI title/description updated; HITL router annotated as optional
  - `services.yaml`: api-gateway AI-module ADR references annotated as conditional
  - `infrastructure/feature-flags/README.md`: noted as AI Agents Module dependency

### Added

- **`docs/optional-extensions/ai-agents/README.md`** (new): canonical activation and removal
  checklist for the AI Agents Module extension
- **`docs/quickstart/ai-agents.md`** (new): step-by-step guide for HITL gateway, guardrails,
  harness mode, and autonomous-mode feature flags
- **`src/agents/README.md`** (new): module boundary documentation with governance rules and
  removal instructions
- **`specs/ai/README.md`** (new): scope marker clarifying that AI specs only apply when the
  module is enabled
- **`docs/ai-governance/README.md`** (new): optional marker with governance contacts table

### Added (cont. — Wave 2 security)

- **Database encryption at rest** (`src/shared/db_encryption.py`): AES-256-GCM
  field-level encryption for L1/L2 PII columns; `enc:v1:<base64>` wire format with
  version prefix for zero-downtime key rotation; plaintext passthrough for rolling
  migration; production guard in `Settings.reject_placeholder_secrets` (ADR-0018,
  SPEC-db-encryption-at-rest)
- **`PostgresVectorStore` encryption integration**: optional `EncryptedField`
  dependency encrypts `content` on write and decrypts on read (`src/memory/vector_store.py`)
- **Alembic migration 0002** (`enable_pgcrypto_vector`): enables `pgcrypto` and
  `vector` PostgreSQL extensions
- **Alembic migration 0003** (`create_agent_memory_documents`): creates
  `agent_memory_documents` table with IVFFlat index for cosine similarity search
- **`DB_ENCRYPTION_KEY` config** (`src/shared/config.py`): new `db_encryption_key`
  and `db_encryption_enabled` settings; `.env.example` updated with generation instructions
- **`cryptography>=42.0.0`** added as explicit dependency (`pyproject.toml`)

### Fixed

- **SQL injection** in `PostgresVectorStore._SEARCH`: `source_filter` was interpolated
  directly into the SQL string; replaced with two separate parameterised queries
  (`_SEARCH_ALL`, `_SEARCH_FILTERED`) using asyncpg `$3` binding (ADR-0018 §SQL
  Injection Fix)

### Added (cont.)

- **Redis TLS connection support** (`src/api/rest/main.py`): `REDIS_TLS_ENABLED` and
  `REDIS_TLS_CA_CERT` settings wire TLS into `redis.asyncio.from_url`; production
  startup blocked when TLS is disabled (ADR-0019, SPEC-redis-tls)
- **HITLRedisStore value encryption** (`src/agents/hitl_store.py`): full JSON payload
  encrypted with AES-256-GCM via optional `EncryptedField` dependency; passthrough
  path for unencrypted legacy rows; 11 new unit tests
- **K8s Ingress TLS** (`infrastructure/k8s/ingress.yaml`): HTTPS termination via
  cert-manager + Let's Encrypt, HSTS, HTTP→HTTPS redirect, security headers,
  per-IP rate limiting; `ClusterIssuer` manifests for prod and staging
- **Certificate rotation runbook** (`docs/sre/runbooks/cert-rotation.md`): routine
  renewal, manual rotation, emergency revocation, encryption key rotation procedures;
  alert thresholds and escalation matrix
- **PRR-SEC-005 to PRR-SEC-008** (`docs/sre/prr/prr-checklist.yaml`): TLS
  verification, `DB_ENCRYPTION_KEY` in Vault, key rotation schedule, cert expiry check
- **ADR-0019** (`docs/adr/ADR-0019-redis-tls-value-encryption.md`): Redis TLS and
  value encryption architectural decision

### Changed

- **CLAUDE.md §3.2**: four new inviolable security rules — TLS 1.2+ for all
  endpoints, `EncryptedField` for L1/L2 PII at rest, no unencrypted HITL payloads
  in Redis, production startup validation
- **`skills/sre/prr.md`**: three new PRR blockers — TLS verification, encryption key,
  certificate expiry

---

## [1.4.1] - 2026-05-28

### Added

- **Canonical Glossary** (`docs/glossary.md`): expanded from ~30 terms to 131 terms across
  10 thematic sections — AI Governance & Agents, Privacy & Data Protection, Compliance & Legal,
  Security, SRE & Reliability, Observability, Infrastructure & Middleware, APIs & Protocols,
  Development Practices & SDLC, Python & Framework Stack. Covers all abbreviations and
  domain terms used across specs, ADRs, skills, and source code.

---

## [1.4.0] - 2026-05-28

### Added

- **Architecture diagrams** (7 Mermaid diagrams): system topology + request lifecycle
  sequence (`docs/architecture.md`), request state machine, HITL/HOTL decision flowchart,
  4-layer guardrail pipeline, Kafka event topology, multi-agent harness sprint loop
- **RiskScorer** (`src/agents/risk_scorer.py`): deterministic 5-factor weighted risk scorer
  (irreversibility 0.35, external effect 0.25, scale 0.20, data sensitivity 0.15, rejection
  rate 0.05); replaces LLM self-reported `risk_score` in the orchestrator `_act` phase;
  47 unit tests with 100% branch coverage
- **Data retention job** (`src/jobs/retention_job.py`): `RetentionJob` enforces
  `specs/privacy/data-retention.md` — deletes expired `agent_memory_documents`, archives
  and hard-deletes aged `audit_events`, verifies compliance post-sweep
- **Retention CronJob** (`infrastructure/k8s/retention-cronjob.yaml`): daily 02:00 UTC
  K8s CronJob with dedicated `retention-job` ServiceAccount (DBA role for audit DELETE)
- **HITL notification spec** (`specs/ai/hitl-notification.md`): webhook payload schema,
  HMAC-SHA256 signature, 3-attempt retry policy, `NotificationService` protocol,
  `MultiChannelNotificationService` fan-out, reviewer dashboard contract, observability
- **CUSTOMISING.md**: full template adoption guide — minimum required changes, what to
  remove per stack, SDD first-spec walkthrough, harness_mode selection guide, upstream sync
- **Control loop specs**:
  - `specs/ai/feedback-loop.md`: convergence contract, thresholds table, worked 7-cycle
    example, rollback/override procedures, Mermaid control loop diagram
  - `specs/ai/agent-memory.md`: memory recall sequence diagram showing explicit recall
    in the Reason phase, injection API, and skip conditions

### Changed

- **README**: added 3-command end-to-end demo, `make infra-up` port/role table, health
  check verification step (`/health` + `/ready`), and "what to remove" per-stack guidance
- **`src/agents/orchestrator/orchestrator.py`**: `RiskScorer` injected as optional
  dependency; authoritative `risk_score` computed in `_act` before HITL routing

---

## [1.3.1] - 2026-05-27

### Changed

- **CLAUDE.md**: added Section 0 (development commands — setup, run, test, lint, docs) and
  Section 0.1 (architecture overview — request pipeline, key layers, infrastructure fallback
  pattern, harness modes, autonomy levels); updated file header to standard Claude Code prefix.

---

## [1.3.0] - 2026-05-27

### Added

- **A1 — AI Dependency Manifest**: `docs/dependency-manifest.yaml` — canonical AI dependency
  manifest complementing SBOM; documents Claude model IDs, API versions, onboarding dates,
  data classification, and governance controls (ADR-0010, ADR-0012); uploaded as artifact in `sbom.yml`

- **A2 — Sandbox Executor** (ADR-0016, SPEC-sandbox-execution):
  - `src/agents/sandbox_executor.py`: `SandboxExecutor` executes agent-generated commands inside
    ephemeral Docker containers with `--network none`, CPU/memory caps, zero host-env leakage,
    configurable timeout; controlled by `sandbox-mode` OpenFeature flag (3 variants)
  - `specs/ai/sandbox-execution.md`, `docs/adr/ADR-0016-agent-sandbox-execution-policy.md`
  - `infrastructure/feature-flags/flags/sandbox-mode.yaml`, `docker-compose.sandbox.yml`
  - 28 unit tests (98% coverage)

- **A3 — Feedback Loop** (SPEC-feedback-loop):
  - `src/agents/feedback_loop.py`: `FeedbackLoop` queries Prometheus for HITL rejection/approval
    rates per `action_type` and adjusts `risk_score` bias; publishes to Kafka `agent.feedback.applied`
  - `src/observability/metrics.py`: 3 new feedback metrics (Gauge × 2, Counter × 1)
  - `infrastructure/monitoring/grafana/dashboards/agent-feedback-loop.json`: 7-panel dashboard
  - `docs/api/asyncapi/v1/asyncapi.yaml`: `agent.feedback.applied` channel added
  - `Makefile`: `agent-feedback-check` target
  - 21 unit tests (92% coverage)

- **B1 — Granular Autonomy Levels** (`specs/ai/autonomous-mode-levels.md`, ADR-0015 rev):
  - `src/shared/feature_flags.py`: `get_autonomy_level(action_type, risk_score) → AutonomyLevel`
    with 5 graduated levels: FULL → MEDIUM_RISK → LOW_RISK → TESTS_ONLY → READ_ONLY → NONE
  - Five new flagd flag definitions in `infrastructure/feature-flags/flags/`
  - `tests/unit/shared/test_feature_flags.py`: 28 tests (was 6)

- **B2 — Agent Supervision Dashboard** (`specs/observability/agent-supervision.md`):
  - `infrastructure/monitoring/grafana/dashboards/agent-supervision.json`: 11-panel Grafana
    dashboard (Active HITL Queue, HITL by Agent, Approval/Rejection Rate, Wait Time p50/p99,
    Action Latency, LLM Token Budget, Autonomous Resolution Rate, Jaeger trace deep-link)

- **B4 — Self-Reflection & Auto-Correction** (`specs/ai/harness-design.md §9`):
  - `src/agents/harness/decision_tree_logger.py`: `DecisionTreeLogger` records every
    branching decision to the immutable audit log (`action = "decision_bifurcation"`)
  - `src/agents/harness/models.py`: added `DecisionPoint`, `PatchProposal`, `ExecutionSummary`
  - `src/agents/harness/coordinator.py`: PatchProposal via LLM self-reflection after
    `harness_patch_proposal_threshold` failures; ExecutionSummary attached to HITL payloads
  - 28 unit tests

- **B3 — Persistent Agent Memory** (`specs/ai/agent-memory.md`, ADR-0017):
  - `src/memory/vector_store.py`: `VectorStore` protocol + `InMemoryVectorStore` + `PostgresVectorStore`
  - `src/memory/document_indexer.py`: indexes `specs/` and `docs/adr/` via `pii_filter`
  - `src/memory/session_memory.py`: Redis-backed session cache, 24 h TTL default
  - `src/memory/bug_history_store.py`: HITL rejection recall via semantic similarity
  - `docs/privacy/dpia/dpia-agent-memory.md`: DPIA draft (DPO sign-off pending)
  - `.github/workflows/index-docs.yml`: auto-indexes on push to main
  - 58 unit tests

- **D1 — Vibe-to-Agentic Onboarding Guide** (Issue #12):
  - `docs/quickstart/vibe-to-agentic.md`: 3-level progressive onboarding guide
    (Level 1 Vibe Mode — day one safe prompts; Level 2 Supervised Agentic — reading
    `EvaluatorScore` / `ExecutionSummary`, HITL checkpoints; Level 3 Full Agentic —
    configuring `AutonomyLevel` per action type, tuning `risk_score` thresholds,
    interpreting audit log failure patterns, monitoring SLOs)
  - Includes explicit developer-autonomy risk warning and SDD mandatory-cycle reminder

- **C1 — Agent MTTD/MTTR Metrics** (`specs/observability/agent-performance.md`):
  - `src/observability/metrics.py`: 4 new metrics — `agent_mttd_seconds` (Histogram),
    `agent_mttr_seconds` (Histogram), `agent_autonomous_resolution_rate` (Gauge),
    `agent_cost_per_resolution_tokens` (Histogram); `record_agent_performance()` helper
  - `infrastructure/monitoring/grafana/dashboards/agent-performance.json`: 4-panel dashboard
    (MTTD p50/p99, MTTR p50/p99, autonomous resolution rate gauge, cost per resolution p50/p99)
  - SLO targets: MTTD p99 ≤ 60 s, MTTR p99 ≤ 600 s, resolution rate ≥ 80%, cost p99 ≤ 10 000 tokens
  - 17 unit tests

- **C2 — Hybrid Workflow Docs**:
  - `docs/quickstart/hybrid-workflow.md`: 4-phase Vibe → Agêntico cycle guide
    (Explore, Supervised Agêntico, Full Agêntico, Review & Land) with phase entry/exit conditions
    and governance gates
  - `CLAUDE.md §9`: Hybrid Workflow Mode section with phase table and ADR-0015 governance gate

- **C3 — Agent Chaos Experiments**:
  - `tests/chaos/experiments/agent-context-overflow.yaml`: oversized context truncation + no 500s
  - `tests/chaos/experiments/hitl-store-degradation.yaml`: Redis latency + outage; no silent approval
  - `tests/chaos/experiments/prompt-injection-under-load.yaml`: 50 concurrent injections; all blocked 400
  - `tests/chaos/experiments/evaluator-disagreement.yaml`: split PASS/FAIL verdict triggers HITL
  - `tests/chaos/experiments/llm-api-timeout.yaml`: Toxiproxy timeout; back-off + HITL escalation

- **C4 — Inter-Agent Protocol** (`specs/ai/harness-design.md`):
  - `infrastructure/proto/harness_state.proto`: `HarnessStateEnvelope` with `correlation_id`,
    sprint status enum, `oneof` payload (SprintStarted, SprintEvaluated, PatchProposalApplied,
    SprintEscalated, SprintCompleted)
  - `docs/api/asyncapi/v1/asyncapi.yaml`: `agent.harness.state` channel +
    `HarnessStateChanged` message + `HarnessStateChangedPayload` schema
  - `src/agents/harness/models.py`: `correlation_id` added to `TaskBrief`, `SprintContract`,
    `HarnessResult`, `ExecutionSummary`
  - `src/agents/harness/coordinator.py`: propagates `correlation_id` through sprint lifecycle
    and audit log events

### Changed

- `CLAUDE.md` §3.3: added sandbox rule — "NEVER execute agent-generated code outside
  `src/agents/sandbox_executor.py` without explicit HITL approval" (ADR-0016)
- `CLAUDE.md` §9: added Hybrid Workflow Mode section (C2)
- `src/shared/config.py`: added `sandbox_*`, `feedback_*`, `memory_*`, and
  `harness_patch_proposal_threshold` settings

### Fixed

- `src/shared/llm_client.py`: added `AnthropicLLMClient` — was imported by
  `src/workers/request_consumer.py` at module level but never defined, causing
  `ImportError` on worker startup (latent production bug)
- `tests/unit/agents/test_request_consumer.py`: `RequestConsumer` now has 100%
  unit test coverage (was 0%)

### Privacy

- `docs/privacy/dpia/dpia-agent-memory.md`: DPIA v1.1 — DPO sign-off complete
  2026-05-27; all five §4 items approved; Agent Memory feature cleared for
  production traffic (ADR-0017)

---

## [1.2.1] - 2026-05-26

### Added

- `docs/audit/expert-audit-2026-05-26.md`: audit summary document — 18 findings across four
  severity tiers, per-commit breakdown, and test impact table (PR #7)

---

## [1.2.0] - 2026-05-26

### Fixed

- `src/api/rest/routers/hitl.py`: `hitl_status` endpoint replaced stale `gateway._requests`
  dict access (AttributeError 500) with `gateway._store.pending_count()` — aligned with the
  HITLStore protocol introduced in Wave 3b (ADR-0011)
- `src/observability/metrics.py`: removed duplicate `ACTIVE_HITL_REQUESTS.dec()` from
  `record_hitl_decision()` — gauge lifecycle is the gateway's responsibility; double-decrement
  drove the gauge negative on every approved/rejected decision (ADR-0011)
- `src/agents/hitl_gateway.py`: `record_decision()` now archives APPROVED/REJECTED requests
  via `store.archive()` so `pending_count()` stays accurate and the hard cap is not inflated
  by decided entries (ADR-0011)
- `harness/doc-check.yml`: `spec-exists` and `adr-current` gates rewritten to use
  `PR_BODY_FILE` (mirrors spec-compliance fix); removed `.git/MERGE_MSG` primary source which
  is only populated during local merges and causes false-passes in PR CI (specs/ai/guardrails.md)
- `src/agents/harness/coordinator.py`: PII masking applied pre-LLM (`_generate()`) and
  pre-HITL (`_escalate_to_hitl()`, `_review_spec_with_hitl()`) via `mask_text` / `mask_dict`
  — three mandatory interception points enforced (specs/ai/guardrails.md, ADR-0012)
- `src/agents/hitl_gateway.py`: `ACTIVE_HITL_REQUESTS` gauge now decrements correctly on
  APPROVED/REJECTED decisions — was only decrementing on EXPIRED (ADR-0011)
- `harness/code-check.yml`: `spec-compliance` gate rewritten to use `PR_BODY_FILE` and avoid
  false-pass when it is unset; set `blocking: false`
- `src/agents/harness/coordinator.py` (`_run_simplified`): uses caller-supplied
  `success_criteria` or a description-anchored fallback — removes vague generic criterion
  (specs/ai/harness-design.md §2)
- `skills/privacy/pii.md`: removed fictitious `L2_FIELD_NAMES` registry block; replaced with
  accurate guidance — masking is value-pattern-based, not field-name-based (ADR-0012)
- `src/agents/harness/models.py`: `TaskBrief` gains optional `success_criteria` field
- `harness/code-check.yml`: SAST gate replaced `semgrep || true` with `bandit -r src/ -ll`
  (authoritative SAST tool per `skills/devsecops/secret-scanning.md`)
- `harness/code-check.yml` / `harness/staging-check.yml`: pii-scan gate `|| true` bypass
  removed; staging-check regex fixed (`[^[]` instead of broken `[^\[MASKED]`)
- `skills/ai/guardrails.md` / `skills/privacy/pii.md`: `[TOKEN]` reclassified from L3 to L2
  (JWT/session tokens are Sensitive, not Internal) (ADR-0012)
- `src/guardrails/prompt_injection_guard.py`: dead `_check_length()` method removed (was
  defined but never called in `validate()`)

### Added

- `tests/unit/agents/test_hitl_gateway.py`: gauge-decrement tests (approved + rejected paths)
  and archive tests (approved, rejected, pending count accuracy)
- `tests/unit/guardrails/test_audit_logger.py`: 9 tests covering all 4 query filters, limit,
  copy-on-append, event ID return, and `AuditWriteError` propagation
- `tests/unit/guardrails/test_action_limits.py`: 8 tests for `check_scope_limit()` and the
  unified `check()` guardrail (scope denial, rate limit denial, within-limits pass)
- `tests/unit/api/test_hitl_router.py`: 4 tests covering HITL status endpoint (200 + 503)
  and decision endpoint (404 unknown + 200 valid approval)
- `tests/unit/agents/test_hitl_gateway.py`: `TestHITLGatewayInit` — verifies default
  `InMemoryHITLStore` is created when no store is supplied

---

## [1.1.1] - 2026-05-26

### Fixed

- `src/guardrails/pii_filter.py`: `_get_patterns()` promovido para `ClassVar` — 7 regexes compiladas uma vez no import em vez de a cada chamada a `detect()` / `mask_text()` (hot path: executa antes de todo log write e LLM call) (ADR-0012)
- `src/guardrails/prompt_injection_guard.py`: `RejectionReason.NESTED_INSTRUCTION` removido do enum — era dead code não utilizado pelo guard e exposto na API pública (ADR-0012)
- `src/shared/config.py`: `database_url` e `redis_url` agora validados em produção — placeholders rejeitados no startup (ADR-0008); `SECRET_KEY` com menos de 32 chars rejeitado quando `JWT_ALGORITHM=HS256`
- `src/shared/config.py`: `service_version` lido dinamicamente de `version.txt` em vez de hardcoded `"0.0.0"` (ADR-0002)
- `src/api/rest/main.py`: `AsyncGenerator[None, None]` corrigido para `AsyncGenerator[None]` — default arg desnecessário removido (UP043, Python 3.13)
- `alembic/versions/0001_create_audit_events.py`: role do DB lido do `alembic.ini` via `context.config.get_main_option("db_app_role", "app_user")` em vez de hardcoded; `REVOKE` envolto em guard `DO $$ IF EXISTS` para não falhar silenciosamente se a role não existir (ADR-0011)
- `alembic/env.py`: substituído `engine_from_config` síncrono por `create_async_engine` + `asyncio.run()` — codebase só tem asyncpg, sem psycopg2 (ADR-0002)
- `.github/workflows/ci.yml`: job `build` agora requer `[test-unit, test-security, test-integration]` — antes podia rodar com testes falhando; Kafka atualizado de `7.6.0` para `7.7.0`
- `.github/workflows/cd-production.yml`: gates de canary substituídos de `bc` (não disponível no ubuntu-latest) para `python3`; estratégias de deploy restritas a `[canary]`
- `docker-compose.yml`: Redis com `--save 60 1` (persistência activada); Kafka com listener `INTERNAL://kafka:29092` para comunicação inter-container sem usar o listener externo

### Added

- `tests/conftest.py`: fixtures `stub_llm` (`StubLLMClient`) e `audit_logger` (`AuditLogger` + `InMemoryAuditStorage`) disponíveis globalmente para todos os testes — elimina duplicação inline
- `mkdocs.yml`: configuração mínima do mkdocs-material criada — `make docs-serve` e `mkdocs build --strict` agora funcionam; nav cobre todos os docs existentes (ADRs, AI Governance, Privacy, SRE, Change Management)
- `.github/dependabot.yml`: Dependabot configurado para pip e github-actions com cadência semanal e limite de 5 PRs por ecossistema
- `infrastructure/message-broker/schema-registry/avro/`: 6 schemas Avro stub criados com os nomes exatos referenciados em `services.yaml` (`request-created-v1.avsc`, `hitl-decision-v1.avsc`, `audit-event-v1.avsc`, `domain-entity-created-v1.avsc`, `domain-entity-updated-v1.avsc`, `event-processed-v1.avsc`) — CI `contract-drift` agora passa (ADR-0003)
- `tests/unit/shared/test_config.py`: 3 novos testes — `DATABASE_URL` com placeholder rejeitado em produção, `REDIS_URL` com placeholder rejeitado em produção, `SECRET_KEY` curto com HS256 rejeitado

### Changed

- `pyproject.toml`: alinhado para Python 3.13 — `requires-python = ">=3.13"`, `ruff target-version = "py313"`, `mypy python_version = "3.13"`; adicionado `"alembic/**" = ["S608"]` em `per-file-ignores` (SQL dinâmico é padrão em migrations)
- `Dockerfile`: ambos os stages atualizados de `python:3.12-slim` para `python:3.13-slim`
- `.github/workflows/ci.yml`: todos os 4 steps `setup-python` atualizados de `"3.12"` para `"3.13"`
- `.env.example`: `REDIS_PASSWORD=devpassword` e `REDIS_URL` com senha adicionados; alinhado com `docker-compose.yml`
- `Makefile`: `make new-service` agora cria estrutura mínima Python (`src/<name>/`, `__init__.py`, `README.md`, `pyproject.toml`) em vez de diretório vazio
- `.gitignore`: `resumo-*.md` e `site/` adicionados para evitar commit de artifacts de sessão e build do mkdocs

### Removed

- `resumo-memória-2026-05-26.md`: artifact de sessão Claude Code removido do repositório

---

## [1.1.0] - 2026-05-26

### Added (multi-language template — Block 4)

- `.github/workflows/ci-java.yml`: Java CI pipeline — `lint-java` (Checkstyle + SpotBugs + OWASP dependency-check), `test-java-unit` (JaCoCo ≥ 80%), `test-java-integration` (PostgreSQL + Redis + Kafka services), `build-java` (Spring Boot buildpack); auto-discovers all `services/*/pom.xml`; triggered only on Java/contract file changes
- `.github/workflows/ci-go.yml`: Go CI pipeline — `lint-go` (golangci-lint + proto drift check), `test-go-unit` (race detector + 80% coverage gate), `test-go-integration` (PostgreSQL + Redis + Kafka services), `build-go`; auto-discovers all `services/*/go.mod`; triggered only on Go/proto file changes
- `.github/workflows/ci-frontend.yml`: Frontend CI pipeline — `lint-frontend` (ESLint + TypeScript + API client drift check), `test-frontend-unit` (Jest + 80% coverage gate), `test-frontend-e2e` (Playwright), `build-frontend` (Docker image); matrix over `app:` list; triggered only on `frontend/**` or OpenAPI changes
- `docs/quickstart/add-new-service.md`: step-by-step 10-step checklist for registering a new service — language selection table (Python/Java/Go criteria), directory scaffold, services.yaml registration, CODEOWNERS, Prometheus scrape config, K8s manifests, env vars, CI wiring, Dockerfile templates per language, spec-first requirement, day-1 PR checklist
- `infrastructure/k8s/service.yaml`: K8s ClusterIP Service manifest template for agent-service

### Changed (multi-language template — Block 4)

- `.github/workflows/ci.yml`: added `contract-drift` job — validates OpenAPI + AsyncAPI specs are parseable, proto files compile, and `services.yaml` schema file references all exist on disk
- `CONTRIBUTING.md`: added per-language test/lint command table to "Before opening a PR" section; added checklist items for `services.yaml` and Prometheus config when adding new services; linked to `add-new-service.md`
- `docs/quickstart/README.md`: added `add-new-service.md` row to "After reading your language guide" table; updated label to "read these in order"
- `Makefile`: added `new-service` scaffold target (`make new-service NAME=foo LANG=python|java|go`); creates directory structure, go.mod, K8s manifests from templates; updated `.PHONY` list

### Added (multi-language template — Block 3)

- `infrastructure/monitoring/prometheus/prometheus.yml`: Prometheus scrape config — jobs for api-gateway (port 8000 `/metrics`), domain-service (port 8080 `/actuator/prometheus`), event-worker (port 8090 `/metrics`), otel-collector self-telemetry; rule_files wired to golden-signals.yaml; commented stubs for postgres/kafka exporters
- `infrastructure/monitoring/grafana/provisioning/datasources/datasource.yml`: Grafana datasource provisioning — Prometheus as default datasource with exemplar→Jaeger trace linking; Jaeger datasource
- `infrastructure/monitoring/grafana/provisioning/dashboards/dashboard.yml`: Grafana dashboard provisioning — auto-loads all JSON dashboards from `/var/lib/grafana/dashboards` with 30s hot-reload
- `docker-compose.yml`: fixed Grafana volume mounts — provisioning directory now correctly wired (`./grafana/provisioning:/etc/grafana/provisioning`) and dashboard JSONs mounted at `/var/lib/grafana/dashboards`
- `docs/api/grpc/proto/ai_service.proto`: example proto file — `AgentService` (SubmitTask unary + WatchTask server-streaming) and `HITLService` (SubmitForApproval + GetDecision); replaces .gitkeep; includes field numbering rules and generation instructions
- `docs/quickstart/contract-driven-dev.md`: contract-driven development guide — OpenAPI→TypeScript/Java/Go/Python generation commands; AsyncAPI+Avro consumer patterns per language; gRPC stub generation per language; contract change workflow; CI diff-check pattern; quick-reference table of all generators
- `docs/quickstart/README.md`: added "After reading your language guide" row linking to contract-driven-dev.md

### Changed (multi-language template — Block 3)

- `Makefile`: added `gen-proto-python`, `gen-sources-java`, `gen-api-client-python` targets; updated `.PHONY` list

### Added (multi-language template — Block 2)

- `docker-compose.yml`: shared development infrastructure stack — PostgreSQL 16, Redis 7, Kafka 7.7 (KRaft), Schema Registry, OTel Collector, Jaeger, Prometheus, Grafana, flagd; healthchecks on all services; named volumes; monorepo-dev network
- `docker-compose.test.yml`: lightweight integration-test stack with offset ports (PG 5433, Redis 6380, Kafka 9093) and tmpfs for speed; no observability services
- `.env.example`: fully rewritten — organized into per-language sections (Python, Java, Go, Frontend, Jobs); REQUIRED vs OPTIONAL markers on every var; Spring Boot property name translations; test environment vars (TEST_DATABASE_URL etc.); security generation instructions
- `frontend/.env.example`: frontend-only env stub — NEXT*PUBLIC*\* vars only, browser-safe HTTP OTel endpoint, flagd OFREP URL; no secrets

### Changed (multi-language template — Block 2)

- `Makefile`: added `infra-up`, `infra-down`, `infra-reset`, `test-infra-up`, `test-infra-down` targets for managing docker-compose stacks; updated .PHONY list

### Added (multi-language template — Block 1)

- `docs/quickstart/java-backend.md`: Java/Spring Boot developer quickstart — prerequisites, project layout, setup steps, resilience patterns (Resilience4j), PII masking, HITL REST client, Kafka consumer, structured logging, Testcontainers conventions, key ADRs
- `docs/quickstart/go-backend.md`: Go developer quickstart — prerequisites, project layout, setup steps, circuit breaker (gobreaker), context timeouts, PII masking, HITL REST client, structured slog, OTel Go SDK, testcontainers-go conventions, key ADRs
- `docs/quickstart/frontend.md`: React/Next.js developer quickstart — prerequisites, project layout, generated API client (openapi-generator), React Query + HITL polling, PII masking in UI, OTel browser tracing, Jest + Playwright testing conventions, key ADRs
- `docs/quickstart/jobs-worker.md`: Scheduled jobs & batch worker quickstart — BaseJob interface, APScheduler registration, idempotency + checkpointing pattern, HITL routing from batch context, job README requirements, K8s CronJob deployment
- `services.yaml`: service catalog (root) — all services with language, type, port, image, owner, Kafka publish/subscribe topics, runtime dependencies, governing ADRs; topic catalogue with schema paths, partitions, retention
- `.devcontainer/devcontainer.json`: multi-language devcontainer — Python 3.12, Java 21, Go 1.23, Node 20, Docker-in-Docker, kubectl + helm; VS Code extensions for all languages; port forwarding for all services and infra
- `.devcontainer/post-create.sh`: automated post-create script — installs uv, pnpm, Go tools (air, golangci-lint, protoc plugins), Java/Maven verification, pre-commit hooks, copies .env.example, starts infra stack, runs Alembic migrations

### Changed (multi-language template — Block 1)

- `Makefile`: extended with per-language targets (`test-python`, `test-java`, `test-go`, `test-frontend`, `lint-*`, `format-*`, `build-*`, `run-*`); added `gen-proto-go`, `gen-api-client-ts`, `new-service` scaffold; legacy aliases preserved; `help` column width updated; `SERVICE` and `APP` variables added

### Added (documentation — post v1.0.0 audit)

- `infrastructure/README.md`: criado — overview de K8s manifests, probe configuration, HPA custom metrics, related ADRs
- `infrastructure/feature-flags/README.md`: criado — arquitetura OpenFeature + flagd, catálogo de flags, instruções para adicionar nova flag
- `SETUP/013-prompt.md`: criado — prompt de scaffolding para a camada de resiliência e maturidade de plataforma (retry, HITL store, feature flags, K8s, alembic, chaos experiments)

### Changed (documentation — post v1.0.0 audit)

- `README.md`: versão atualizada para 1.0.0; ADR-0014 e ADR-0015 adicionados à seção de ADRs chave; seção Feature Flags criada; CUJ-001 dashboard adicionado à tabela de Observability; RB-003-hitl-recovery adicionado à seção On-call; estrutura de repositório atualizada com novos módulos; seção "Harness Engineering & Design Audit" adicionada com scorecard D1–D8
- `CLAUDE.md`: `src/agents/hitl_store.py` e `src/shared/feature_flags.py` adicionados à tabela de File Ownership; `infrastructure/feature-flags/` adicionado à governança; rule 3.3 atualizada com referência ao controle HOTL via feature flag (ADR-0015)
- `docs/adr/README.md`: ADR-0015 (Feature Flag Strategy) adicionado ao Master Index
- `MONOREPO-STRUCTURE-EN.md`: `src/agents/` atualizado com `hitl_store.py` e subdiretório `harness/`; `src/shared/` atualizado com `retry.py`, `db_client.py`, `llm_client.py`, `feature_flags.py`
- `SETUP/README.md`: prompts 011 (Validation) e 012 (Postmortem) com descrições corrigidas (estavam trocadas); prompt 013 adicionado; file map atualizado com todos os arquivos das waves P1/P2/P3; versão do template bumped para 2.2.0

---

## [1.0.0] - 2026-05-25

### Added (P3 Wave 3c — platform maturity)

- `src/shared/feature_flags.py`: `is_autonomous_mode_enabled()` — thin OpenFeature SDK
  wrapper that evaluates the `autonomous-mode` flag; falls back to
  `settings.autonomous_mode_enabled` when the SDK is unavailable (ADR-0015)
- `docs/adr/ADR-0015-feature-flag-strategy.md`: documents choice of OpenFeature + flagd —
  vendor-neutral CNCF standard; provider swap (LaunchDarkly, Unleash) requires no
  application code changes
- `infrastructure/feature-flags/flags/autonomous-mode.yaml`: flag definition with
  `defaultVariant: "off"` (HITL required by default)
- `infrastructure/feature-flags/flagd.yaml`: k8s Deployment + Service + ConfigMap for
  flagd (lightweight OpenFeature evaluation server reading flags from mounted YAML)
- `infrastructure/k8s/prometheus-adapter-config.yaml`: Prometheus Adapter ConfigMap with
  rules mapping `agent_semaphore_waiting` and `kafka_consumer_lag` to `custom.metrics.k8s.io`
- `tests/unit/shared/test_feature_flags.py`: 6 unit tests using `InMemoryProvider` —
  flag on/off, SDK-overrides-settings, fallback on SDK error

### Changed (P3 Wave 3c — platform maturity)

- `src/agents/orchestrator/orchestrator.py`: HITL routing now gated by
  `is_autonomous_mode_enabled()` — when autonomous mode is enabled (HOTL), high-risk
  actions bypass HITL approval; disabled by default for safety
- `infrastructure/k8s/hpa.yaml`: added custom-metric rules for `agent_semaphore_waiting`
  (scale when avg > 3 waiting per pod) and `kafka_consumer_lag` (scale when lag > 5000);
  added `behavior` block with stabilization windows to prevent thrashing (PRR-CAP-001)
- `pyproject.toml`: added `openfeature-sdk>=0.4.0` to runtime dependencies

### Added (P3 Wave 3b — HITL Redis persistence)

- `src/agents/hitl_store.py`: `HITLStore` Protocol + `InMemoryHITLStore` + `HITLRedisStore` —
  pluggable persistence backends for HITL requests; Redis-backed store survives pod restarts
  (ADR-0011). Schema: `hitl:req:{id}` (active, TTL = expires_at + 24 h grace),
  `hitl:pending` sorted set (score = expires_at timestamp), `hitl:expired:{id}` (7-day audit archive)
- `docs/runbooks/RB-003-hitl-recovery.md`: HITL recovery runbook covering pod restart, Redis
  failover, stuck queue, capacity exhaustion, and manual key inspection (satisfies PRR-OPS-002)
- `tests/integration/test_hitl_redis_store.py`: 14 integration tests for `HITLRedisStore`
  using `fakeredis` (no external service required) — save/get round-trip, TTL semantics,
  archive, pending-expired queries

### Changed (P3 Wave 3b — HITL Redis persistence)

- `src/agents/hitl_gateway.py`: `HITLGateway` now accepts an injectable `store: HITLStore`
  parameter; defines `HITLStore` Protocol; defaults to `InMemoryHITLStore` via lazy import
  when no store is provided — breaks no existing callers
- `src/api/rest/main.py`: lifespan startup selects `HITLRedisStore` when Redis is available,
  falls back to `InMemoryHITLStore` for local dev; wires store into `HITLGateway`
- `src/shared/config.py`: added `hitl_redis_key_prefix`, `hitl_redis_ttl_grace_hours`,
  `hitl_expired_ttl_days` configuration fields
- `tests/unit/agents/test_hitl_gateway.py`: updated to construct `InMemoryHITLStore` explicitly
  and inject into `HITLGateway`; assertions updated from direct dict access to store API
- `pyproject.toml`: added `fakeredis>=2.0.0` to dev dependencies

### Added (P3 Wave 3a — quick wins)

- `infrastructure/k8s/deployment.yaml`: `startupProbe` added (httpGet `/health`,
  `failureThreshold: 30`, `periodSeconds: 10` — 5-minute startup window). Prevents
  premature liveness kills during slow boot (asyncpg pool + Redis ping). Reduced
  `livenessProbe.initialDelaySeconds` from 15 → 5 since startupProbe owns the
  startup gate.
- `infrastructure/monitoring/grafana/cuj-dashboards/CUJ-001-user-request-processing.json`:
  Grafana dashboard covering all 7 steps of CUJ-001 with 12 panels — SLO stat rows
  (availability ≥ 99.9%, p99 latency ≤ 500ms, HITL approval ≤ 300s, error budget),
  time-series for request rate/latency/HITL queue/decisions/semaphore saturation/LLM
  tokens/DLQ depth. Satisfies PRR-OBS-005 (blocking).

### Added (harness audit P2 — operational resilience)

- `src/shared/db_client.py`: `ResilientDBPool` — wraps `asyncpg.Pool` with per-call
  `asyncio.wait_for` timeout, exponential-backoff retry via `with_retry`, and three-state
  circuit breaker via `CircuitBreaker`; reuses existing patterns from `retry.py` (ADR-0002)
- `src/api/rest/main.py`: `asyncio.Semaphore(settings.max_concurrent_agents)` created at
  startup — caps simultaneous agent coroutines to prevent event-loop starvation under burst load
- `src/observability/metrics.py`: `AGENT_SEMAPHORE_WAITING` gauge (requests waiting for a slot)
  and `DLQ_MESSAGES_COUNTER` counter (messages routed to Dead Letter Queue)
- `tests/unit/shared/test_db_client.py`: 9 unit tests — happy path, circuit breaker states,
  timeout propagation
- `tests/unit/agents/test_hitl_gateway.py`: 7 unit tests — hard cap enforcement, post-expiry
  eviction, slot recycling after eviction
- `tests/unit/api/test_requests_semaphore.py`: 4 unit tests — 503 + `Retry-After` when all
  slots occupied, 202 when capacity available, backwards-compatibility without semaphore state

### Fixed (harness audit P2 — operational resilience)

- `src/api/rest/main.py`: DB pool now wrapped in `ResilientDBPool` — every query gets
  timeout + retry + circuit breaker protection (previously unguarded)
- `src/guardrails/audit_logger.py`: `PostgresAuditStorage` type annotation updated to accept
  `ResilientDBPool` alongside `asyncpg.Pool` — no runtime behaviour change
- `src/agents/hitl_gateway.py`: `expire_stale_requests()` now evicts expired entries from
  `_requests` dict after marking them EXPIRED — prevents unbounded memory growth
- `src/agents/hitl_gateway.py`: `submit_for_approval()` raises `HITLGatewayError` when store
  reaches `settings.hitl_max_pending_requests` — explicit backpressure instead of silent OOM
- `src/shared/config.py`: added `max_concurrent_agents: int = 20` and
  `hitl_max_pending_requests: int = 500` configuration fields
- `src/api/rest/routers/requests.py`: endpoint returns 503 + `Retry-After: 5` header when
  `agent_semaphore._value == 0` — operationally visible backpressure
- `tests/chaos/experiments/network-partition.yaml`: DLQ assertion regex escaped and aligned
  to real metric name `dlq_messages_total`
- `.github/workflows/chaos-schedule.yml`: schedule updated to weekday nightly runs
  (`0 2 * * 1-5`) — chaos experiments now committed and active in CI

### Fixed (harness audit P1 — production safety)

- `infrastructure/k8s/pdb.yaml`: `minAvailable` corrected from 1 → 2 to satisfy PRR-CAP-003;
  prevents zero-replica windows during node drains with a 2-replica deployment
- `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`: `AgentActionErrorRate` query
  label corrected from `outcome=` to `result=` to match `agent_actions_total` label in `metrics.py`
- `infrastructure/monitoring/prometheus/rules/golden-signals.yaml`: `LLMTokenBudgetNearing` query
  fixed to use actual metric names (`llm_tokens_total{token_type="input"}` / `llm_tokens_budget_total`)
- `src/api/rest/main.py`: `asyncpg.create_pool()` wrapped in `asyncio.wait_for(timeout=15s)` and
  Redis ping wrapped in `asyncio.wait_for(timeout=5s)` to prevent infinite boot loops on
  unresponsive dependencies
- `src/api/rest/main.py`: `InMemoryAuditStorage` fallback now raises `RuntimeError` when
  `app_env == "production"` — prevents silent audit record loss on pod restart

### Added (harness audit P1 — production safety)

- `src/shared/config.py`: `model_validator` rejects placeholder secrets (`LLM_API_KEY`,
  `SECRET_KEY`) when `app_env == "production"` — fail-fast at startup prevents misconfigured pods
  from reaching first LLM call
- `src/observability/metrics.py`: `LLM_TOKEN_BUDGET` gauge (`llm_tokens_budget_total`) and
  `init_budget_gauge()` helper — sets the static monthly budget at startup so the
  `LLMTokenBudgetNearing` alert can compute a ratio
- `tests/unit/shared/test_config.py`: 7 unit tests covering production secret validation
  (placeholder rejection, environment scoping, case-insensitivity)
- `tests/unit/shared/test_metrics.py`: 3 unit tests for `init_budget_gauge()` and
  `LLM_TOKEN_BUDGET` gauge behaviour

### Added (harness engineering compliance — ADR-0014, ADR-0011)

- `src/shared/retry.py` — `TransientError`, `CircuitBreakerError`, `with_retry()` tenacity decorator
  (exponential backoff + jitter), `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN state machine),
  `ResilientLLMClientWrapper` composing timeout + circuit breaker + retry (ADR-0014)
- `src/shared/llm_client.py`: `TimeoutLLMClientWrapper` applying `asyncio.wait_for` ceiling on
  all LLM calls — prevents event loop starvation from unresponsive upstream (ADR-0014)
- `src/guardrails/audit_logger.py`: `PostgresAuditStorage` full implementation backed by asyncpg;
  parameterized INSERT-only writes, parameterized SELECT with optional filters; wired as default
  production backend when DB pool is available (ADR-0011)
- `alembic/versions/0001_create_audit_events.py` — migration creating `audit_events` table with
  two composite indexes and `REVOKE UPDATE, DELETE` for append-only enforcement (ADR-0011)
- `alembic/env.py`, `alembic.ini` — Alembic configuration wired to `settings.database_url` (ADR-0002)
- `src/guardrails/action_limits.py`: `ActionLimiter.check(action_type, parameters)` — unified
  async entry point combining scope and rate checks; raises `ValueError` on denial (ADR-0014)
- `src/api/rest/_limiter.py` — shared slowapi `Limiter` singleton keyed by client IP (ADR-0002)
- `infrastructure/k8s/deployment.yaml` — K8s Deployment with liveness/readiness probes,
  `preStop` hook, resource requests/limits, and RollingUpdate strategy (ADR-0005)
- `infrastructure/k8s/service.yaml` — ClusterIP Service for agent-service (ADR-0005)
- `infrastructure/k8s/pdb.yaml` — PodDisruptionBudget `minAvailable: 1` (PRR-CAP-003) (ADR-0005)
- `infrastructure/k8s/hpa.yaml` — HorizontalPodAutoscaler 70% CPU target, 2–10 replicas
  (PRR-CAP-001) (ADR-0005)
- `tests/chaos/experiments/kill-agent.yaml` — Chaos Toolkit experiment: kill pod, verify
  Golden Signals recovery (specs/sre/game-day-playbook.md)
- `tests/chaos/experiments/network-partition.yaml` — Chaos Toolkit experiment: agent ↔ Kafka
  partition via Toxiproxy, verify DLQ routing and lag recovery (ADR-0007)
- `tests/chaos/experiments/broker-outage.yaml` — Chaos Toolkit experiment: Kafka StatefulSet
  scaled to 0, verify producer buffering and zero data loss (ADR-0007)
- `.github/workflows/chaos-schedule.yml` — weekly scheduled chaos CI running all three
  experiments against staging (specs/sre/game-day-playbook.md)

### Changed (harness engineering compliance — ADR-0014, ADR-0011)

- `src/api/rest/main.py`: lifespan now initializes asyncpg pool, Redis client, `AuditLogger`
  (PostgresAuditStorage in prod, InMemoryAuditStorage on failed pool), and `HITLGateway` in
  `app.state`; mounts `/metrics` ASGI app; registers slowapi middleware and rate-limit handler;
  wires OTel `FastAPIInstrumentor` (ADR-0002, ADR-0003, ADR-0011)
- `src/api/rest/routers/health.py`: `/ready` performs real asyncpg and Redis connectivity
  checks with `asyncio.wait_for` timeouts; returns 503 when either dependency is unreachable
  (ADR-0002)
- `src/api/rest/routers/hitl.py`: implemented `get_hitl_gateway` dependency, `hitl_status`
  returning real pending count from `app.state.hitl_gateway`, and `submit_decision` calling
  `gateway.record_decision()` (ADR-0011)
- `src/api/rest/routers/requests.py`: `submit_request` decorated with
  `@limiter.limit("{rate_limit_requests_per_minute}/minute")` to enforce per-IP rate limit
  (ADR-0002)
- `src/agents/hitl_gateway.py`: added `asyncio.Lock` protecting `_requests` dict; all
  read/write operations use phase-separated locking (state transition under lock, I/O outside)
  (ADR-0011)
- `src/agents/orchestrator/orchestrator.py`: `_act()` now `await`s `action_limiter.check()`
  using the new unified method signature (ADR-0014)
- `src/shared/config.py`: added `llm_call_timeout_seconds`, `redis_call_timeout_seconds`,
  `shutdown_drain_seconds`, `llm_circuit_breaker_threshold`, `llm_circuit_breaker_reset_seconds`,
  `llm_retry_max_attempts` (ADR-0014)
- `Dockerfile`: replaced `CMD` with `ENTRYPOINT` (exec form) and added `STOPSIGNAL SIGTERM`
  so uvicorn receives signals directly as PID 1 (ADR-0005)
- `pyproject.toml`: added `tenacity>=8.3.0` and `slowapi>=0.1.9` to production dependencies

### Added

- `.secrets.baseline` criado para habilitar `detect-secrets` no pre-commit hook (P2-01)
- Governance headers (`Owner`/`Reviewer`/`Status`/`Last updated`) adicionados aos 13 skill files (P2-03)

### Fixed

- `tests/unit/guardrails/test_pii_filter.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `tests/unit/guardrails/test_prompt_injection_guard.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `tests/security/test_pii_leakage.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `tests/security/test_owasp_llm_top10.py`: adicionados `Spec:` e `ADR:` no docstring (P2-04)
- `specs/api/async-api-design.md`: Testing Requirements corrigido para documentar uso do
  `InMemoryProducer` para testes estruturais + Kafka real em CI (P2-05)

### Added

- Avro schemas (5 arquivos) em `infrastructure/message-broker/schema-registry/avro/` cobrindo
  todos os 8 event types do catálogo: `domain_request.avsc`, `agent_action.avsc`,
  `hitl_decision.avsc`, `domain_result.avsc`, `audit_event.avsc` (ADR-0003, ADR-0005)
- `tests/integration/test_kafka_events.py` — testes de contrato Kafka: envelope structure,
  PII masking pre-publish, topic naming convention, UUID v4 idempotency key,
  non-PII field preservation (ADR-0003, ADR-0012)

### Fixed

- `skills/ai/guardrails.md`: corrigidos nomes de métodos errados (`audit_logger.record()` →
  `await audit_logger.log_event(AuditEvent(...))`, `injection_guard.check()` →
  `injection_guard.validate()`, `result.rejected` → `not result.is_valid`,
  `result.category` → `result.rejection_reason`) (P0-01)
- `skills/ai/guardrails.md`: tokens de masking corrigidos de `[MASKED_L2]`/`[MASKED_L1]`
  para tokens por tipo `[EMAIL]`/`[CPF]` conforme implementação real em `pii_filter.py` (P0-02)
- `skills/privacy/pii.md`: tabela de Classification Levels e exemplo de teste corrigidos —
  `[MASKED_L1/L2/L3]` → `[CPF]`/`[CARD]`, `[EMAIL]`/`[PHONE]`/`[IP]`, `[TOKEN]`/`[UUID]`
  (P0-03, ADR-0012)
- `specs/ai/guardrails.md`: tabela de masking tokens no Layer 1 PII Filter corrigida para
  tokens por tipo, alinhando spec com código e ADR-0012 (P0-04 / P1-04)
- `src/shared/config.py`: adicionados `hitl_risk_threshold: float = 0.4` e
  `hotl_override_window_seconds: int = 300` — campos referenciados pelo orchestrator e
  ausentes da configuração (P0-05, ADR-0011, specs/ai/hitl-hotl.md)
- `specs/README.md`: `specs/api/async-api-design.md` registrado na tabela de ownership
  com Owner: Tech Lead, Reviewer: DevOps Lead, Status: Approved (P1-01)

### Added (harness design — ADR-0014)

- `docs/adr/ADR-0014-multi-agent-harness-strategy.md` — architectural decision capturing why
  multi-agent harness is needed (quality plateau, context exhaustion), Planner+Generator+Evaluator
  pattern, cost multipliers, and rejected alternatives (ADR-0014)
- `specs/ai/harness-design.md` — full harness design spec: agent roles, sprint contract schema,
  context management strategy, handoff model, harness modes, HITL integration, observability (ADR-0014)
- `src/agents/harness/models.py` — typed dataclasses: `TaskBrief`, `SprintContract`, `ProductSpec`,
  `GeneratorArtifact`, `EvaluatorScore`, `ContextSnapshot`, `HarnessResult` (ADR-0014)
- `src/agents/harness/context_manager.py` — `ContextManager` with `should_reset()`,
  `create_snapshot()` (decisions capped at 20/200 chars, PII safety-net applied),
  `restore_prompt()` (ADR-0014, specs/ai/harness-design.md §3)
- `src/agents/harness/planner.py` — `PlannerAgent` with injection guard, PII masking,
  LLM planning call, audit logging on `plan_generated` (ADR-0014, specs/ai/harness-design.md §1.1)
- `src/agents/harness/evaluator.py` — `EvaluatorAgent` with explicit skepticism system prompt,
  4-dimension scoring (quality/originality/craft/functionality), pass threshold per dimension
  (ADR-0014, specs/ai/harness-design.md §1.3)
- `src/agents/harness/coordinator.py` — `HarnessCoordinator` supporting solo/simplified/full modes;
  generate→evaluate→retry loop; HITL escalation on max iterations; optional spec HITL review
  (ADR-0014, specs/ai/harness-design.md §1.4)
- `src/shared/llm_client.py` — `LLMClient` Protocol + `StubLLMClient` for tests (ADR-0014)
- `skills/ai/harness.md` — multi-agent harness skill: mode selection table, sprint contract
  checklist, evaluator skepticism block, context reset pattern, HITL escalation protocol (ADR-0014)
- `tests/unit/agents/harness/test_context_manager.py` — 17 unit tests for `ContextManager`
  (should_reset, create_snapshot, restore_prompt) (ADR-0014)
- `tests/unit/agents/harness/test_evaluator.py` — 11 unit tests for `EvaluatorAgent`
  (pass/fail dimensions, threshold boundary, audit log, invalid JSON) (ADR-0014)
- `tests/unit/agents/harness/test_planner.py` — 10 unit tests for `PlannerAgent`
  (injection rejection, invalid JSON, audit log, missing contracts) (ADR-0014)
- `tests/unit/agents/test_orchestrator.py` — 9 unit tests for `AgentOrchestrator`
  (PII masking, injection guard, HITL routing, write-before-execute invariant) (ADR-0011, ADR-0014)
- `tests/integration/test_harness_pipeline.py` — 11 integration tests for end-to-end simplified
  harness pipeline (HarnessResult, artifact storage, evaluator audit log, no HITL escalation on
  first pass) (ADR-0014)

### Changed (harness design — ADR-0014)

- `src/shared/config.py`: added 7 harness settings fields (`harness_mode`, `harness_context_reset_threshold`,
  `harness_max_iterations`, `harness_evaluator_pass_threshold`, `harness_planner_enabled`,
  `harness_evaluator_enabled`, `harness_planner_hitl_review`) (ADR-0014)
- `src/agents/orchestrator/orchestrator.py`: closed `_reason()` and `_act()` `NotImplementedError`
  stubs; added LLM call with masked context, HITL routing via `HITLGateway`, write-before-execute
  audit log, `llm_client` constructor parameter (ADR-0010, ADR-0011)
- `CLAUDE.md`: added Multi-Agent Harness row to Skill Activation Table (ADR-0014)
- `skills/README.md`: added Multi-Agent Harness row to skill catalog (ADR-0014)
- `docs/adr/README.md`: added ADR-0014 row to Master Index (ADR-0014)
- `specs/README.md`: added `specs/ai/harness-design.md` to Ownership Table (ADR-0014)

### Added (anterior — P0/P1 audit sprint anterior)

- ADR-0002 through ADR-0009: Technology Stack, Async API, Observability, Message Broker,
  Deployment Strategy, Service Mesh, Secrets Management, Caching Strategy
- `pyproject.toml` with Ruff, mypy (strict), pytest, and Bandit configuration (R-01)
- `Dockerfile` multi-stage build (builder + production) with non-root user (R-02)
- `.pre-commit-config.yaml` enforcing Ruff, mypy, detect-secrets, and Bandit before commit (R-03)
- `version.txt` for Makefile version management (R-05)
- `specs/api/async-api-design.md` async API design rules and event catalogue (S-01)
- `docs/api/openapi/v1/openapi.yaml` REST API contract stub (T-04)
- `docs/api/asyncapi/v1/asyncapi.yaml` Kafka async event contract stub (T-04)
- `src/api/rest/main.py`, `routers/health.py`, `routers/requests.py`, `routers/hitl.py` — FastAPI stubs (T-02)
- `src/agents/orchestrator/orchestrator.py` — Perception→Reason→Act loop skeleton (T-05)
- `tests/integration/test_hitl_gateway_integration.py` — HITL lifecycle integration tests (T-01)
- `tests/integration/test_pii_filter_pipeline.py` — PII masking three-interception-point tests (T-01)
- `tests/integration/test_audit_logger_integration.py` — write-before-execute invariant tests (T-01)
- `skills/observability/otel-instrumentation.md` OTel spans, metrics, and logging skill (SK-02)
- `skills/api/rest-api-design.md` REST vs. async decision rules and security checklist (SK-01)
- `skills/devsecops/secret-scanning.md` SAST, detect-secrets, and dependency audit skill (SK-01)
- `skills/sdlc/spec-lifecycle.md` SDD spec writing and lifecycle skill (SK-01)

### Changed

- `CLAUDE.md`: added 4 new skills to the Skill Activation Table; fixed broken reference
  to `specs/api/async-api-design.md` (R-04)
- `skills/README.md`: catalog updated to include 4 new skills (SK-03)
- `src/*/`: all source modules now include `Spec:` and `ADR:` lines in module docstrings (T-03)
- `.github/workflows/ci.yml`: added `governance` job validating ADR index, skill paths,
  and spec paths on every PR (A-04, SK-03); fixed Kafka KRaft config removing
  Zookeeper dependency (R-06); added `detect-secrets` to lint job

---

## [0.1.0] - 2026-05-24

### Added

- Initial monorepo scaffold with full enterprise structure (Issue #1)
- `CLAUDE.md` behavioral contract for AI-assisted development
- Spec-Driven Development (SDD) workflow and 10-step standard process
- Architecture Decision Records framework (`docs/adr/`) with ADR-0001 through ADR-0013
- CI/CD pipeline with 5 stages: Validate → Test → Security → Build → Deploy (ADR-0006)
- Golden Signals observability stack: Prometheus + Grafana + OpenTelemetry (ADR-0004)
- HITL/HOTL human oversight model for AI agents (ADR-0011)
- PII masking guardrail with L1–L4 classification (`src/guardrails/pii_filter.py`) (ADR-0012)
- Prompt injection defense (`src/guardrails/prompt_injection_guard.py`) — OWASP LLM01
- Immutable audit logger for all agent actions (`src/guardrails/audit_logger.py`) — OWASP LLM09
- HITL gateway for human approval of agent actions (`src/agents/hitl_gateway.py`)
- Structured JSON logger with PII masking (`src/observability/logger.py`)
- OpenTelemetry bootstrap (`src/observability/otel_setup.py`)
- Prometheus Golden Signals metrics (`src/observability/metrics.py`)
- Pydantic Settings configuration (`src/shared/config.py`)
- SLO/SLI definitions template (`docs/sre/slo/slo.yaml`)
- Production Readiness Review template (`docs/sre/prr/PRR-TEMPLATE.md`)
- Critical User Journey template (`docs/sre/cuj/CUJ-001-user-request-processing.md`)
- Data privacy documentation: DPIA (GDPR Art. 35), RIPD (LGPD Art. 38), PII inventory
- EU AI Act compliance checklist (`docs/ai-governance/eu-ai-act-compliance.md`)
- NIST AI RMF mapping (`docs/ai-governance/nist-ai-rmf.md`)
- Change management process with RFC and CAB (`docs/change-management/`)
- Runbooks: rollback procedure, disaster recovery
- Enterprise skills catalog (`skills/`)
- Security tests for OWASP LLM Top 10 (`tests/security/test_owasp_llm_top10.py`)
- PII leakage test suite (`tests/security/test_pii_leakage.py`)
- Chaos engineering game day playbook (`tests/chaos/runbooks/game-day-playbook.md`)
- Canary + blue-green deploy scripts (`infrastructure/scripts/deploy/`)
- Async-first event topology with Kafka (ADR-0003, ADR-0005)

### Privacy

- PII inventory established with L1–L4 classification (Issue #1, ADR-0012)
- Data retention policy defined: 30d hot / 90d warm / 1y cold (ADR-0013)
- DPIA and RIPD templates created for GDPR Art. 35 and LGPD Art. 38 compliance
- Data Processing Register (RoPA) template created

[Unreleased]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.7...HEAD
[1.17.7]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.6...v1.17.7
[1.17.6]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.5...v1.17.6
[1.17.5]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.4...v1.17.5
[1.17.4]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.3...v1.17.4
[1.17.3]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.2...v1.17.3
[1.17.2]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.1...v1.17.2
[1.17.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.17.0...v1.17.1
[1.17.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.15.0...v1.17.0
[1.15.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.5.2...v1.6.0
[1.5.2]: https://github.com/valdomirosouza/Repository-Template/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/valdomirosouza/Repository-Template/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/valdomirosouza/Repository-Template/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/valdomirosouza/Repository-Template/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/valdomirosouza/Repository-Template/releases/tag/v0.1.0
