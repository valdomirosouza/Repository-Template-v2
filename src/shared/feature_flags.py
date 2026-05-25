"""Feature flag client — thin wrapper around the OpenFeature SDK.

Falls back to settings.autonomous_mode_enabled when the SDK is unavailable
(local dev without flagd, or SDK not yet configured).

Spec: specs/system/architecture.md
ADR:  ADR-0015 (Feature Flag Strategy)
"""

from __future__ import annotations

from src.shared.config import settings


def is_autonomous_mode_enabled() -> bool:
    """Return True if the 'autonomous-mode' feature flag is enabled.

    Evaluation order:
    1. OpenFeature SDK (flagd provider in production, InMemoryProvider in tests).
    2. settings.autonomous_mode_enabled fallback (if SDK raises or is not configured).
    """
    try:
        from openfeature import api  # optional dep — openfeature-sdk

        client = api.get_client()
        return client.get_boolean_value("autonomous-mode", settings.autonomous_mode_enabled)
    except Exception:
        return settings.autonomous_mode_enabled
