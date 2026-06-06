# Skill — Adding a New Language to the Stack

**Owner:** Tech Lead | **Status:** Active | **Last updated:** 2026-06-05
**Issue:** #10

Activate this skill when extending the monorepo to support a language outside
the default stack (Python, Java, Go, Node.js).

---

## 5-Step Extension Protocol

### Step 1 — Write the Language ADR

Before adding any files, record the decision:

```markdown
# ADR-XXXX: <Language> Service Addition

**Status:** Proposed
**Context:** Why this language? What service will use it?
**Decision:** Which version, build tool, and linter?
**Consequences:** CI time impact, onboarding cost, maintenance burden.
```

File at `docs/adr/ADR-XXXX-<language>-service-addition.md`.
The ADR must be **Accepted** before proceeding to Step 2.

### Step 2 — Scaffold the Service

```bash
make new-service NAME=<name> LANG=<language>
```

If `LANG` is not yet supported by the scaffold command, create the directory
structure manually following the conventions of an existing service:

```
services/<name>/
  src/           # source code
  tests/         # unit and integration tests
  Dockerfile     # multi-stage build
  <build-file>   # pom.xml / go.mod / package.json / pyproject.toml / etc.
  README.md
```

Register the new service in `services.yaml` (canonical service registry) and
add it to `.github/CODEOWNERS`.

### Step 3 — Add to the CI Pipeline

Create `.github/workflows/ci-<language>.yml` modelled on an existing language
workflow (e.g. `ci-go.yml` for a compiled language, `ci.yml` for interpreted).

Minimum CI gates required for all languages:

| Gate             | Tool                         | Blocks merge        |
| ---------------- | ---------------------------- | ------------------- |
| Lint             | language-native linter       | Yes                 |
| Unit tests       | language-native test runner  | Yes                 |
| SAST             | language-appropriate scanner | Yes                 |
| Dependency audit | language-native SCA tool     | Yes                 |
| Build            | `docker build`               | Yes                 |
| Container scan   | Trivy                        | Yes (CRITICAL/HIGH) |

Reference tools by language:

| Language | Lint            | SAST             | SCA                                |
| -------- | --------------- | ---------------- | ---------------------------------- |
| Rust     | `clippy`        | `cargo-audit`    | `cargo-deny`                       |
| Ruby     | `rubocop`       | `brakeman`       | `bundler-audit`                    |
| C#       | `dotnet format` | Roslyn analyzers | `dotnet list package --vulnerable` |
| COBOL    | `cobollint`     | manual review    | N/A                                |

Add the new workflow to the `needs:` list in `cd-staging.yml` and `cd-production.yml`
so deployments wait for the new gate.

### Step 4 — Add the Skills Catalog Entry

Create `skills/<domain>/<language>-patterns.md` following the structure of
`skills/data/data-pipeline.md`:

```markdown
# Skill — <Language> Patterns

**Owner:** Tech Lead | **Status:** Active

## 1. Project Structure

## 2. Testing Conventions

## 3. OTel Instrumentation

## 4. PII Handling

## 5. Related
```

Add a row to the Skill Activation Table in `CLAUDE.md §4`:

```
| <Language> service or pattern | `skills/<domain>/<language>-patterns.md` | Any <language> service work |
```

### Step 5 — Update CLAUDE.md and CHANGELOG

In `CLAUDE.md §0` (Development Commands), add the language-specific make targets
under "Other Languages":

```bash
make test-unit-<lang>   SERVICE=<name>   # unit tests
make lint-<lang>        SERVICE=<name>   # linter
make run-<lang>         SERVICE=<name>   # dev server
```

Update `CHANGELOG.md` under `[Unreleased]` → `Added`.

---

## Checklist

- [ ] ADR written and accepted
- [ ] Service scaffolded and registered in `services.yaml` + `CODEOWNERS`
- [ ] CI workflow created with all 6 required gates
- [ ] Skills catalog entry created
- [ ] `CLAUDE.md §0` make targets added
- [ ] `CLAUDE.md §4` skill row added
- [ ] `CHANGELOG.md` updated
