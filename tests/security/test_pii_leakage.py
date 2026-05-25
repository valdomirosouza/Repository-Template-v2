"""PII leakage prevention tests.

Spec: specs/ai/guardrails.md (Layer 1), specs/privacy/pii-inventory.md
ADR:  ADR-0012 (PII Masking Strategy)

Verifies that after applying pii_filter, no PII from the input appears
in the output. Uses only clearly synthetic, fake data.

Synthetic data standards used in this file:
  Email:  fake@example.com / test@example.org
  CPF:    000.000.000-00   (all-zero — not a valid Brazilian CPF)
  IP:     192.0.2.x        (TEST-NET per RFC 5737)
  Phone:  +00 00 00000-0000
"""

from src.guardrails.pii_filter import PIIFilter, PIILevel, mask_dict, mask_text

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
        text = f"Email: {SYNTHETIC_EMAIL}, CPF: {SYNTHETIC_CPF}, IP: {SYNTHETIC_IP}"
        output = mask_text(text)
        assert SYNTHETIC_EMAIL not in output
        assert SYNTHETIC_CPF not in output
        assert SYNTHETIC_IP not in output

    def test_non_pii_text_preserved(self):
        text = "The service is healthy and running at 100% capacity."
        output = mask_text(text)
        assert output == text

    def test_replacement_tokens_present_after_masking(self):
        output = mask_text(f"Email: {SYNTHETIC_EMAIL}")
        assert "[EMAIL]" in output

    def test_empty_string_no_leakage(self):
        assert mask_text("") == ""


class TestNoLeakageInMaskedDict:
    def test_nested_dict_no_leakage(self):
        data = {
            "profile": {
                "email": SYNTHETIC_EMAIL,
                "ip": SYNTHETIC_IP,
            },
            "role": "analyst",
        }
        result = mask_dict(data)
        assert SYNTHETIC_EMAIL not in str(result)
        assert SYNTHETIC_IP not in str(result)
        assert result["role"] == "analyst"

    def test_list_values_masked(self):
        data = {"emails": [SYNTHETIC_EMAIL, "other@example.org"]}
        result = mask_dict(data)
        assert SYNTHETIC_EMAIL not in str(result)
        assert "other@example.org" not in str(result)

    def test_non_pii_values_preserved(self):
        data = {"count": 42, "status": "active", "level": "standard"}
        result = mask_dict(data)
        assert result["count"] == 42
        assert result["status"] == "active"

    def test_deeply_nested_no_leakage(self):
        data = {"a": {"b": {"c": {"email": SYNTHETIC_EMAIL}}}}
        result = mask_dict(data)
        assert SYNTHETIC_EMAIL not in str(result)


class TestL1CriticalNeverInOutput:
    """L1 data must be masked even at the most permissive masking level."""

    def test_cpf_always_masked(self):
        pii = PIIFilter()
        # L1 must be masked when min_level is L1 or more restrictive
        output = pii.mask_text(f"ID: {SYNTHETIC_CPF}", min_level=PIILevel.L1_CRITICAL)
        assert SYNTHETIC_CPF not in output

    def test_cpf_masked_at_l2_min_level(self):
        pii = PIIFilter()
        # L1 fields should also be masked when min_level=L2
        output = pii.mask_text(f"ID: {SYNTHETIC_CPF}", min_level=PIILevel.L2_SENSITIVE)
        assert SYNTHETIC_CPF not in output

    def test_email_masked_at_l2_min_level(self):
        pii = PIIFilter()
        output = pii.mask_text(f"Email: {SYNTHETIC_EMAIL}", min_level=PIILevel.L2_SENSITIVE)
        assert SYNTHETIC_EMAIL not in output


class TestMaskingIsIdempotent:
    """Masking an already-masked output must not double-mask or break."""

    def test_masking_twice_is_safe(self):
        once = mask_text(f"Email: {SYNTHETIC_EMAIL}")
        twice = mask_text(once)
        assert SYNTHETIC_EMAIL not in twice
        assert twice.count("[EMAIL]") >= 1
