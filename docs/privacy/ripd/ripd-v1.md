# Relatório de Impacto à Proteção de Dados Pessoais (RIPD) — v1

**LGPD Art. 38 | Versão:** 1.0 | **Data:** 2026-05-24 | **Status:** Rascunho

---

## Seção 1 — Identificação

| Campo             | Detalhe                                                   |
| ----------------- | --------------------------------------------------------- |
| Nome da atividade | Processamento de Ações de Agente de IA com Integração LLM |
| Controlador       | \<Nome da Organização\>                                   |
| Encarregado (DPO) | \<Nome do DPO\> — dpo@\<org-domain\>                      |
| Autor             | \<Nome do Autor\>                                         |
| Versão            | 1.0                                                       |

---

## Seção 2 — Descrição do Tratamento

**Finalidade:** Processar solicitações de usuários por meio de agentes de IA que utilizam inferência LLM para raciocinar e propor ações. Ações com efeito no mundo real requerem aprovação humana (HITL) antes da execução.

**Base legal (LGPD):**

- Art. 7, II — execução de contrato
- Art. 7, IX — legítimo interesse para monitoramento operacional

**Titulares dos dados:** Usuários cadastrados que submetem solicitações ao sistema.

**Dados pessoais tratados:**

| Categoria                       | Nível          | Como é tratado                             |
| ------------------------------- | -------------- | ------------------------------------------ |
| Contexto do usuário (mascarado) | L2 → tokens    | Enviado ao LLM após mascaramento           |
| ID do usuário                   | L3             | Incluído no log de auditoria (anonimizado) |
| Metadados de sessão             | L3             | Usado para correlação de requisições       |
| Endereço IP                     | L2 → mascarado | Registrado apenas como token `[IP]`        |

**Operadores e suboperadores:**

- Provedor de LLM (\<Nome do Provedor\>) — DPA-\<ID\>: confirma que dados não são usados para treinamento
- Provedor de infraestrutura em nuvem (\<Nome do Provedor\>) — DPA-\<ID\>

**Transferência internacional:** Sim — provedor de LLM em \<País\>. Mecanismo: proteções equivalentes exigidas pela ANPD (Art. 33 LGPD). Referência: DPA-\<ID\>.

**Retenção:** Histórico de ações do agente: 90 dias ativos + 30 dias exclusão suave. Logs de interação LLM: 30 dias.

---

## Seção 3 — Necessidade e Proporcionalidade

| Questão                                                      | Avaliação                                                                                                                   |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| O tratamento é necessário para a finalidade declarada?       | Sim — a inferência LLM é a capacidade central; nenhuma alternativa alcança o mesmo resultado sem contexto de dados pessoais |
| A minimização de dados é aplicada?                           | Sim — apenas contexto mascarado é enviado ao LLM; PII bruta nunca sai do perímetro do sistema                               |
| Os mecanismos de direitos dos titulares estão implementados? | Sim — acesso, correção, exclusão e portabilidade implementados                                                              |
| A base legal está estabelecida?                              | Sim — contrato (Art. 7, II) para o serviço principal                                                                        |

---

## Seção 4 — Avaliação de Riscos

| Risco                                               | Probabilidade (1–3) | Impacto (1–3) | Score | Mitigação                                                                                     | Risco Residual |
| --------------------------------------------------- | ------------------- | ------------- | ----- | --------------------------------------------------------------------------------------------- | -------------- |
| PII não mascarada enviada ao provedor LLM           | 2                   | 3             | 6     | Filtro de PII obrigatório na chamada LLM (ADR-0012); teste automatizado `test_pii_leakage.py` | Baixo          |
| Acesso não autorizado aos logs de auditoria         | 2                   | 3             | 6     | Controle de acesso baseado em função; logs de auditoria somente leitura                       | Baixo          |
| Dados do titular não excluídos mediante solicitação | 1                   | 3             | 3     | Fluxo de exclusão documentado e testado; SLA de 15 dias úteis                                 | Baixo          |
| Autonomia excessiva do agente — ações sem aprovação | 1                   | 3             | 3     | Gateway HITL obrigatório para todas as ações consequentes; timeout = rejeição                 | Baixo          |
| Violação de dados no provedor LLM terceirizado      | 1                   | 3             | 3     | DPA confirma ausência de treinamento; apenas dados mascarados                                 | Baixo          |

---

## Seção 5 — Medidas de Mitigação

**Medidas técnicas:**

- Mascaramento de PII em três pontos de interceptação obrigatórios (chamada LLM, escrita de log, publicação no broker)
- Gateway HITL bloqueia ações consequentes até aprovação humana
- Log de auditoria imutável de todas as decisões do agente
- TLS 1.3 em trânsito; AES-256 em repouso para dados L1
- Purga automatizada mensal de retenção com relatório de verificação
- Suite de testes automatizados de vazamento de PII (`tests/security/test_pii_leakage.py`)

**Medidas organizacionais:**

- Encarregado revisa todas as novas atividades de tratamento antes da liberação em produção
- Engenheiros recebem treinamento em privacidade desde a concepção
- SLA de direitos dos titulares: 15 dias úteis para resposta
- Procedimento de resposta a incidentes documentado em `docs/runbooks/disaster-recovery.md`
- Procedimento de notificação de incidentes à ANPD documentado

---

## Seção 6 — Aprovação

| Função                               | Nome            | Data             | Decisão                                              |
| ------------------------------------ | --------------- | ---------------- | ---------------------------------------------------- |
| Encarregado consultado               | \<Nome do DPO\> | \<Data\>         | \<Aprovado / Aprovado com condições / Não aprovado\> |
| Condições do Encarregado (se houver) |                 |                  | \<Condições\>                                        |
| Data de aprovação final              |                 | \<Data\>         |                                                      |
| Data da próxima revisão              |                 | \<Data + 1 ano\> |                                                      |

---

## Histórico de Versões

| Versão | Data       | Autor     | Alterações                        |
| ------ | ---------- | --------- | --------------------------------- |
| 1.0    | 2026-05-24 | \<Autor\> | RIPD inicial para scaffold v0.1.0 |
