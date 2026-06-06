# Skill — Agentic Cyber Defense

**Owner:** Security Lead | **Status:** Active | **Last updated:** 2026-06-05
**ADR:** ADR-0036 | **Issue:** #9
**Extends:** `skills/devsecops/secret-scanning.md`

Activate this skill when a CI security gate (Bandit, SpotBugs, gosec, Trivy, OWASP
dep-check) fails on a PR or when a new HIGH/CRITICAL security finding is detected.

---

## 1. Automated Response Protocol

When a CI security gate fails, execute these steps in order before touching any code:

### Step 1 — Parse the tool output

Extract structured findings using the agent-readable format (§2). Each tool has a
known output format:

| Tool            | Output format             | Key fields to extract                                                                              |
| --------------- | ------------------------- | -------------------------------------------------------------------------------------------------- |
| Bandit          | JSON (`-f json`)          | `issue_severity`, `issue_confidence`, `filename`, `line_number`, `test_id`, `issue_text`           |
| gosec           | JSON (`-fmt json`)        | `severity`, `confidence`, `file`, `line`, `rule_id`, `details`                                     |
| Trivy           | JSON (`--format json`)    | `Vulnerabilities[].Severity`, `.VulnerabilityID`, `.PkgName`, `.InstalledVersion`, `.FixedVersion` |
| SpotBugs        | XML → parse `BugInstance` | `priority`, `type`, `SourceLine.classname`, `SourceLine.start`                                     |
| OWASP dep-check | JSON                      | `vulnerabilities[].severity`, `.name` (CVE), `packages[].id`                                       |

```bash
# Bandit — re-run with JSON output for parsing
uv run bandit -r src/ -ll -x tests/ -f json -o /tmp/bandit_findings.json

# Trivy — re-run with JSON output
trivy fs . --format json --severity HIGH,CRITICAL -o /tmp/trivy_findings.json

# gosec — re-run with JSON output
(cd services/event-worker && gosec -fmt json ./... > /tmp/gosec_findings.json 2>&1)
```

### Step 2 — Classify each finding

Map each finding to the agent-readable format (§2) and filter by severity:

```python
ACTIONABLE_SEVERITIES = {"critical", "high"}  # lowercase
# medium / low → record metric only, no advisory
```

### Step 3 — Record the Prometheus metric

For every finding, regardless of severity:

```python
from src.observability.metrics import SECURITY_FINDING_COUNTER
SECURITY_FINDING_COUNTER.labels(
    tool="bandit",          # bandit | gosec | trivy | spotbugs | owasp-dep-check
    severity="high",        # critical | high | medium | low
    status="open",          # open | resolved
).inc()
```

### Step 4 — For HIGH/CRITICAL: create a GitHub Security Advisory draft

```bash
gh api repos/{owner}/{repo}/security-advisories \
  --method POST \
  --field summary="[{tool}] {severity}: {description}" \
  --field description="$(cat <<EOF
**Tool:** {tool}
**Severity:** {severity}
**CWE:** {cwe}
**File:** {file}:{line}
**CVE:** {cve_id}

**Description:**
{description}

**Remediation:**
{remediation}

**Detected in PR:** #{pr_number}
**CI run:** {run_url}
EOF
)" \
  --field severity="{severity}" \
  --field state="draft"
```

> **Gate rule:** If severity is `high` or `critical` and no mitigating ADR exists that
> explicitly accepts this risk, the PR **MUST NOT merge** until the finding is resolved
> or an ADR is written and approved. Emit `[HITL-ESCALATE]` and stop.

### Step 5 — Post a structured PR comment

```bash
gh pr comment {pr_number} --body "$(cat <<EOF
## 🔒 Security Finding — Action Required

| Field | Value |
|-------|-------|
| **Tool** | {tool} |
| **Severity** | {severity} |
| **CVE / Rule** | {cve_id} |
| **CWE** | {cwe} |
| **File** | \`{file}:{line}\` |
| **Package** | {package} (installed: {installed_version} → fix: {fixed_version}) |

**Description:** {description}

### Remediation
{remediation}

### Next Steps
- [ ] Apply the fix in this PR, or
- [ ] Write an ADR documenting accepted risk (requires Security Lead approval), or
- [ ] Add to \`.trivyignore\` / \`.bandit\` with an expiry date if a false positive

_Detected by agentic-cyber-defense skill · ADR-0036_
EOF
)"
```

---

## 2. Agent-Readable Finding Format

All findings are normalised to this structure before any downstream action:

```json
{
  "tool": "bandit | gosec | trivy | spotbugs | owasp-dep-check",
  "cve_id": "CVE-YYYY-NNNNN | RULE-ID | null",
  "severity": "critical | high | medium | low",
  "confidence": "high | medium | low | null",
  "file": "src/path/to/file.py",
  "line": 42,
  "cwe": "CWE-NNN | null",
  "package": "package-name | null",
  "installed_version": "1.2.3 | null",
  "fixed_version": "1.2.4 | null",
  "description": "One-sentence description of the vulnerability",
  "remediation": "Specific fix instruction"
}
```

---

## 3. Mitigating ADR Lookup

Before escalating, check whether an existing ADR explicitly accepts this risk:

```bash
grep -rn "{cve_id}\|{rule_id}" docs/adr/
```

If found: reference the ADR in the PR comment instead of blocking. If not found and
severity is HIGH/CRITICAL: emit `[HITL-ESCALATE]` and await Security Lead sign-off.

---

## 4. Remediation Guidance by Tool

### Bandit (Python SAST)

| Rule                         | Fix                                                 |
| ---------------------------- | --------------------------------------------------- |
| B301 `pickle`                | Replace with `json` or `msgpack`                    |
| B303 MD5/SHA1                | Replace with `hashlib.sha256` or `hashlib.sha3_256` |
| B602 `subprocess` shell=True | Use `shell=False` with list args                    |
| B608 SQL injection           | Use parameterised queries (SQLAlchemy bindparams)   |
| B105 hardcoded password      | Move to `.env` / Vault secret                       |

### Trivy (Container / Dependency CVEs)

```bash
# Check if a fix version exists
trivy fs . --severity HIGH,CRITICAL --ignore-unfixed

# Update the dependency
uv add <package>==<fixed_version>   # Python
mvn versions:use-latest-releases    # Java
go get <module>@<version>           # Go
```

### gosec (Go SAST)

| Rule                       | Fix                                                  |
| -------------------------- | ---------------------------------------------------- |
| G101 hardcoded credentials | Move to env var / Vault                              |
| G201/G202 SQL injection    | Use `db.QueryContext` with args, never `fmt.Sprintf` |
| G304 file path injection   | Validate and clean paths with `filepath.Clean`       |
| G401/G501 weak crypto      | Replace `md5`/`sha1` with `sha256`                   |

---

## 5. Escalation Decision Tree

```
Finding detected
    ├─ severity = critical or high?
    │       ├─ mitigating ADR exists? → reference ADR in comment, proceed
    │       └─ no mitigating ADR?
    │               └─ [HITL-ESCALATE] risk_level=high → await Security Lead
    ├─ severity = medium
    │       └─ record metric, post comment, do NOT block
    └─ severity = low
            └─ record metric only, no comment
```

---

## 6. Related

- `skills/devsecops/secret-scanning.md` — secret detection and SAST baseline
- `skills/devsecops/owasp-top10.md` — OWASP control mapping
- `specs/security/threat-model.md` — STRIDE analysis
- `CLAUDE.md §14` — `[HITL-ESCALATE]` format
- ADR-0036 — decision record for this skill
