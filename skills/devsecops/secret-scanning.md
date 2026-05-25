# Skill — DevSecOps & Secret Scanning

**Owner:** Security Lead | **Reviewer:** DevOps Lead | **Status:** Active | **Last updated:** 2026-05-24

Activate this skill for any work touching CI/CD pipelines, secret management, SAST, or dependency auditing.

ADR: ADR-0008 (Secrets Management)

---

## Secret Scanning

Secrets are detected at two points:

| Point       | Tool           | Command                                                   | Blocks   |
| ----------- | -------------- | --------------------------------------------------------- | -------- |
| Pre-commit  | detect-secrets | runs via `.pre-commit-config.yaml`                        | commit   |
| CI lint job | detect-secrets | `uv run detect-secrets scan --baseline .secrets.baseline` | PR merge |

**Baseline initialisation** (run once after cloning):

```bash
detect-secrets scan > .secrets.baseline
```

If a new intentional non-secret pattern triggers the scanner:

```bash
detect-secrets audit .secrets.baseline   # mark as non-secret interactively
git add .secrets.baseline && git commit -m "chore: update secrets baseline"
```

**Never commit** `.env`, `*.pem`, `*.key`, or any file containing a real API key.
The `.gitignore` excludes these by pattern — do not remove those rules.

---

## SAST (Static Analysis Security Testing)

Bandit scans `src/` on every CI run and in the pre-commit hook:

```bash
uv run bandit -r src/ -ll -x tests/
```

`-ll` means severity ≥ MEDIUM. Address all findings before merging.

Common findings and what to do:

| Finding                 | Rule | Fix                                              |
| ----------------------- | ---- | ------------------------------------------------ |
| `subprocess` shell=True | B602 | Use `shell=False` with a list of arguments       |
| `pickle.loads`          | B301 | Reject — never deserialise untrusted pickle data |
| `hashlib.md5`           | B303 | Replace with `hashlib.sha256`                    |
| Hardcoded password      | B105 | Move to `.env` / Vault — update secrets baseline |

---

## Dependency Auditing

```bash
uv run pip-audit   # checks all dependencies against OSV/CVE databases
```

Runs in the CI `test-security` job. A CVE with severity ≥ HIGH blocks the build.

To temporarily suppress a false positive (document why in the PR):

```bash
uv run pip-audit --ignore-vuln GHSA-xxxx-xxxx-xxxx
```

---

## CI Security Gate Summary

The `test-security` job in `.github/workflows/ci.yml` runs:

1. `bandit` — SAST
2. `pip-audit` — dependency CVE check
3. `pytest tests/security/` — PII leakage + OWASP LLM Top 10 tests

All three must pass before the `build` job runs. The `build` job is a prerequisite
for staging deploy — so a failing security gate blocks all deployments.

---

## Adding a New Secret Type

1. Add the pattern to `.secrets.baseline` via `detect-secrets scan`
2. Add an environment variable entry to `.env.example` with a placeholder value
3. Add the variable to `src/shared/config.py` with `str = "placeholder-set-in-env"`
4. Document the rotation schedule in `docs/adr/ADR-0008-secrets-management.md`
