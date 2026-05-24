# Model Card — \<Model Name\>

**Version:** 1.0 | **Date:** 2026-05-24 | **Owner:** AI Governance Lead

---

## Model Details

| Field               | Value                              |
| ------------------- | ---------------------------------- |
| Provider            | \<Provider Name\>                  |
| Model ID / Version  | \<model-id-version\>               |
| API endpoint        | Configured via `LLM_MODEL` env var |
| Modality            | Text → Text                        |
| Context window      | \<N\> tokens                       |
| In production since | \<Date\>                           |

**Intended use cases:**

- Reasoning over user requests and proposing structured actions
- Classifying input risk level for HITL/HOTL routing
- Generating draft outputs for human review

**Out-of-scope uses:**

- Processing of unmasked personal data (L1 or L2 PII must be masked before ingestion)
- Autonomous execution of irreversible actions without HITL approval
- Use cases outside the documented agent scope in `specs/ai/agent-design.md`

---

## Training Data (if fine-tuned)

| Field        | Value                                               |
| ------------ | --------------------------------------------------- |
| Fine-tuned   | No (using base provider model)                      |
| Data sources | N/A                                                 |
| Date range   | N/A                                                 |
| Known biases | Inherited from base model — see provider model card |

For fine-tuned versions: document data sources, date range, known biases, and
filtering applied here before deploying.

---

## Performance

| Benchmark                         | Score                    | Evaluation methodology                        |
| --------------------------------- | ------------------------ | --------------------------------------------- |
| Task accuracy (internal eval set) | \<Score\>%               | \<Methodology\>                               |
| Latency p50                       | \<N\>ms                  | Measured in staging under representative load |
| Latency p99                       | \<N\>ms                  | Measured in staging under representative load |
| Token efficiency                  | \<N\> avg tokens/request | Measured over 7-day production sample         |

Evaluation dataset: synthetic, PII-free test cases stored in `tests/fixtures/`.

---

## Ethical Considerations

**Known failure modes:**

- Hallucination on low-context requests — mitigated by output validation in `guardrails/output_validator.py`
- Bias toward majority patterns in training data — see bias audit summary below
- Degraded performance on domain-specific terminology outside training distribution

**Bias assessment summary:**
See `docs/ai-governance/bias-audit.md` for the full bias audit report.
Key findings: \<summary of findings or "Initial audit pending — due \<Date\>"\>

**Autonomy level:** HITL for all consequential actions; HOTL for read-only and
classification flows. See ADR-0011 and `docs/ai-governance/autonomy-boundaries.md`.

---

## Privacy

| Field                      | Value                                                                     |
| -------------------------- | ------------------------------------------------------------------------- |
| Data sent to model         | Masked user context only — L1/L2 PII replaced with tokens before API call |
| PII handling               | Mandatory masking via `src/guardrails/pii_filter.py` (ADR-0012)           |
| Data retention at provider | Per DPA-\<ID\>: \<N\> days; no use for model training                     |
| Data Processing Agreement  | DPA-\<ID\> signed \<Date\>                                                |
| Cross-border transfer      | \<Country\> — SCCs / adequacy decision reference                          |

---

## Monitoring in Production

| Signal              | Metric                               | Dashboard           |
| ------------------- | ------------------------------------ | ------------------- |
| Error rate          | `llm_call_errors_total`              | golden-signals.json |
| Latency             | `llm_call_latency_seconds` (p50/p99) | golden-signals.json |
| Token usage         | `llm_token_usage_total`              | finops.json         |
| HITL rejection rate | `hitl_rejections_total`              | sre-overview.json   |

Drift detection: compare output distribution weekly against baseline eval set.
Retraining / model upgrade trigger: accuracy drop > 5% or bias audit finding rated HIGH.

---

## Changelog

| Version | Date       | Change                                 |
| ------- | ---------- | -------------------------------------- |
| 1.0     | 2026-05-24 | Initial model card for scaffold v0.1.0 |
