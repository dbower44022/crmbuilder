"""Vocabulary tests for the v0.7 governance additions.

Covers the eight new relationship kinds, the six new entity types, and the
``_kinds_for_pair`` source/target bindings.
"""

from __future__ import annotations

from crmbuilder_v2.access import vocab

_NEW_KINDS = {
    "conversation_belongs_to_project",
    "project_planned_in_reference_book",
    "conversation_records_session",
    "conversation_opens_against_work_ticket",
    "conversation_succeeds_conversation",
    "close_out_payload_produced_by_conversation",
    "deposit_event_applies_close_out_payload",
    "deposit_event_wrote_record",
}
_NEW_TYPES = {
    "project",
    "conversation",
    "reference_book",
    "work_ticket",
    "close_out_payload",
    "deposit_event",
}


def test_new_relationship_kinds_registered():
    assert _NEW_KINDS <= vocab.REFERENCE_RELATIONSHIPS


def test_new_entity_types_registered():
    assert _NEW_TYPES <= vocab.ENTITY_TYPES


def test_kinds_for_pair_governance_bindings():
    kfp = vocab._kinds_for_pair
    assert "conversation_belongs_to_project" in kfp("conversation", "project")
    assert "conversation_records_session" in kfp("conversation", "session")
    assert "conversation_opens_against_work_ticket" in kfp(
        "conversation", "work_ticket"
    )
    assert "conversation_succeeds_conversation" in kfp(
        "conversation", "conversation"
    )
    assert "project_planned_in_reference_book" in kfp(
        "project", "reference_book"
    )
    assert "close_out_payload_produced_by_conversation" in kfp(
        "close_out_payload", "conversation"
    )
    assert "deposit_event_applies_close_out_payload" in kfp(
        "deposit_event", "close_out_payload"
    )
    for target in ("session", "decision", "planning_item", "reference"):
        assert "deposit_event_wrote_record" in kfp("deposit_event", target)


def test_same_type_supersedes_admitted_for_governance_entities():
    for t in _NEW_TYPES:
        assert "supersedes" in vocab._kinds_for_pair(t, t)


def test_kinds_for_pair_does_not_leak_bindings():
    # A binding kind must not appear on an unrelated pair.
    assert "conversation_belongs_to_project" not in vocab._kinds_for_pair(
        "project", "conversation"
    )
    assert "deposit_event_wrote_record" not in vocab._kinds_for_pair(
        "deposit_event", "close_out_payload"
    )


def test_relationship_rules_cover_new_types():
    for t in _NEW_TYPES:
        assert (t, t) in vocab.RELATIONSHIP_RULES
