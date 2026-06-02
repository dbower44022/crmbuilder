"""Requirement repository tests — PI-004 cohort (v0.5+).

Covers ``requirement.md`` §3.7 acceptance criteria 1–9 / 14:
schema migration shape, identifier-format constraint, case-insensitive
global name uniqueness, MoSCoW priority enum + default + unconstrained
transitions, status enum + transition validation, the eight repository
methods (happy path + at least one error case each), identifier
auto-assignment under concurrency, soft-delete / restore round-trip,
and vocab-registration smoke for all five outbound relationship kinds.
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
from crmbuilder_v2.access.repositories import requirement
from sqlalchemy import inspect

# Expected ``requirements`` columns and their SQLite affinities (criterion 1).
_EXPECTED_COLUMNS = {
    "requirement_identifier": "VARCHAR",
    "requirement_name": "VARCHAR",
    "requirement_description": "TEXT",
    "requirement_acceptance_summary": "TEXT",
    "requirement_priority": "VARCHAR",
    "requirement_status": "VARCHAR",
    "requirement_notes": "TEXT",
    "requirement_created_at": "DATETIME",
    "requirement_updated_at": "DATETIME",
    "requirement_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_requirements_table_has_ten_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "requirements" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("requirements")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    # Primary key is the prefixed-string identifier; no surrogate ``id``.
    pk = inspector.get_pk_constraint("requirements")
    assert pk["constrained_columns"] == ["requirement_identifier", "engagement_id"]
    # Soft-delete and notes nullability per the spec.
    assert columns["requirement_deleted_at"]["nullable"] is True
    assert columns["requirement_notes"]["nullable"] is True
    assert columns["requirement_name"]["nullable"] is False
    assert columns["requirement_description"]["nullable"] is False
    assert columns["requirement_acceptance_summary"]["nullable"] is False
    assert columns["requirement_priority"]["nullable"] is False
    assert columns["requirement_status"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.create_requirement(
            s,
            name="Bad",
            description="d",
            acceptance_summary="a",
            identifier="REQ-1",
        )


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        row = requirement.create_requirement(
            s,
            name="Explicit",
            description="d",
            acceptance_summary="a",
            identifier="REQ-042",
        )
    assert row["requirement_identifier"] == "REQ-042"


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive global name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="Capture mentor slots", description="d",
            acceptance_summary="a",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.create_requirement(
            s, name="CAPTURE mentor SLOTS", description="d2",
            acceptance_summary="a2",
        )


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    """A soft-deleted row no longer reserves its name."""
    with session_scope() as s:
        requirement.create_requirement(
            s, name="Capture slots", description="d",
            acceptance_summary="a",
        )
    with session_scope() as s:
        requirement.delete_requirement(s, "REQ-001")
    with session_scope() as s:
        row = requirement.create_requirement(
            s, name="CAPTURE SLOTS", description="d2",
            acceptance_summary="a2",
        )
    assert row["requirement_name"] == "CAPTURE SLOTS"


# ---------------------------------------------------------------------------
# Criterion 4 — MoSCoW priority enum + default + unrestricted transitions
# ---------------------------------------------------------------------------


def test_default_priority_is_should(v2_env):
    with session_scope() as s:
        row = requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    assert row["requirement_priority"] == "should"


def test_priority_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
            priority="maybe",
        )


@pytest.mark.parametrize("priority", ["must", "should", "could", "wont"])
def test_all_four_moscow_priorities_accepted_on_create(v2_env, priority):
    with session_scope() as s:
        row = requirement.create_requirement(
            s, name=f"X-{priority}", description="d",
            acceptance_summary="a", priority=priority,
        )
    assert row["requirement_priority"] == priority


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("should", "must"),
        ("must", "wont"),
        ("could", "should"),
        ("wont", "must"),
    ],
)
def test_priority_transitions_are_unconstrained(v2_env, start, target):
    """Per spec §3.2.3 priority has no transition rules — any-to-any."""
    with session_scope() as s:
        requirement.create_requirement(
            s, name="P", description="d", acceptance_summary="a",
            priority=start,
        )
    with session_scope() as s:
        row = requirement.patch_requirement(s, "REQ-001", priority=target)
    assert row["requirement_priority"] == target


# ---------------------------------------------------------------------------
# Criterion 5 — status enum + transition validation
# ---------------------------------------------------------------------------


def test_status_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
            status="archived",
        )


def test_default_status_is_candidate(v2_env):
    with session_scope() as s:
        row = requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    assert row["requirement_status"] == "candidate"


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
        requirement.create_requirement(
            s, name="T", description="d", acceptance_summary="a",
            status=start,
        )
    with session_scope() as s:
        row = requirement.patch_requirement(s, "REQ-001", status=target)
    assert row["requirement_status"] == target


@pytest.mark.parametrize("start", ["confirmed", "deferred"])
def test_regression_to_candidate_rejected(v2_env, start):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="T", description="d", acceptance_summary="a",
            status=start,
        )
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        requirement.patch_requirement(s, "REQ-001", status="candidate")
    assert exc.value.from_status == start
    assert exc.value.to_status == "candidate"


# ---------------------------------------------------------------------------
# Criterion 6 — the eight repository methods
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_requirements",
        "get_requirement",
        "create_requirement",
        "update_requirement",
        "patch_requirement",
        "delete_requirement",
        "restore_requirement",
        "next_requirement_identifier",
    ):
        assert callable(getattr(requirement, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        created = requirement.create_requirement(
            s,
            name="Capture mentor availability slots",
            description="When a mentor registers, capture their weekly windows.",
            acceptance_summary=(
                "A mentor record carries at least one availability "
                "window after registration."
            ),
            priority="must",
            notes="consultant scratchpad",
        )
    assert created["requirement_identifier"] == "REQ-001"
    assert created["requirement_priority"] == "must"
    with session_scope() as s:
        fetched = requirement.get_requirement(s, "REQ-001")
    assert (
        fetched["requirement_name"] == "Capture mentor availability slots"
    )
    assert fetched["requirement_notes"] == "consultant scratchpad"
    assert (
        fetched["requirement_acceptance_summary"].startswith(
            "A mentor record"
        )
    )


def test_update_requirement_full_replace(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="Old", description="od", acceptance_summary="oa",
        )
    with session_scope() as s:
        row = requirement.update_requirement(
            s,
            "REQ-001",
            requirement_identifier="REQ-001",
            name="New",
            description="nd",
            acceptance_summary="na",
            priority="must",
            notes="now has notes",
            status="confirmed",
        )
    assert row["requirement_name"] == "New"
    assert row["requirement_notes"] == "now has notes"
    assert row["requirement_status"] == "confirmed"
    assert row["requirement_priority"] == "must"


def test_update_requirement_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.update_requirement(
            s,
            "REQ-001",
            requirement_identifier="REQ-999",
            name="X",
            description="d",
            acceptance_summary="a",
            priority="should",
            status="candidate",
        )


def test_patch_requirement_partial(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s:
        row = requirement.patch_requirement(
            s, "REQ-001", description="sharpened description"
        )
    assert row["requirement_description"] == "sharpened description"
    assert row["requirement_name"] == "X"


def test_patch_requirement_unknown_field_rejected(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.patch_requirement(s, "REQ-001", bogus="value")


def test_patch_requirement_acceptance_summary(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="initial",
        )
    with session_scope() as s:
        row = requirement.patch_requirement(
            s, "REQ-001", acceptance_summary="sharpened acceptance"
        )
    assert (
        row["requirement_acceptance_summary"] == "sharpened acceptance"
    )


def test_patch_requirement_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        requirement.patch_requirement(s, "REQ-404", description="x")


def test_create_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="First", description="d", acceptance_summary="a",
            identifier="REQ-001",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        requirement.create_requirement(
            s, name="Second", description="d", acceptance_summary="a",
            identifier="REQ-001",
        )


def test_list_requirements_orders_by_identifier(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="B", description="d", acceptance_summary="a",
        )
        requirement.create_requirement(
            s, name="A", description="d", acceptance_summary="a",
        )
        requirement.create_requirement(
            s, name="C", description="d", acceptance_summary="a",
        )
    with session_scope() as s:
        ids = [
            r["requirement_identifier"]
            for r in requirement.list_requirements(s)
        ]
    assert ids == ["REQ-001", "REQ-002", "REQ-003"]


# ---------------------------------------------------------------------------
# Criterion 8 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_requirement_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert requirement.next_requirement_identifier(s) == "REQ-001"


def test_next_requirement_identifier_increments(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="A", description="d", acceptance_summary="a",
        )
        requirement.create_requirement(
            s, name="B", description="d", acceptance_summary="a",
        )
    with session_scope() as s:
        assert requirement.next_requirement_identifier(s) == "REQ-003"


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
                row = requirement.create_requirement(
                    s,
                    name=f"Concurrent requirement {index}",
                    description="d",
                    acceptance_summary="a",
                )
            results.append(row["requirement_identifier"])
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
# Criterion 9 — soft-delete / restore round-trip
# ---------------------------------------------------------------------------


def test_soft_delete_hides_from_default_list_and_get(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s:
        deleted = requirement.delete_requirement(s, "REQ-001")
    assert deleted["requirement_deleted_at"] is not None
    with session_scope() as s:
        assert requirement.list_requirements(s) == []
        assert (
            len(requirement.list_requirements(s, include_deleted=True)) == 1
        )
        assert requirement.get_requirement(s, "REQ-001") is None
        assert (
            requirement.get_requirement(s, "REQ-001", include_deleted=True)
            is not None
        )


def test_soft_delete_is_idempotent(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s:
        requirement.delete_requirement(s, "REQ-001")
    with session_scope() as s:
        second = requirement.delete_requirement(s, "REQ-001")
    assert second["requirement_deleted_at"] is not None


def test_restore_clears_deleted_at(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s:
        requirement.delete_requirement(s, "REQ-001")
    with session_scope() as s:
        restored = requirement.restore_requirement(s, "REQ-001")
    assert restored["requirement_deleted_at"] is None
    with session_scope() as s:
        assert len(requirement.list_requirements(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        requirement.create_requirement(
            s, name="X", description="d", acceptance_summary="a",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        requirement.restore_requirement(s, "REQ-001")


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        requirement.delete_requirement(s, "REQ-404")


# ---------------------------------------------------------------------------
# Criterion 14 — vocab registrations for the five outbound kinds
# ---------------------------------------------------------------------------


def test_requirement_in_entity_types():
    from crmbuilder_v2.access.vocab import ENTITY_TYPES

    assert "requirement" in ENTITY_TYPES


def test_all_five_relationship_kinds_registered():
    from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS

    for kind in (
        "requirement_scopes_to_domain",
        "requirement_touches_entity",
        "requirement_touches_field",
        "requirement_realized_by_process",
        "requirement_verified_by_test_spec",
    ):
        assert kind in REFERENCE_RELATIONSHIPS


def test_kinds_for_pair_admits_live_targets():
    from crmbuilder_v2.access.vocab import _kinds_for_pair

    # Four live target types — clauses active in _kinds_for_pair.
    assert "requirement_scopes_to_domain" in _kinds_for_pair(
        "requirement", "domain"
    )
    assert "requirement_touches_entity" in _kinds_for_pair(
        "requirement", "entity"
    )
    assert "requirement_touches_field" in _kinds_for_pair(
        "requirement", "field"
    )
    assert "requirement_realized_by_process" in _kinds_for_pair(
        "requirement", "process"
    )
