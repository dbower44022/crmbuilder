"""CRM Candidate repository tests — UI v0.4 slice E.

Covers ``crm_candidate.md`` section 3.7 acceptance criteria 1–8:
schema migration shape, identifier-format constraint, case-insensitive
engagement-global name uniqueness, status enum + terminal-state
transition validation, singleton-``selected`` enforcement on three
operations, the eight repository methods (happy path + at least one
error case each), identifier auto-assignment under concurrency, and
the soft-delete / restore round-trip including the singleton-blocked
restore case.
"""

from __future__ import annotations

import threading

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    SelectedCandidateConflictError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import crm_candidate
from sqlalchemy import inspect

# Expected ``crm_candidates`` columns and their SQLite affinities (criterion 1).
_EXPECTED_COLUMNS = {
    "crm_candidate_identifier": "VARCHAR",
    "crm_candidate_name": "VARCHAR",
    "crm_candidate_status": "VARCHAR",
    "crm_candidate_fit_reason": "TEXT",
    "crm_candidate_notes": "TEXT",
    "crm_candidate_created_at": "DATETIME",
    "crm_candidate_updated_at": "DATETIME",
    "crm_candidate_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_crm_candidates_table_has_eight_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "crm_candidates" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("crm_candidates")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = inspector.get_pk_constraint("crm_candidates")
    assert pk["constrained_columns"] == ["crm_candidate_identifier", "engagement_id"]
    assert columns["crm_candidate_deleted_at"]["nullable"] is True
    assert columns["crm_candidate_notes"]["nullable"] is True
    assert columns["crm_candidate_name"]["nullable"] is False
    assert columns["crm_candidate_fit_reason"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        crm_candidate.create_crm_candidate(
            s,
            name="Bad",
            fit_reason="fr",
            identifier="CRM-1",
        )


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        row = crm_candidate.create_crm_candidate(
            s,
            name="Explicit",
            fit_reason="fr",
            identifier="CRM-042",
        )
    assert row["crm_candidate_identifier"] == "CRM-042"


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="EspoCRM", fit_reason="fr")
    with session_scope() as s, pytest.raises(UnprocessableError):
        crm_candidate.create_crm_candidate(s, name="espocrm", fit_reason="fr2")


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    """A soft-deleted row no longer reserves its name."""
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="EspoCRM", fit_reason="fr")
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-001")
    with session_scope() as s:
        row = crm_candidate.create_crm_candidate(
            s, name="ESPOCRM", fit_reason="fr2"
        )
    assert row["crm_candidate_name"] == "ESPOCRM"


# ---------------------------------------------------------------------------
# Criterion 4 — status enum + terminal-state transitions
# ---------------------------------------------------------------------------


def test_status_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        crm_candidate.create_crm_candidate(
            s, name="X", fit_reason="fr", status="archived"
        )


def test_default_status_is_active(v2_env):
    with session_scope() as s:
        row = crm_candidate.create_crm_candidate(
            s, name="X", fit_reason="fr"
        )
    assert row["crm_candidate_status"] == "active"


@pytest.mark.parametrize("target", ["selected", "declined", "removed"])
def test_active_can_transition_to_any_terminal(v2_env, target):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s:
        row = crm_candidate.patch_crm_candidate(
            s, "CRM-001", status=target
        )
    assert row["crm_candidate_status"] == target


@pytest.mark.parametrize("start", ["selected", "declined", "removed"])
@pytest.mark.parametrize(
    "target", ["active", "selected", "declined", "removed"]
)
def test_no_transitions_out_of_terminal_states(v2_env, start, target):
    """Every terminal state has no valid successors (other than itself).

    The same-value case (e.g. selected → selected) is a no-op and
    permitted; every other transition raises StatusTransitionError.
    """
    if start == target:
        # No-op transitions are always permitted by spec; covered
        # separately in test_no_op_status_change_is_permitted.
        return
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="X", fit_reason="fr", status=start
        )
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        crm_candidate.patch_crm_candidate(s, "CRM-001", status=target)
    assert exc.value.from_status == start
    assert exc.value.to_status == target


def test_no_op_status_change_is_permitted(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="X", fit_reason="fr", status="declined"
        )
    with session_scope() as s:
        row = crm_candidate.patch_crm_candidate(
            s, "CRM-001", status="declined"
        )
    assert row["crm_candidate_status"] == "declined"


# ---------------------------------------------------------------------------
# Criterion 5 — singleton-`selected` constraint on three operations
# ---------------------------------------------------------------------------


def test_create_second_selected_rejected(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
    with session_scope() as s, pytest.raises(
        SelectedCandidateConflictError
    ) as exc:
        crm_candidate.create_crm_candidate(
            s, name="B", fit_reason="fr", status="selected"
        )
    assert exc.value.existing_identifier == "CRM-001"


def test_patch_into_selected_rejected_when_one_exists(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
        crm_candidate.create_crm_candidate(s, name="B", fit_reason="fr")
    with session_scope() as s, pytest.raises(
        SelectedCandidateConflictError
    ) as exc:
        crm_candidate.patch_crm_candidate(
            s, "CRM-002", status="selected"
        )
    assert exc.value.existing_identifier == "CRM-001"


def test_put_into_selected_rejected_when_one_exists(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
        crm_candidate.create_crm_candidate(s, name="B", fit_reason="fr")
    with session_scope() as s, pytest.raises(
        SelectedCandidateConflictError
    ):
        crm_candidate.update_crm_candidate(
            s,
            "CRM-002",
            crm_candidate_identifier="CRM-002",
            name="B",
            fit_reason="fr",
            status="selected",
        )


def test_restore_selected_rejected_when_another_selected_live(v2_env):
    """Restoring a soft-deleted selected record fails if another is live."""
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-001")
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="B", fit_reason="fr", status="selected"
        )
    with session_scope() as s, pytest.raises(
        SelectedCandidateConflictError
    ) as exc:
        crm_candidate.restore_crm_candidate(s, "CRM-001")
    assert exc.value.existing_identifier == "CRM-002"


def test_soft_delete_selected_frees_singleton_slot(v2_env):
    """Soft-deleting a `selected` record permits another to take selected."""
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
        crm_candidate.create_crm_candidate(s, name="B", fit_reason="fr")
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-001")
    with session_scope() as s:
        row = crm_candidate.patch_crm_candidate(
            s, "CRM-002", status="selected"
        )
    assert row["crm_candidate_status"] == "selected"


def test_restore_selected_permitted_when_no_other_selected(v2_env):
    """A soft-deleted `selected` record restores when the slot is free."""
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-001")
    with session_scope() as s:
        row = crm_candidate.restore_crm_candidate(s, "CRM-001")
    assert row["crm_candidate_status"] == "selected"
    assert row["crm_candidate_deleted_at"] is None


def test_no_op_re_put_of_selected_record_is_permitted(v2_env):
    """PUT-ing an already-selected record with the same status doesn't
    trigger the singleton check."""
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="A", fit_reason="fr", status="selected"
        )
    with session_scope() as s:
        row = crm_candidate.update_crm_candidate(
            s,
            "CRM-001",
            crm_candidate_identifier="CRM-001",
            name="A",
            fit_reason="fr",
            status="selected",
        )
    assert row["crm_candidate_status"] == "selected"


# ---------------------------------------------------------------------------
# Criterion 6 — the eight repository methods (happy path + an error case)
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_crm_candidates",
        "get_crm_candidate",
        "create_crm_candidate",
        "update_crm_candidate",
        "patch_crm_candidate",
        "delete_crm_candidate",
        "restore_crm_candidate",
        "next_crm_candidate_identifier",
    ):
        assert callable(getattr(crm_candidate, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        created = crm_candidate.create_crm_candidate(
            s,
            name="EspoCRM",
            fit_reason="Open source, self-hostable, strong customization",
            notes="consultant scratchpad",
        )
    assert created["crm_candidate_identifier"] == "CRM-001"
    with session_scope() as s:
        fetched = crm_candidate.get_crm_candidate(s, "CRM-001")
    assert fetched["crm_candidate_name"] == "EspoCRM"
    assert fetched["crm_candidate_notes"] == "consultant scratchpad"


def test_get_missing_returns_none(v2_env):
    with session_scope() as s:
        assert crm_candidate.get_crm_candidate(s, "CRM-404") is None


def test_list_orders_by_identifier(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="B", fit_reason="fr")
        crm_candidate.create_crm_candidate(s, name="A", fit_reason="fr")
        crm_candidate.create_crm_candidate(s, name="C", fit_reason="fr")
    with session_scope() as s:
        ids = [
            r["crm_candidate_identifier"]
            for r in crm_candidate.list_crm_candidates(s)
        ]
    assert ids == ["CRM-001", "CRM-002", "CRM-003"]


def test_update_full_replace(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="Old", fit_reason="ofr")
    with session_scope() as s:
        row = crm_candidate.update_crm_candidate(
            s,
            "CRM-001",
            crm_candidate_identifier="CRM-001",
            name="New",
            fit_reason="nfr",
            notes="now noted",
            status="declined",
        )
    assert row["crm_candidate_name"] == "New"
    assert row["crm_candidate_notes"] == "now noted"
    assert row["crm_candidate_status"] == "declined"


def test_update_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s, pytest.raises(UnprocessableError):
        crm_candidate.update_crm_candidate(
            s,
            "CRM-001",
            crm_candidate_identifier="CRM-999",
            name="X",
            fit_reason="fr",
            status="active",
        )


def test_patch_partial(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s:
        row = crm_candidate.patch_crm_candidate(
            s, "CRM-001", fit_reason="sharpened reason"
        )
    assert row["crm_candidate_fit_reason"] == "sharpened reason"
    assert row["crm_candidate_name"] == "X"


def test_patch_unknown_field_rejected(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s, pytest.raises(UnprocessableError):
        crm_candidate.patch_crm_candidate(s, "CRM-001", bogus="value")


def test_patch_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        crm_candidate.patch_crm_candidate(s, "CRM-404", fit_reason="x")


def test_create_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="First", fit_reason="fr", identifier="CRM-001"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        crm_candidate.create_crm_candidate(
            s, name="Second", fit_reason="fr", identifier="CRM-001"
        )


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert crm_candidate.next_crm_candidate_identifier(s) == "CRM-001"


def test_next_identifier_increments(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="A", fit_reason="fr")
        crm_candidate.create_crm_candidate(s, name="B", fit_reason="fr")
    with session_scope() as s:
        assert crm_candidate.next_crm_candidate_identifier(s) == "CRM-003"


def test_next_identifier_skips_soft_deleted(v2_env):
    """A soft-deleted row's identifier is not reused."""
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="A", fit_reason="fr")
        crm_candidate.create_crm_candidate(s, name="B", fit_reason="fr")
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-002")
    with session_scope() as s:
        assert crm_candidate.next_crm_candidate_identifier(s) == "CRM-003"


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(
            s, name="First", fit_reason="fr", identifier="CRM-001"
        )
    monkeypatch.setattr(
        crm_candidate, "next_crm_candidate_identifier", lambda _s: "CRM-001"
    )
    with session_scope() as s:
        row = crm_candidate.create_crm_candidate(
            s, name="Second", fit_reason="fr"
        )
    assert row["crm_candidate_identifier"] == "CRM-002"


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
                row = crm_candidate.create_crm_candidate(
                    s,
                    name=f"Concurrent {index}",
                    fit_reason="fr",
                )
            results.append(row["crm_candidate_identifier"])
        except Exception as exc:  # noqa: BLE001
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
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s:
        deleted = crm_candidate.delete_crm_candidate(s, "CRM-001")
    assert deleted["crm_candidate_deleted_at"] is not None
    with session_scope() as s:
        assert crm_candidate.list_crm_candidates(s) == []
        assert (
            len(crm_candidate.list_crm_candidates(s, include_deleted=True))
            == 1
        )
        assert crm_candidate.get_crm_candidate(s, "CRM-001") is None
        assert (
            crm_candidate.get_crm_candidate(
                s, "CRM-001", include_deleted=True
            )
            is not None
        )


def test_soft_delete_is_idempotent(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-001")
    with session_scope() as s:
        stored = crm_candidate.get_crm_candidate(
            s, "CRM-001", include_deleted=True
        )
    with session_scope() as s:
        second = crm_candidate.delete_crm_candidate(s, "CRM-001")
    assert second["crm_candidate_deleted_at"] is not None
    assert (
        second["crm_candidate_deleted_at"]
        == stored["crm_candidate_deleted_at"]
    )


def test_restore_clears_deleted_at(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s:
        crm_candidate.delete_crm_candidate(s, "CRM-001")
    with session_scope() as s:
        restored = crm_candidate.restore_crm_candidate(s, "CRM-001")
    assert restored["crm_candidate_deleted_at"] is None
    with session_scope() as s:
        assert len(crm_candidate.list_crm_candidates(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        crm_candidate.create_crm_candidate(s, name="X", fit_reason="fr")
    with session_scope() as s, pytest.raises(UnprocessableError):
        crm_candidate.restore_crm_candidate(s, "CRM-001")


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        crm_candidate.delete_crm_candidate(s, "CRM-404")
