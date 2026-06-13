"""Outbound URL allow-list / SSRF guard (OWASP A10).

Validate a **server-side outbound request URL** before it is fetched. Use this at every HTTP-client
boundary that could receive a user- or LLM-influenced URL (CLAUDE.md §3.2 A10: "outbound allow-list,
no user-controlled server-side URLs").

Policy:

* **Always** reject non-``http(s)`` schemes (``file:``, ``gopher:``, ``ftp:`` … are SSRF vectors).
* **Always** reject cloud-metadata / link-local endpoints (AWS/GCP/Alibaba IMDS, ``169.254.0.0/16``,
  ``fe80::/10``) — these are never a legitimate outbound target and are the SSRF crown jewels.
* When ``settings.outbound_url_allowlist`` is non-empty, the host must match (exact or dot-suffix).
* Loopback / private hosts are **not** blocked by default — internal services (Prometheus, internal
  APIs) legitimately use them. Adopters tighten by populating the allow-list.

Spec: ``specs/security/threat-model.md`` (A10 — SSRF).
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Cloud-metadata / link-local hostnames that are never a legitimate outbound target.
_METADATA_HOSTS = frozenset(
    {
        "169.254.169.254",  # AWS / Azure IMDS
        "metadata.google.internal",  # GCP
        "metadata.goog",  # GCP
        "100.100.100.200",  # Alibaba Cloud
    }
)


class OutboundURLNotAllowed(ValueError):
    """Raised when a server-side outbound URL is blocked by the SSRF allow-list."""


def _host_is_metadata(host: str) -> bool:
    h = host.strip("[]").lower()
    if h in _METADATA_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    # Link-local covers the 169.254.0.0/16 IMDS range and IPv6 fe80::/10.
    return ip.is_link_local


def _host_matches(host: str, allowlist: Iterable[str]) -> bool:
    host = host.lower()
    for entry in allowlist:
        e = entry.strip().lower().lstrip("*")  # tolerate "*.example.com" → ".example.com"
        if not e:
            continue
        if e.startswith("."):
            if host == e[1:] or host.endswith(e):
                return True
        elif host == e:
            return True
    return False


def _configured_allowlist() -> list[str]:
    # Imported lazily to avoid a circular import at module load (config imports widely).
    from src.shared.config import settings

    return list(settings.outbound_url_allowlist)


def validate_outbound_url(url: str, allowlist: Iterable[str] | None = None) -> str:
    """Return ``url`` if it is a permitted outbound target, else raise ``OutboundURLNotAllowed``.

    ``allowlist`` overrides ``settings.outbound_url_allowlist`` (for tests / per-call policy).
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise OutboundURLNotAllowed(f"scheme '{parts.scheme}' not allowed (http/https only)")
    host = parts.hostname
    if not host:
        raise OutboundURLNotAllowed("URL has no host")
    if _host_is_metadata(host):
        raise OutboundURLNotAllowed(f"host '{host}' is a blocked metadata/link-local endpoint")
    allow = list(allowlist) if allowlist is not None else _configured_allowlist()
    if allow and not _host_matches(host, allow):
        raise OutboundURLNotAllowed(f"host '{host}' is not in the outbound allow-list")
    return url


def is_outbound_url_allowed(url: str, allowlist: Iterable[str] | None = None) -> bool:
    """Non-raising form of :func:`validate_outbound_url`."""
    try:
        validate_outbound_url(url, allowlist=allowlist)
    except OutboundURLNotAllowed:
        return False
    return True
