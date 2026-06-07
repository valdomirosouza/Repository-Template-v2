# ADR-0002 — Technology Stack Selection

**Status:** Accepted
**Date:** 2026-05-24
**Authors:** Tech Lead

> **Baseline update (2026-06-06, ADR-0059):** the Python runtime baseline was raised
> from 3.12 to **3.13** (and Go to 1.24, Node to 22) to keep the toolchain aligned across
> devcontainer, Dockerfiles, and docs. The original decision below is preserved as the
> historical record; the authoritative current versions are in `pyproject.toml`
> (`requires-python`), the Dockerfiles, and `.devcontainer/devcontainer.json`.

---

## Context

The system requires a primary application runtime and framework that supports:

- Async-first I/O for high-throughput event consumption and LLM API calls
- Strong type safety to reduce runtime errors in a complex domain model
- First-class support for Pydantic v2 (used for settings, models, and API contracts)
- A package manager that supports reproducible, fast dependency resolution
- Active ecosystem for OWASP security libraries, OTel instrumentation, and Kafka clients

---

## Decision

Adopt **Python 3.12** with **FastAPI** as the HTTP framework, **uv** as the package manager, and **Pydantic v2** as the data validation layer.

| Layer              | Tool             | Rationale                                              |
| ------------------ | ---------------- | ------------------------------------------------------ |
| Runtime            | Python 3.12      | Async-native, LLM SDK ecosystem, team expertise        |
| HTTP framework     | FastAPI          | Async, auto-OpenAPI, Pydantic-native, high performance |
| Package manager    | uv               | Rust-based, 10–100× faster than pip, lock-file support |
| Data validation    | Pydantic v2      | Runtime type safety, Settings management, JSON schema  |
| ASGI server        | Uvicorn          | Production-grade ASGI for FastAPI                      |
| DB migrations      | Alembic          | Version-controlled schema migrations                   |
| Async DB driver    | asyncpg          | Native async PostgreSQL driver, high performance       |
| Testing            | pytest + asyncio | Async test support, extensive plugin ecosystem         |
| Linting/formatting | Ruff             | Rust-based, replaces flake8 + isort + black            |
| Type checking      | mypy (strict)    | Catches type errors before runtime                     |

---

## Consequences

### Positive

- FastAPI's automatic OpenAPI schema generation keeps `docs/api/openapi/` in sync with code.
- Pydantic v2 Settings (see `src/shared/config.py`) provides validated, typed configuration loaded from environment variables — no untyped `os.getenv()` calls.
- uv's lock file ensures bit-for-bit reproducible builds across dev, CI, and production.
- Python's rich async ecosystem (aiokafka, redis-py async, httpx) supports all required integrations.

### Negative / Trade-offs

- Python's GIL limits CPU-bound parallelism. Mitigated by async I/O for I/O-bound workloads and multiprocessing for CPU-bound tasks.
- FastAPI startup time increases with dependency injection graph size. Monitor with PRR checklist.

---

## Alternatives Considered

**Django REST Framework**
Rejected: synchronous-first design requires workarounds for async consumers; heavier ORM is incompatible with the async-first architecture principle.

**Flask + extensions**
Rejected: not async-native; requires Quart or async workarounds; no built-in OpenAPI generation.

**Go (stdlib + chi/gin)**
Rejected: team has deep Python expertise; LLM SDK ecosystem is Python-first; migration cost outweighs performance gains for this workload profile.

**Node.js + NestJS**
Rejected: Python is the primary language for LLM/ML tooling; introducing a second primary language increases operational complexity.
