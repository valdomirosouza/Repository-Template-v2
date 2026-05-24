# Prompt 010 — Guardrails Source Code + Tests

> **Requires:** Prompts 001 and 009 completed.
> Reference document: `MONOREPO-STRUCTURE-EN.md` (Section 9 AI Governance,
> Section "SOURCE CODE → guardrails/", Section "TESTS → security/").
>
> ## CONTENT POLICY NOTE — READ BEFORE IMPLEMENTING
>
> All guardrail code and tests in this prompt are **defensive controls** that
> detect and reject invalid inputs. Implementation rules:
>
> 1. All detection logic uses **structural pattern matching and format validation**,
>    not reproduction of real attack strings.
> 2. All test inputs use **clearly synthetic placeholder tokens** such as
>    `SYNTHETIC_INJECT_ATTEMPT`, `SYNTHETIC_OVERRIDE_TOKEN`, `TEST_JAILBREAK_PATTERN`.
>    Never use real exploit strings, real PII, or real credentials in any file.
> 3. PII tests use only **obviously fake data**: `fake@example.com`, `000.000.000-00`,
>    `192.0.2.1` (TEST-NET), `Test User`, `SYNTHETIC_CPF`.
> 4. The goal of every function is to **return a safe value or raise a rejection**,
>    never to reproduce or store the detected pattern.

---

## Task

Create the following source code and test files with real, production-quality Python.
Apply the content policy rules above throughout.

---

## `src/guardrails/pii_filter.py`

PII masking with L1–L4 classification. Implement:

```python
from enum import Enum
import re

class PIILevel(Enum):
    L1_CRITICAL = 1    # CPF/SSN, health data, biometric — never in logs or LLM
    L2_SENSITIVE = 2   # name, email, phone, IP — mask in logs, pseudonymise for analytics
    L3_INTERNAL = 3    # username, session token — internal audit only
    L4_PUBLIC = 4      # declared role, org name — no special handling

@dataclass
class PIIMatch:
    field_type: str     # e.g. "EMAIL", "CPF", "IP"
    level: PIILevel
    start: int
    end: int
    replacement_token: str   # e.g. "[EMAIL]"

class PIIFilter:
    """
    Detects and replaces PII patterns in text and dictionaries.
    Uses format-based structural patterns only — no real PII stored in code.
    """

    def mask_text(self, text: str, min_level: PIILevel = PIILevel.L2_SENSITIVE) -> str:
        """Replace all PII at or above min_level with replacement tokens."""

    def mask_dict(self, data: dict, min_level: PIILevel = PIILevel.L2_SENSITIVE) -> dict:
        """Recursively mask PII in all string values of a dictionary."""

    def detect(self, text: str) -> list[PIIMatch]:
        """Return all PII matches found, without masking."""

    def _get_patterns(self) -> list[tuple[str, PIILevel, re.Pattern, str]]:
        """
        Returns list of (field_type, level, compiled_pattern, token).
        Patterns match the FORMAT/STRUCTURE of PII categories.
        Use patterns that match the shape of each category
        (e.g., email format, CPF digit structure, IPv4 format)
        without storing any real personal data.
        """
```

Detection patterns to implement (structural format matching only):

- Email address format → `[EMAIL]` (L2)
- Brazilian CPF format (NNN.NNN.NNN-NN or 11 digits) → `[CPF]` (L1)
- Phone number formats (E.164, local) → `[PHONE]` (L2)
- IPv4 address → `[IP]` (L2)
- IPv6 address → `[IP]` (L2)
- JWT token shape (three base64 segments separated by dots) → `[TOKEN]` (L3)
- UUID format → `[UUID]` (L3)
- Credit card format (Luhn-shaped 13–19 digit groups) → `[CARD]` (L1)

Provide a module-level singleton: `pii_filter = PIIFilter()`
and convenience functions: `mask_text(text)`, `mask_dict(data)`.

---

## `src/guardrails/prompt_injection_guard.py`

Input validation guard that detects structurally anomalous inputs and rejects them
before they reach the LLM. Implements **structural and heuristic checks only** —
no real payload strings stored in code.

```python
from enum import Enum
from dataclasses import dataclass

class RejectionReason(Enum):
    EXCESSIVE_LENGTH = "excessive_length"
    STRUCTURAL_ANOMALY = "structural_anomaly"   # unusual instruction-like structure
    ROLE_OVERRIDE_PATTERN = "role_override_pattern"   # attempts to redefine agent role
    REPETITIVE_PATTERN = "repetitive_pattern"   # unusual character/token repetition
    ENCODING_ANOMALY = "encoding_anomaly"       # unusual encoding or escape sequences
    NESTED_INSTRUCTION = "nested_instruction"   # deeply nested directive structure

@dataclass
class ValidationResult:
    is_valid: bool
    rejection_reason: RejectionReason | None = None
    risk_score: float = 0.0     # 0.0 = clean, 1.0 = high anomaly
    sanitised_input: str | None = None  # input after safe normalisation if valid

class PromptInjectionGuard:
    """
    Validates LLM inputs using structural heuristics.
    Rejects inputs that match anomaly signatures associated with
    instruction-override attempts. Never stores or logs the rejected content
    in full — logs only the rejection reason and a truncated hash.
    """

    def __init__(self, max_input_length: int = 8000, risk_threshold: float = 0.7): ...

    def validate(self, user_input: str) -> ValidationResult:
        """
        Run all structural checks. Returns ValidationResult.
        Logs rejection event (reason + input hash) via observability logger.
        Never raises — always returns a ValidationResult.
        """

    def _check_length(self, text: str) -> float: ...
    def _check_structural_anomaly(self, text: str) -> float: ...
    def _check_role_override_pattern(self, text: str) -> float: ...
    def _check_repetition(self, text: str) -> float: ...
    def _check_encoding(self, text: str) -> float: ...
    def _compute_risk_score(self, scores: list[float]) -> float: ...
    def _sanitise(self, text: str) -> str:
        """Normalise unicode, strip null bytes, collapse excessive whitespace."""
```

Implementation guidance:

- `_check_structural_anomaly`: detect unusually high ratio of imperative-form
  structural markers relative to input length (length + marker density heuristic)
- `_check_role_override_pattern`: detect inputs where early tokens are anomalously
  similar in structure to system-level directive formats (structural similarity score)
- `_check_repetition`: detect inputs with character or n-gram entropy below threshold
- Never log, store, or return the full rejected input — only log `sha256(input)[:16]`
  and the rejection reason
- Provide module-level singleton: `injection_guard = PromptInjectionGuard()`

---

## `tests/unit/guardrails/test_pii_filter.py`

Unit tests for `src/guardrails/pii_filter.py`.
**All test inputs must use clearly synthetic, obviously fake data.**

```python
import pytest
from src.guardrails.pii_filter import PIIFilter, PIILevel, mask_text, mask_dict

class TestPIIFilterEmail:
    def test_masks_email_in_plain_text(self):
        result = mask_text("Contact fake@example.com for support")
        assert "[EMAIL]" in result
        assert "fake@example.com" not in result

    def test_preserves_non_pii_text(self):
        result = mask_text("The service is running normally")
        assert result == "The service is running normally"

    def test_masks_multiple_emails(self):
        result = mask_text("From: a@example.com To: b@example.org")
        assert result.count("[EMAIL]") == 2

class TestPIIFilterCPF:
    def test_masks_cpf_formatted(self):
        # Using all-zero CPF — clearly synthetic, not a real Brazilian CPF
        result = mask_text("CPF: 000.000.000-00")
        assert "[CPF]" in result
        assert "000.000.000-00" not in result

    def test_masks_cpf_unformatted(self):
        result = mask_text("cpf 00000000000")
        assert "[CPF]" in result

class TestPIIFilterIP:
    def test_masks_ipv4_test_net(self):
        # 192.0.2.x is TEST-NET per RFC 5737 — safe to use in tests
        result = mask_text("Request from 192.0.2.1")
        assert "[IP]" in result
        assert "192.0.2.1" not in result

class TestMaskDict:
    def test_masks_nested_dict(self):
        data = {"user": {"email": "fake@example.com", "role": "admin"}}
        result = mask_dict(data)
        assert result["user"]["email"] == "[EMAIL]"
        assert result["user"]["role"] == "admin"

    def test_level_filter_skips_l4(self):
        data = {"org": "Example Corp"}   # L4 public — should not be masked
        result = mask_dict(data, min_level=PIILevel.L2_SENSITIVE)
        assert result["org"] == "Example Corp"
```

Add additional tests covering: phone masking, JWT token masking, UUID masking,
empty string input, very long input, dict with nested lists.

---

## `tests/unit/guardrails/test_prompt_injection_guard.py`

Unit tests for `src/guardrails/prompt_injection_guard.py`.
**All test inputs use clearly synthetic placeholder tokens — no real exploit strings.**

```python
import pytest
from src.guardrails.prompt_injection_guard import (
    PromptInjectionGuard, ValidationResult, RejectionReason
)

class TestNormalInputs:
    def test_accepts_normal_question(self):
        guard = PromptInjectionGuard()
        result = guard.validate("What is the status of my order?")
        assert result.is_valid is True
        assert result.rejection_reason is None

    def test_accepts_multi_sentence_input(self):
        guard = PromptInjectionGuard()
        result = guard.validate(
            "I need help with my account. The issue started yesterday."
        )
        assert result.is_valid is True

class TestLengthValidation:
    def test_rejects_excessively_long_input(self):
        guard = PromptInjectionGuard(max_input_length=100)
        long_input = "a" * 200
        result = guard.validate(long_input)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.EXCESSIVE_LENGTH

class TestStructuralAnomalyDetection:
    def test_rejects_synthetic_role_override_pattern(self):
        # Placeholder token — represents the structural shape, not a real payload
        guard = PromptInjectionGuard()
        synthetic_input = "SYNTHETIC_ROLE_OVERRIDE_PATTERN " * 20
        result = guard.validate(synthetic_input)
        # Guard may reject due to repetition or structural anomaly
        assert result.risk_score > 0.5

    def test_rejects_high_repetition_input(self):
        guard = PromptInjectionGuard()
        repetitive = "SYNTHETIC_REPEAT_TOKEN " * 50
        result = guard.validate(repetitive)
        assert result.is_valid is False
        assert result.rejection_reason == RejectionReason.REPETITIVE_PATTERN

class TestSanitisation:
    def test_sanitised_input_returned_on_valid(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Hello\x00World")   # null byte
        if result.is_valid:
            assert "\x00" not in (result.sanitised_input or "")

    def test_risk_score_range(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Normal input text")
        assert 0.0 <= result.risk_score <= 1.0
```

---

## `tests/security/test_owasp_llm_top10.py`

Defensive validation suite — verifies that guardrails **reject** the risk categories
defined in OWASP LLM Top 10. Uses placeholder tokens only.

```python
"""
Defensive validation suite for OWASP LLM Top 10 guardrail coverage.

Each test verifies that the relevant guardrail REJECTS a synthetic
placeholder input representing a risk category — it does NOT test
actual exploit payloads.

Risk categories tested by name (no payload content stored):
  LLM01 - Input manipulation attempts (structural anomaly detection)
  LLM06 - PII exposure prevention (masking before LLM call)
  LLM08 - Excessive agency prevention (action scope limits)
  LLM09 - Audit log integrity (immutable write enforcement)
"""
import pytest
from src.guardrails.pii_filter import PIIFilter, PIILevel
from src.guardrails.prompt_injection_guard import PromptInjectionGuard, RejectionReason
from src.guardrails.action_limits import ActionLimiter, ActionLimitConfig


class TestLLM01_InputManipulationPrevention:
    """Verify guard rejects structurally anomalous inputs (LLM01 category)."""

    def test_high_repetition_rejected(self):
        guard = PromptInjectionGuard()
        synthetic = "SYNTHETIC_INJECT_ATTEMPT " * 60
        result = guard.validate(synthetic)
        assert not result.is_valid, "Guard must reject high-repetition synthetic input"

    def test_excessive_length_rejected(self):
        guard = PromptInjectionGuard(max_input_length=500)
        long_synthetic = "SYNTHETIC_PADDING_TOKEN " * 100
        result = guard.validate(long_synthetic)
        assert not result.is_valid
        assert result.rejection_reason == RejectionReason.EXCESSIVE_LENGTH

    def test_normal_input_accepted(self):
        guard = PromptInjectionGuard()
        result = guard.validate("Please summarise the latest report.")
        assert result.is_valid


class TestLLM06_PIIExposurePrevention:
    """Verify PII is masked before reaching LLM boundary (LLM06 category)."""

    def test_email_masked_before_llm(self):
        pii = PIIFilter()
        raw = "User email is fake@example.com"
        masked = pii.mask_text(raw)
        assert "fake@example.com" not in masked
        assert "[EMAIL]" in masked

    def test_cpf_masked_before_llm(self):
        pii = PIIFilter()
        # Synthetic CPF — all zeros, clearly not a real person
        raw = "Document: 000.000.000-00"
        masked = pii.mask_text(raw)
        assert "000.000.000-00" not in masked

    def test_clean_text_unchanged(self):
        pii = PIIFilter()
        raw = "The request completed successfully."
        assert pii.mask_text(raw) == raw


class TestLLM08_ExcessiveAgencyPrevention:
    """Verify action scope limits block out-of-scope agent actions (LLM08 category)."""

    def test_disallowed_action_type_rejected(self):
        config = ActionLimitConfig(
            agent_id="test-agent",
            max_actions_per_minute=10,
            max_actions_per_hour=100,
            allowed_action_types=["read_document", "summarise"],
            max_records_affected=10,
            allowed_environments=["staging"],
        )
        limiter = ActionLimiter(config=config, redis_client=None)
        allowed, reason = limiter.check_scope_limit(
            agent_id="test-agent",
            action_type="delete_all_records",   # not in allowed_action_types
            parameters={},
        )
        assert not allowed
        assert "not allowed" in reason.lower()

    def test_allowed_action_type_passes(self):
        config = ActionLimitConfig(
            agent_id="test-agent",
            max_actions_per_minute=10,
            max_actions_per_hour=100,
            allowed_action_types=["read_document"],
            max_records_affected=10,
            allowed_environments=["staging"],
        )
        limiter = ActionLimiter(config=config, redis_client=None)
        allowed, _ = limiter.check_scope_limit(
            agent_id="test-agent",
            action_type="read_document",
            parameters={},
        )
        assert allowed


class TestLLM09_AuditLogIntegrity:
    """Verify audit logger enforces write integrity (LLM09 category)."""

    @pytest.mark.asyncio
    async def test_audit_event_persisted(self):
        from src.guardrails.audit_logger import AuditLogger, InMemoryAuditStorage
        from src.shared.models import AuditEvent

        storage = InMemoryAuditStorage()
        logger = AuditLogger(storage_backend=storage)
        event = AuditEvent(
            event_type="agent_action",
            agent_id="test-agent",
            action="read_document",
            outcome="success",
        )
        event_id = await logger.log_event(event)
        assert event_id is not None
        events = await logger.query_events(agent_id="test-agent")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_failed_write_raises_error(self):
        from src.guardrails.audit_logger import AuditLogger, AuditWriteError
        from src.shared.models import AuditEvent

        class FailingStorage:
            async def append(self, event): raise RuntimeError("Storage unavailable")
            async def query(self, **kwargs): return []

        logger = AuditLogger(storage_backend=FailingStorage())
        event = AuditEvent(
            event_type="agent_action",
            agent_id="test-agent",
            action="write_record",
            outcome="pending",
        )
        with pytest.raises(AuditWriteError):
            await logger.log_event(event)
```

---

## `tests/security/test_pii_leakage.py`

Assertion tests confirming that PII does not appear in outputs after masking.
Uses synthetic data only.

```python
"""
PII leakage prevention tests.

Verifies that after applying pii_filter, no PII from the input
appears in the output. Uses only clearly synthetic, fake data.
Synthetic data standards used in this file:
  Email:  fake@example.com / test@test.org
  CPF:    000.000.000-00  (all-zero — not a valid Brazilian CPF)
  IP:     192.0.2.x       (TEST-NET per RFC 5737)
  Phone:  +00 00 00000-0000
"""
import pytest
from src.guardrails.pii_filter import mask_text, mask_dict, PIIFilter, PIILevel


SYNTHETIC_EMAIL = "fake@example.com"
SYNTHETIC_CPF = "000.000.000-00"
SYNTHETIC_IP = "192.0.2.1"
SYNTHETIC_PHONE = "+00 00 00000-0000"


class TestNoLeakageInMaskedText:

    def test_email_not_in_output(self):
        output = mask_text(f"User: {SYNTHETIC_EMAIL}")
        assert SYNTHETIC_EMAIL not in output

    def test_cpf_not_in_output(self):
        output = mask_text(f"Document: {SYNTHETIC_CPF}")
        assert SYNTHETIC_CPF not in output

    def test_ip_not_in_output(self):
        output = mask_text(f"Origin: {SYNTHETIC_IP}")
        assert SYNTHETIC_IP not in output

    def test_phone_not_in_output(self):
        output = mask_text(f"Contact: {SYNTHETIC_PHONE}")
        assert SYNTHETIC_PHONE not in output

    def test_multiple_pii_fields_all_masked(self):
        text = (
            f"Email: {SYNTHETIC_EMAIL}, "
            f"CPF: {SYNTHETIC_CPF}, "
            f"IP: {SYNTHETIC_IP}"
        )
        output = mask_text(text)
        assert SYNTHETIC_EMAIL not in output
        assert SYNTHETIC_CPF not in output
        assert SYNTHETIC_IP not in output


class TestNoLeakageInMaskedDict:

    def test_nested_dict_no_leakage(self):
        data = {
            "profile": {
                "email": SYNTHETIC_EMAIL,
                "ip": SYNTHETIC_IP,
            },
            "role": "analyst",   # L4 — should remain
        }
        result = mask_dict(data)
        assert SYNTHETIC_EMAIL not in str(result)
        assert SYNTHETIC_IP not in str(result)
        assert result["role"] == "analyst"

    def test_list_values_masked(self):
        data = {"emails": [SYNTHETIC_EMAIL, "other@example.org"]}
        result = mask_dict(data)
        assert SYNTHETIC_EMAIL not in str(result)


class TestL1CriticalNeverInLogs:
    """L1 data must be masked even at the most permissive masking level."""

    def test_cpf_masked_at_all_levels(self):
        pii = PIIFilter()
        for level in PIILevel:
            output = pii.mask_text(f"ID: {SYNTHETIC_CPF}", min_level=level)
            if level == PIILevel.L1_CRITICAL or level.value <= PIILevel.L1_CRITICAL.value:
                # L1 is always masked regardless of min_level
                assert SYNTHETIC_CPF not in output
```

---

## `tests/chaos/runbooks/game-day-playbook.md`

Game day playbook for chaos engineering exercises. Include:

- **Purpose:** validate system resilience through controlled failure injection in staging
- **Schedule:** weekly (automated via `.github/workflows/chaos-schedule.yml`)
- **Participants:** SRE Lead, On-call engineer, optional: Tech Lead
- **Pre-game-day checklist:** staging environment healthy, Golden Signals baseline
  captured, rollback procedure reviewed, HITL gateway confirmed operational
- **Experiment catalogue:**

| Experiment        | File                                             | Target         | Expected behaviour                                                          |
| ----------------- | ------------------------------------------------ | -------------- | --------------------------------------------------------------------------- |
| Kill agent pod    | `tests/chaos/experiments/kill-agent.yaml`        | Agent service  | HITL queue drains; pending approvals preserved; service recovers within RTO |
| Network partition | `tests/chaos/experiments/network-partition.yaml` | Agent ↔ Broker | Circuit breaker activates; DLQ receives undelivered events; no data loss    |
| Broker outage     | `tests/chaos/experiments/broker-outage.yaml`     | Kafka          | Producers buffer; consumers pause gracefully; replay on recovery            |

- **Execution steps per experiment:**
  1. Confirm staging is healthy (Golden Signals green)
  2. Start experiment via Litmus / Chaos Toolkit
  3. Monitor Golden Signals for deviation
  4. Record: time to detect, time to recover, any data loss
  5. Stop experiment; verify full recovery
  6. Document findings in `docs/postmortems/`

- **Pass criteria:** RTO met, no data loss, HITL approvals preserved,
  audit log intact, automated alerts fired within 2 minutes of fault injection
- **Fail criteria:** RTO exceeded, data loss detected, audit log corrupted,
  automated alerts did not fire

- **Post-game-day actions:** update runbooks with findings, file tickets for
  any resilience gaps discovered, schedule follow-up if pass criteria not met

---

### Validation

After creating all files, confirm:

- `src/guardrails/pii_filter.py` implements all 8 detection pattern categories
- `src/guardrails/prompt_injection_guard.py` has 6 check methods and never
  logs the full rejected input (only hash + reason)
- All test files use only synthetic placeholder data (no real PII, no real exploits)
- `tests/security/test_owasp_llm_top10.py` covers LLM01, LLM06, LLM08, LLM09
- `tests/security/test_pii_leakage.py` defines `SYNTHETIC_*` constants at the top
- `tests/chaos/runbooks/game-day-playbook.md` contains the pass/fail criteria section
