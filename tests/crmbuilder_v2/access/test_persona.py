"""Persona repository tests — v0.5+ (PI-003).

Covers ``persona.md`` §3.7 acceptance criteria 1–5, 7, 8 plus two
persona-specific assertions:

* Soft-deleting a persona does NOT cascade-delete its
  ``persona_scopes_to_domain`` or ``persona_realized_as_entity``
  references (spec §3.4.6).
* ``persona_status`` changes never consult the affiliated domains'
  statuses or the realization entity's status (spec §3.4.3).
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
from crmbuilder_v2.access.repositories import (
    domain,
    entity,
    persona,
    references,
)
from sqlalchemy import inspect

# Expected ``personas`` columns and their SQLite affinities (criterion 1).
_EXPECTED_COLUMNS = {
    "persona_identifier": "VARCHAR",
    "persona_name": "VARCHAR",
    "persona_role_summary": "TEXT",
    "persona_responsibilities": "TEXT",
    "persona_notes": "TEXT",
    "persona_status": "VARCHAR",
    "persona_created_at": "DATETIME",
    "persona_updated_at": "DATETIME",
    "persona_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_personas_table_has_nine_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "personas" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("personas")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    # Primary key is the prefixed-string identifier; no surrogate ``id``.
    pk = inspector.get_pk_constraint("personas")
    assert pk["constrained_columns"] == ["persona_identifier", "engagement_id"]
    # Soft-delete and optional-content nullability per the spec.
    assert columns["persona_deleted_at"]["nullable"] is True
    assert columns["persona_responsibilities"]["nullable"] is True
    assert columns["persona_notes"]["nullable"] is True
    assert columns["persona_name"]["nullable"] is False
    assert columns["persona_role_summary"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        persona.create_persona(
            s, name="Bad", role_summary="r", identifier="PER-1"
        )


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        row = persona.create_persona(
            s, name="Explicit", role_summary="r", identifier="PER-042"
        )
    assert row["persona_identifier"] == "PER-042"


def test_post_without_identifier_auto_assigns_sequence(v2_env):
    with session_scope() as s:
        first = persona.create_persona(s, name="A", role_summary="r")
        second = persona.create_persona(s, name="B", role_summary="r")
    assert first["persona_identifier"] == "PER-001"
    assert second["persona_identifier"] == "PER-002"


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness(v2_env):
    with session_scope() as s:
        persona.create_persona(
            s, name="Mentor Coordinator", role_summary="r"
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        persona.create_persona(
            s, name="MENTOR COORDINATOR", role_summary="r2"
        )


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    """A soft-deleted row no longer reserves its name."""
    with session_scope() as s:
        persona.create_persona(s, name="Mentor", role_summary="r")
    with session_scope() as s:
        persona.delete_persona(s, "PER-001")
    with session_scope() as s:
        row = persona.create_persona(s, name="MENTOR", role_summary="r2")
    assert row["persona_name"] == "MENTOR"


# ---------------------------------------------------------------------------
# Criterion 4 — status enum + transition validation
# ---------------------------------------------------------------------------


def test_status_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        persona.create_persona(
            s, name="X", role_summary="r", status="archived"
        )


def test_default_status_is_candidate(v2_env):
    with session_scope() as s:
        row = persona.create_persona(s, name="X", role_summary="r")
    assert row["persona_status"] == "candidate"


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
        persona.create_persona(s, name="T", role_summary="r", status=start)
    with session_scope() as s:
        row = persona.patch_persona(s, "PER-001", status=target)
    assert row["persona_status"] == target


@pytest.mark.parametrize("start", ["confirmed", "deferred"])
def test_regression_to_candidate_rejected(v2_env, start):
    with session_scope() as s:
        persona.create_persona(s, name="T", role_summary="r", status=start)
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        persona.patch_persona(s, "PER-001", status="candidate")
    assert exc.value.from_status == start
    assert exc.value.to_status == "candidate"


def test_no_op_status_change_is_permitted(v2_env):
    with session_scope() as s:
        persona.create_persona(
            s, name="T", role_summary="r", status="confirmed"
        )
    with session_scope() as s:
        row = persona.patch_persona(s, "PER-001", status="confirmed")
    assert row["persona_status"] == "confirmed"


# ---------------------------------------------------------------------------
# Criterion 5 — the eight repository methods (happy path + an error case)
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_personas",
        "get_persona",
        "create_persona",
        "update_persona",
        "patch_persona",
        "delete_persona",
        "restore_persona",
        "next_persona_identifier",
    ):
        assert callable(getattr(persona, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        created = persona.create_persona(
            s,
            name="Mentor",
            role_summary="A person who provides mentoring guidance",
            responsibilities="- Approves applications\n- Pairs mentees",
            notes="consultant scratchpad",
        )
    assert created["persona_identifier"] == "PER-001"
    with session_scope() as s:
        fetched = persona.get_persona(s, "PER-001")
    assert fetched["persona_name"] == "Mentor"
    assert fetched["persona_notes"] == "consultant scratchpad"
    assert fetched["persona_responsibilities"].startswith("- Approves")


def test_get_persona_missing_returns_none(v2_env):
    with session_scope() as s:
        assert persona.get_persona(s, "PER-404") is None


def test_list_personas_orders_by_identifier(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="B", role_summary="r")
        persona.create_persona(s, name="A", role_summary="r")
        persona.create_persona(s, name="C", role_summary="r")
    with session_scope() as s:
        ids = [p["persona_identifier"] for p in persona.list_personas(s)]
    assert ids == ["PER-001", "PER-002", "PER-003"]


def test_update_persona_full_replace(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="Old", role_summary="or")
    with session_scope() as s:
        row = persona.update_persona(
            s,
            "PER-001",
            persona_identifier="PER-001",
            name="New",
            role_summary="nr",
            responsibilities="now has resp",
            notes="now has notes",
            status="confirmed",
        )
    assert row["persona_name"] == "New"
    assert row["persona_responsibilities"] == "now has resp"
    assert row["persona_notes"] == "now has notes"
    assert row["persona_status"] == "confirmed"


def test_update_persona_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s, pytest.raises(UnprocessableError):
        persona.update_persona(
            s,
            "PER-001",
            persona_identifier="PER-999",
            name="X",
            role_summary="r",
            status="candidate",
        )


def test_patch_persona_partial(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s:
        row = persona.patch_persona(
            s, "PER-001", role_summary="updated summary"
        )
    assert row["persona_role_summary"] == "updated summary"
    assert row["persona_name"] == "X"


def test_patch_persona_clears_notes_when_explicit_null(v2_env):
    """PATCH with explicit ``notes=None`` clears the field."""
    with session_scope() as s:
        persona.create_persona(
            s, name="X", role_summary="r", notes="scratchpad"
        )
    with session_scope() as s:
        row = persona.patch_persona(s, "PER-001", notes=None)
    assert row["persona_notes"] is None


def test_patch_persona_unknown_field_rejected(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s, pytest.raises(UnprocessableError):
        persona.patch_persona(s, "PER-001", bogus="value")


def test_patch_persona_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        persona.patch_persona(s, "PER-404", role_summary="x")


def test_create_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        persona.create_persona(
            s, name="First", role_summary="r", identifier="PER-001"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        persona.create_persona(
            s, name="Second", role_summary="r", identifier="PER-001"
        )


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_persona_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert persona.next_persona_identifier(s) == "PER-001"


def test_next_persona_identifier_increments(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="A", role_summary="r")
        persona.create_persona(s, name="B", role_summary="r")
    with session_scope() as s:
        assert persona.next_persona_identifier(s) == "PER-003"


def test_next_persona_identifier_skips_soft_deleted(v2_env):
    """A soft-deleted row's identifier is not reused."""
    with session_scope() as s:
        persona.create_persona(s, name="A", role_summary="r")
        persona.create_persona(s, name="B", role_summary="r")
    with session_scope() as s:
        persona.delete_persona(s, "PER-002")
    with session_scope() as s:
        assert persona.next_persona_identifier(s) == "PER-003"


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    """The auto-assign retry recovers when the computed id is taken."""
    with session_scope() as s:
        persona.create_persona(
            s, name="First", role_summary="r", identifier="PER-001"
        )
    monkeypatch.setattr(persona, "next_persona_identifier", lambda _s: "PER-001")
    with session_scope() as s:
        row = persona.create_persona(s, name="Second", role_summary="r")
    assert row["persona_identifier"] == "PER-002"


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
                row = persona.create_persona(
                    s, name=f"Concurrent persona {index}", role_summary="r"
                )
            results.append(row["persona_identifier"])
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
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s:
        deleted = persona.delete_persona(s, "PER-001")
    assert deleted["persona_deleted_at"] is not None
    with session_scope() as s:
        assert persona.list_personas(s) == []
        assert len(persona.list_personas(s, include_deleted=True)) == 1
        assert persona.get_persona(s, "PER-001") is None
        assert (
            persona.get_persona(s, "PER-001", include_deleted=True) is not None
        )


def test_soft_delete_is_idempotent(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s:
        persona.delete_persona(s, "PER-001")
    with session_scope() as s:
        stored = persona.get_persona(s, "PER-001", include_deleted=True)
    with session_scope() as s:
        second = persona.delete_persona(s, "PER-001")
    assert second["persona_deleted_at"] is not None
    assert second["persona_deleted_at"] == stored["persona_deleted_at"]


def test_restore_clears_deleted_at(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s:
        persona.delete_persona(s, "PER-001")
    with session_scope() as s:
        restored = persona.restore_persona(s, "PER-001")
    assert restored["persona_deleted_at"] is None
    with session_scope() as s:
        assert len(persona.list_personas(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        persona.create_persona(s, name="X", role_summary="r")
    with session_scope() as s, pytest.raises(UnprocessableError):
        persona.restore_persona(s, "PER-001")


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        persona.delete_persona(s, "PER-404")


# ---------------------------------------------------------------------------
# Persona-specific — outbound references survive soft-delete (spec §3.4.6)
# ---------------------------------------------------------------------------


def test_soft_delete_does_not_cascade_scopes_or_realization_references(
    v2_env,
):
    """Soft-deleting a persona leaves both outbound reference kinds in place.

    Per ``persona.md`` §3.4.6 both ``persona_scopes_to_domain`` and
    ``persona_realized_as_entity`` references persist in the ``refs``
    table; they surface via the show-deleted toggle on either side.
    """
    with session_scope() as s:
        persona.create_persona(
            s, name="Volunteer Mentor", role_summary="r"
        )
        domain.create_domain(
            s, name="Mentor Recruitment", purpose="p", description="d"
        )
        entity.create_entity(s, name="Mentor", description="d")
        references.create(
            s,
            source_type="persona",
            source_id="PER-001",
            target_type="domain",
            target_id="DOM-001",
            relationship="persona_scopes_to_domain",
        )
        references.create(
            s,
            source_type="persona",
            source_id="PER-001",
            target_type="entity",
            target_id="ENT-001",
            relationship="persona_realized_as_entity",
        )
    with session_scope() as s:
        persona.delete_persona(s, "PER-001")
    with session_scope() as s:
        # Both outbound references still exist.
        touching = references.list_touching(
            s, entity_type="persona", entity_id="PER-001"
        )
        assert len(touching["as_source"]) == 2
        kinds = {r["relationship"] for r in touching["as_source"]}
        assert kinds == {
            "persona_scopes_to_domain",
            "persona_realized_as_entity",
        }
        from_domain = references.list_touching(
            s, entity_type="domain", entity_id="DOM-001"
        )
        assert len(from_domain["as_target"]) == 1
        from_entity = references.list_touching(
            s, entity_type="entity", entity_id="ENT-001"
        )
        assert len(from_entity["as_target"]) == 1


# ---------------------------------------------------------------------------
# Persona-specific — status independent of affiliation / realization (3.4.3)
# ---------------------------------------------------------------------------


def test_persona_status_change_does_not_consult_affiliated_domains(v2_env):
    """A persona's status transition never depends on its affiliations
    or realization.

    Per ``persona.md`` §3.4.3 the lifecycles are managed independently:
    a persona scoped to a ``deferred`` domain and realized as a
    ``deferred`` entity can still be ``confirmed``, and changing the
    upstream statuses never cascades to the persona.
    """
    with session_scope() as s:
        persona.create_persona(s, name="Program Manager", role_summary="r")
        domain.create_domain(
            s, name="Fundraising", purpose="p", description="d"
        )
        entity.create_entity(s, name="Staff", description="d")
        references.create(
            s,
            source_type="persona",
            source_id="PER-001",
            target_type="domain",
            target_id="DOM-001",
            relationship="persona_scopes_to_domain",
        )
        references.create(
            s,
            source_type="persona",
            source_id="PER-001",
            target_type="entity",
            target_id="ENT-001",
            relationship="persona_realized_as_entity",
        )
    # The affiliated domain and the realization entity each move to
    # ``deferred``.
    with session_scope() as s:
        domain.patch_domain(s, "DOM-001", status="deferred")
        entity.patch_entity(s, "ENT-001", status="deferred")
    # The persona can still be confirmed — its status is its own field.
    with session_scope() as s:
        row = persona.patch_persona(s, "PER-001", status="confirmed")
    assert row["persona_status"] == "confirmed"
    # And neither upstream status was touched by the persona change.
    with session_scope() as s:
        assert domain.get_domain(s, "DOM-001")["domain_status"] == "deferred"
        assert entity.get_entity(s, "ENT-001")["entity_status"] == "deferred"
