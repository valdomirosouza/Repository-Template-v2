# Claude Code Session Primer

> Auto-loaded at session start. Supplements `CLAUDE.md` and `skills/sdlc/agent-onboarding.md`.
> Keep this file concise — it is loaded into every session's context window.

---

## Repo Identity

- **Repo:** Repository-Template-v2
- **Type:** Multi-language enterprise monorepo template (Python/FastAPI, Java/Spring Boot, Go, Next.js)
- **Current version:** see `version.txt`
- **Active branch convention:** `develop` for work-in-progress; `main` for releases

## Critical Paths (highest sensitivity — escalate before touching)

| Path                            | Why sensitive                           |
| ------------------------------- | --------------------------------------- |
| `src/agents/hitl_gateway.py`    | Dual-approval: Security + AI Governance |
| `src/guardrails/`               | Security Lead approval required         |
| `src/shared/feature_flags.py`   | Controls HITL/HOTL autonomy — ADR-0015  |
| `infrastructure/feature-flags/` | Governance review required              |
| `.github/workflows/`            | DevOps Lead ownership                   |

## Open Work

Check current open issues before starting:

```bash
gh issue list --repo valdomirosouza/Repository-Template-v2 --state open --label agentic-sdlc
```

Wave labels: `wave-1` (done) → `wave-2` → `wave-3` → `wave-4` → `wave-5`

## Session Bootstrap Checklist

- [ ] CLAUDE.md read and §14 escalation triggers noted
- [ ] `services.yaml` scanned for affected service
- [ ] Relevant skill(s) loaded (max 2)
- [ ] GitHub Issue identified with spec reference
- [ ] Spec status confirmed as `Approved`

## ADR Quick Index (most recent)

| ADR      | Decision                              |
| -------- | ------------------------------------- |
| ADR-0030 | RTK token efficiency integration      |
| ADR-0031 | Agent onboarding protocol             |
| ADR-0032 | Sub-agent specialization registry     |
| ADR-0033 | Long-running agent session durability |
| ADR-0034 | Agentic escalation protocol           |
| ADR-0035 | AI-assisted CI review                 |
| ADR-0036 | Agentic cyber defense protocol        |

Full index: `docs/adr/README.md`
