"""Vocabulary tests for WTK-106 — the `migration_mapping` methodology entity.

Covers the WTK-104 design spec's vocab surface
(methodology-schema-specs/migration_mapping.md §10): the standard
four-status lifecycle, the two-value level and disposition enums, the
closed four-kind transform-rule vocabulary, the two edge kinds with their
(entity | field)-only pair rules (invariant I12), the entity-type
registration, and the `rejected_by_decision` source-set extension.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import vocab

_FROM = "migration_mapping_migrates_from_record"
_TO = "migration_mapping_migrates_to_record"


def test_statuses_are_the_standard_four():
    assert vocab.MIGRATION_MAPPING_STATUSES == frozenset(
        {"candidate", "confirmed", "deferred", "rejected"}
    )


def test_transitions_mirror_the_methodology_lifecycle():
    # Same map as domain/entity/field — no per-type variation (spec §3.4.1).
    assert (
        vocab.MIGRATION_MAPPING_STATUS_TRANSITIONS
        == vocab.FIELD_STATUS_TRANSITIONS
    )
    assert vocab.MIGRATION_MAPPING_STATUS_TRANSITIONS["rejected"] == frozenset()
    # One-way propose-verify gate: no status lists candidate as a successor.
    assert all(
        "candidate" not in succ
        for succ in vocab.MIGRATION_MAPPING_STATUS_TRANSITIONS.values()
    )


def test_levels_are_the_two_data_bearing_capture_types():
    assert vocab.MIGRATION_MAPPING_LEVELS == frozenset({"entity", "field"})
    assert vocab.MIGRATION_MAPPING_LEVELS < vocab.BASELINE_CAPTURE_TYPES


def test_dispositions():
    assert vocab.MIGRATION_MAPPING_DISPOSITIONS == frozenset(
        {"keep", "transform"}
    )


def test_transform_rule_kinds_are_the_prd_named_set():
    assert vocab.MIGRATION_TRANSFORM_RULE_KINDS == frozenset(
        {"type_change", "enum_value_map", "merge", "split"}
    )


def test_edge_kinds_registered():
    assert _FROM in vocab.REFERENCE_RELATIONSHIPS
    assert _TO in vocab.REFERENCE_RELATIONSHIPS


def test_entity_type_registered():
    assert "migration_mapping" in vocab.ENTITY_TYPES
    assert "migration_mapping" in vocab.CHANGE_LOG_ENTITY_TYPES


@pytest.mark.parametrize("target", ["entity", "field"])
def test_edge_kinds_admitted_for_data_bearing_targets(target):
    kinds = vocab.RELATIONSHIP_RULES[("migration_mapping", target)]
    assert _FROM in kinds
    assert _TO in kinds


@pytest.mark.parametrize("target", ["persona", "process", "manual_config"])
def test_edge_kinds_unrepresentable_for_non_data_capture_types(target):
    # Invariant I12: dispositions on the three non-data capture types
    # create no migration mapping (spec §2).
    kinds = vocab.RELATIONSHIP_RULES[("migration_mapping", target)]
    assert _FROM not in kinds
    assert _TO not in kinds


def test_edge_kinds_do_not_leak_to_other_sources():
    assert _FROM not in vocab._kinds_for_pair("entity", "field")
    assert _TO not in vocab._kinds_for_pair("field", "entity")
    assert _FROM not in vocab._kinds_for_pair("entity", "migration_mapping")


def test_rejected_by_decision_extended_to_migration_mapping():
    # Spec §10: the rejected terminal requires the rationale edge, so the
    # source set grows to include the new status-bearing type.
    assert "rejected_by_decision" in vocab.RELATIONSHIP_RULES[
        ("migration_mapping", "decision")
    ]
    assert "rejected_by_decision" not in vocab._kinds_for_pair(
        "migration_mapping", "session"
    )


def test_generic_kinds_still_apply():
    kinds = vocab.RELATIONSHIP_RULES[("migration_mapping", "migration_mapping")]
    assert "is_about" in kinds
    assert "references" in kinds
    assert "supersedes" in kinds
