# Prompt 002 — Root Governance Files

> **Requires:** Prompt 001 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Sections: Executive Summary, Section 12).
> Skip any file that already exists with real content.

---

## Task

Create the following root-level governance files with **real, substantive content**
(not placeholders). Each file must be production-ready.

---

### Files to create

#### `CLAUDE.md`

Behavioral contract for Claude Code. Must include:

- Identity and scope (senior engineer + governance advisor)
- SDD 10-step mandatory workflow (read spec → check ADR → glossary → issue →
  DPIA check → implement → test → guardrails → update ADR → update CHANGELOG)
- Inviolable rules: Privacy, Security, AI Governance, Architecture, Quality
- Skill activation table mapping trigger domains to `skills/*` paths
- Glossary reference pointing to `docs/glossary.md`
- Branch naming and Conventional Commits format
- PR checklist
- File ownership quick-reference table

---

#### `README.md`

Project entry point. Minimum sections from Section 12 of the reference document:

- Quick Start (`make setup`, prerequisites)
- Daily workflow (`make test`, `make lint`, `make deploy-staging`, `make rollback`)
- Repository structure overview (short tree)
- API reference table (REST / AsyncAPI / gRPC) with spec file paths
- Observability table (Metrics, Traces, Logs) with dashboard paths
- On-call resource table (runbooks, rollback, DR, agent-failure)
- Architecture Decisions (key ADR links)
- AI Governance summary (HITL/HOTL, guardrails)
- Privacy summary (LGPD / GDPR, masking, DPIA/RIPD)
- Links to CONTRIBUTING.md, SECURITY.md, CHANGELOG.md, LICENSE

---

#### `CHANGELOG.md`

Keep-a-Changelog 1.1.0 format. Include:

- `[Unreleased]` section (empty, ready for next changes)
- `[0.1.0] - 2026-05-24` initial entry listing all scaffold components added
- Categories: Added, Changed, Fixed, Security, Removed, Privacy
- Every entry must reference Issue #, ADR # (if applicable), RFC # (if applicable)
- Footer links: `[Unreleased]` and `[0.1.0]` comparison URLs

---

#### `SECURITY.md`

Vulnerability disclosure policy. Include:

- Supported versions table
- Private reporting instructions (GitHub Security Advisories preferred; email fallback)
- What to include in a report: description, component affected, steps to reproduce,
  severity estimate, suggested fix (optional)
- Response timeline SLA table: acknowledgement 48h → triage 5 business days →
  Critical fix 14 days → High fix 30 days → Medium 60 days → Low 90 days
- Scope table (in-scope / out-of-scope)
- AI-specific concerns: name the risk categories only — "prompt manipulation
  resistance", "sensitive data exposure controls", "agent autonomy boundaries",
  "audit log integrity". Do not describe attack techniques.
- Coordinated disclosure policy (reporter notifies → we fix → we publish advisory
  → reporter may publish after patch)
- Note on personal data in security reports: handled under PRIVACY.md; deleted
  after issue is resolved

---

#### `PRIVACY.md`

Data processing notice referencing LGPD (Lei 13.709/2018) and GDPR (EU 2016/679). Include:

- Data controller details (placeholder fields)
- Legal basis table for each processing activity
- PII classification table (L1 Critical → L4 Public) with examples and handling rules
- AI/LLM processing section: masking-before-ingestion policy
- Data retention summary table (link to `docs/privacy/data-retention-policy.md`)
- Data subject rights table with how-to-exercise instructions
- Third-party processors table (placeholder rows with DPA reference column)
- Cross-border transfer mechanisms (SCCs for GDPR; ANPD equivalency for LGPD)
- Security measures list
- DPIA/RIPD references
- Breach notification obligations (GDPR 72h; LGPD reasonable timeframe)

---

#### `CONTRIBUTING.md`

Full contribution guide. Include:

- SDD cycle explanation (10 steps)
- Branch naming convention with examples
- Conventional Commits format table (types, scopes, breaking changes)
- Pull request process (checklist, required reviewers by change type, quality gates table)
- Change management tiers: Standard / Normal / Emergency
- Privacy-by-design contributor rules (no real PII in tests, no PII in logs,
  flag new PII fields, DPO notification for L1/L2 additions)
- Testing requirements table (unit, integration, security, contract, performance)
- Documentation requirements (CHANGELOG, ADR, spec, runbooks)
- Link to CODE_OF_CONDUCT.md and SECURITY.md

---

#### `CODE_OF_CONDUCT.md`

Community standards document based on **Contributor Covenant 2.1**.

Structure the file as follows — write each section with professional, policy-style
prose appropriate for an enterprise engineering team. Do **not** enumerate specific
examples of misconduct; refer readers to the enforcement contact for edge-case
judgements.

**Sections to include:**

1. **Our Pledge** — commitment to a welcoming, respectful, and inclusive community
   regardless of background or identity (keep general; no enumerated lists of
   identity categories — just state the principle).

2. **Our Standards** — describe the expected positive behaviours:
   - Respectful and constructive communication
   - Welcoming feedback and differing viewpoints
   - Accepting responsibility and learning from mistakes
   - Focusing on what is best for the community
     State that behaviour that undermines these standards is subject to enforcement
     action, and direct readers to contact the maintainers for clarification.

3. **Enforcement Responsibilities** — maintainers are responsible for clarifying
   and enforcing these standards; they may remove, edit, or reject contributions
   that do not align with this Code of Conduct.

4. **Scope** — applies within all project spaces and when an individual is
   officially representing the project in public spaces.

5. **Enforcement** — reports of conduct issues should be sent to the project
   maintainers at [conduct@\<org-domain\>]. All reports will be reviewed promptly
   and handled with confidentiality. Responses are proportionate to the nature
   and severity of the issue.

6. **Enforcement Guidelines** — four response tiers (names only, no detailed
   descriptions of what triggers each):
   - Correction
   - Warning
   - Temporary suspension
   - Permanent removal

7. **Attribution** — state that this Code of Conduct is adapted from the
   Contributor Covenant, version 2.1, and include the canonical URL:
   https://www.contributor-covenant.org/version/2/1/code_of_conduct/

---

#### `.env.example`

Template for all environment variables the system requires. Group by category.
All values must use clearly synthetic placeholders — no real credentials.

```
# ── APP CORE ──────────────────────────────────────────────────────────────────
APP_ENV=development
APP_PORT=8000
LOG_LEVEL=INFO
SERVICE_NAME=template-service
SERVICE_VERSION=0.1.0

# ── DATABASE ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# ── REDIS ─────────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# ── MESSAGE BROKER (KAFKA) ────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP=template-consumer-group
KAFKA_SCHEMA_REGISTRY_URL=http://localhost:8081

# ── LLM / AI ──────────────────────────────────────────────────────────────────
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
LLM_API_KEY=your-llm-api-key-here
LLM_MAX_TOKENS=4096
LLM_TOKEN_BUDGET_PER_REQUEST=2000
HITL_APPROVAL_TIMEOUT_SECONDS=300

# ── OBSERVABILITY ─────────────────────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=template-service
PROMETHEUS_PORT=9090
JAEGER_AGENT_HOST=localhost

# ── FEATURE FLAGS ─────────────────────────────────────────────────────────────
FEATURE_FLAG_PROVIDER=local
FEATURE_FLAG_SDK_KEY=your-flag-sdk-key-here
AUTONOMOUS_MODE_ENABLED=false

# ── SECURITY ──────────────────────────────────────────────────────────────────
SECRET_KEY=your-secret-key-here-replace-before-use
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# ── PRIVACY ───────────────────────────────────────────────────────────────────
PII_MASKING_ENABLED=true
PII_AUDIT_LOG_ENABLED=true
DATA_RETENTION_DAYS=30

# ── FINOPS ────────────────────────────────────────────────────────────────────
LLM_MONTHLY_TOKEN_BUDGET=1000000
COST_ALERT_THRESHOLD_USD=100.0
```

---

#### `Makefile`

GNU Make file with the targets listed below. Include a `.PHONY` declaration
covering all targets and a `help` target that prints available commands.

Targets:

- `setup` — `uv sync`, copy `.env.example` → `.env` if `.env` does not exist,
  `docker compose up -d`, run DB migrations
- `test` — `pytest tests/ --cov=src --cov-report=term-missing -q`
- `test-unit` — `pytest tests/unit/ -q`
- `test-security` — `pytest tests/security/ -q` (comment: "defensive validation suite")
- `lint` — `ruff check src/ tests/` + `mypy src/` + `detect-secrets scan`
- `format` — `ruff format src/ tests/`
- `build` — `docker build --target production -t $(IMAGE_NAME):$(VERSION) .`
- `deploy-staging` — `$(MAKE) build` + push + `helm upgrade --install`
- `rollback` — `bash infrastructure/scripts/deploy/rollback.sh --env=staging`
- `docs-serve` — `mkdocs serve`
- `openapi-ui` — `npx swagger-ui-watcher docs/api/openapi/v1/openapi.yaml`
- `asyncapi-ui` — `npx @asyncapi/cli preview docs/api/asyncapi/v1/asyncapi.yaml`
- `sbom` — `syft . -o cyclonedx-json=sbom.cyclonedx.json`
- `clean` — remove `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`, `htmlcov/`
- `help` — print all targets with one-line descriptions

Include variables at the top: `IMAGE_NAME`, `VERSION`, `REGISTRY`.

---

#### `.gitignore`

Combined Python + Node.js + secrets + IDE ignore file.

```
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
dist/
build/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
coverage.xml

# Node.js
node_modules/
npm-debug.log*
.npm/

# Environment / secrets — never commit these
.env
.env.local
.env.*.local
*.pem
*.key
*.p12
secrets/

# IDE
.idea/
.vscode/
*.swp
*.swo
.DS_Store
Thumbs.db

# Docker
.docker/

# Terraform
.terraform/
*.tfstate
*.tfstate.backup
.terraform.lock.hcl
terraform.tfvars

# Generated in CI — do not commit manually
sbom.cyclonedx.json
docs/site/

# Test outputs
test-results/
.hypothesis/
```

---

### Validation

After creating all files, confirm:

- All 10 files exist at the repository root
- `CLAUDE.md` skill activation table references all paths under `skills/`
- `.env.example` contains no real credentials (all values are placeholders)
- `Makefile` has a `.PHONY` line covering all targets
- `CODE_OF_CONDUCT.md` does NOT enumerate specific misconduct examples inline —
  it references the conduct contact email and the Contributor Covenant URL
