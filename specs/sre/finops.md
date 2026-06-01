# Spec FIN-001: FinOps Budget Template and Cost-Allocation Guide

**Spec ID:** FIN-001
**Version:** 1.0.0
**Date:** 2026-05-31
**Status:** Accepted
**Author:** Valdomiro Souza
**Related ADR:** ADR-0020

---

## 1. Problem Statement

ADR-0020 defines the cost allocation strategy for this system but provides no
actionable template artefacts. Engineering teams have no standard reference for:

- Monthly budget thresholds per environment
- Required cost allocation tags for cloud resources
- Alert rules for spend anomalies
- Cloud cost optimization checklist
- Chargeback/showback model for internal reporting

## 2. Solution

Deliver `docs/sre/finops.md` — a complete FinOps reference document that covers
budget templates, cost allocation, alerting, optimization, and maturity model.

The document is environment-agnostic (AWS/GCP/Azure placeholders) and follows the
FinOps Foundation's Inform → Optimize → Operate maturity model.

## 3. Scope

### In scope

- Monthly budget template (per environment × service)
- Cost allocation tag taxonomy
- Alert threshold rules (70% warning / 90% critical / 100% block)
- Cloud cost optimization checklist (15 items)
- Chargeback/showback model description
- FinOps maturity self-assessment table
- Cost review cadence

### Out of scope

- Cloud-provider-specific pricing APIs
- Automated cost anomaly detection tooling (future ADR)
- FinOps platform integration (e.g., Apptio, CloudHealth)

## 4. Acceptance Criteria

- [ ] `docs/sre/finops.md` present and follows repo doc style
- [ ] Budget template covers dev/staging/production environments
- [ ] Minimum 5 required cost allocation tags defined
- [ ] Alert thresholds documented for 70% / 90% / 100% spend
- [ ] Optimization checklist has ≥ 10 actionable items
- [ ] CHANGELOG.md updated under `[Unreleased]`

## 5. References

- ADR-0020: Cost allocation strategy
- FinOps Foundation: https://www.finops.org
- `docs/sre/slo/slo.yaml` — SLO targets (cost efficiency is a reliability concern)
