<!-- Infrastructure / pipeline / deploy change. ?template=infrastructure-change.md -->

## Summary

<!-- What infrastructure changed and why. -->

## Linked issue / RFC

Closes #
RFC: <!-- RFC-NNNN (required for Normal/Emergency changes) -->

## Change classification (ISO 27001)

- [ ] Standard · [ ] Normal (CAB-approved) · [ ] Emergency (retroactive RFC ≤ 24h)

## Canary / rollback plan

- [ ] Canary path documented (5% → 25% → 100%) with SLO gate
- [ ] Rollback tested in staging (`make rollback`); within MTTR target

## Cost impact

<!-- Expected change to infra/cloud cost, if any. -->

## Scans

- [ ] IaC scan (Checkov) passed on `infrastructure/` changes
- [ ] Container scan (Trivy) clean — zero CRITICAL CVEs (if images changed)

## Approvals

- [ ] CAB approval recorded (Normal/Emergency) — RFC_ID in merge commit
- [ ] DevOps Lead review requested
- [ ] `CHANGELOG.md` updated
