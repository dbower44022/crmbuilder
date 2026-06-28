"""PI-046 (REQ-387) — ``reference`` is a declared entity type.

``vocab._kinds_for_pair`` admitted ``target_type="reference"`` for the
``deposit_event_wrote_record`` kind, but ``reference`` was absent from
``ENTITY_TYPES`` — so the create-edge validator rejected ``target_type="reference"``
(``require_in(target_type, ENTITY_TYPES)``) and ``RELATIONSHIP_RULES`` never
generated the ``("deposit_event", "reference")`` key. Declaring ``reference`` closes
the contradiction: a deposit event's wrote-record edge to a reference now validates.
"""

from __future__ import annotations

from crmbuilder_v2.access import vocab
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import references


def test_reference_is_a_declared_entity_type():
    assert "reference" in vocab.ENTITY_TYPES


def test_relationship_rules_generate_deposit_event_to_reference():
    key = ("deposit_event", "reference")
    assert key in vocab.RELATIONSHIP_RULES
    assert "deposit_event_wrote_record" in vocab.RELATIONSHIP_RULES[key]


def test_change_log_set_unchanged_reference_already_present():
    # CHANGE_LOG_ENTITY_TYPES carried "reference" via its explicit union already,
    # so declaring it in ENTITY_TYPES leaves the change_log set identical.
    assert "reference" in vocab.CHANGE_LOG_ENTITY_TYPES


def test_every_relationship_rule_uses_declared_entity_types():
    # The consistency invariant REQ-387 protects: no admitted (source, target)
    # pair names an entity type absent from the declared set.
    for source, target in vocab.RELATIONSHIP_RULES:
        assert source in vocab.ENTITY_TYPES, source
        assert target in vocab.ENTITY_TYPES, target


def test_create_deposit_event_wrote_record_edge_to_reference(v2_env):
    # The acceptance criterion: a wrote-record edge from a deposit event to a
    # reference record is now created instead of being rejected at the
    # entity-type gate. (references.create validates types, not row existence.)
    with session_scope() as s:
        ref = references.create(
            s,
            source_type="deposit_event",
            source_id="DEP-001",
            target_type="reference",
            target_id="REF-0001",
            relationship="deposit_event_wrote_record",
        )
    assert ref["source_type"] == "deposit_event"
    assert ref["target_type"] == "reference"
    assert ref["relationship"] == "deposit_event_wrote_record"
