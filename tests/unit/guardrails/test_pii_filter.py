"""Unit tests for src/guardrails/pii_filter.py.

Spec: specs/ai/guardrails.md (Layer 1 — PII Filter)
ADR:  ADR-0012 (PII Masking Strategy)

All test inputs use clearly synthetic, obviously fake data.
No real personal data appears in this file.
"""

import pytest

from src.guardrails.pii_filter import PIIFilter, PIILevel, mask_dict, mask_ip, mask_text


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

    def test_empty_string_returns_empty(self):
        assert mask_text("") == ""

    def test_masks_email_subdomain(self):
        result = mask_text("user@mail.example.co.uk")
        assert "user@mail.example.co.uk" not in result
        assert "[EMAIL]" in result


class TestPIIFilterCPF:
    def test_masks_cpf_formatted(self):
        # All-zero CPF — clearly synthetic, not a real Brazilian CPF
        result = mask_text("CPF: 000.000.000-00")
        assert "[CPF]" in result
        assert "000.000.000-00" not in result

    def test_masks_cpf_unformatted(self):
        result = mask_text("cpf 00000000000")
        assert "[CPF]" in result

    def test_masks_cpf_with_dashes(self):
        result = mask_text("ID: 000-000-000-00")
        assert "000-000-000-00" not in result


class TestPIIFilterIP:
    def test_masks_ipv4_test_net(self):
        # 192.0.2.x is TEST-NET per RFC 5737 — safe synthetic value
        result = mask_text("Request from 192.0.2.1")
        assert "[IP]" in result
        assert "192.0.2.1" not in result

    def test_masks_ipv4_loopback_shape(self):
        result = mask_text("addr=127.0.0.1 port=8080")
        assert "127.0.0.1" not in result

    def test_preserves_non_ip_numbers(self):
        result = mask_text("version 3.14")
        assert "3.14" in result  # short decimal — not matched as IP


class TestPIIFilterPhone:
    def test_masks_e164_format(self):
        result = mask_text("Call +00 00 00000-0000")
        assert "+00 00 00000-0000" not in result
        assert "[PHONE]" in result


class TestPIIFilterToken:
    def test_masks_jwt_shaped_token(self):
        # Synthetic token with JWT structural shape (three base64url segments)
        synthetic_jwt = "aaaaaaaaaa.bbbbbbbbbb.cccccccccc"
        result = mask_text(f"Authorization: Bearer {synthetic_jwt}")
        assert synthetic_jwt not in result

    def test_masks_uuid(self):
        synthetic_uuid = "00000000-0000-0000-0000-000000000000"
        result = mask_text(f"id={synthetic_uuid}", min_level=PIILevel.L3_INTERNAL)
        assert synthetic_uuid not in result
        assert "[UUID]" in result


class TestMaskDict:
    def test_masks_nested_dict(self):
        data = {"user": {"email": "fake@example.com", "role": "admin"}}
        result = mask_dict(data)
        assert result["user"]["email"] == "[EMAIL]"
        assert result["user"]["role"] == "admin"

    def test_level_filter_passes_l4(self):
        data = {"org": "Example Corp"}  # L4 public — should not be masked
        result = mask_dict(data, min_level=PIILevel.L2_SENSITIVE)
        assert result["org"] == "Example Corp"

    def test_masks_list_values(self):
        data = {"emails": ["a@example.com", "b@example.org"]}
        result = mask_dict(data)
        assert "a@example.com" not in str(result)
        assert "b@example.org" not in str(result)

    def test_preserves_non_string_values(self):
        data = {"count": 42, "active": True, "score": 0.9}
        result = mask_dict(data)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["score"] == 0.9

    def test_empty_dict_returns_empty(self):
        assert mask_dict({}) == {}

    def test_deeply_nested_dict(self):
        data = {"a": {"b": {"c": {"email": "test@example.com"}}}}
        result = mask_dict(data)
        assert result["a"]["b"]["c"]["email"] == "[EMAIL]"

    def test_very_long_string_input(self):
        long_text = "x" * 10_000
        result = mask_text(long_text)
        assert result == long_text  # no PII — unchanged


class TestMaskIp:
    """Granular sub-field IP masking (#232, SPEC-LGS-001 FR-02, ADR-0012).

    Uses RFC 5737 (IPv4 TEST-NET) and RFC 3849 (IPv6 documentation) ranges only.
    """

    def test_ipv4_last_octet_zeroed(self):
        assert mask_ip("203.0.113.42") == "203.0.113.0"

    def test_ipv6_last_80_bits_zeroed_keeps_48_prefix(self):
        assert mask_ip("2001:db8:dead:beef:1:2:3:4") == "2001:db8:dead::"

    def test_compressed_ipv6_normalised_then_masked(self):
        masked = mask_ip("2001:db8::dead:beef")
        assert "dead:beef" not in masked
        assert masked.startswith("2001:db8")

    def test_masking_is_idempotent(self):
        once = mask_ip("203.0.113.42")
        assert mask_ip(once) == once

    @pytest.mark.parametrize(
        "bad",
        [None, "", "   ", "not-an-ip", "999.999.1.1", "example.com", "203.0.113.42.7"],
    )
    def test_malformed_returns_invalid_sentinel(self, bad):
        assert mask_ip(bad) == PIIFilter.INVALID_IP

    def test_raw_value_never_echoed_on_malformed(self):
        # A bad value must not leak back to the caller.
        assert "secret-host" not in mask_ip("secret-host.internal")

    def test_static_method_matches_module_function(self):
        assert PIIFilter.mask_ip("203.0.113.42") == mask_ip("203.0.113.42")

    def test_free_text_masking_still_fully_tokenises_ip(self):
        # mask_ip is additive; the default free-text path is unchanged (not weakened).
        assert mask_text("client 203.0.113.42 connected") == "client [IP] connected"
