# Skills Catalog

Skills are reusable Claude Code instruction sets for recurring domain tasks in this repository. When a task matches a skill domain, Claude loads and follows that skill before proceeding.

## How Skills Work

Skills are activated automatically based on the task context, as defined in the **Skill Activation Table** in `CLAUDE.md`. Each skill file contains domain-specific guidance, checklists, and patterns that Claude applies during implementation.

You can also reference a skill explicitly by mentioning it in your request.

---

## Full Catalog

| Skill                | Path                                             | Domain           | Activation Trigger                                       |
| -------------------- | ------------------------------------------------ | ---------------- | -------------------------------------------------------- |
| Golden Signals       | `skills/sre/golden-signals.md`                   | SRE              | Any observability, SLO, or on-call work                  |
| PRR                  | `skills/sre/prr.md`                              | SRE              | Before any production deploy                             |
| CUJ                  | `skills/sre/cuj.md`                              | SRE              | Defining or testing critical user journeys               |
| AI Guardrails        | `skills/ai/guardrails.md`                        | AI Safety        | Any agent or guardrail implementation                    |
| PII                  | `skills/privacy/pii.md`                          | Privacy          | Any data handling code                                   |
| LGPD                 | `skills/privacy/lgpd.md`                         | Privacy          | Brazilian data subjects or LGPD obligations              |
| GDPR                 | `skills/privacy/gdpr.md`                         | Privacy          | EU data subjects or GDPR obligations                     |
| RFC Process          | `skills/change-management/rfc-process.md`        | Change Mgmt      | Normal or Emergency changes                              |
| Deploy & Rollback    | `skills/change-management/deploy-rollback.md`    | Change Mgmt      | Any deploy or rollback operation                         |
| OTel Instrumentation | `skills/observability/otel-instrumentation.md`   | Observability    | Metrics, traces, or structured logs                      |
| REST API Design      | `skills/api/rest-api-design.md`                  | API              | Any REST endpoint design or implementation               |
| DevSecOps            | `skills/devsecops/secret-scanning.md`            | DevSecOps        | CI/CD, secret scanning, SAST, dep audit                  |
| Spec Lifecycle (SDD) | `skills/sdlc/spec-lifecycle.md`                  | SDLC             | Writing, reviewing, or updating a spec                   |
| Multi-Agent Harness  | `skills/ai/harness.md`                           | AI Agents        | Multi-step agent tasks, sprint contracts, harness design |
| RTK Setup            | `skills/token-efficiency/rtk-setup.md`           | Token Efficiency | First session on a new machine; "install rtk"            |
| RTK Commands         | `skills/token-efficiency/rtk-commands.md`        | Token Efficiency | Any test/lint/build/git/docker command                   |
| RTK Context Hygiene  | `skills/token-efficiency/rtk-context-hygiene.md` | Token Efficiency | Session start, context window concerns                   |

---

## Adding a New Skill

1. Create `skills/<domain>/<skill-name>.md` with substantive guidance
2. Add a row to the catalog table above
3. Add a row to the Skill Activation Table in `CLAUDE.md`
4. Reference in `specs/` if the skill governs a spec domain

Skills files are owned by `@org/tech-lead` (see `.github/CODEOWNERS`).
