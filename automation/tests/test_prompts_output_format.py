"""Tests for automation.prompts.output_format — structured output specification."""

import pytest

from automation.prompts.output_format import (
    NON_PROMPTABLE_ITEM_TYPES,
    PROMPTABLE_ITEM_TYPES,
    TYPE_PAYLOAD_SPECS,
    get_output_spec,
    is_promptable,
)


class TestIsPromptable:
    def test_all_nine_promptable(self):
        assert len(PROMPTABLE_ITEM_TYPES) == 9

    def test_three_non_promptable(self):
        assert NON_PROMPTABLE_ITEM_TYPES == {
            "stakeholder_review", "crm_configuration", "verification",
        }

    def test_promptable_returns_true(self):
        for t in PROMPTABLE_ITEM_TYPES:
            assert is_promptable(t) is True

    def test_non_promptable_returns_false(self):
        for t in NON_PROMPTABLE_ITEM_TYPES:
            assert is_promptable(t) is False

    def test_unknown_returns_false(self):
        assert is_promptable("bogus") is False


class TestGetOutputSpec:
    def test_contains_all_six_envelope_fields(self):
        spec = get_output_spec("master_prd", 42)
        assert "output_version" in spec
        assert "work_item_type" in spec
        assert "work_item_id" in spec
        assert "session_type" in spec
        assert "payload" in spec
        assert "decisions" in spec
        assert "open_issues" in spec

    def test_substitutes_item_type_and_id(self):
        spec = get_output_spec("entity_prd", 99)
        assert '"entity_prd"' in spec
        assert "99" in spec

    @pytest.mark.parametrize("item_type", list(PROMPTABLE_ITEM_TYPES))
    def test_every_type_has_payload_spec(self, item_type):
        spec = get_output_spec(item_type, 1)
        assert "Payload Specification" in spec
        assert len(spec) > 200

    def test_payload_spec_content_for_master_prd(self):
        spec = get_output_spec("master_prd", 1)
        assert "organization_overview" in spec
        assert "personas" in spec
        assert "domains" in spec

    def test_clarification_note(self):
        spec = get_output_spec("master_prd", 1, session_type="clarification")
        assert "clarification session" in spec
        assert "optional" in spec

    def test_initial_no_clarification_note(self):
        spec = get_output_spec("master_prd", 1, session_type="initial")
        assert "clarification session" not in spec

    def test_non_promptable_raises(self):
        with pytest.raises(ValueError, match="does not produce prompts"):
            get_output_spec("stakeholder_review", 1)

    def test_all_types_have_payload_specs(self):
        assert set(TYPE_PAYLOAD_SPECS.keys()) == PROMPTABLE_ITEM_TYPES
