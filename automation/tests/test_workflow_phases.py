"""Tests for automation.workflow.phases — item_type-to-phase mapping."""

import pytest

from automation.workflow.phases import (
    ITEM_TYPE_TO_PHASE,
    PHASE_NAMES,
    SERVICE_AWARE_ITEM_TYPES,
    get_phase,
    get_phase_name,
)


class TestGetPhase:
    """Tests for get_phase()."""

    @pytest.mark.parametrize(
        ("item_type", "expected_phase"),
        [
            ("master_prd", 1),
            ("business_object_discovery", 2),
            ("entity_prd", 2),
            ("stakeholder_review", 7),
            ("yaml_generation", 8),
            ("crm_selection", 9),
            ("crm_deployment", 10),
            ("crm_configuration", 11),
            ("verification", 12),
        ],
    )
    def test_static_item_types(self, item_type, expected_phase):
        assert get_phase(item_type) == expected_phase

    @pytest.mark.parametrize(
        ("item_type", "expected_phase"),
        [
            ("domain_overview", 3),
            ("process_definition", 5),
            ("domain_reconciliation", 6),
        ],
    )
    def test_service_aware_non_service(self, item_type, expected_phase):
        assert get_phase(item_type, is_service=False) == expected_phase

    @pytest.mark.parametrize("item_type", [
        "domain_overview",
        "process_definition",
        "domain_reconciliation",
    ])
    def test_service_aware_service_domain(self, item_type):
        assert get_phase(item_type, is_service=True) == 4

    def test_is_service_ignored_for_static_types(self):
        assert get_phase("master_prd", is_service=True) == 1
        assert get_phase("entity_prd", is_service=True) == 2

    def test_unknown_item_type_raises(self):
        with pytest.raises(ValueError, match="Unknown item_type: bogus"):
            get_phase("bogus")

    def test_all_12_item_types_covered(self):
        all_types = set(ITEM_TYPE_TO_PHASE.keys()) | SERVICE_AWARE_ITEM_TYPES
        assert len(all_types) == 12


class TestGetPhaseName:
    """Tests for get_phase_name()."""

    @pytest.mark.parametrize(
        ("phase", "expected_name"),
        list(PHASE_NAMES.items()),
    )
    def test_all_phase_names(self, phase, expected_name):
        assert get_phase_name(phase) == expected_name

    def test_unknown_phase_raises(self):
        with pytest.raises(ValueError, match="Unknown phase number: 99"):
            get_phase_name(99)

    def test_twelve_phases_defined(self):
        assert len(PHASE_NAMES) == 12
        assert set(PHASE_NAMES.keys()) == set(range(1, 13))
