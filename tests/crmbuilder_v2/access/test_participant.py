"""Participant repository tests — REL-040 / PI-094 (REQ-412).

Covers the ``participant`` methodology entity: schema shape, identifier
format + auto-assignment, case-insensitive name uniqueness, status enum
+ transitions, PATCH/PUT, soft-delete round-trip, and the
``persona_backed_by_participant`` reference (a Persona backed by a
Participant), including that soft-deleting a participant does NOT
cascade-delete the backing reference.
"""

from __future__ import annotations

import threading

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import (
    participant,
    persona,
    references,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "participant_identifier": "VARCHAR",
    "participant_name": "VARCHAR",
    "participant_role_kind": "VARCHAR",
    "participant_affiliation": "VARCHAR",
    "participant_contact": "VARCHAR",
    "participant_notes": "TEXT",
    "participant_status": "VARCHAR",
    "participant_created_at": "DATETIME",
    "participant_updated_at": "DATETIME",
    "participant_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


def test_participants_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "participants" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("participants")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = inspector.get_pk_constraint("participants")
    assert set(pk["constrained_columns"]) == {
        "participant_identifier",
        "engagement_id",
    }
    assert columns["participant_deleted_at"]["nullable"] is True
    assert columns["participant_affiliation"]["nullable"] is True
    assert columns["participant_contact"]["nullable"] is True
    assert columns["participant_name"]["nullable"] is False
    assert columns["participant_role_kind"]["nullable"] is False


# ---------------------------------------------------------------------------
# Identifier format + auto-assignment
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        participant.create_participant(
            s, name="Bad", role_kind="Client SME", identifier="PTC-1"
        )


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        row = participant.create_participant(
            s, name="Explicit", role_kind="Client SME", identifier="PTC-042"
        )
    assert row["participant_identifier"] == "PTC-042"


def test_post_without_identifier_auto_assigns_sequence(v2_env):
    with session_scope() as s:
        first = participant.create_participant(
            s, name="A", role_kind="Client SME"
        )
        second = participant.create_participant(
            s, name="B", role_kind="Client Administrator"
        )
    assert first["participant_identifier"] == "PTC-001"
    assert second["participant_identifier"] == "PTC-002"


def test_explicit_identifier_collision_conflicts(v2_env):
    with session_scope() as s:
        participant.create_participant(
            s, name="A", role_kind="Client SME", identifier="PTC-005"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        participant.create_participant(
            s, name="B", role_kind="Client SME", identifier="PTC-005"
        )


# ---------------------------------------------------------------------------
# Name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness(v2_env):
    with session_scope() as s:
        participant.create_participant(
            s, name="Jane Doe", role_kind="Client SME"
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        participant.create_participant(
            s, name="JANE DOE", role_kind="Client Administrator"
        )


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    with session_scope() as s:
        participant.create_participant(
            s, name="Temp", role_kind="Client SME"
        )
    with session_scope() as s:
        participant.delete_participant(s, "PTC-001")
    with session_scope() as s:
        row = participant.create_participant(
            s, name="Temp", role_kind="Client SME"
        )
    assert row["participant_identifier"] == "PTC-002"


# ---------------------------------------------------------------------------
# Status enum + transitions
# ---------------------------------------------------------------------------


def test_default_status_is_active(v2_env):
    with session_scope() as s:
        row = participant.create_participant(
            s, name="A", role_kind="Client SME"
        )
    assert row["participant_status"] == "active"


def test_invalid_status_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        participant.create_participant(
            s, name="A", role_kind="Client SME", status="archived"
        )


def test_status_toggles_active_inactive(v2_env):
    with session_scope() as s:
        participant.create_participant(s, name="A", role_kind="Client SME")
    with session_scope() as s:
        row = participant.patch_participant(s, "PTC-001", status="inactive")
        assert row["participant_status"] == "inactive"
    with session_scope() as s:
        row = participant.patch_participant(s, "PTC-001", status="active")
        assert row["participant_status"] == "active"


def test_status_noop_is_allowed(v2_env):
    with session_scope() as s:
        participant.create_participant(s, name="A", role_kind="Client SME")
    with session_scope() as s:
        row = participant.patch_participant(s, "PTC-001", status="active")
        assert row["participant_status"] == "active"


# ---------------------------------------------------------------------------
# PATCH / PUT
# ---------------------------------------------------------------------------


def test_patch_unknown_field_rejected(v2_env):
    with session_scope() as s:
        participant.create_participant(s, name="A", role_kind="Client SME")
    with session_scope() as s, pytest.raises(UnprocessableError):
        participant.patch_participant(s, "PTC-001", nickname="nope")


def test_patch_partial_fields(v2_env):
    with session_scope() as s:
        participant.create_participant(
            s,
            name="Jane",
            role_kind="Client SME",
            affiliation="Acme",
            contact="jane@acme.example",
        )
    with session_scope() as s:
        row = participant.patch_participant(
            s, "PTC-001", role_kind="Client Administrator", notes="promoted"
        )
    assert row["participant_role_kind"] == "Client Administrator"
    assert row["participant_notes"] == "promoted"
    # Untouched fields survive.
    assert row["participant_affiliation"] == "Acme"
    assert row["participant_contact"] == "jane@acme.example"


def test_put_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        participant.create_participant(s, name="A", role_kind="Client SME")
    with session_scope() as s, pytest.raises(UnprocessableError):
        participant.update_participant(
            s,
            "PTC-001",
            participant_identifier="PTC-999",
            name="A",
            role_kind="Client SME",
            status="active",
        )


def test_put_replaces_optional_fields(v2_env):
    with session_scope() as s:
        participant.create_participant(
            s,
            name="Jane",
            role_kind="Client SME",
            affiliation="Acme",
            notes="keep?",
        )
    with session_scope() as s:
        row = participant.update_participant(
            s,
            "PTC-001",
            name="Jane",
            role_kind="Client SME",
            affiliation=None,
            notes=None,
            status="active",
        )
    assert row["participant_affiliation"] is None
    assert row["participant_notes"] is None


# ---------------------------------------------------------------------------
# Soft-delete round-trip
# ---------------------------------------------------------------------------


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        participant.create_participant(s, name="A", role_kind="Client SME")
    with session_scope() as s:
        participant.delete_participant(s, "PTC-001")
    with session_scope() as s:
        assert participant.get_participant(s, "PTC-001") is None
        assert (
            participant.get_participant(s, "PTC-001", include_deleted=True)
            is not None
        )
    with session_scope() as s:
        row = participant.restore_participant(s, "PTC-001")
        assert row["participant_deleted_at"] is None


def test_restore_non_deleted_rejected(v2_env):
    with session_scope() as s:
        participant.create_participant(s, name="A", role_kind="Client SME")
    with session_scope() as s, pytest.raises(UnprocessableError):
        participant.restore_participant(s, "PTC-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        participant.update_participant(
            s, "PTC-404", name="x", role_kind="y", status="active"
        )


# ---------------------------------------------------------------------------
# persona_backed_by_participant reference
# ---------------------------------------------------------------------------


def test_persona_backed_by_participant_reference(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="Volunteer Mentor", role_summary="r")
        participant.create_participant(
            s, name="Jane Doe", role_kind="Client SME"
        )
        references.create(
            s,
            source_type="persona",
            source_id="PER-001",
            target_type="participant",
            target_id="PTC-001",
            relationship="persona_backed_by_participant",
        )
    with session_scope() as s:
        from_persona = references.list_touching(
            s, entity_type="persona", entity_id="PER-001"
        )
        assert len(from_persona["as_source"]) == 1
        assert (
            from_persona["as_source"][0]["relationship"]
            == "persona_backed_by_participant"
        )
        to_participant = references.list_touching(
            s, entity_type="participant", entity_id="PTC-001"
        )
        assert len(to_participant["as_target"]) == 1


def test_soft_delete_does_not_cascade_backing_reference(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="Volunteer Mentor", role_summary="r")
        participant.create_participant(
            s, name="Jane Doe", role_kind="Client SME"
        )
        references.create(
            s,
            source_type="persona",
            source_id="PER-001",
            target_type="participant",
            target_id="PTC-001",
            relationship="persona_backed_by_participant",
        )
    with session_scope() as s:
        participant.delete_participant(s, "PTC-001")
    with session_scope() as s:
        to_participant = references.list_touching(
            s, entity_type="participant", entity_id="PTC-001"
        )
        assert len(to_participant["as_target"]) == 1


# ---------------------------------------------------------------------------
# Concurrent auto-assignment never shares an identifier
# ---------------------------------------------------------------------------


def test_concurrent_autoassign_unique(v2_env):
    errors: list[Exception] = []
    ids: list[str] = []

    def worker(n: int) -> None:
        # PI-123: a spawned thread does not inherit the parent ContextVar, so
        # set the active engagement here (production sets it per request).
        from crmbuilder_v2.access import engagement_scope as _es

        _es.set_active_engagement("ENG-001")
        try:
            with session_scope() as s:
                row = participant.create_participant(
                    s, name=f"P{n}", role_kind="Client SME"
                )
            ids.append(row["participant_identifier"])
        except Exception as exc:  # noqa: BLE001 — collected and asserted on
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], errors
    assert len(ids) == 8
    assert len(set(ids)) == 8


# ---------------------------------------------------------------------------
# Vocab pair-direction rule (the UI reference-create filter's contract)
# ---------------------------------------------------------------------------


def test_pair_direction_rule():
    from crmbuilder_v2.access import vocab

    assert "persona_backed_by_participant" in vocab.RELATIONSHIP_RULES.get(
        ("persona", "participant"), frozenset()
    )
    assert "persona_backed_by_participant" not in vocab.RELATIONSHIP_RULES.get(
        ("participant", "persona"), frozenset()
    )
