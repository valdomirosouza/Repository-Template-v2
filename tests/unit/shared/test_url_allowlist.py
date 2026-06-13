"""Unit tests for the outbound URL allow-list / SSRF guard (OWASP A10).

Spec: specs/security/threat-model.md (A10 — SSRF).
"""

from __future__ import annotations

import pytest

from src.shared.url_allowlist import (
    OutboundURLNotAllowed,
    is_outbound_url_allowed,
    validate_outbound_url,
)

pytestmark = pytest.mark.unit


class TestSchemes:
    @pytest.mark.parametrize("url", ["http://example.com", "https://example.com/path"])
    def test_http_https_allowed(self, url: str) -> None:
        assert validate_outbound_url(url, allowlist=[]) == url

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "gopher://example.com",
            "ftp://example.com",
            "data:text/html,<b>",
        ],
    )
    def test_dangerous_schemes_blocked(self, url: str) -> None:
        with pytest.raises(OutboundURLNotAllowed):
            validate_outbound_url(url, allowlist=[])


class TestMetadataEndpoints:
    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://100.100.100.200/",
            "http://[fe80::1]/",
        ],
    )
    def test_metadata_and_link_local_blocked_even_without_allowlist(self, url: str) -> None:
        # Empty allow-list is permissive, but metadata/link-local is ALWAYS blocked.
        with pytest.raises(OutboundURLNotAllowed):
            validate_outbound_url(url, allowlist=[])


class TestAllowlistEnforcement:
    def test_host_must_match_when_allowlist_set(self) -> None:
        with pytest.raises(OutboundURLNotAllowed):
            validate_outbound_url("https://evil.example", allowlist=["api.anthropic.com"])

    def test_exact_host_match_passes(self) -> None:
        url = "https://api.anthropic.com/v1/messages"
        assert validate_outbound_url(url, allowlist=["api.anthropic.com"]) == url

    def test_dot_suffix_match_passes(self) -> None:
        url = "https://prom.internal.example.com/api/v1/query"
        assert validate_outbound_url(url, allowlist=[".internal.example.com"])

    def test_wildcard_prefix_tolerated(self) -> None:
        assert is_outbound_url_allowed("https://a.example.com", allowlist=["*.example.com"])

    def test_empty_allowlist_permits_normal_host(self) -> None:
        # Internal/private hosts are NOT blocked by default (legitimate internal services).
        assert is_outbound_url_allowed("http://localhost:9090/api/v1/query", allowlist=[])
        assert is_outbound_url_allowed("http://10.0.0.5:9090", allowlist=[])


class TestSettingsBackedDefault:
    def test_uses_settings_allowlist_when_none_passed(self) -> None:
        # Default settings.outbound_url_allowlist is empty → permissive (metadata still blocked).
        assert validate_outbound_url("https://api.anthropic.com/v1/messages")
        with pytest.raises(OutboundURLNotAllowed):
            validate_outbound_url("http://169.254.169.254/latest/meta-data/")


class TestMalformed:
    def test_no_host_rejected(self) -> None:
        assert not is_outbound_url_allowed("https:///nohost", allowlist=[])

    def test_non_raising_form(self) -> None:
        assert is_outbound_url_allowed("https://ok.example", allowlist=["ok.example"])
        assert not is_outbound_url_allowed("http://169.254.169.254", allowlist=[])
