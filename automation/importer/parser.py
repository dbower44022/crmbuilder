"""JSON parsing and validation for Import Processor.

Implements L2 PRD Section 11.2 — three layers of validation:
Layer 1: Syntax (strip markdown fences, trailing text, json.loads)
Layer 2: Envelope (output_version, work_item_type, work_item_id, etc.)
Layer 3: Payload structure (type-specific top-level key checks)
"""

from __future__ import annotations

import json
import re

# Supported output version — major must match, minor is flexible.
SUPPORTED_MAJOR_VERSION = 1

# Required top-level envelope fields and their expected JSON types.
ENVELOPE_FIELDS = {
    "output_version": str,
    "work_item_type": str,
    "work_item_id": int,
    "session_type": str,
    "payload": dict,
    "decisions": list,
    "open_issues": list,
}

VALID_SESSION_TYPES = frozenset({"initial", "revision", "clarification"})

VALID_WORK_ITEM_TYPES = frozenset({
    "master_prd",
    "business_object_discovery",
    "entity_prd",
    "domain_overview",
    "process_definition",
    "domain_reconciliation",
    "yaml_generation",
    "crm_selection",
    "crm_deployment",
})

# Required payload top-level keys per work item type and their expected JSON types.
PAYLOAD_KEYS: dict[str, dict[str, type]] = {
    "master_prd": {
        "organization_overview": str,
        "personas": list,
        "domains": list,
        "processes": list,
    },
    "business_object_discovery": {
        "business_objects": list,
        "entity_participation": list,
        "dependency_order": list,
    },
    "entity_prd": {
        "entity_metadata": dict,
        "native_fields": list,
        "custom_fields": list,
        "relationships": list,
    },
    "domain_overview": {
        "domain_purpose": str,
        "personas": list,
        "business_process_inventory": list,
        "data_reference": list,
    },
    "process_definition": {
        "process_purpose": str,
        "triggers": dict,
        "personas": list,
        "workflow": list,
        "completion": dict,
        "system_requirements": list,
        "process_data": list,
        "data_collected": list,
    },
    "domain_reconciliation": {
        "domain_overview_narrative": str,
        "personas": list,
        "conflict_resolutions": list,
        "consolidated_data_reference": list,
        "cross_process_gaps": list,
    },
    "yaml_generation": {
        "entity_configurations": list,
        "relationship_configurations": list,
        "layout_definitions": list,
        "resolved_exceptions": list,
        "unresolved_exceptions": list,
    },
    "crm_selection": {
        "recommended_platforms": list,
        "requirements_coverage": list,
        "platform_risks": list,
    },
    "crm_deployment": {
        "deployment_plan": dict,
        "infrastructure_decisions": list,
        "platform_specific_notes": list,
        "open_items": list,
    },
}


class ParserError(Exception):
    """Raised when JSON parsing or validation fails."""

    def __init__(self, message: str, layer: int, detail: str | None = None) -> None:
        self.layer = layer
        self.detail = detail
        super().__init__(message)


def _strip_fences(raw: str) -> str:
    """Strip markdown code fences and trailing non-JSON text.

    Handles patterns like:
        ```json\n{...}\n```
        ```\n{...}\n```
    Also strips any text after the last closing brace/bracket.
    """
    text = raw.strip()

    # Strip opening code fence
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)

    # Strip closing code fence
    text = re.sub(r"\n?```\s*$", "", text)

    # Strip trailing non-JSON text after the last closing brace
    # Find the last } and truncate everything after it
    last_brace = text.rfind("}")
    if last_brace != -1:
        text = text[: last_brace + 1]

    return text.strip()


def parse_layer1(raw: str) -> dict:
    """Layer 1 — Syntax: strip fences, parse JSON.

    :param raw: Raw pasted text, possibly with markdown fences.
    :returns: Parsed JSON as a dict.
    :raises ParserError: On JSON syntax error with line/char position.
    """
    if not raw or not raw.strip():
        raise ParserError(
            "Input is empty — no JSON to parse",
            layer=1,
        )

    cleaned = _strip_fences(raw)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ParserError(
            f"JSON syntax error at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            layer=1,
            detail=f"line={exc.lineno}, col={exc.colno}",
        ) from exc

    if not isinstance(parsed, dict):
        raise ParserError(
            "Expected a JSON object at the top level, got "
            f"{type(parsed).__name__}",
            layer=1,
        )

    return parsed


def parse_layer2(
    envelope: dict,
    expected_item_type: str,
    expected_work_item_id: int,
    expected_session_type: str,
) -> None:
    """Layer 2 — Envelope: validate common envelope fields.

    :param envelope: Parsed JSON dict from Layer 1.
    :param expected_item_type: The work item's item_type to match against.
    :param expected_work_item_id: The work item's id to match against.
    :param expected_session_type: The AISession's session_type to match against.
    :raises ParserError: On any envelope validation failure.
    """
    # Check each required field
    for field_name, expected_type in ENVELOPE_FIELDS.items():
        if field_name not in envelope:
            raise ParserError(
                f"Missing required envelope field: '{field_name}'",
                layer=2,
                detail=field_name,
            )
        value = envelope[field_name]
        if not isinstance(value, expected_type):
            # Special case: work_item_id can be int or float-that-is-int
            if field_name == "work_item_id" and isinstance(value, (int, float)):
                if value != int(value):
                    raise ParserError(
                        f"Envelope field '{field_name}' must be an integer, "
                        f"got float {value}",
                        layer=2,
                        detail=field_name,
                    )
            else:
                raise ParserError(
                    f"Envelope field '{field_name}' must be "
                    f"{expected_type.__name__}, got {type(value).__name__}",
                    layer=2,
                    detail=field_name,
                )

    # Version compatibility — major must match
    version_str = envelope["output_version"]
    try:
        parts = version_str.split(".")
        major = int(parts[0])
    except (ValueError, IndexError) as exc:
        raise ParserError(
            f"Invalid output_version format: '{version_str}' — "
            "expected 'major.minor' (e.g., '1.0')",
            layer=2,
            detail="output_version",
        ) from exc
    if major != SUPPORTED_MAJOR_VERSION:
        raise ParserError(
            f"Incompatible output_version: major version {major} "
            f"(supported: {SUPPORTED_MAJOR_VERSION})",
            layer=2,
            detail="output_version",
        )

    # work_item_type must match
    wit = envelope["work_item_type"]
    if wit not in VALID_WORK_ITEM_TYPES:
        raise ParserError(
            f"Unknown work_item_type: '{wit}'",
            layer=2,
            detail="work_item_type",
        )
    if wit != expected_item_type:
        raise ParserError(
            f"work_item_type mismatch: envelope says '{wit}', "
            f"expected '{expected_item_type}'",
            layer=2,
            detail="work_item_type",
        )

    # work_item_id must match
    wid = int(envelope["work_item_id"])
    if wid != expected_work_item_id:
        raise ParserError(
            f"work_item_id mismatch: envelope says {wid}, "
            f"expected {expected_work_item_id}",
            layer=2,
            detail="work_item_id",
        )

    # session_type must match
    st = envelope["session_type"]
    if st not in VALID_SESSION_TYPES:
        raise ParserError(
            f"Invalid session_type: '{st}' — "
            f"expected one of {sorted(VALID_SESSION_TYPES)}",
            layer=2,
            detail="session_type",
        )
    if st != expected_session_type:
        raise ParserError(
            f"session_type mismatch: envelope says '{st}', "
            f"expected '{expected_session_type}'",
            layer=2,
            detail="session_type",
        )


def parse_layer3(envelope: dict) -> None:
    """Layer 3 — Payload Structure: validate type-specific payload keys.

    :param envelope: Validated envelope dict from Layer 2.
    :raises ParserError: If required payload keys are missing or wrong type.
    """
    work_item_type = envelope["work_item_type"]
    payload = envelope["payload"]

    expected_keys = PAYLOAD_KEYS.get(work_item_type)
    if expected_keys is None:
        raise ParserError(
            f"No payload specification for work_item_type '{work_item_type}'",
            layer=3,
            detail="work_item_type",
        )

    for key_name, expected_type in expected_keys.items():
        if key_name not in payload:
            raise ParserError(
                f"Missing required payload key '{key_name}' for "
                f"work_item_type '{work_item_type}'",
                layer=3,
                detail=f"payload.{key_name}",
            )
        value = payload[key_name]
        if not isinstance(value, expected_type):
            raise ParserError(
                f"Payload key '{key_name}' must be {expected_type.__name__}, "
                f"got {type(value).__name__}",
                layer=3,
                detail=f"payload.{key_name}",
            )


def parse_and_validate(
    raw: str,
    expected_item_type: str,
    expected_work_item_id: int,
    expected_session_type: str,
) -> dict:
    """Run all three validation layers and return the parsed envelope.

    :param raw: Raw pasted text.
    :param expected_item_type: The work item's item_type.
    :param expected_work_item_id: The work item's id.
    :param expected_session_type: The AISession's session_type.
    :returns: Validated envelope dict.
    :raises ParserError: On any validation failure (layer 1, 2, or 3).
    """
    envelope = parse_layer1(raw)
    parse_layer2(envelope, expected_item_type, expected_work_item_id, expected_session_type)
    parse_layer3(envelope)
    return envelope
