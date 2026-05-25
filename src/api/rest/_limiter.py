"""Shared slowapi Limiter instance.

Spec: specs/api/rest-api-design.md (Rate Limiting)
ADR:  ADR-0002 (Technology Stack Selection)

Import this module (not slowapi directly) to ensure a single Limiter instance
is shared between main.py (middleware registration) and routers (decorators).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
