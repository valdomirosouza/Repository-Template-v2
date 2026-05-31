# Dependency Policy

> **Status:** Active · **Version:** 1.0 · **Last updated:** 2026-05-31
> **Owner:** Tech Lead
> **Enforcement:** CI gates in `ci.yml` (SCA, licence check, Trivy); pre-commit hooks

This policy governs how third-party dependencies are introduced, maintained, and removed
across all languages in this monorepo (Python, Java, Go, Node.js) and all artefact types
(packages, container base images, GitHub Actions, infrastructure modules).

---

## 1. Approved Registries

Only packages sourced from the following registries may be used in production builds.

| Language / Type   | Approved registry                                      | Notes                                                                   |
| ----------------- | ------------------------------------------------------ | ----------------------------------------------------------------------- |
| Python            | [PyPI](https://pypi.org)                               | `uv` with `uv.lock`; no `--extra-index-url` without Tech Lead approval  |
| Java              | [Maven Central](https://central.sonatype.com)          | No JCenter (deprecated); private Nexus for internal artefacts           |
| Go                | [pkg.go.dev](https://pkg.go.dev) (GOPROXY)             | `GONOSUMCHECK` must not be set in CI                                    |
| Node.js           | [npmjs.com](https://www.npmjs.com)                     | `npm ci` with committed `package-lock.json`; no `yarn` without approval |
| Container images  | GHCR (`ghcr.io`) or Docker Hub official images         | Base images must be pinned by digest (ADR-0029)                         |
| GitHub Actions    | `github.com` marketplace                               | Must be SHA-pinned (ADR-0029); internal actions preferred               |
| Terraform modules | [registry.terraform.io](https://registry.terraform.io) | Version-pinned in `versions.tf`; no `git::` sources                     |

**Unapproved registries** (e.g. custom PyPI mirrors, private npm registries, `git+https://` package URLs) require written Tech Lead approval and a corresponding entry in `docs/dependency-manifest.yaml`.

---

## 2. Licence Policy

### Allowed without approval

- MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, Python-2.0, MPL-2.0, CC0-1.0, Unlicense

### Allowed with Tech Lead approval

- LGPL-2.0, LGPL-2.1, LGPL-3.0 — permitted for dynamically-linked libraries only; must not be statically linked or bundled into a distributed artefact
- Creative Commons (non-CC0) — permitted for documentation assets only; not for code

### Prohibited

- GPL-2.0, GPL-3.0, AGPL-3.0 — copyleft licences incompatible with proprietary distribution
- BUSL (Business Source Licence) — time-limited open source; legal review required
- SSPL (Server Side Public Licence) — MongoDB licence; not OSI-approved
- Unknown / unlicensed — any dependency without a declared SPDX licence identifier is blocked

**Enforcement:** `license-checker` runs in `ci.yml` build stage. Any new `GPL/AGPL/BUSL/SSPL` finding blocks the build. Unknown licences are flagged as warnings and must be resolved within one sprint.

---

## 3. Introducing a New Dependency

All new production dependencies must go through the following process before merging:

1. **Check the registry and licence** (§1, §2) — confirm source is approved and licence is allowed.
2. **Run SCA locally:**

   ```bash
   # Python
   uv run pip-audit

   # Java
   make lint-java SERVICE=<name>   # includes OWASP dep-check

   # Go
   go list -json -m all | nancy sleuth

   # Node.js
   npm audit --audit-level=high
   ```

3. **Check for existing alternatives** — search `docs/dependency-manifest.yaml` and `pyproject.toml` / `pom.xml` / `go.mod` / `package.json` to avoid redundant dependencies.
4. **Add to `docs/dependency-manifest.yaml`** — document: name, version constraint, purpose, security note (if any), and data classification if it handles personal data.
5. **Add a PR comment** explaining why this dependency is necessary and why no existing dependency covers the use case.
6. **Tech Lead review** — required for any dependency that:
   - Handles cryptography, authentication, or PII
   - Adds a native extension or C binding
   - Has > 1 critical CVE in its history (check via OSV.dev)
   - Is not in the top-1000 downloads for its ecosystem

---

## 4. Version Pinning Requirements

| Artefact type         | Pinning requirement                                                        | Rationale                                                     |
| --------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Python packages       | Exact version in `uv.lock`                                                 | Reproducible builds                                           |
| Java dependencies     | Version ranges in `pom.xml`; resolved versions in `dependency:tree` output | Maven resolution is deterministic with `dependencyManagement` |
| Go modules            | Exact version + checksum in `go.sum`                                       | Go module proxy guarantees immutability                       |
| Node.js packages      | Exact version in `package-lock.json`                                       | `npm ci` enforces lock file                                   |
| Container base images | Digest pinning (`FROM image@sha256:…`)                                     | Tag mutability prevention (ADR-0029)                          |
| GitHub Actions        | SHA commit pin (`uses: action@<sha>`)                                      | Supply chain attack prevention (ADR-0029)                     |
| Terraform modules     | Version constraint + lock file (`.terraform.lock.hcl`)                     | Prevents silent upgrades                                      |

**No floating versions** (`latest`, `*`, `>=0.0.0`) are permitted in production builds. Dependabot is configured to submit PRs for patch and minor updates; major version upgrades require manual review.

---

## 5. Update Cadence

| Update type                   | SLA                         | Process                                               |
| ----------------------------- | --------------------------- | ----------------------------------------------------- |
| **Critical CVE** (CVSS ≥ 9.0) | 48 hours                    | Emergency change; hotfix branch; security label on PR |
| **High CVE** (CVSS 7.0–8.9)   | 7 days                      | Normal change; feature branch                         |
| **Medium CVE** (CVSS 4.0–6.9) | 30 days                     | Backlog; next sprint                                  |
| **Low CVE** / informational   | 90 days                     | Batch with regular dependency updates                 |
| **Non-security patch**        | Next sprint                 | Dependabot auto-merge if all gates pass               |
| **Minor version**             | Quarterly                   | Manual review; verify no breaking changes             |
| **Major version**             | Planned; Tech Lead approval | ADR may be required if it changes architecture        |

Dependabot is configured in `.github/dependabot.yml` with `auto-merge` enabled for patch-level non-security updates that pass all CI gates.

---

## 6. Removal Policy

A dependency must be removed when:

- It is no longer referenced in production code (detected by `uv run pip-check` or equivalent)
- It has reached end-of-life and has no maintained fork
- It is superseded by a built-in language feature or another approved dependency
- A critical CVE cannot be patched within the SLA and no fix is available

Removal PRs must update `docs/dependency-manifest.yaml` to mark the entry as `status: removed` with a `removed_date` and `reason` field.

---

## 7. SCA Gate Thresholds

The CI pipeline blocks merge on:

| Scanner           | Language | Blocking threshold                                         |
| ----------------- | -------- | ---------------------------------------------------------- |
| `pip-audit`       | Python   | Any CRITICAL or HIGH CVE                                   |
| OWASP dep-check   | Java     | CVSS ≥ 7.0 (configurable via `failBuildOnCVSS` in pom.xml) |
| `nancy`           | Go       | Any CRITICAL or HIGH CVE                                   |
| `npm audit`       | Node.js  | `--audit-level=high`                                       |
| Trivy (container) | All      | Any CRITICAL CVE in base image or installed packages       |

Findings below the blocking threshold are reported as warnings and must appear in the PR body with a documented risk acceptance if not remediated.

---

## 8. Vendoring

Vendoring (committing third-party source into the repo) is **prohibited by default** for the following reasons:

- Vendored code bypasses SCA scanning
- It inflates repository size and git history
- Security patches require manual vendored-copy updates

**Exceptions** (require Tech Lead approval and a note in `docs/dependency-manifest.yaml`):

- A dependency is unavailable on an approved registry and has no alternative
- An air-gapped deployment environment requires it
- A dependency requires a local patch that cannot be contributed upstream

When vendoring is approved, the vendored directory must be clearly marked (e.g. `vendor/`), included in Trivy and SAST scans, and updated on the same CVE SLA as non-vendored dependencies.
