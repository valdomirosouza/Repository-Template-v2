"""Unit tests for ActionSchemaValidator — structural payload validation.

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV3)
ADR:  ADR-0050
Issue: #35
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.agents.action_schema_validator import (
    ActionSchemaError,
    ActionSchemaValidator,
    _matches_type,
)

# ── _matches_type helper ──────────────────────────────────────────────────────


class TestMatchesType:
    def test_string_type(self) -> None:
        assert _matches_type("hello", "string") is True
        assert _matches_type(42, "string") is False

    def test_integer_type(self) -> None:
        assert _matches_type(42, "integer") is True
        assert _matches_type(3.14, "integer") is False

    def test_bool_is_not_integer(self) -> None:
        # bool is a subclass of int in Python — must be explicitly excluded
        assert _matches_type(True, "integer") is False

    def test_number_accepts_int_and_float(self) -> None:
        assert _matches_type(42, "number") is True
        assert _matches_type(3.14, "number") is True

    def test_boolean_type(self) -> None:
        assert _matches_type(True, "boolean") is True
        assert _matches_type(False, "boolean") is True
        assert _matches_type(1, "boolean") is False

    def test_object_type(self) -> None:
        assert _matches_type({}, "object") is True
        assert _matches_type([], "object") is False

    def test_array_type(self) -> None:
        assert _matches_type([], "array") is True
        assert _matches_type({}, "array") is False

    def test_null_type(self) -> None:
        assert _matches_type(None, "null") is True
        assert _matches_type("", "null") is False

    def test_unknown_type_passes(self) -> None:
        assert _matches_type("anything", "custom_type") is True


# ── Validation ────────────────────────────────────────────────────────────────


class TestValidate:
    def _make_validator(self) -> ActionSchemaValidator:
        return ActionSchemaValidator.from_dict(
            {
                "write-db-record": {
                    "required": ["table", "data"],
                    "properties": {
                        "table": {"type": "string"},
                        "data": {"type": "object"},
                        "operation": {"type": "string"},
                    },
                    "max_payload_bytes": 1024,
                }
            }
        )

    def test_valid_payload_passes(self) -> None:
        v = self._make_validator()
        result = v.validate("write-db-record", {"table": "users", "data": {"name": "Alice"}})
        assert result.valid is True
        assert result.errors == []

    def test_missing_required_field_fails(self) -> None:
        v = self._make_validator()
        result = v.validate("write-db-record", {"table": "users"})  # missing 'data'
        assert result.valid is False
        assert any("data" in e for e in result.errors)

    def test_wrong_field_type_fails(self) -> None:
        v = self._make_validator()
        result = v.validate("write-db-record", {"table": 42, "data": {}})  # table should be str
        assert result.valid is False
        assert any("table" in e for e in result.errors)

    def test_oversized_payload_fails(self) -> None:
        v = self._make_validator()
        result = v.validate(
            "write-db-record",
            {"table": "users", "data": {"padding": "X" * 2000}},
        )
        assert result.valid is False
        assert any("exceeds limit" in e for e in result.errors)

    def test_unknown_action_type_is_allowed(self) -> None:
        v = self._make_validator()
        result = v.validate("unknown-action", {"anything": "goes"})
        assert result.valid is True

    def test_optional_field_type_checked_when_present(self) -> None:
        v = self._make_validator()
        result = v.validate(
            "write-db-record",
            {"table": "users", "data": {}, "operation": 999},  # operation should be str
        )
        assert result.valid is False
        assert any("operation" in e for e in result.errors)

    def test_optional_field_absent_is_fine(self) -> None:
        v = self._make_validator()
        result = v.validate(
            "write-db-record",
            {"table": "users", "data": {}},  # no operation — that's fine
        )
        assert result.valid is True

    def test_multiple_errors_reported(self) -> None:
        v = self._make_validator()
        result = v.validate("write-db-record", {})  # both required fields missing
        assert result.valid is False
        assert len(result.errors) >= 2

    def test_underscore_name_normalized(self) -> None:
        v = self._make_validator()
        result = v.validate("write_db_record", {"table": "users", "data": {}})
        assert result.valid is True


# ── validate_or_raise ─────────────────────────────────────────────────────────


class TestValidateOrRaise:
    def test_raises_on_invalid_payload(self) -> None:
        v = ActionSchemaValidator.from_dict(
            {"write-db-record": {"required": ["table", "data"], "properties": {}}}
        )
        with pytest.raises(ActionSchemaError, match="schema validation"):
            v.validate_or_raise("write-db-record", {"table": "users"})  # missing data

    def test_no_raise_on_valid_payload(self) -> None:
        v = ActionSchemaValidator.from_dict(
            {"write-db-record": {"required": ["table"], "properties": {}}}
        )
        v.validate_or_raise("write-db-record", {"table": "users"})  # must not raise

    def test_no_raise_for_unknown_action_type(self) -> None:
        v = ActionSchemaValidator.from_dict({})
        v.validate_or_raise("ghost-action", {"anything": "goes"})  # unknown → allowed


# ── from_directory ────────────────────────────────────────────────────────────


class TestFromDirectory:
    def test_loads_schemas_from_directory(self, tmp_path: Path) -> None:
        schema_content = textwrap.dedent("""\
            required:
              - table
              - data
            properties:
              table:
                type: string
              data:
                type: object
            max_payload_bytes: 5000
        """)
        schema_file = tmp_path / "write-db-record.schema.yaml"
        schema_file.write_text(schema_content)
        v = ActionSchemaValidator.from_directory(tmp_path)
        assert "write-db-record" in v.registered_action_types

    def test_missing_directory_gives_empty_validator(self, tmp_path: Path) -> None:
        v = ActionSchemaValidator.from_directory(tmp_path / "nonexistent")
        assert v.registered_action_types == []
        result = v.validate("any-action", {"x": 1})
        assert result.valid is True

    def test_multiple_schema_files_loaded(self, tmp_path: Path) -> None:
        for name in ["write-db-record", "send-email", "execute-code"]:
            (tmp_path / f"{name}.schema.yaml").write_text("required: []\nproperties: {}")
        v = ActionSchemaValidator.from_directory(tmp_path)
        assert len(v.registered_action_types) == 3
