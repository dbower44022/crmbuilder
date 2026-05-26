"""Test spec repository tests — PI-004 cohort closer (v0.5+).

Covers ``test_spec.md`` §3.7 acceptance criteria 1-10 / 15:
schema migration shape, identifier-format constraint, case-insensitive
global name uniqueness, three-status methodology enum + transition
validation, four-value outcome enum + UNRESTRICTED transitions, the
§3.4.4 cross-field invariant on ``last_run_at`` / outcome / notes, the
eight standard repository methods plus the :func:`record_run`
convenience helper (happy path + at least one error case each),
identifier auto-assignment, soft-delete / restore round-trip, and
vocab-registration smoke for the three outbound relationship kinds.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import entity, test_spec
from crmbuilder_v2.access.repositories import references as refs_repo
from sqlalchemy import inspect


def _seed_kwargs(**overrides):
    """Defaults for a test_spec create call."""
    base = {
        "name": "Mentor application submission produces confirmation email",
        "description": "Verifies the mentor-application happy path.",
        "steps": "1. Open form. 2. Fill required fields. 3. Submit.",
        "expected": "Confirmation email arrives at the applicant's address within 2 minutes.",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_test_specs_table_has_fifteen_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "test_specs" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("test_specs")}
    expected = {
        "test_spec_identifier": "VARCHAR",
        "test_spec_name": "VARCHAR",
        "test_spec_description": "TEXT",
        "test_spec_setup": "TEXT",
        "test_spec_steps": "TEXT",
        "test_spec_expected": "TEXT",
        "test_spec_notes": "TEXT",
        "test_spec_status": "VARCHAR",
        "test_spec_last_run_outcome": "VARCHAR",
        "test_spec_last_run_at": "DATETIME",
        "test_spec_last_run_notes": "TEXT",
        "test_spec_created_at": "DATETIME",
        "test_spec_updated_at": "DATETIME",
        "test_spec_deleted_at": "DATETIME",
    }
    assert set(columns) == set(expected)
    for name, affinity in expected.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = inspector.get_pk_constraint("test_specs")
    assert pk["constrained_columns"] == ["test_spec_identifier"]
    # Setup / notes / last_run_at / last_run_notes nullable; the rest
    # required.
    assert columns["test_spec_setup"]["nullable"] is True
    assert columns["test_spec_notes"]["nullable"] is True
    assert columns["test_spec_last_run_at"]["nullable"] is True
    assert columns["test_spec_last_run_notes"]["nullable"] is True
    assert columns["test_spec_deleted_at"]["nullable"] is True
    assert columns["test_spec_name"]["nullable"] is False
    assert columns["test_spec_description"]["nullable"] is False
    assert columns["test_spec_steps"]["nullable"] is False
    assert columns["test_spec_expected"]["nullable"] is False
    assert columns["test_spec_status"]["nullable"] is False
    assert columns["test_spec_last_run_outcome"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criteria 2 / 9 — identifier format + auto-assignment
# ---------------------------------------------------------------------------


def test_create_with_minimum_fields_assigns_identifier(v2_env):
    with session_scope() as s:
        row = test_spec.create_test_spec(s, **_seed_kwargs())
    assert row["test_spec_identifier"] == "TST-001"


def test_create_with_explicit_identifier_then_collision(v2_env):
    with session_scope() as s:
        test_spec.create_test_spec(
            s, **_seed_kwargs(identifier="TST-042")
        )
    with session_scope() as s, pytest.raises(ConflictError):
        test_spec.create_test_spec(
            s,
            **_seed_kwargs(
                name="Different name", identifier="TST-042"
            ),
        )


def test_create_rejects_malformed_identifier(v2_env):
    for bad in ("tst-001", "TST-1", "TS-001", "TST-1234"):
        with session_scope() as s, pytest.raises(UnprocessableError):
            test_spec.create_test_spec(
                s, **_seed_kwargs(name=f"name-{bad}", identifier=bad)
            )


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive name uniqueness
# ---------------------------------------------------------------------------


def test_create_rejects_duplicate_name_case_insensitive(v2_env):
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs(name="Mentor app"))
    with session_scope() as s, pytest.raises(UnprocessableError):
        test_spec.create_test_spec(s, **_seed_kwargs(name="MENTOR APP"))


# ---------------------------------------------------------------------------
# Criteria 4 / 5 — dual-axis enums + transitions
# ---------------------------------------------------------------------------


def test_create_defaults_status_and_outcome(v2_env):
    with session_scope() as s:
        row = test_spec.create_test_spec(s, **_seed_kwargs())
    assert row["test_spec_status"] == "candidate"
    assert row["test_spec_last_run_outcome"] == "not_run"
    assert row["test_spec_last_run_at"] is None
    assert row["test_spec_last_run_notes"] is None


def test_status_transition_valid(v2_env):
    """candidate → confirmed → deferred → confirmed all succeed."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs(name="A"))
    with session_scope() as s:
        test_spec.patch_test_spec(s, "TST-001", status="confirmed")
    with session_scope() as s:
        test_spec.patch_test_spec(s, "TST-001", status="deferred")
    with session_scope() as s:
        test_spec.patch_test_spec(s, "TST-001", status="confirmed")
    with session_scope() as s:
        row = test_spec.get_test_spec(s, "TST-001")
    assert row is not None and row["test_spec_status"] == "confirmed"


def test_status_transition_invalid_rejected(v2_env):
    """confirmed → candidate raises StatusTransitionError (propose-verify gate)."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs(name="A"))
        test_spec.patch_test_spec(s, "TST-001", status="confirmed")
    with session_scope() as s, pytest.raises(StatusTransitionError):
        test_spec.patch_test_spec(s, "TST-001", status="candidate")


def test_outcome_transitions_unrestricted(v2_env):
    """All four outcome values reachable from each other (§3.4.2)."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    sequence = ["passing", "failing", "skipped", "not_run", "passing"]
    for outcome in sequence:
        with session_scope() as s:
            row = test_spec.patch_test_spec(
                s, "TST-001", last_run_outcome=outcome
            )
        assert row["test_spec_last_run_outcome"] == outcome


# ---------------------------------------------------------------------------
# Criterion 6 — §3.4.4 cross-field invariant
# ---------------------------------------------------------------------------


def test_outcome_to_run_state_auto_sets_last_run_at(v2_env):
    """PATCH outcome=passing without last_run_at: server defaults to now()."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    before = datetime.now(UTC)
    with session_scope() as s:
        row = test_spec.patch_test_spec(
            s, "TST-001", last_run_outcome="passing"
        )
    after = datetime.now(UTC)
    assert row["test_spec_last_run_outcome"] == "passing"
    # ``to_dict`` serialises datetimes to ISO 8601 strings; parse back.
    last_at_str = row["test_spec_last_run_at"]
    assert last_at_str is not None
    last_at = datetime.fromisoformat(last_at_str)
    # last_at should fall within [before, after + slack].
    assert before - timedelta(seconds=5) <= last_at <= after + timedelta(
        seconds=5
    )


def test_outcome_to_run_state_with_explicit_last_run_at(v2_env):
    """PATCH outcome=passing + last_run_at supplied: server honors the value."""
    explicit = datetime(2026, 1, 15, 12, 30, 0, tzinfo=UTC)
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    with session_scope() as s:
        row = test_spec.patch_test_spec(
            s,
            "TST-001",
            last_run_outcome="passing",
            last_run_at=explicit,
        )
    # ``to_dict`` serialises to ISO 8601 string; compare round-tripped.
    assert (
        datetime.fromisoformat(row["test_spec_last_run_at"]) == explicit
    )


def test_outcome_to_run_state_with_explicit_null_last_run_at_rejected(v2_env):
    """PATCH outcome=passing + explicit last_run_at=None: 422."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(UnprocessableError):
        test_spec.patch_test_spec(
            s,
            "TST-001",
            last_run_outcome="passing",
            last_run_at=None,
        )


def test_outcome_to_not_run_clears_last_run_fields(v2_env):
    """PATCH outcome=not_run clears last_run_at AND last_run_notes."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
        test_spec.patch_test_spec(
            s,
            "TST-001",
            last_run_outcome="passing",
            last_run_notes="all good",
        )
    with session_scope() as s:
        row = test_spec.patch_test_spec(
            s, "TST-001", last_run_outcome="not_run"
        )
    assert row["test_spec_last_run_outcome"] == "not_run"
    assert row["test_spec_last_run_at"] is None
    assert row["test_spec_last_run_notes"] is None


# ---------------------------------------------------------------------------
# record_run convenience helper (§3.8.1)
# ---------------------------------------------------------------------------


def test_record_run_helper_success(v2_env):
    """record_run sets outcome + auto-sets last_run_at + records notes."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    with session_scope() as s:
        row = test_spec.record_run(
            s, "TST-001", outcome="passing", notes="ok"
        )
    assert row["test_spec_last_run_outcome"] == "passing"
    assert row["test_spec_last_run_at"] is not None
    assert row["test_spec_last_run_notes"] == "ok"


def test_record_run_helper_resets_to_not_run(v2_env):
    """record_run with outcome=not_run clears all three; notes arg ignored."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
        test_spec.record_run(
            s, "TST-001", outcome="failing", notes="step 4 timed out"
        )
    with session_scope() as s:
        row = test_spec.record_run(
            s, "TST-001", outcome="not_run", notes="ignored on reset"
        )
    assert row["test_spec_last_run_outcome"] == "not_run"
    assert row["test_spec_last_run_at"] is None
    assert row["test_spec_last_run_notes"] is None


def test_record_run_helper_invalid_outcome_rejected(v2_env):
    """record_run with a non-enum outcome value raises 422."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(UnprocessableError):
        test_spec.record_run(s, "TST-001", outcome="nope")


# ---------------------------------------------------------------------------
# Soft-delete / restore (§3.4.6)
# ---------------------------------------------------------------------------


def test_soft_delete_then_restore_round_trip(v2_env):
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
        test_spec.delete_test_spec(s, "TST-001")
    with session_scope() as s:
        # Default list excludes soft-deleted.
        rows = test_spec.list_test_specs(s)
        assert rows == []
        rows_all = test_spec.list_test_specs(s, include_deleted=True)
        assert len(rows_all) == 1
    with session_scope() as s:
        test_spec.restore_test_spec(s, "TST-001")
    with session_scope() as s:
        rows = test_spec.list_test_specs(s)
        assert len(rows) == 1


def test_restore_on_not_deleted_raises(v2_env):
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(UnprocessableError):
        test_spec.restore_test_spec(s, "TST-001")


def test_delete_missing_test_spec_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        test_spec.delete_test_spec(s, "TST-404")


def test_soft_delete_does_not_cascade_outgoing_refs(v2_env):
    """Soft-deleting a test_spec leaves its outbound references in place."""
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
        entity.create_entity(
            s,
            name="Mentor Application",
            description="An entity for testing cascade behavior.",
        )
    with session_scope() as s:
        refs_repo.create(
            s,
            source_type="test_spec",
            source_id="TST-001",
            target_type="entity",
            target_id="ENT-001",
            relationship="test_spec_touches_entity",
        )
    with session_scope() as s:
        test_spec.delete_test_spec(s, "TST-001")
    with session_scope() as s:
        # The reference row persists despite the source being soft-deleted.
        rows = refs_repo.list_all(s)
        kept = [
            r
            for r in rows
            if r.get("source_type") == "test_spec"
            and r.get("source_id") == "TST-001"
        ]
    assert len(kept) == 1
    # The repository row dict uses key ``relationship`` (the access
    # layer renames ``relationship_kind`` on read per
    # ``references.py:_row_dict``).
    assert kept[0]["relationship"] == "test_spec_touches_entity"


# ---------------------------------------------------------------------------
# next_test_spec_identifier
# ---------------------------------------------------------------------------


def test_next_test_spec_identifier_empty_table(v2_env):
    with session_scope() as s:
        assert test_spec.next_test_spec_identifier(s) == "TST-001"


def test_next_test_spec_identifier_after_create(v2_env):
    with session_scope() as s:
        test_spec.create_test_spec(s, **_seed_kwargs())
    with session_scope() as s:
        assert test_spec.next_test_spec_identifier(s) == "TST-002"


# ---------------------------------------------------------------------------
# Vocab registrations (criterion 15)
# ---------------------------------------------------------------------------


def test_test_spec_in_entity_types():
    from crmbuilder_v2.access.vocab import ENTITY_TYPES

    assert "test_spec" in ENTITY_TYPES


def test_three_outbound_kinds_registered():
    from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS

    for kind in (
        "test_spec_touches_entity",
        "test_spec_touches_field",
        "test_spec_exercises_process",
    ):
        assert kind in REFERENCE_RELATIONSHIPS


def test_kinds_for_pair_admits_live_targets():
    from crmbuilder_v2.access.vocab import _kinds_for_pair

    assert "test_spec_touches_entity" in _kinds_for_pair(
        "test_spec", "entity"
    )
    assert "test_spec_touches_field" in _kinds_for_pair(
        "test_spec", "field"
    )
    assert "test_spec_exercises_process" in _kinds_for_pair(
        "test_spec", "process"
    )


def test_requirement_test_spec_pair_now_active():
    """The previously-dormant requirement→test_spec clause is now live."""
    from crmbuilder_v2.access.vocab import _kinds_for_pair

    assert "requirement_verified_by_test_spec" in _kinds_for_pair(
        "requirement", "test_spec"
    )
