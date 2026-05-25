# Skill — PII Handling

Activate this skill for any code that reads, writes, transforms, or transmits personal data.

---

## Classification Levels

| Level | Name      | Examples                                          | Masking token                |
| ----- | --------- | ------------------------------------------------- | ---------------------------- |
| L1    | Critical  | CPF, SSN, health records, biometric data          | `[CPF]`, `[CARD]`            |
| L2    | Sensitive | Email, full name, phone, IP address, home address | `[EMAIL]`, `[PHONE]`, `[IP]` |
| L3    | Internal  | User ID, session token, request ID                | `[TOKEN]`, `[UUID]`          |
| L4    | Public    | Publicly available info                           | Pass through                 |

Full field inventory: `docs/privacy/pii-inventory.md` and `specs/privacy/pii-inventory.md`

---

## How to Classify a New Data Field

```
Is the field directly tied to a natural person's identity or body?
  YES → L1 (Critical)

Can it identify a person when combined with other fields?
  YES → L2 (Sensitive)

Is it a system-internal identifier that could be traced back to a person?
  YES → L3 (Internal)

Is it publicly available with no privacy risk?
  YES → L4 (Public / pass-through)
```

When uncertain, escalate to DPO. Err towards the higher classification.

---

## Adding a New Field

1. Classify the field using the decision tree above
2. Add a row to the field inventory table in `docs/privacy/pii-inventory.md`
3. Add the field name to the masking registry in `src/guardrails/pii_filter.py`
4. Write a unit test confirming the field is masked (synthetic data only)
5. If L1 or L2: notify DPO — new personal data processing may require DPIA/RIPD update

---

## Implementing Masking for a New Field

Add the field name to the field registry in `pii_filter.py`:

```python
# Field-name-based masking registry
L2_FIELD_NAMES = {
    "email", "full_name", "phone_number", "ip_address",
    "new_field_name",  # add here
}
```

Unit test using synthetic data:

```python
def test_masks_new_field():
    result = pii_filter.mask_dict({"new_field_name": "test@example.com"})
    assert result["new_field_name"] == "[EMAIL]"
    # token depends on detected PII type; for an email value the token is [EMAIL]
    # Never use real email addresses in tests
```

---

## Three Mandatory Masking Points

Every path that handles personal data must apply masking at all three points:

1. **Pre-LLM call** — mask before constructing the prompt: `pii_filter.mask_dict(context)`
2. **Pre-log write** — mask before emitting any structured log line
3. **Pre-broker publish** — mask before calling `producer.send()`

Missing any one of these is a P1 privacy incident.

---

## Synthetic Data Standard for Tests

| PII type   | Use this synthetic value               |
| ---------- | -------------------------------------- |
| CPF        | `000.000.000-00`                       |
| Email      | `test@example.com`                     |
| Full name  | `Test User`                            |
| IP address | `192.0.2.1` (RFC 5737 TEST-NET)        |
| Phone      | `+55 11 00000-0000`                    |
| User ID    | `00000000-0000-0000-0000-000000000000` |

Real PII in any test file, fixture, or seed is a **P1 security incident** — file it immediately.

---

## DPO Notification Requirement

Notify the DPO (via `docs/privacy/data-processing-register.md` update + direct message) whenever:

- A new L1 or L2 field is introduced
- A new processing purpose is added
- Data is shared with a new third-party processor
- Retention period for any field changes

The DPO will determine if a DPIA/RIPD update is required before the change goes to production.
