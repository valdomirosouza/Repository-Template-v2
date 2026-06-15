# Reference: Request Lifecycle (submit → HITL → audit)

> **Owner:** Tech Lead | **Status:** Living reference
> An annotated tour of the **critical path** — what actually happens to a request from `POST
/v1/requests` to a human decision and an immutable audit record. It maps the architecture in
> `specs/system/request-pipeline.md` and the journeys in `docs/sre/cuj/CUJ-001…` / `CUJ-002…` to the
> code. File references point at functions (stable) rather than line numbers (which drift); open the
> file to see the exact lines.

```
POST /v1/requests ─► RequestStore ─► Kafka: domain.request.created
                                          │
                          RequestConsumer (asyncio task)
                                          │
                          AgentOrchestrator.run()  ── Perceive → Reason → Act
                                          │
                                   HITLGateway
                              ┌───────────┴───────────┐
                       HITL (block)              HOTL (autonomous)
                              │                        │
        POST /v1/hitl/requests/{id}/decision     execute if autonomy permits
                              │                        │
                         audit_events (immutable, write-before-execute)
```

---

## 1. Submit — `POST /v1/requests`

`src/api/rest/routers/requests.py` → `submit_request()`:

1. Generates a `request_id` (UUID v4).
2. Saves a `RequestState` with `status="queued"` to the request store.
3. **Masks PII** (`mask_dict`, `src/guardrails/pii_filter.py`) before anything leaves the process.
4. Publishes a `domain.request.created` envelope to the broker, keyed by `request_id`.
5. Returns **202 Accepted** with the polling URL (`GET /v1/requests/{request_id}`); **503** if the
   store/broker is unavailable.

Store + broker are injected from `app.state` (wired in the FastAPI lifespan, `src/api/rest/main.py`),
so the same handler runs against Redis/Kafka in prod and the in-memory fallbacks locally.

## 2. Persist — `RequestStore`

`src/agents/request_store.py`: `RedisRequestStore` keys state as `{request_redis_key_prefix}:state:{request_id}`
with a TTL of `request_result_ttl_hours` (default 24h); `InMemoryRequestStore` is the dict-backed
fallback. See `docs/data/redis-key-standards.md`.

## 3. Consume — `RequestConsumer`

`src/workers/request_consumer.py` runs as an asyncio task (started in lifespan) consuming
`domain.request.created`:

- **Idempotency:** skips a message whose stored status is not `queued` (no reprocessing).
- Sets status `processing`, then calls `AgentOrchestrator.run()` with the masked input + `trace_id`.
- **Offset is committed only after handling completes** (success or DLQ) — no silent loss (REM-012).
- **Failure path:** retries with exponential backoff up to `kafka_consumer_max_retries`; on exhaustion
  publishes to `domain.request.dlq` and sets status `failed`. Emits a consumer-heartbeat metric for
  the liveness probe (REM-013).

## 4. Orchestrate — Perceive → Reason → Act

`src/agents/orchestrator/orchestrator.py` → `run()` wraps the three phases in an OTel `agent.task` span:

- **Perceive** (`_perceive`): mask PII (ADR-0012) and run the **prompt injection guard**
  (`src/guardrails/prompt_injection_guard.py`); reject on injection. Span attrs: fields masked,
  injection risk score.
- **Reason** (`_reason`): build the system prompt (+ optional spec-contract boundary and learning
  precedents), call the LLM via `AnthropicLLMClient` (`src/shared/llm_client.py`), and parse the
  response against the `agent_action_v1` schema.
- **Act** (`_act` / `_act_inner`): sanitize output (OWASP LLM02/LLM05), compute the authoritative
  risk score (`RiskScorer`), resolve autonomy (feature flag), check the tool registry, then apply
  the decision matrix below.

### Act decision matrix (simplified)

```
mandatory HITL category            → HITL (cannot be downgraded)
unregistered tool                  → BLOCKED
schema invalid                     → HITL
output sink detected               → HITL
risk_score ≥ hitl_risk_threshold   → HITL
permits autonomous + reversible    → HOTL (execute at autonomy level)
permits autonomous + irreversible  → HITL (ADR-0055)
otherwise                          → HITL
```

`hitl_risk_threshold` defaults to `0.4` (`src/shared/config.py`); see `specs/ai/hitl-hotl.md`.

## 5. Gate — `HITLGateway`

`src/agents/hitl_gateway.py`:

- **`submit_for_approval()`** (HITL path): sets `expires_at`, captures the OTel trace context (so the
  later decision links back to this span), stores the request (`hitl_store.py`, key
  `{hitl_redis_key_prefix}:request:{id}`), enforces `hitl_max_pending_requests`, **writes a
  `hitl.request.submitted` audit event (outcome `PENDING`) before** publishing `agent.action.proposed`.
- HOTL path: if autonomy + reversibility allow, the action executes without blocking (still audited).

## 6. Decide — `POST /v1/hitl/requests/{request_id}/decision`

`src/api/rest/routers/hitl.py` → `submit_decision()` (requires a `hitl-operator` JWT;
`GET /v1/hitl/requests` lists the pending queue, `GET /v1/hitl/status` is the subsystem health):

- Builds a `HITLDecision` with `decision` ∈ {`APPROVED`,`REJECTED`}, `rationale` (10–1000 chars), and
  `approver_id` **taken from the JWT subject, not the body** (anti-forgery, REM-001).
- Calls `gateway.record_decision()`, which (under lock) validates the request is still `PENDING` and
  not expired, transitions status, archives it (`hitl_requests_archive`), then **writes a
  `hitl.decision.recorded` audit event** (outcome = the decision, with `wait_duration_seconds`) and
  publishes the outcome to the broker. An expired request becomes `EXPIRED` (never auto-approved).

The operator UI that calls this is `frontend/web/src/app/hitl/page.tsx` (`ApprovalCard`).

## 7. Audit — immutable, write-before-execute

`src/guardrails/audit_logger.py` → `log_event()` appends to the `audit_events` table
(`PostgresAuditStorage`; `InMemoryAuditStorage` locally, **blocked in `app_env=production`** per
ADR-0075). The table **REVOKEs UPDATE/DELETE** from the app role at the SQL level (migration
`0001_create_audit_events.py`, ADR-0026/SOX). A failed audit write raises `AuditWriteError` and
**blocks the action** — the system never performs an effect it could not record.

---

## Try it locally

```bash
make setup-minimal && make run          # app on :8000, Swagger at /docs (non-prod)
# submit a request, then poll its status, then approve via the HITL queue (operator JWT required)
```

See `docs/quickstart/python-backend.md` and `docs/quickstart/hybrid-workflow.md`.

## Related

- `specs/system/request-pipeline.md` — pipeline contract · `specs/ai/hitl-hotl.md`
- `docs/sre/cuj/CUJ-001-user-request-processing.md` · `docs/sre/cuj/CUJ-002-hitl-decision-flow.md`
- `docs/data/data-model-catalog.md` · `docs/data/erd.md` · `docs/api/error-model.md`
