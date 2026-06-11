# Post-Mortem: INC-XXX — [Título curto do incidente]

> **Cultura blameless:** Este documento segue os princípios da cultura blameless do Google SRE.
> O objetivo é aprender, não atribuir culpa. Foque em sistemas, processos e condições —
> nunca em pessoas. Consulte: _Google SRE Book, Cap. 15 — Postmortem Culture_.

---

**Data:** YYYY-MM-DD
**Duração do impacto:** HH:MM UTC → HH:MM UTC (N minutos)
**Severidade:** <!-- P1 Crítico / P2 Alto / P3 Médio / P4 Baixo — SEV1/SEV2/SEV3 -->
**Incident Commander:** <!-- Nome do responsável pela coordenação -->
**Autor(es):** <!-- Nome(s) do(s) autor(es) do post-mortem -->
**Status:** <!-- RASCUNHO / EM REVISÃO / FECHADO -->

---

## Resumo Executivo

<!-- 2–4 frases: o que aconteceu, qual foi o impacto principal, como foi resolvido.
     Deve ser legível por stakeholders não-técnicos. -->

---

## Impacto

| Métrica                         | Valor                                           |
| ------------------------------- | ----------------------------------------------- |
| Duração do incidente            | <!-- N minutos -->                              |
| Usuários / requisições afetados | <!-- N% ou N usuários -->                       |
| Serviços afetados               | <!-- api-gateway, agent-service, etc. -->       |
| Endpoints críticos              | <!-- /api/checkout, /v1/status, etc. -->        |
| SLO impactado                   | <!-- Disponibilidade: 99.X% (target: 99.9%) --> |
| Error budget consumido          | <!-- N% do budget mensal -->                    |
| MTTD (detecção)                 | <!-- N minutos -->                              |
| MTTR (resolução)                | <!-- N minutos -->                              |
| Impacto em receita / negócio    | <!-- Descreva ou "Sem impacto direto" -->       |

---

## Linha do Tempo

| Horário (UTC) | Evento                                                                        |
| ------------- | ----------------------------------------------------------------------------- |
| HH:MM         | <!-- Condição que precipitou o incidente (deploy, spike de tráfego, etc.) --> |
| HH:MM         | <!-- Primeiro sinal de degradação detectado -->                               |
| HH:MM         | <!-- Alerta disparado / engenheiro on-call acionado -->                       |
| HH:MM         | <!-- Diagnóstico concluído / causa raiz identificada -->                      |
| HH:MM         | <!-- Mitigação iniciada -->                                                   |
| HH:MM         | <!-- Serviço normalizado -->                                                  |
| HH:MM         | <!-- Incidente encerrado / post-mortem agendado -->                           |

---

## Causa Raiz

### Root Cause (Vulnerabilidade Sistêmica)

<!-- O que tornou o sistema susceptível a este tipo de falha?
     Descreva a condição estrutural — não o evento que a expôs. -->

### Trigger (Gatilho)

<!-- O evento específico que expôs a vulnerabilidade (deploy, pico de tráfego,
     mudança de configuração, falha de dependência externa). -->

### Fator Agravante (se aplicável)

<!-- O que tornou o impacto pior do que seria em condições normais? -->

### Análise dos 5 Porquês

<!-- Use quando a causa raiz não for imediatamente óbvia.
     Delete esta seção se a causa raiz for direta e evidente. -->

1. Por que [sintoma principal]? → [resposta]
2. Por que [resposta anterior]? → [resposta]
3. Por que [resposta anterior]? → [resposta]
4. Por que [resposta anterior]? → [resposta]
5. Por que [resposta anterior]? → **Causa raiz identificada**

---

## O Que Foi Bem

<!-- Celebre o que funcionou: detecção rápida, degradação graciosa,
     decisão correta do on-call, eficácia de um alerta, etc.
     Esta seção é obrigatória — evita que post-mortems sejam
     exclusivamente negativos. Mínimo: 2 itens. -->

- [ Item 1 — ex.: "Rate limiting protegeu o sistema de avalanche de requisições durante a degradação" ]
- [ Item 2 ]
- [ Item 3 ]

---

## O Que Pode Melhorar

<!-- Identifique lacunas sistêmicas — não erros de pessoas.
     Cada item aqui deve virar um action item na seção seguinte. -->

- [ Item 1 — ex.: "Não havia alerta para uso de memória Redis acima de 80%" ]
- [ Item 2 ]
- [ Item 3 ]

---

## Papel do Sistema de AI / HITL-HOTL

<!-- Preencha esta seção se o agente AI esteve envolvido no incidente ou na resposta.
     Delete se não for aplicável. -->

**Modo de operação durante o incidente:** <!-- HITL / HOTL / Desabilitado -->

| Aspecto                    | Descrição                                                     |
| -------------------------- | ------------------------------------------------------------- |
| O que o agente detectou    | <!-- Diagnóstico produzido pelo agente -->                    |
| MTTD com agente            | <!-- Tempo até primeira detecção -->                          |
| Decisão humana (HOTL/HITL) | <!-- Ação tomada pelo on-call com base no brief do agente --> |
| Limitações identificadas   | <!-- Blind spots, falsos negativos, tool-use limits, etc. --> |
| Funcionou como esperado?   | <!-- Sim / Não / Parcialmente — explique -->                  |

---

## Ações Corretivas

### Imediatas (já executadas)

<!-- Ações tomadas durante o incidente para mitigar o impacto. -->

1. ✅ [Ação 1 — ex.: Rollback executado]
2. ✅ [Ação 2]

### Preventivas (longo prazo)

| Prioridade | Ação                                               | Responsável   | Prazo         | Status                                     |
| ---------- | -------------------------------------------------- | ------------- | ------------- | ------------------------------------------ |
| P0         | <!-- Ação crítica — evita recorrência imediata --> | <!-- Quem --> | <!-- Data --> | <!-- Aberto / Em andamento / Concluído --> |
| P1         | <!-- Ação importante -->                           |               |               |                                            |
| P2         | <!-- Ação de melhoria -->                          |               |               |                                            |

> **Regra:** Cada item de "O Que Pode Melhorar" deve ter pelo menos uma ação corretiva correspondente.

---

## Lições para a Knowledge Base

<!-- Fatos técnicos objetivos aprendidos neste incidente, formatados para
     reutilização futura (pelo time e pelo agente AI em contexto RAG).
     Escreva como afirmações técnicas diretas, não como narrativa. -->

- [Fato técnico 1 — ex.: "Redis com maxmemory-policy noeviction e sem maxmemory → OOM em picos de tráfego"]
- [Fato técnico 2]
- [Padrão de diagnóstico — ex.: "Latência P50 saudável + P95/P99 críticos → falha em subconjunto de instâncias, não saturação global"]
- [Solução imediata — ex.: "Solução imediata para Redis OOM: redis-cli CONFIG SET maxmemory-policy allkeys-lru"]

---

## Referências

<!-- Links para runbooks, ADRs, dashboards, incidentes relacionados, literatura. -->

- Runbook relacionado: <!-- [RB-XXX nome](../runbooks/RB-XXX-nome.md) — substituir pelo runbook relevante em docs/runbooks/ -->
- Incidente similar: <!-- INC-XXX — Título -->
- Dashboard: <!-- Grafana → "Golden Signals" → painel relevante -->
- ADR relacionado: <!-- ADR-XXXX — Título -->
- Literatura: <!-- Google SRE Book Cap. XX / artigo externo -->
