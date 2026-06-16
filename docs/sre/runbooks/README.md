# SRE Operational Runbooks

SRE operational runbooks for this system, in the **`RB-SRE-NNN` namespace**.

These are distinct from the incident-response runbooks in
[`docs/runbooks/`](../../runbooks/README.md) (the `RB-NNN` namespace, driven by the
alert → runbook mapping). The two namespaces exist so an ID never collides across
domains — `RB-005` (kafka-consumer-lag, incident) and `RB-SRE-005`
(agent-session-recovery, SRE) are different runbooks. See ADR-0033 and issue #195.

All runbooks follow the same **blameless format** described in
[`docs/runbooks/README.md`](../../runbooks/README.md).

---

## Numbered runbooks (`RB-SRE-NNN`)

| ID         | Runbook                                                                        | Spec / ADR |
| ---------- | ------------------------------------------------------------------------------ | ---------- |
| RB-SRE-004 | [RB-SRE-004-canary-probe-validation.md](RB-SRE-004-canary-probe-validation.md) | ADR-0042   |
| RB-SRE-005 | [RB-SRE-005-agent-session-recovery.md](RB-SRE-005-agent-session-recovery.md)   | ADR-0033   |
| RB-SRE-006 | [RB-SRE-006-restore-drill.md](RB-SRE-006-restore-drill.md)                     | ADR-0082   |

> Numbering note: the `004`/`005` digits are retained from before the namespace split
> (no renumber) to preserve continuity with prior references and the changelog.

---

## Operational procedures (named)

Topic-named operational runbooks in this directory:

- [api-gateway-high-error-rate.md](api-gateway-high-error-rate.md)
- [cert-rotation.md](cert-rotation.md)
- [db-key-rotation.md](db-key-rotation.md)
- [dlq-accumulating.md](dlq-accumulating.md)
- [hitl-queue-backlog.md](hitl-queue-backlog.md)
- [kafka-consumer-lag.md](kafka-consumer-lag.md)
- [redis-connection-failure.md](redis-connection-failure.md)
- [redis-ha.md](redis-ha.md)
