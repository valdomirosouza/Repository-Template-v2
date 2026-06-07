# Control Applicability Matrix & Cross-Cutting Control Bindings

> **Owner:** Compliance Lead + Tech Lead · **Status:** Active · **ADR:** ADR-0060
> Companion to the Task Atomicity & 2-Skill Budget directive (`CLAUDE.md` §4, ADR-0060).

Compliance, privacy, and security obligations are **cross-cutting**: they attach to a task
by _what the task touches_, not by which phase it lives in. The per-phase coverage check
(ADR-0058) does not capture them — the trigger table below does. Run these triggers before
executing **any** task. Each true trigger binds a control; each control maps to either a
**domain skill** (counts against the 2-skill budget) or an **ambient ADR/CI gate** (does not).

---

## 1. Cross-cutting control-binding triggers

Run before every task. A control whose binding is a skill consumes a slot of the 2-skill
budget (`CLAUDE.md` §4); a control bound to an ambient ADR/CI gate does not.

| If the task…                                             | Bind                                                                                 | Counts vs budget? |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------- |
| Reads, stores, or transmits personal data                | `privacy/pii` + `privacy/lgpd` and/or `privacy/gdpr` (per data-subject jurisdiction) | **Yes** (skill)   |
| Handles data-subject requests (access / erasure / port.) | `privacy/data-subject-rights`                                                        | **Yes** (skill)   |
| Exposes an endpoint or processes untrusted input         | `devsecops/owasp-top10` (+ OWASP LLM Top 10 for LLM I/O)                             | **Yes** (skill)   |
| Adds/changes a dependency, image, or pipeline step       | `devsecops/secret-scanning` + SBOM/SCA gate                                          | Skill + ambient   |
| Writes/reads the audit log or financial-relevant record  | SOX audit-immutability — **ADR-0026**, _only if in regulatory scope_ (see §2)        | Ambient (ADR/CI)  |
| Changes the production deploy / change process           | ISO 27001 three-tier change mgmt — **ADR-0027** + `change-management/cab-process`    | Ambient + skill   |
| Modifies the CI/CD security posture                      | DevSecOps pipeline security — **ADR-0029** (SAST/SCA/IaC/SBOM)                       | Ambient (ADR/CI)  |

**The budget interaction is a feature, not a conflict.** If a single task fires **3 or more
control triggers**, do **not** load 3 skills — that is the split signal from the atomicity
rule (ADR-0060). A task that is simultaneously a PII task, an OWASP task, _and_ a
SOX-evidence task is not atomic: split it into a privacy task, a security task, and a
compliance-evidence task, each within budget.

**Compliance artifacts are evidence.** A control-bound task still obeys "one task = one
reviewable artifact" — but the artifact is the _evidence_ the control was applied: a
DPIA/RIPD entry, a PII-classification mapping, an SBOM attestation, an OWASP test, an
audit-log assertion. Producing that evidence is the definition of done for the task.

---

## 2. Per-project applicability matrix

**Applicability is conditional — check scope before binding.** Some controls are not
universal. Never apply a regulatory control by default; apply it because this matrix says it
is in scope. Fill in the right-hand column for _this_ deployment and consult it before
treating any control as mandatory.

| Dimension                  | Question                                                        | This project (fill in)       |
| -------------------------- | --------------------------------------------------------------- | ---------------------------- |
| SOX (ADR-0026)             | Is the org a U.S.-listed public company / SEC-regulated entity? | _e.g. No → SOX out of scope_ |
| Data-subject jurisdictions | Whose personal data is processed? (EU → GDPR, BR → LGPD, …)     | _e.g. EU + BR → GDPR + LGPD_ |
| Data residency             | Where must data be stored / may it leave a region?              | _e.g. EU-only_               |
| PCI-DSS                    | Are cardholder/payment data handled?                            | _e.g. No_                    |
| HIPAA                      | Is protected health information (PHI) handled?                  | _e.g. No_                    |
| Sector / other regimes     | Any sector-specific obligation (FedRAMP, ISO 27001 cert, …)?    | _e.g. ISO 27001 (ADR-0027)_  |

Record exemptions explicitly. When a control is out of scope, **note the exemption** rather
than silently skipping it — e.g. "SOX (ADR-0026): not in scope — org is not SEC-listed."

---

## 3. Worked example — partitioning a control-heavy phase

A single phase that "needs" rules + guardrails + ADR + RFC + harness looks like it blows the
2-skill budget. It doesn't — each is its own atomic task (ADR-0060):

| Atomic task         | Artifact        | Skills (≤ 2)                                             |
| ------------------- | --------------- | -------------------------------------------------------- |
| Record the decision | 1 ADR           | `sdlc/spec-lifecycle`                                    |
| Propose the change  | 1 RFC           | `change-management/rfc-process`                          |
| Add safety controls | 1 guardrail mod | `ai/guardrails` + `devsecops/secret-scanning`            |
| Wire the harness    | 1 harness comp  | `ai/harness` + `observability/otel-instrumentation`      |
| Cover with tests    | 1 test file     | `engineering/testing-strategy` + `devsecops/owasp-top10` |

Rules (`CLAUDE.md`) and context (repo structure, prior ADRs) ride along as ambient context
in every task — they never consume a slot. The phase completes because its artifacts were
_partitioned across atomic tasks_, not because any single task carried the whole load.

---

## See also

- `CLAUDE.md` §4 — Task Atomicity & the 2-Skill Budget (decomposition oracle)
- ADR-0060 — decision record · ADR-0026 (SOX) · ADR-0027 (ISO 27001) · ADR-0029 (DevSecOps pipeline)
- `docs/compliance/iso27001-annex-a-control-matrix.md` — distinct: ISO 27001 Annex A controls
- `docs/privacy/` — DPIA/RIPD templates and PII inventory
