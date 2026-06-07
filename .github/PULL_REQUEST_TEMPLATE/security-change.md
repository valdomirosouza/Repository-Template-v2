<!-- Security change / vulnerability remediation. ?template=security-change.md -->

## Summary

<!-- What security issue this addresses and how. -->

## Linked issue / spec

Closes #
Threat model: `specs/security/threat-model.md`

## STRIDE category

- [ ] Spoofing · [ ] Tampering · [ ] Repudiation · [ ] Info disclosure · [ ] DoS · [ ] Elevation

## Finding reference

CVE / advisory / scanner finding: <!-- e.g. CVE-2026-xxxxx, Trivy/Bandit ID -->

## Remediation evidence

- [ ] Fix verified locally; before/after evidence in PR
- [ ] SAST rerun clean (`bandit` / `gosec` / `SpotBugs`)
- [ ] SCA rerun clean (`pip-audit` / OWASP dep-check)
- [ ] No new CRITICAL/HIGH findings (or documented risk acceptance)

## Rollback plan

<!-- How to revert safely if this regresses. -->

## Review

- [ ] Security Lead review requested
- [ ] `CHANGELOG.md` updated; no secrets/PII added
