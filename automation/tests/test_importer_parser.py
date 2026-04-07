"""Tests for automation.importer.parser — JSON parsing and validation."""

import json

import pytest

from automation.importer.parser import (
    ParserError,
    parse_and_validate,
    parse_layer1,
    parse_layer2,
    parse_layer3,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_envelope(
    work_item_type="master_prd",
    work_item_id=1,
    session_type="initial",
    payload=None,
    decisions=None,
    open_issues=None,
    output_version="1.0",
):
    """Build a valid envelope dict."""
    if payload is None:
        payload = _make_payload(work_item_type)
    return {
        "output_version": output_version,
        "work_item_type": work_item_type,
        "work_item_id": work_item_id,
        "session_type": session_type,
        "payload": payload,
        "decisions": decisions if decisions is not None else [],
        "open_issues": open_issues if open_issues is not None else [],
    }


def _make_payload(work_item_type):
    """Build a minimal valid payload for the given type."""
    payloads = {
        "master_prd": {
            "organization_overview": "Overview",
            "personas": [],
            "domains": [],
            "processes": [],
        },
        "business_object_discovery": {
            "business_objects": [],
            "entity_participation": [],
            "dependency_order": [],
        },
        "entity_prd": {
            "entity_metadata": {},
            "native_fields": [],
            "custom_fields": [],
            "relationships": [],
        },
        "domain_overview": {
            "domain_purpose": "Purpose",
            "personas": [],
            "business_process_inventory": [],
            "data_reference": [],
        },
        "process_definition": {
            "process_purpose": "Purpose",
            "triggers": {},
            "personas": [],
            "workflow": [],
            "completion": {},
            "system_requirements": [],
            "process_data": [],
            "data_collected": [],
        },
        "domain_reconciliation": {
            "domain_overview_narrative": "Narrative",
            "personas": [],
            "conflict_resolutions": [],
            "consolidated_data_reference": [],
            "cross_process_gaps": [],
        },
        "yaml_generation": {
            "entity_configurations": [],
            "relationship_configurations": [],
            "layout_definitions": [],
            "resolved_exceptions": [],
            "unresolved_exceptions": [],
        },
        "crm_selection": {
            "recommended_platforms": [],
            "requirements_coverage": [],
            "platform_risks": [],
        },
        "crm_deployment": {
            "deployment_plan": {},
            "infrastructure_decisions": [],
            "platform_specific_notes": [],
            "open_items": [],
        },
    }
    return payloads[work_item_type]


# ===========================================================================
# Layer 1 — Syntax
# ===========================================================================

class TestLayer1:
    def test_valid_json(self):
        result = parse_layer1('{"key": "value"}')
        assert result == {"key": "value"}

    def test_empty_input(self):
        with pytest.raises(ParserError, match="Input is empty") as exc_info:
            parse_layer1("")
        assert exc_info.value.layer == 1

    def test_whitespace_only(self):
        with pytest.raises(ParserError, match="Input is empty"):
            parse_layer1("   \n\t  ")

    def test_json_syntax_error(self):
        with pytest.raises(ParserError, match="JSON syntax error") as exc_info:
            parse_layer1('{"key": }')
        assert exc_info.value.layer == 1
        assert "line=" in exc_info.value.detail

    def test_strip_json_code_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = parse_layer1(raw)
        assert result == {"key": "value"}

    def test_strip_plain_code_fence(self):
        raw = '```\n{"key": "value"}\n```'
        result = parse_layer1(raw)
        assert result == {"key": "value"}

    def test_strip_trailing_text(self):
        raw = '{"key": "value"}\n\nHere is some trailing text.'
        result = parse_layer1(raw)
        assert result == {"key": "value"}

    def test_strip_fence_and_trailing_text(self):
        raw = '```json\n{"key": "value"}\n```\n\nSome text after.'
        result = parse_layer1(raw)
        assert result == {"key": "value"}

    def test_not_an_object(self):
        with pytest.raises(ParserError, match="Expected a JSON object"):
            parse_layer1("[1, 2, 3]")

    def test_truncated_json(self):
        with pytest.raises(ParserError, match="JSON syntax error"):
            parse_layer1('{"key": "val')


# ===========================================================================
# Layer 2 — Envelope
# ===========================================================================

class TestLayer2:
    def test_valid_envelope(self):
        env = _make_envelope()
        # Should not raise
        parse_layer2(env, "master_prd", 1, "initial")

    def test_missing_field(self):
        env = _make_envelope()
        del env["output_version"]
        with pytest.raises(ParserError, match="Missing required.*output_version") as exc_info:
            parse_layer2(env, "master_prd", 1, "initial")
        assert exc_info.value.layer == 2

    def test_wrong_type_payload(self):
        env = _make_envelope()
        env["payload"] = "not a dict"
        with pytest.raises(ParserError, match="payload.*must be dict"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_wrong_type_decisions(self):
        env = _make_envelope()
        env["decisions"] = "not a list"
        with pytest.raises(ParserError, match="decisions.*must be list"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_bad_version_format(self):
        env = _make_envelope(output_version="abc")
        with pytest.raises(ParserError, match="Invalid output_version"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_incompatible_major_version(self):
        env = _make_envelope(output_version="2.0")
        with pytest.raises(ParserError, match="Incompatible output_version"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_compatible_minor_version(self):
        env = _make_envelope(output_version="1.5")
        parse_layer2(env, "master_prd", 1, "initial")

    def test_unknown_work_item_type(self):
        env = _make_envelope()
        env["work_item_type"] = "unknown_type"
        with pytest.raises(ParserError, match="Unknown work_item_type"):
            parse_layer2(env, "unknown_type", 1, "initial")

    def test_work_item_type_mismatch(self):
        env = _make_envelope(work_item_type="entity_prd")
        with pytest.raises(ParserError, match="work_item_type mismatch"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_work_item_id_mismatch(self):
        env = _make_envelope(work_item_id=99)
        with pytest.raises(ParserError, match="work_item_id mismatch"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_invalid_session_type(self):
        env = _make_envelope()
        env["session_type"] = "invalid"
        with pytest.raises(ParserError, match="Invalid session_type"):
            parse_layer2(env, "master_prd", 1, "invalid")

    def test_session_type_mismatch(self):
        env = _make_envelope(session_type="revision")
        with pytest.raises(ParserError, match="session_type mismatch"):
            parse_layer2(env, "master_prd", 1, "initial")

    def test_each_missing_field(self):
        for field in ("output_version", "work_item_type", "work_item_id",
                       "session_type", "payload", "decisions", "open_issues"):
            env = _make_envelope()
            del env[field]
            with pytest.raises(ParserError, match=f"Missing.*{field}"):
                parse_layer2(env, "master_prd", 1, "initial")


# ===========================================================================
# Layer 3 — Payload Structure
# ===========================================================================

class TestLayer3:
    @pytest.mark.parametrize("work_item_type", [
        "master_prd", "business_object_discovery", "entity_prd",
        "domain_overview", "process_definition", "domain_reconciliation",
        "yaml_generation", "crm_selection", "crm_deployment",
    ])
    def test_valid_payload(self, work_item_type):
        env = _make_envelope(work_item_type=work_item_type)
        parse_layer3(env)  # Should not raise

    def test_missing_payload_key(self):
        env = _make_envelope(work_item_type="master_prd")
        del env["payload"]["personas"]
        with pytest.raises(ParserError, match="Missing required payload key 'personas'"):
            parse_layer3(env)

    def test_wrong_payload_key_type(self):
        env = _make_envelope(work_item_type="master_prd")
        env["payload"]["personas"] = "not a list"
        with pytest.raises(ParserError, match="personas.*must be list"):
            parse_layer3(env)

    def test_extra_keys_allowed(self):
        env = _make_envelope(work_item_type="master_prd")
        env["payload"]["extra_key"] = "allowed"
        parse_layer3(env)  # Should not raise


# ===========================================================================
# Full parse_and_validate
# ===========================================================================

class TestParseAndValidate:
    def test_full_valid(self):
        env = _make_envelope()
        raw = json.dumps(env)
        result = parse_and_validate(raw, "master_prd", 1, "initial")
        assert result["work_item_type"] == "master_prd"

    def test_full_valid_with_fences(self):
        env = _make_envelope()
        raw = f"```json\n{json.dumps(env)}\n```"
        result = parse_and_validate(raw, "master_prd", 1, "initial")
        assert result["work_item_type"] == "master_prd"

    def test_layer1_failure(self):
        with pytest.raises(ParserError) as exc_info:
            parse_and_validate("{bad", "master_prd", 1, "initial")
        assert exc_info.value.layer == 1

    def test_layer2_failure(self):
        env = _make_envelope(work_item_type="entity_prd")
        raw = json.dumps(env)
        with pytest.raises(ParserError) as exc_info:
            parse_and_validate(raw, "master_prd", 1, "initial")
        assert exc_info.value.layer == 2

    def test_layer3_failure(self):
        env = _make_envelope()
        del env["payload"]["personas"]
        raw = json.dumps(env)
        with pytest.raises(ParserError) as exc_info:
            parse_and_validate(raw, "master_prd", 1, "initial")
        assert exc_info.value.layer == 3
