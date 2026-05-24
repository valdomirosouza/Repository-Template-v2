# Prompt 012 — Postmortem Template

> **Requires:** Prompt 001 completed.
> Reference: `docs/postmortems/tmp/` (exemplos reais de post-mortems do projeto).
> Skip any file that already exists with real content.

---

## Context

The repository has real post-mortem examples in `docs/postmortems/tmp/`:

- `INC-001-redis-oom.md` — P2, Redis OOM during traffic spike, 5 Whys analysis
- `INC-002-latency-spike.md` — P3, Blue/Green latency spike, HOTL model in action
- `INC-003-bluegreen-deploy-failure.md` — SEV1, cascading 5xx, AI Copilot role documented

Read all three examples before writing the template. The template must reflect
the actual patterns, tone, and structure used in this project.

---

## Task

Create one file: `docs/postmortems/POSTMORTEM-TEMPLATE.md`

---

## `docs/postmortems/POSTMORTEM-TEMPLATE.md`

A blameless post-mortem template. Requirements derived from the three examples:

### Header block

```
# Post-Mortem: INC-XXX — [Título curto do incidente]
```

Metadata fields:

- `Data:` YYYY-MM-DD
- `Duração do impacto:` HH:MM UTC → HH:MM UTC (N minutos)
- `Severidade:` P1 Crítico / P2 Alto / P3 Médio / P4 Baixo
- `Incident Commander:` placeholder
- `Autor(es):` placeholder
- `Status:` RASCUNHO / EM REVISÃO / FECHADO

Include a blameless culture note citing _Google SRE Book, Cap. 15_.

### Required sections (in this order)

1. **Resumo Executivo** — 2–4 sentences readable by non-technical stakeholders

2. **Impacto** — table with: incident duration, users/requests affected,
   services affected, critical endpoints, SLO impact (actual % vs target %),
   error budget consumed, MTTD, MTTR, business/revenue impact

3. **Linha do Tempo** — UTC timestamp table; key events: trigger, first signal,
   alert fired, diagnosis complete, mitigation start, service normalised, incident closed

4. **Causa Raiz** — three sub-sections:
   - Root Cause (systemic vulnerability)
   - Trigger (the specific event)
   - Fator Agravante (optional)
   - Análise dos 5 Porquês (conditional — include with note to delete if not needed)

5. **O Que Foi Bem** — checklist format; mandatory minimum 2 items;
   note explaining why this section is required (avoid purely negative postmortems)

6. **O Que Pode Melhorar** — checklist format; each item must map to an action item

7. **Papel do Sistema de AI / HITL-HOTL** — table covering: operation mode
   (HITL/HOTL/disabled), what the agent detected, MTTD with agent, human decision
   taken, limitations identified, whether it worked as expected.
   Include a note to delete if AI was not involved.

8. **Ações Corretivas** — two sub-sections:
   - Imediatas (already executed) — numbered list with ✅
   - Preventivas (long-term) — table with Priority, Action, Owner, Deadline, Status
   - Include the rule: every "O Que Pode Melhorar" item needs at least one action

9. **Lições para a Knowledge Base** — bullet list of objective technical facts
   formatted for RAG reuse; written as direct technical assertions, not narrative

10. **Referências** — related runbook, similar incident, Grafana dashboard,
    ADR, external literature

### Style requirements

- Language: Portuguese (section titles) with English technical terms inline
- Tone: blameless; focus on systems and conditions, never people
- All placeholder values clearly marked with `<!-- comment -->` or `[placeholder]`
- Each section includes a brief comment explaining what to write there
- Consistent with the 3 example files in `docs/postmortems/tmp/`

### Validation

After creating the file, confirm:

- [ ] All 10 sections present in the correct order
- [ ] Header has all 6 metadata fields
- [ ] Impacto table has MTTD and MTTR rows
- [ ] 5 Porquês sub-section exists with note to delete if not needed
- [ ] AI/HITL-HOTL section has delete-if-not-applicable note
- [ ] Ações Corretivas has the mapping rule note
- [ ] Lições para a Knowledge Base includes at least one example of a "padrão de diagnóstico"
- [ ] File does not contain any real PII or real incident data
