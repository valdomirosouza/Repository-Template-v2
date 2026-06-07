# Scaffold System

Generate a new service from a language template with a single command. Templates live in
`scaffold/templates/<lang>/`; generation is driven by `scaffold/scaffold.py` and wrapped by
`make new-service` (Reusability Uplift, ADR-0059).

## 1. Overview

`make new-service` scaffolds a ready-to-edit service and, optionally, **self-registers**
it across the repo's catalogs. Supported languages:

| `LANG`   | Stack                      | Generated layout                             |
| -------- | -------------------------- | -------------------------------------------- |
| `python` | FastAPI + uv               | `src/<module>/`, `tests/`                    |
| `java`   | Spring Boot (Maven)        | `src/main/java/...`, `Dockerfile`, `pom.xml` |
| `go`     | net/http + standard layout | `cmd/`, `internal/`, `Dockerfile`, `go.mod`  |

## 2. Usage

```bash
# Scaffold only (prints the manual registration steps):
make new-service NAME=payments LANG=python

# Scaffold AND self-register (services.yaml + CODEOWNERS + Prometheus scrape job):
make new-service NAME=payments LANG=python OWNER=platform PORT=8020 REGISTER=true

# Java / Go:
make new-service NAME=ledger   LANG=java OWNER=payments-team PORT=8030 REGISTER=true
make new-service NAME=ingestor LANG=go   OWNER=data-team     PORT=8040 REGISTER=true
```

| Flag       | Default         | Meaning                                |
| ---------- | --------------- | -------------------------------------- |
| `NAME`     | _(required)_    | Service name (kebab-case)              |
| `LANG`     | _(required)_    | `python` \| `java` \| `go`             |
| `OWNER`    | `platform-team` | CODEOWNERS team handle                 |
| `PORT`     | `8010`          | Primary port (Prometheus target)       |
| `REGISTER` | `false`         | When `true`, update the registry files |

## 3. Generated file trees

**python**

```text
services/<name>/
  pyproject.toml
  src/<module>/__init__.py
  src/<module>/config.py
  src/<module>/main.py          # FastAPI app + /health endpoint
  tests/unit/test_health.py
```

**java**

```text
services/<name>/
  Dockerfile
  README.md
  pom.xml
  src/main/java/com/<org>/<module>/Application.java
  src/main/java/com/<org>/<module>/api/HealthController.java
  src/main/resources/application.properties
  src/test/java/com/<org>/<module>/HealthControllerTest.java
```

**go**

```text
services/<name>/
  Dockerfile
  README.md
  go.mod
  cmd/<module>/main.go
  internal/config/config.go
  internal/handler/health.go
  internal/handler/health_test.go
```

## 4. Post-generation checklist

1. Edit `services/<name>/README.md` — purpose, owner, SLO.
2. Implement the service against its spec (`specs/…`) — no code without a spec (SDD).
3. If you did not pass `REGISTER=true`, update `services.yaml`, `.github/CODEOWNERS`, and
   `infrastructure/monitoring/prometheus/prometheus.yml`.
4. Add a K8s manifest under `infrastructure/k8s/` if the service deploys to a cluster.
5. Run `make test-<lang> SERVICE=<name>` and `make lint-<lang> SERVICE=<name>`.

## 5. Customising templates

Templates are plain file trees under `scaffold/templates/<lang>/`. To change what new
services look like, edit the files there. Two placeholders are substituted at generation
time:

- `__SERVICE_NAME__` → the `NAME` you pass (kebab-case).
- `__MODULE_NAME__` → the language-appropriate module form (e.g. snake_case for Python).

Add a new language by creating `scaffold/templates/<lang>/` and adding `<lang>` to
`VALID_LANGS` in `scaffold/scaffold.py`.
