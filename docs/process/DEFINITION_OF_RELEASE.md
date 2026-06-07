# Definition of Release (DoR-Release)

> **Version:** 1.0.0 | **Last updated:** 2026-06-06
> **Owner:** Release Manager | **Approver:** Release Manager + Security Lead
> **ADR:** ADR-0052 | **Workflow phase:** Phase 12 — Release Candidate

A release is ready for production promotion only when **ALL** of the following criteria are met. The Release Manager applies the `rc-approved` label on the release PR once satisfied.

---

## DoR-Release Checklist

### Completeness

- [ ] All Issues in the release milestone are `status: done`
- [ ] Zero open `priority: P0` or `priority: P1` issues linked to this release
- [ ] `CHANGELOG.md` — `[Unreleased]` section moved to `[{version}] - {date}`
- [ ] `version.txt` and `pyproject.toml` agree on the new version number

### Test Gates

- [ ] Full CI suite green on `release/{version}` branch (unit + integration + security)
- [ ] Chaos tests green: `pytest tests/chaos/`
- [ ] Model contract tests green: `pytest tests/model_contract/ -m model_contract`
- [ ] Abuse case tests green: `pytest tests/abuse_cases/ -m abuse_case`
- [ ] DAST (OWASP ZAP full scan) passed in staging — scan report linked in release PR

### Security & Compliance

- [ ] SBOM generated via Syft and cosign-attested on the release image
- [ ] Container scan (Trivy) — zero CRITICAL CVEs
- [ ] SCA scan (pip-audit / OWASP dep-check) — no unmitigated CRITICAL findings
- [ ] HITL operator tokens rotated and rotation documented in ops log
- [ ] `make agentic-maturity-check` output reviewed and accepted by Tech Lead
- [ ] ISO 27001 change type label applied to release PR (`standard-change` / `normal-change` / `emergency-change`)
- [ ] CAB approval obtained for Normal or Emergency changes (`RFC_ID` in release commit message)

### Operational Readiness

- [ ] PRR checklist (`skills/sre/prr.md`) signed off for all new services or components
- [ ] Runbooks updated for all new failure modes introduced in this release
- [ ] Rollback plan documented and tested in staging (`make rollback` dry-run confirmed)
- [ ] Grafana dashboards cover all new feature critical paths
- [ ] On-call SRE briefed on new failure modes and rollback procedure

### Release Notes

- [ ] Release notes generated from `CHANGELOG.md` and reviewed by Release Manager
- [ ] Breaking changes explicitly called out with migration instructions
- [ ] Deprecations listed with sunset dates

### Governance

- [ ] `rc-approved` label applied by Release Manager to the release PR
- [ ] Security Lead has reviewed the release notes security section
- [ ] DORA metrics baseline recorded pre-release for post-deploy comparison

---

## Production Promotion Sequence

After all criteria above are met, production deployment follows the canary sequence defined in `cd-production.yml`:

```
5% canary → readiness gate (SLO burn rate check) →
25% canary → readiness gate →
100% rollout → GitHub Release tag → deployment notification
```

Abort and rollback automatically if the SLO burn rate exceeds the threshold at any canary step.

---

## Related

- `docs/process/DEFINITION_OF_DONE.md` — story-level completion criteria
- `docs/process/WORKFLOW.md` — full Phase 12–14 release process
- `skills/change-management/deploy-rollback.md` — deployment procedure
- `skills/sre/prr.md` — Production Readiness Review checklist
- `docs/sre/slo/slo.yaml` — SLO definitions and MTTR targets
