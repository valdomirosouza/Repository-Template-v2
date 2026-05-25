# Skill — REST API Design

**Owner:** Tech Lead | **Reviewer:** Security Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill when designing or implementing REST endpoints.

Spec: specs/system/architecture.md, specs/api/async-api-design.md
ADR: ADR-0002 (Technology Stack), ADR-0003 (Async API Strategy)

---

## When to Use REST vs. Async Events

| Use REST (sync) for              | Use Kafka events (async) for             |
| -------------------------------- | ---------------------------------------- |
| User-facing queries (< 10 req/s) | High-volume agent pipelines              |
| HITL approval submission         | Agent-internal communication             |
| Health and readiness probes      | Audit event publishing                   |
| Sub-second latency requirement   | Latency-tolerant flows (> 2s acceptable) |

**Rule (ADR-0003):** any flow > 10 req/s must use async events, not REST polling.

---

## Contract-First Workflow

1. Update `docs/api/openapi/v1/openapi.yaml` first — schema before code.
2. Add request/response Pydantic models in the router file.
3. Implement the endpoint handler.
4. Write unit tests for the router (mock dependencies, not the HTTP layer).

---

## Router Structure

```
src/api/rest/routers/
├── __init__.py
├── health.py      — /health, /ready (no auth required)
├── requests.py    — /v1/requests (submit + poll)
└── hitl.py        — /v1/hitl/... (decision submission)
```

Each router file must have a module docstring with `Spec:` and `ADR:` lines.

---

## Security Checklist

- [ ] All user-supplied string inputs validated with Pydantic field constraints (`min_length`, `max_length`, `pattern`)
- [ ] No string-concatenated SQL — use parameterized queries via SQLAlchemy ORM
- [ ] No `eval()`, `exec()`, or `pickle.loads()` on request data
- [ ] Rate limiting applied at the ASGI middleware level (settings: `rate_limit_requests_per_minute`)
- [ ] CORS restricted to `settings.allowed_origins`
- [ ] Docs UI (`/docs`) disabled in production (`docs_url=None` in `main.py`)

---

## PII in Request Bodies

All user-supplied text must be masked before being logged or forwarded to the agent:

```python
from src.guardrails.pii_filter import mask_dict

masked = mask_dict({"request_text": body.request_text})
logger.info("Request received", **masked)        # log masked
await broker.publish(topic, envelope(masked))    # publish masked
```

Never log `body.request_text` directly.

---

## Response Codes

| Scenario                       | Code |
| ------------------------------ | ---- |
| Async request accepted         | 202  |
| Resource created synchronously | 201  |
| Successful read/update         | 200  |
| Validation error               | 422  |
| Not found                      | 404  |
| Server error                   | 500  |

Use FastAPI's `status` module constants, not integer literals.
