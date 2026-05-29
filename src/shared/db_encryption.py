"""Application-layer AES-256-GCM encryption for database columns.

Spec: specs/privacy/db-encryption-at-rest.md
ADR:  ADR-0018 (Database Encryption at Rest)

Wire format: enc:v1:<base64(nonce[12] || ciphertext_with_tag)>

The 'v1' version prefix enables zero-downtime key rotation — future keys use
'v2', 'v3', etc. The decrypt() passthrough path lets plaintext rows coexist
with encrypted rows during a rolling migration window.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX = "enc:v1:"
_NONCE_BYTES = 12  # 96-bit nonce — AESGCM recommended size
_KEY_BYTES = 32  # 256-bit key


class EncryptedField:
    """AES-256-GCM field-level encryption for L1/L2 PII columns.

    Each encrypt() call generates a fresh random nonce, so repeated encryption
    of the same plaintext yields different ciphertexts (IND-CPA secure).
    The authentication tag (16 bytes) is appended by AESGCM.encrypt() and
    verified transparently by AESGCM.decrypt() — InvalidTag is raised on tamper.
    """

    def __init__(self, key_hex: str) -> None:
        raw = bytes.fromhex(key_hex)
        if len(raw) != _KEY_BYTES:
            raise ValueError(
                f"DB_ENCRYPTION_KEY must be {_KEY_BYTES * 2} hex characters "
                f"({_KEY_BYTES} bytes for AES-256). "
                'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        self._aesgcm = AESGCM(raw)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext; returns enc:v1:<base64> string."""
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return _PREFIX + base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, value: str) -> str:
        """Decrypt an enc:v1:... value.

        If value does not start with the prefix it is returned as-is — this
        passthrough path allows rows written before encryption was enabled to
        be read without a blocking schema migration.
        """
        if not value.startswith(_PREFIX):
            return value
        data = base64.b64decode(value[len(_PREFIX) :])
        nonce, ciphertext = data[:_NONCE_BYTES], data[_NONCE_BYTES:]
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    @staticmethod
    def is_encrypted(value: str) -> bool:
        return value.startswith(_PREFIX)
