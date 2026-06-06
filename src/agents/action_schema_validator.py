"""Structural schema validator for agent action payloads.

Validates action payloads against declared JSON-like schemas BEFORE they enter the
HITL store or tool execution layer. Catches hallucinated or injected payloads that do
not conform to the expected structure for a given action_type.

Defense-in-depth: schema validation runs before HITL gating — a malformed payload
never reaches the HITL queue or tool execution path.

Schema files live in infrastructure/agent-tools/action-schemas/<action_type>.schema.yaml
(kebab-case, e.g. write-db-record.schema.yaml).

Spec: secure-by-design-agentic-ai-compliance-v2.md §Pillar 4 (CV3)
ADR:  ADR-0050
Issue: #35
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.observability.logger import get_logger

logger = get_logger("action_schema_validator")

# Hard cap: payloads larger than this are rejected regardless of schema (LLM hallucination guard).
_MAX_PAYLOAD_BYTES = 10_240  # 10 KB


class ActionSchemaError(Exception):
    """Raised when an action payload fails schema validation."""


@dataclass
class SchemaDefinition:
    """Parsed schema for a single action_type."""

    action_type: str
    required: list[str] = field(default_factory=list)
    properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    max_payload_bytes: int = _MAX_PAYLOAD_BYTES


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


class ActionSchemaValidator:
    """Validates action payloads against loaded schema definitions.

    Schemas are loaded from YAML files on construction. Unknown action types
    (no schema registered) are allowed through with a warning — the validator
    only blocks known-bad payloads, not unknown actions.

    Usage::

        validator = ActionSchemaValidator.from_directory(
            Path("infrastructure/agent-tools/action-schemas")
        )
        validator.validate_or_raise("write-db-record", {"table": "users", "data": {}})
    """

    def __init__(self, schemas: dict[str, SchemaDefinition]) -> None:
        self._schemas = schemas

    # ── Factories ─────────────────────────────────────────────────────────────

    @classmethod
    def from_directory(cls, directory: Path) -> ActionSchemaValidator:
        """Load all *.schema.yaml files from a directory."""
        schemas: dict[str, SchemaDefinition] = {}
        if not directory.exists():
            logger.warning("action_schema_validator.no_schema_dir", path=str(directory))
            return cls(schemas)

        for schema_file in sorted(directory.glob("*.schema.yaml")):
            action_type = schema_file.stem.replace(".schema", "")
            try:
                raw = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
                schemas[action_type] = SchemaDefinition(
                    action_type=action_type,
                    required=raw.get("required", []),
                    properties=raw.get("properties", {}),
                    max_payload_bytes=raw.get("max_payload_bytes", _MAX_PAYLOAD_BYTES),
                )
                logger.info(
                    "action_schema_validator.schema_loaded",
                    action_type=action_type,
                    required_fields=len(schemas[action_type].required),
                )
            except Exception as exc:
                logger.error(
                    "action_schema_validator.schema_load_error",
                    path=str(schema_file),
                    error=str(exc),
                )
        return cls(schemas)

    @classmethod
    def from_dict(cls, schemas_dict: dict[str, dict[str, Any]]) -> ActionSchemaValidator:
        """Build from inline dict (for tests and programmatic construction)."""
        schemas = {
            k: SchemaDefinition(
                action_type=k,
                required=v.get("required", []),
                properties=v.get("properties", {}),
                max_payload_bytes=v.get("max_payload_bytes", _MAX_PAYLOAD_BYTES),
            )
            for k, v in schemas_dict.items()
        }
        return cls(schemas)

    # ── Validation API ────────────────────────────────────────────────────────

    def validate(self, action_type: str, payload: dict[str, Any]) -> ValidationResult:
        """Validate a payload against the schema for the given action_type.

        Returns a ValidationResult. Does not raise.
        """
        # Normalize: underscore → hyphen for schema lookup
        normalized = action_type.replace("_", "-")
        schema = self._schemas.get(normalized)

        if schema is None:
            # No schema registered for this action_type — allow through with a warning.
            logger.debug(
                "action_schema_validator.no_schema",
                action_type=action_type,
            )
            return ValidationResult(valid=True)

        errors: list[str] = []

        # Check 1: payload size
        try:
            payload_bytes = len(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            errors.append(f"Payload is not JSON-serializable: {exc}")
            return ValidationResult(valid=False, errors=errors)

        if payload_bytes > schema.max_payload_bytes:
            errors.append(
                f"Payload size {payload_bytes} bytes exceeds limit of "
                f"{schema.max_payload_bytes} bytes"
            )

        # Check 2: required fields
        for field_name in schema.required:
            if field_name not in payload:
                errors.append(f"Missing required field: '{field_name}'")

        # Check 3: type validation for declared properties
        for field_name, field_schema in schema.properties.items():
            if field_name not in payload:
                continue  # presence is enforced by required check above
            expected_type = field_schema.get("type")
            if expected_type:
                actual = payload[field_name]
                if not _matches_type(actual, expected_type):
                    errors.append(
                        f"Field '{field_name}': expected type '{expected_type}', "
                        f"got '{type(actual).__name__}'"
                    )

        passed = len(errors) == 0
        if not passed:
            logger.warning(
                "action_schema_validator.validation_failed",
                action_type=action_type,
                errors=errors,
            )
        return ValidationResult(valid=passed, errors=errors)

    def validate_or_raise(self, action_type: str, payload: dict[str, Any]) -> None:
        """Validate and raise ActionSchemaError on failure.

        This is the blocking gate used by HITLGateway.submit_for_approval().
        """
        result = self.validate(action_type, payload)
        if not result.valid:
            raise ActionSchemaError(
                f"Action '{action_type}' payload failed schema validation "
                f"({len(result.errors)} error(s)): {'; '.join(result.errors)}"
            )

    @property
    def registered_action_types(self) -> list[str]:
        return list(self._schemas.keys())


def _matches_type(value: Any, expected: str) -> bool:
    """Check if a Python value matches a JSON Schema type string."""
    _type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": type(None),
    }
    py_type = _type_map.get(expected)
    if py_type is None:
        return True  # unknown type — allow
    # bool is a subclass of int in Python; for "integer" we must exclude bool
    if expected == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, py_type)
