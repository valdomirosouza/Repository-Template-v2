"""Unit tests for src/shared/db_encryption.py.

Spec: specs/privacy/db-encryption-at-rest.md §7 (Acceptance Criteria)
ADR:  ADR-0018 (Database Encryption at Rest)
"""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from src.shared.db_encryption import _KEY_BYTES, _PREFIX, EncryptedField

# A valid 32-byte test key (never use in production).
_TEST_KEY = "a" * 64  # 64 hex chars = 32 bytes


class TestEncryptedFieldInit:
    def test_valid_key_accepted(self) -> None:
        EncryptedField(_TEST_KEY)

    def test_key_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="DB_ENCRYPTION_KEY must be"):
            EncryptedField("ab" * 16)  # 16 bytes, not 32

    def test_key_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="DB_ENCRYPTION_KEY must be"):
            EncryptedField("ab" * 33)  # 33 bytes

    def test_non_hex_key_raises(self) -> None:
        with pytest.raises(ValueError):
            EncryptedField("z" * 64)  # invalid hex chars


class TestEncryptDecrypt:
    def setup_method(self) -> None:
        self.ef = EncryptedField(_TEST_KEY)

    def test_roundtrip_ascii(self) -> None:
        plain = "hello world"
        assert self.ef.decrypt(self.ef.encrypt(plain)) == plain

    def test_roundtrip_unicode(self) -> None:
        plain = "João da Silva — CPF [MASKED]"
        assert self.ef.decrypt(self.ef.encrypt(plain)) == plain

    def test_roundtrip_empty_string(self) -> None:
        assert self.ef.decrypt(self.ef.encrypt("")) == ""

    def test_roundtrip_long_string(self) -> None:
        plain = "x" * 10_000
        assert self.ef.decrypt(self.ef.encrypt(plain)) == plain

    def test_encrypt_produces_prefix(self) -> None:
        assert self.ef.encrypt("data").startswith(_PREFIX)

    def test_nonce_uniqueness(self) -> None:
        plain = "same input"
        ct1 = self.ef.encrypt(plain)
        ct2 = self.ef.encrypt(plain)
        assert ct1 != ct2, "Two encryptions of the same plaintext must differ (random nonce)"

    def test_decrypt_passthrough_for_plaintext(self) -> None:
        plain = "not yet encrypted"
        assert self.ef.decrypt(plain) == plain

    def test_decrypt_passthrough_empty(self) -> None:
        assert self.ef.decrypt("") == ""

    def test_is_encrypted_true(self) -> None:
        assert EncryptedField.is_encrypted(self.ef.encrypt("x"))

    def test_is_encrypted_false_for_plaintext(self) -> None:
        assert not EncryptedField.is_encrypted("plaintext")

    def test_is_encrypted_false_for_empty(self) -> None:
        assert not EncryptedField.is_encrypted("")


class TestTamperDetection:
    def setup_method(self) -> None:
        self.ef = EncryptedField(_TEST_KEY)

    def test_corrupted_ciphertext_raises_invalid_tag(self) -> None:
        ct = self.ef.encrypt("sensitive data")
        # Flip a byte in the base64 payload to corrupt the authentication tag.
        payload = ct[len(_PREFIX) :]
        corrupted_payload = payload[:-4] + ("A" if payload[-4] != "A" else "B") + payload[-3:]
        corrupted = _PREFIX + corrupted_payload
        with pytest.raises((InvalidTag, Exception)):
            self.ef.decrypt(corrupted)

    def test_truncated_ciphertext_raises(self) -> None:
        ct = self.ef.encrypt("data")
        truncated = ct[: len(_PREFIX) + 5]
        with pytest.raises(Exception):
            self.ef.decrypt(truncated)


class TestCrossKeyIsolation:
    def test_different_key_cannot_decrypt(self) -> None:
        ef1 = EncryptedField(_TEST_KEY)
        ef2 = EncryptedField("b" * 64)
        ct = ef1.encrypt("secret")
        with pytest.raises(Exception):
            ef2.decrypt(ct)


class TestKeySize:
    def test_key_bytes_constant_is_32(self) -> None:
        assert _KEY_BYTES == 32

    def test_prefix_constant(self) -> None:
        assert _PREFIX == "enc:v1:"
