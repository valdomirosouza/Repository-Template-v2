# Skill: RTK Commands (Token Efficiency — Reference)

**Spec:** RTK-001 | **ADR:** ADR-0030 | **Source:** https://github.com/rtk-ai/rtk

## Purpose

Mapping of every common command in this monorepo to its RTK-optimized form.
Use this as the lookup table whenever running any shell command during a Claude Code session.

## When to activate

- Before running ANY test, lint, build, docker, git, or infra command
- Trigger phrases: "run tests", "check lint", "deploy", "diff", "check status"
- Auto-activated by the PreToolUse hook — this skill is the human-readable reference

## Core Rule

**Always prefer `rtk <cmd>` over raw `<cmd>` for any command with output > 10 lines.**
The hook handles this automatically for bash tool calls.
For explicit calls, use the mappings below.

## Command Map — This Repository

### Python / Testing

| Raw command                         | RTK equivalent               | Savings |
| ----------------------------------- | ---------------------------- | ------- |
| `pytest` / `make test-python`       | `rtk pytest`                 | −90%    |
| `make test-unit-python`             | `rtk pytest tests/unit/`     | −90%    |
| `make test-security-python`         | `rtk pytest tests/security/` | −90%    |
| `ruff check .` / `make lint-python` | `rtk ruff check`             | −80%    |
| `uv pip list`                       | `rtk pip list`               | −70%    |
| `uv pip outdated`                   | `rtk pip outdated`           | −70%    |

### Java

| Raw command                 | RTK equivalent                 | Savings |
| --------------------------- | ------------------------------ | ------- |
| `mvn test` (domain-service) | `rtk mvn-build`                | −80%    |
| `mvn checkstyle:check`      | `rtk err mvn checkstyle:check` | −75%    |

### Go

| Raw command         | RTK equivalent          | Savings |
| ------------------- | ----------------------- | ------- |
| `go test ./...`     | `rtk go test`           | −90%    |
| `golangci-lint run` | `rtk golangci-lint run` | −85%    |

### Frontend (Next.js)

| Raw command                   | RTK equivalent        | Savings |
| ----------------------------- | --------------------- | ------- |
| `jest` / `make test-frontend` | `rtk jest`            | −80%    |
| `tsc --noEmit`                | `rtk tsc`             | −80%    |
| `next build`                  | `rtk next build`      | −80%    |
| `playwright test`             | `rtk playwright test` | −80%    |

### Git

| Raw command           | RTK equivalent            | Savings |
| --------------------- | ------------------------- | ------- |
| `git status`          | `rtk git status`          | −80%    |
| `git diff`            | `rtk git diff`            | −75%    |
| `git log -n 10`       | `rtk git log -n 10`       | −80%    |
| `git add .`           | `rtk git add`             | −92%    |
| `git commit -m "..."` | `rtk git commit -m "..."` | −92%    |
| `git push`            | `rtk git push`            | −92%    |

### Docker / Infra

| Raw command                                 | RTK equivalent           | Savings |
| ------------------------------------------- | ------------------------ | ------- |
| `docker compose ps` / `make infra-up` check | `rtk docker compose ps`  | −80%    |
| `docker ps`                                 | `rtk docker ps`          | −80%    |
| `docker logs <name>`                        | `rtk docker logs <name>` | −80%    |
| `kubectl get pods`                          | `rtk kubectl pods`       | −80%    |
| `kubectl logs <pod>`                        | `rtk kubectl logs <pod>` | −80%    |

### Files & Structure

| Raw command                         | RTK equivalent                  | Savings |
| ----------------------------------- | ------------------------------- | ------- |
| `ls -la` / directory listing        | `rtk ls .`                      | −80%    |
| `cat <large-file>`                  | `rtk read <file>`               | −70%    |
| `cat <huge-file>` (signatures only) | `rtk read <file> -l aggressive` | −90%    |
| `grep -r "pattern" .`               | `rtk grep "pattern" .`          | −80%    |
| `diff file1 file2`                  | `rtk diff file1 file2`          | −75%    |

### Make Targets (use `.rtk/filters.toml` custom filter)

| Raw command               | RTK equivalent                               |
| ------------------------- | -------------------------------------------- |
| `make setup`              | `rtk proxy make setup` (passthrough + track) |
| `make infra-up`           | `rtk proxy make infra-up`                    |
| `make sbom`               | `rtk err make sbom` (errors only)            |
| `make deploy-staging ...` | `rtk proxy make deploy-staging ...`          |
| `make rollback`           | `rtk proxy make rollback`                    |

### Alembic / DB

| Raw command            | RTK equivalent                        |
| ---------------------- | ------------------------------------- |
| `alembic upgrade head` | `rtk err uv run alembic upgrade head` |
| `alembic history`      | `rtk summary uv run alembic history`  |

### Security Scanning

| Raw command           | RTK equivalent                                      |
| --------------------- | --------------------------------------------------- |
| `trivy image <img>`   | `rtk err trivy image <img>` (errors/criticals only) |
| `detect-secrets scan` | `rtk err detect-secrets scan`                       |

## When NOT to use rtk

- `make setup` for the very first time (you need to see full output)
- `rtk proxy <cmd>` for full output when debugging a failed filter
- Commands that require interactive TTY (rtk passes through automatically)
