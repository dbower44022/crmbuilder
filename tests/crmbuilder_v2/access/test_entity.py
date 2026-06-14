"""Entity repository tests — UI v0.4 slice C.

Covers ``entity.md`` section 3.7 acceptance criteria 1–5 and 8:
schema migration shape, identifier-format constraint, case-insensitive
name uniqueness, status enum + transition validation, the eight
repository methods (happy path + at least one error case each),
identifier auto-assignment under concurrency, and the soft-delete /
restore round-trip.

Two entity-specific assertions per the slice prompt: soft-deleting an
entity does NOT cascade-delete its ``entity_scopes_to_domain``
references (spec 3.4.6), and ``entity_status`` changes never consult
the affiliated domains' statuses (spec 3.4.3).
"""

from __future__ import annotations

import threading

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import domain, entity, references
from sqlalchemy import inspect

# Expected ``entities`` columns and their SQLite affinities (criterion 1).
# v0.5+ PI-010 grew the eight-column shape by one — ``entity_kind`` —
# per entity.md v1.1 §3.2.3 / DEC-292.
_EXPECTED_COLUMNS = {
    "entity_identifier": "VARCHAR",
    "entity_name": "VARCHAR",
    "entity_status": "VARCHAR",
    "entity_kind": "TEXT",
    "entity_description": "TEXT",
    "entity_notes": "TEXT",
    # PRJ-025 PI-182 — intrinsic engine-neutral design intent (§6).
    "entity_default_sort_field": "TEXT",
    "entity_default_sort_direction": "TEXT",
    "entity_track_activity": "BOOLEAN",
    "entity_created_at": "DATETIME",
    "entity_updated_at": "DATETIME",
    "entity_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_entities_table_has_nine_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "entities" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("entities")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    # Primary key is the prefixed-string identifier; no surrogate ``id``.
    pk = inspector.get_pk_constraint("entities")
    assert pk["constrained_columns"] == ["entity_identifier", "engagement_id"]
    # Soft-delete and timestamp nullability per the spec.
    assert columns["entity_deleted_at"]["nullable"] is True
    assert columns["entity_notes"]["nullable"] is True
    assert columns["entity_name"]["nullable"] is False
    assert columns["entity_description"]["nullable"] is False
    # PI-010 / DEC-292: entity_kind is TEXT NULL with five-value enum.
    assert columns["entity_kind"]["nullable"] is True


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.create_entity(s, name="Bad", description="d", identifier="ENT-1")


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        row = entity.create_entity(
            s, name="Explicit", description="d", identifier="ENT-042"
        )
    assert row["entity_identifier"] == "ENT-042"


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="Contact", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.create_entity(s, name="contact", description="d2")


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    """A soft-deleted row no longer reserves its name."""
    with session_scope() as s:
        entity.create_entity(s, name="Contact", description="d")
    with session_scope() as s:
        entity.delete_entity(s, "ENT-001")
    with session_scope() as s:
        row = entity.create_entity(s, name="CONTACT", description="d2")
    assert row["entity_name"] == "CONTACT"


# ---------------------------------------------------------------------------
# Criterion 4 — status enum + transition validation
# ---------------------------------------------------------------------------


def test_status_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.create_entity(s, name="X", description="d", status="archived")


def test_default_status_is_candidate(v2_env):
    with session_scope() as s:
        row = entity.create_entity(s, name="X", description="d")
    assert row["entity_status"] == "candidate"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("candidate", "confirmed"),
        ("candidate", "deferred"),
        ("confirmed", "deferred"),
        ("deferred", "confirmed"),
    ],
)
def test_valid_status_transitions_permitted(v2_env, start, target):
    with session_scope() as s:
        entity.create_entity(s, name="T", description="d", status=start)
    with session_scope() as s:
        row = entity.patch_entity(s, "ENT-001", status=target)
    assert row["entity_status"] == target


@pytest.mark.parametrize("start", ["confirmed", "deferred"])
def test_regression_to_candidate_rejected(v2_env, start):
    with session_scope() as s:
        entity.create_entity(s, name="T", description="d", status=start)
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        entity.patch_entity(s, "ENT-001", status="candidate")
    assert exc.value.from_status == start
    assert exc.value.to_status == "candidate"


def test_no_op_status_change_is_permitted(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="T", description="d", status="confirmed")
    with session_scope() as s:
        row = entity.patch_entity(s, "ENT-001", status="confirmed")
    assert row["entity_status"] == "confirmed"


# ---------------------------------------------------------------------------
# Criterion 5 — the eight repository methods (happy path + an error case)
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_entities",
        "get_entity",
        "create_entity",
        "update_entity",
        "patch_entity",
        "delete_entity",
        "restore_entity",
        "next_entity_identifier",
    ):
        assert callable(getattr(entity, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        created = entity.create_entity(
            s,
            name="Mentor",
            description="A person who provides mentoring guidance",
            notes="consultant scratchpad",
        )
    assert created["entity_identifier"] == "ENT-001"
    with session_scope() as s:
        fetched = entity.get_entity(s, "ENT-001")
    assert fetched["entity_name"] == "Mentor"
    assert fetched["entity_notes"] == "consultant scratchpad"


def test_get_entity_missing_returns_none(v2_env):
    with session_scope() as s:
        assert entity.get_entity(s, "ENT-404") is None


def test_list_entities_orders_by_identifier(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="B", description="d")
        entity.create_entity(s, name="A", description="d")
        entity.create_entity(s, name="C", description="d")
    with session_scope() as s:
        ids = [e["entity_identifier"] for e in entity.list_entities(s)]
    assert ids == ["ENT-001", "ENT-002", "ENT-003"]


def test_update_entity_full_replace(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="Old", description="od")
    with session_scope() as s:
        row = entity.update_entity(
            s,
            "ENT-001",
            entity_identifier="ENT-001",
            name="New",
            description="nd",
            notes="now has notes",
            status="confirmed",
        )
    assert row["entity_name"] == "New"
    assert row["entity_notes"] == "now has notes"
    assert row["entity_status"] == "confirmed"


def test_update_entity_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.update_entity(
            s,
            "ENT-001",
            entity_identifier="ENT-999",
            name="X",
            description="d",
            status="candidate",
        )


def test_patch_entity_partial(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s:
        row = entity.patch_entity(s, "ENT-001", description="updated description")
    assert row["entity_description"] == "updated description"
    assert row["entity_name"] == "X"


def test_patch_entity_unknown_field_rejected(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.patch_entity(s, "ENT-001", bogus="value")


def test_patch_entity_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        entity.patch_entity(s, "ENT-404", description="x")


def test_create_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        entity.create_entity(
            s, name="First", description="d", identifier="ENT-001"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        entity.create_entity(
            s, name="Second", description="d", identifier="ENT-001"
        )


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_entity_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert entity.next_entity_identifier(s) == "ENT-001"


def test_next_entity_identifier_increments(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="A", description="d")
        entity.create_entity(s, name="B", description="d")
    with session_scope() as s:
        assert entity.next_entity_identifier(s) == "ENT-003"


def test_next_entity_identifier_skips_soft_deleted(v2_env):
    """A soft-deleted row's identifier is not reused."""
    with session_scope() as s:
        entity.create_entity(s, name="A", description="d")
        entity.create_entity(s, name="B", description="d")
    with session_scope() as s:
        entity.delete_entity(s, "ENT-002")
    with session_scope() as s:
        assert entity.next_entity_identifier(s) == "ENT-003"


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    """The auto-assign retry recovers when the computed id is taken."""
    with session_scope() as s:
        entity.create_entity(
            s, name="First", description="d", identifier="ENT-001"
        )
    monkeypatch.setattr(entity, "next_entity_identifier", lambda _s: "ENT-001")
    with session_scope() as s:
        row = entity.create_entity(s, name="Second", description="d")
    assert row["entity_identifier"] == "ENT-002"


def test_concurrent_creates_assign_distinct_identifiers(v2_env):
    """Eight simultaneous create calls never share an identifier."""
    results: list[str] = []
    errors: list[Exception] = []

    def worker(index: int) -> None:
        # PI-123: a spawned thread does not inherit the parent ContextVar, so
        # set the active engagement here (production sets it per request via
        # the scope middleware).
        from crmbuilder_v2.access import engagement_scope as _es
        _es.set_active_engagement("ENG-001")
        try:
            with session_scope() as s:
                row = entity.create_entity(
                    s, name=f"Concurrent entity {index}", description="d"
                )
            results.append(row["entity_identifier"])
        except Exception as exc:  # noqa: BLE001 — collected and asserted on
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(results) == 8
    assert len(set(results)) == 8


# ---------------------------------------------------------------------------
# Criterion 8 — soft-delete / restore round-trip
# ---------------------------------------------------------------------------


def test_soft_delete_hides_from_default_list_and_get(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s:
        deleted = entity.delete_entity(s, "ENT-001")
    assert deleted["entity_deleted_at"] is not None
    with session_scope() as s:
        assert entity.list_entities(s) == []
        assert len(entity.list_entities(s, include_deleted=True)) == 1
        assert entity.get_entity(s, "ENT-001") is None
        assert entity.get_entity(s, "ENT-001", include_deleted=True) is not None


def test_soft_delete_is_idempotent(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s:
        entity.delete_entity(s, "ENT-001")
    with session_scope() as s:
        stored = entity.get_entity(s, "ENT-001", include_deleted=True)
    with session_scope() as s:
        second = entity.delete_entity(s, "ENT-001")
    assert second["entity_deleted_at"] is not None
    assert second["entity_deleted_at"] == stored["entity_deleted_at"]


def test_restore_clears_deleted_at(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s:
        entity.delete_entity(s, "ENT-001")
    with session_scope() as s:
        restored = entity.restore_entity(s, "ENT-001")
    assert restored["entity_deleted_at"] is None
    with session_scope() as s:
        assert len(entity.list_entities(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="X", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.restore_entity(s, "ENT-001")


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        entity.delete_entity(s, "ENT-404")


# ---------------------------------------------------------------------------
# Entity-specific — references do not cascade on soft-delete (spec 3.4.6)
# ---------------------------------------------------------------------------


def test_soft_delete_does_not_cascade_scopes_to_domain_references(v2_env):
    """Soft-deleting an entity leaves its outbound affiliations in place.

    Per ``entity.md`` section 3.4.6 the ``entity_scopes_to_domain``
    references persist in the ``refs`` table; they surface via the
    show-deleted toggle on either side.
    """
    with session_scope() as s:
        entity.create_entity(s, name="Contact", description="d")
        domain.create_domain(s, name="Mentoring", purpose="p", description="d")
        references.create(
            s,
            source_type="entity",
            source_id="ENT-001",
            target_type="domain",
            target_id="DOM-001",
            relationship="entity_scopes_to_domain",
        )
    with session_scope() as s:
        entity.delete_entity(s, "ENT-001")
    with session_scope() as s:
        # The reference still exists and still touches both sides.
        touching = references.list_touching(
            s, entity_type="entity", entity_id="ENT-001"
        )
        assert len(touching["as_source"]) == 1
        assert touching["as_source"][0]["relationship"] == (
            "entity_scopes_to_domain"
        )
        from_domain = references.list_touching(
            s, entity_type="domain", entity_id="DOM-001"
        )
        assert len(from_domain["as_target"]) == 1


# ---------------------------------------------------------------------------
# Entity-specific — status independent of affiliated-domain status (3.4.3)
# ---------------------------------------------------------------------------


def test_entity_status_change_does_not_consult_affiliated_domains(v2_env):
    """An entity's status transition never depends on its domains.

    Per ``entity.md`` section 3.4.3 the two lifecycles are managed
    independently: an entity scoped to a ``deferred`` domain can still
    be ``confirmed``, and changing the domain's status never cascades
    to the entity.
    """
    with session_scope() as s:
        entity.create_entity(s, name="Contact", description="d")
        domain.create_domain(s, name="Fundraising", purpose="p", description="d")
        references.create(
            s,
            source_type="entity",
            source_id="ENT-001",
            target_type="domain",
            target_id="DOM-001",
            relationship="entity_scopes_to_domain",
        )
    # The affiliated domain moves to ``deferred``.
    with session_scope() as s:
        domain.patch_domain(s, "DOM-001", status="deferred")
    # The entity can still be confirmed — its status is its own field.
    with session_scope() as s:
        row = entity.patch_entity(s, "ENT-001", status="confirmed")
    assert row["entity_status"] == "confirmed"
    # And the domain's status was not touched by the entity change.
    with session_scope() as s:
        assert domain.get_domain(s, "DOM-001")["domain_status"] == "deferred"


# ---------------------------------------------------------------------------
# PI-010 / DEC-292 — entity_kind classification (v0.5+ schema growth)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind", ["person", "organization", "event", "transaction", "other"]
)
def test_entity_kind_accepts_each_enum_value(v2_env, kind):
    """Every value in ENTITY_KINDS round-trips through create_entity."""
    with session_scope() as s:
        row = entity.create_entity(
            s, name=f"E-{kind}", description="d", kind=kind
        )
    assert row["entity_kind"] == kind


def test_entity_kind_defaults_to_null(v2_env):
    """Omitted kind is NULL — operator-deferred classification per DEC-292."""
    with session_scope() as s:
        row = entity.create_entity(s, name="Unkinded", description="d")
    assert row["entity_kind"] is None


def test_entity_kind_rejects_invalid_value(v2_env):
    """Anything outside ENTITY_KINDS is rejected with the field error."""
    with session_scope() as s, pytest.raises(UnprocessableError):
        entity.create_entity(
            s, name="Bad Kind", description="d", kind="vegetable"
        )


def test_entity_kind_empty_string_coerces_to_null(v2_env):
    """`""` is treated as a "clear" sentinel by _coerce_kind."""
    with session_scope() as s:
        row = entity.create_entity(
            s, name="Cleared", description="d", kind=""
        )
    assert row["entity_kind"] is None


def test_patch_entity_kind_to_null_clears_field(v2_env):
    with session_scope() as s:
        entity.create_entity(
            s, name="Clearable", description="d", kind="person"
        )
    with session_scope() as s:
        row = entity.patch_entity(s, "ENT-001", kind=None)
    assert row["entity_kind"] is None


def test_patch_entity_kind_changes_value(v2_env):
    with session_scope() as s:
        entity.create_entity(
            s, name="Mover", description="d", kind="person"
        )
    with session_scope() as s:
        row = entity.patch_entity(s, "ENT-001", kind="organization")
    assert row["entity_kind"] == "organization"


def test_update_entity_kind_replaced_under_put_semantics(v2_env):
    """PUT replaces wholesale — omitting kind from the body clears it."""
    with session_scope() as s:
        entity.create_entity(
            s, name="PutCase", description="d", kind="event"
        )
    with session_scope() as s:
        # Note: ``kind`` not passed → defaults to None → clears.
        row = entity.update_entity(
            s,
            "ENT-001",
            name="PutCase",
            description="d",
            status="candidate",
        )
    assert row["entity_kind"] is None


# ---------------------------------------------------------------------------
# PI-010 / DEC-291 — entity_variant_of_entity edge (v0.5+ schema growth)
# ---------------------------------------------------------------------------


def test_variant_edge_round_trips(v2_env):
    """An entity_variant_of_entity edge can be created and surfaced."""
    with session_scope() as s:
        entity.create_entity(s, name="Contact", description="base")
        entity.create_entity(
            s, name="Mentor Contact", description="variant"
        )
        ref = references.create(
            s,
            source_type="entity",
            source_id="ENT-002",
            target_type="entity",
            target_id="ENT-001",
            relationship="entity_variant_of_entity",
        )
    assert ref["relationship"] == "entity_variant_of_entity"


def test_variant_cardinality_rejects_second_outbound_edge(v2_env):
    """An entity may be a variant of at most one other entity (DEC-291)."""
    with session_scope() as s:
        entity.create_entity(s, name="Contact", description="base1")
        entity.create_entity(s, name="Account", description="base2")
        entity.create_entity(
            s, name="Hybrid", description="variant"
        )
        references.create(
            s,
            source_type="entity",
            source_id="ENT-003",
            target_type="entity",
            target_id="ENT-001",
            relationship="entity_variant_of_entity",
        )
    # Attempting a second outbound variant edge from ENT-003 fails.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        references.create(
            s,
            source_type="entity",
            source_id="ENT-003",
            target_type="entity",
            target_id="ENT-002",
            relationship="entity_variant_of_entity",
        )
    assert "cardinality_violation" in str(exc.value.errors[0].code)


def test_variant_rejects_self_reference(v2_env):
    with session_scope() as s:
        entity.create_entity(s, name="Loner", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        references.create(
            s,
            source_type="entity",
            source_id="ENT-001",
            target_type="entity",
            target_id="ENT-001",
            relationship="entity_variant_of_entity",
        )
    assert "self_reference" in str(exc.value.errors[0].code)


def test_variant_one_step_cycle_rejected(v2_env):
    """If A→B exists, B→A is rejected (one-step cycle guard)."""
    with session_scope() as s:
        entity.create_entity(s, name="A", description="d")
        entity.create_entity(s, name="B", description="d")
        references.create(
            s,
            source_type="entity",
            source_id="ENT-001",
            target_type="entity",
            target_id="ENT-002",
            relationship="entity_variant_of_entity",
        )
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        references.create(
            s,
            source_type="entity",
            source_id="ENT-002",
            target_type="entity",
            target_id="ENT-001",
            relationship="entity_variant_of_entity",
        )
    assert "cycle_violation" in str(exc.value.errors[0].code)


def test_variant_vocab_admits_kind(v2_env):
    """`entity_variant_of_entity` is registered in REFERENCE_RELATIONSHIPS."""
    from crmbuilder_v2.access.vocab import (
        REFERENCE_RELATIONSHIPS,
        RELATIONSHIP_RULES,
    )

    assert "entity_variant_of_entity" in REFERENCE_RELATIONSHIPS
    assert "entity_variant_of_entity" in RELATIONSHIP_RULES[("entity", "entity")]


def test_entity_kinds_vocab_shape():
    """ENTITY_KINDS is the five-value enum per DEC-292."""
    from crmbuilder_v2.access.vocab import ENTITY_KINDS

    assert ENTITY_KINDS == frozenset(
        {"person", "organization", "event", "transaction", "other"}
    )
