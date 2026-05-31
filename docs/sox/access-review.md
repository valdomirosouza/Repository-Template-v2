# SOX Quarterly Access Review

> **APPLICABILITY NOTICE**
> This document is required ONLY for organizations publicly listed on U.S. stock exchanges
> (NYSE, NASDAQ) or otherwise subject to SEC reporting obligations under SOX.
> If SOX does not apply, this file may be deleted.

**Review frequency:** Quarterly
**Owner:** Security Lead
**Evidence control:** CC7 (see `specs/compliance/sox-controls.md`)

---

## Instructions

1. Export the current user list from the identity provider and production secret manager.
2. For each entry, verify the justification is still valid and the last_access date is within 90 days.
3. Set `action` to `retain` or `revoke`. Revoke immediately; document date of revocation in notes.
4. Sign off with reviewer name and review_date.
5. Archive this file as `docs/sox/access-review-YYYY-QN.md` at end of quarter.

---

## Access Review Table

| user            | role          | resource       | last_access | justification        | action | reviewer | review_date | notes |
| --------------- | ------------- | -------------- | ----------- | -------------------- | ------ | -------- | ----------- | ----- |
| example@org.com | prod-deployer | k8s/production | YYYY-MM-DD  | On-call SRE rotation | retain | —        | —           | —     |

_Replace the example row above with actual access entries during each quarterly review._

---

## Revocation Log

Record all access revocations here for audit evidence:

| user | resource | revoked_date | revoked_by | reason |
| ---- | -------- | ------------ | ---------- | ------ |

---

## Sign-off

| Reviewer | Role          | Date | Signature |
| -------- | ------------- | ---- | --------- |
|          | Security Lead |      |           |
|          | Tech Lead     |      |           |
