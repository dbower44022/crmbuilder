"""Vocab module tests.

The flat ``REFERENCE_RELATIONSHIPS`` frozenset is exercised indirectly
through the references repository tests. These tests cover the
v0.3 slice C additions: the typed ``RELATIONSHIP_RULES`` lookup and
its helper functions, which feed the cascading
``ReferenceCreateDialog``.
"""

from __future__ import annotations

from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    RELATIONSHIP_RULES,
    kinds_for_source,
    source_types_with_relationships,
    target_types_for,
)


def test_relationship_rules_covers_every_pair():
    """Every (source, target) pair in ENTITY_TYPES is keyed."""
    expected_keys = {(s, t) for s in ENTITY_TYPES for t in ENTITY_TYPES}
    assert set(RELATIONSHIP_RULES.keys()) == expected_keys


def test_relationship_rules_only_uses_known_kinds():
    """Every kind in RELATIONSHIP_RULES is also in REFERENCE_RELATIONSHIPS."""
    for kinds in RELATIONSHIP_RULES.values():
        assert kinds <= REFERENCE_RELATIONSHIPS


def test_relationship_rules_every_pair_has_generic_kinds():
    """Every pair allows the two generic kinds (is_about, references)."""
    for kinds in RELATIONSHIP_RULES.values():
        assert "is_about" in kinds
        assert "references" in kinds


def test_decided_in_target_must_be_session():
    """decided_in is only valid when target is a session."""
    for (_source, target), kinds in RELATIONSHIP_RULES.items():
        if "decided_in" in kinds:
            assert target == "session"


def test_supersedes_requires_same_type():
    """supersedes is only valid when source and target types match."""
    for (source, target), kinds in RELATIONSHIP_RULES.items():
        if "supersedes" in kinds:
            assert source == target


def test_affects_requires_risk_source():
    for (source, _target), kinds in RELATIONSHIP_RULES.items():
        if "affects" in kinds:
            assert source == "risk"


def test_covers_requires_charter_or_status_source():
    for (source, _target), kinds in RELATIONSHIP_RULES.items():
        if "covers" in kinds:
            assert source in ("charter", "status")


def test_legacy_blocks_kind_not_emitted_anywhere():
    """v0.8 retired the legacy ``blocks`` kind in favor of directed
    ``blocked_by`` per methodology §3.4. No pair should emit it."""
    for (_source, _target), kinds in RELATIONSHIP_RULES.items():
        assert "blocks" not in kinds


def test_blocked_by_is_between_same_type_siblings():
    """``blocked_by`` is a same-type sibling edge. Originally planning_item →
    planning_item; PI-112 Phase 4 extends it to sibling Workstreams (and, in
    4b, sibling Work Tasks) per the target-model §7."""
    allowed = {"planning_item", "workstream", "work_task"}
    for (source, target), kinds in RELATIONSHIP_RULES.items():
        if "blocked_by" in kinds:
            assert source == target
            assert source in allowed


def test_kinds_for_source_returns_union():
    """kinds_for_source('decision') is the union over all target types."""
    kinds = kinds_for_source("decision")
    expected = set()
    for (source, _target), per_pair in RELATIONSHIP_RULES.items():
        if source == "decision":
            expected |= set(per_pair)
    assert kinds == frozenset(expected)


def test_target_types_for_session_decided_in_includes_decisions():
    """A session row can have decided_in pointing to many target types."""
    targets = target_types_for("decision", "decided_in")
    assert "session" in targets
    # decided_in only applies to session targets
    assert targets == frozenset({"session"})


def test_target_types_for_decision_supersedes_is_decision_only():
    targets = target_types_for("decision", "supersedes")
    assert targets == frozenset({"decision"})


def test_target_types_for_unknown_kind_is_empty():
    """A kind not present anywhere returns empty."""
    assert target_types_for("decision", "nope") == frozenset()


def test_source_types_with_relationships_is_all_entity_types():
    """Every entity type currently has at least the generic kinds."""
    assert source_types_with_relationships() == ENTITY_TYPES


def test_planning_item_belongs_to_project_completes_chain():
    """PI-112 follow-on: the top of the containment chain (target-model §7)."""
    assert "planning_item_belongs_to_project" in RELATIONSHIP_RULES[
        ("planning_item", "project")
    ]


def test_session_works_work_task_kind():
    """ADO: a session executes a Work Task (area-specialist role)."""
    assert 'session_works_work_task' in RELATIONSHIP_RULES[('session', 'work_task')]
