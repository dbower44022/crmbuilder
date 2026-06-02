"""Domain repository tests — UI v0.4 slice B.

Covers ``domain.md`` section 3.7 acceptance criteria 1–5 and 8:
schema migration shape, identifier-format constraint, case-insensitive
name uniqueness, status enum + transition validation, the eight
repository methods (happy path + at least one error case each),
identifier auto-assignment under concurrency, and the soft-delete /
restore round-trip.
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
from crmbuilder_v2.access.repositories import domain
from sqlalchemy import inspect

# Expected ``domains`` columns and their SQLite affinities (criterion 1).
_EXPECTED_COLUMNS = {
    "domain_identifier": "VARCHAR",
    "domain_name": "VARCHAR",
    "domain_status": "VARCHAR",
    "domain_purpose": "TEXT",
    "domain_description": "TEXT",
    "domain_notes": "TEXT",
    "domain_created_at": "DATETIME",
    "domain_updated_at": "DATETIME",
    "domain_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_domains_table_has_nine_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "domains" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("domains")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    # Primary key is the prefixed-string identifier; no surrogate ``id``.
    pk = inspector.get_pk_constraint("domains")
    assert pk["constrained_columns"] == ["domain_identifier"]
    # Soft-delete and timestamp nullability per the spec.
    assert columns["domain_deleted_at"]["nullable"] is True
    assert columns["domain_notes"]["nullable"] is True
    assert columns["domain_name"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        domain.create_domain(
            s,
            name="Bad",
            purpose="p",
            description="d",
            identifier="DOM-1",
        )


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        row = domain.create_domain(
            s,
            name="Explicit",
            purpose="p",
            description="d",
            identifier="DOM-042",
        )
    assert row["domain_identifier"] == "DOM-042"


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="Mentoring", purpose="p", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        domain.create_domain(s, name="mentoring", purpose="p2", description="d2")


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    """A soft-deleted row no longer reserves its name."""
    with session_scope() as s:
        domain.create_domain(s, name="Mentoring", purpose="p", description="d")
    with session_scope() as s:
        domain.delete_domain(s, "DOM-001")
    with session_scope() as s:
        row = domain.create_domain(
            s, name="MENTORING", purpose="p2", description="d2"
        )
    assert row["domain_name"] == "MENTORING"


# ---------------------------------------------------------------------------
# Criterion 4 — status enum + transition validation
# ---------------------------------------------------------------------------


def test_status_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        domain.create_domain(
            s, name="X", purpose="p", description="d", status="archived"
        )


def test_default_status_is_candidate(v2_env):
    with session_scope() as s:
        row = domain.create_domain(s, name="X", purpose="p", description="d")
    assert row["domain_status"] == "candidate"


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
        domain.create_domain(
            s, name="T", purpose="p", description="d", status=start
        )
    with session_scope() as s:
        row = domain.patch_domain(s, "DOM-001", status=target)
    assert row["domain_status"] == target


@pytest.mark.parametrize("start", ["confirmed", "deferred"])
def test_regression_to_candidate_rejected(v2_env, start):
    with session_scope() as s:
        domain.create_domain(
            s, name="T", purpose="p", description="d", status=start
        )
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        domain.patch_domain(s, "DOM-001", status="candidate")
    assert exc.value.from_status == start
    assert exc.value.to_status == "candidate"


def test_no_op_status_change_is_permitted(v2_env):
    with session_scope() as s:
        domain.create_domain(
            s, name="T", purpose="p", description="d", status="confirmed"
        )
    with session_scope() as s:
        row = domain.patch_domain(s, "DOM-001", status="confirmed")
    assert row["domain_status"] == "confirmed"


# ---------------------------------------------------------------------------
# Criterion 5 — the eight repository methods (happy path + an error case)
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_domains",
        "get_domain",
        "create_domain",
        "update_domain",
        "patch_domain",
        "delete_domain",
        "restore_domain",
        "next_domain_identifier",
    ):
        assert callable(getattr(domain, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        created = domain.create_domain(
            s,
            name="Mentoring",
            purpose="Why the mission needs it",
            description="The kinds of work it covers",
            notes="consultant scratchpad",
        )
    assert created["domain_identifier"] == "DOM-001"
    with session_scope() as s:
        fetched = domain.get_domain(s, "DOM-001")
    assert fetched["domain_name"] == "Mentoring"
    assert fetched["domain_notes"] == "consultant scratchpad"


def test_get_domain_missing_returns_none(v2_env):
    with session_scope() as s:
        assert domain.get_domain(s, "DOM-404") is None


def test_list_domains_orders_by_identifier(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="B", purpose="p", description="d")
        domain.create_domain(s, name="A", purpose="p", description="d")
        domain.create_domain(s, name="C", purpose="p", description="d")
    with session_scope() as s:
        ids = [d["domain_identifier"] for d in domain.list_domains(s)]
    assert ids == ["DOM-001", "DOM-002", "DOM-003"]


def test_update_domain_full_replace(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="Old", purpose="op", description="od")
    with session_scope() as s:
        row = domain.update_domain(
            s,
            "DOM-001",
            domain_identifier="DOM-001",
            name="New",
            purpose="np",
            description="nd",
            notes="now has notes",
            status="confirmed",
        )
    assert row["domain_name"] == "New"
    assert row["domain_notes"] == "now has notes"
    assert row["domain_status"] == "confirmed"


def test_update_domain_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        domain.update_domain(
            s,
            "DOM-001",
            domain_identifier="DOM-999",
            name="X",
            purpose="p",
            description="d",
            status="candidate",
        )


def test_patch_domain_partial(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s:
        row = domain.patch_domain(s, "DOM-001", purpose="updated purpose")
    assert row["domain_purpose"] == "updated purpose"
    assert row["domain_name"] == "X"


def test_patch_domain_unknown_field_rejected(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        domain.patch_domain(s, "DOM-001", bogus="value")


def test_patch_domain_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        domain.patch_domain(s, "DOM-404", purpose="x")


def test_create_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        domain.create_domain(
            s, name="First", purpose="p", description="d", identifier="DOM-001"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        domain.create_domain(
            s, name="Second", purpose="p", description="d", identifier="DOM-001"
        )


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_domain_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert domain.next_domain_identifier(s) == "DOM-001"


def test_next_domain_identifier_increments(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="A", purpose="p", description="d")
        domain.create_domain(s, name="B", purpose="p", description="d")
    with session_scope() as s:
        assert domain.next_domain_identifier(s) == "DOM-003"


def test_next_domain_identifier_skips_soft_deleted(v2_env):
    """A soft-deleted row's identifier is not reused."""
    with session_scope() as s:
        domain.create_domain(s, name="A", purpose="p", description="d")
        domain.create_domain(s, name="B", purpose="p", description="d")
    with session_scope() as s:
        domain.delete_domain(s, "DOM-002")
    with session_scope() as s:
        assert domain.next_domain_identifier(s) == "DOM-003"


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    """The auto-assign retry recovers when the computed id is taken.

    Pre-create ``DOM-001``, then force ``next_domain_identifier`` to
    return that already-taken value. ``_insert_with_autoassign`` must
    catch the IntegrityError, increment, and land on ``DOM-002``.
    """
    with session_scope() as s:
        domain.create_domain(
            s, name="First", purpose="p", description="d", identifier="DOM-001"
        )
    monkeypatch.setattr(domain, "next_domain_identifier", lambda _s: "DOM-001")
    with session_scope() as s:
        row = domain.create_domain(s, name="Second", purpose="p", description="d")
    assert row["domain_identifier"] == "DOM-002"


def test_concurrent_creates_assign_distinct_identifiers(v2_env):
    """Eight simultaneous create calls never share an identifier."""
    results: list[str] = []
    errors: list[Exception] = []

    def worker(index: int) -> None:
        try:
            with session_scope() as s:
                row = domain.create_domain(
                    s,
                    name=f"Concurrent domain {index}",
                    purpose="p",
                    description="d",
                )
            results.append(row["domain_identifier"])
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
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s:
        deleted = domain.delete_domain(s, "DOM-001")
    assert deleted["domain_deleted_at"] is not None
    with session_scope() as s:
        assert domain.list_domains(s) == []
        assert (
            len(domain.list_domains(s, include_deleted=True)) == 1
        )
        assert domain.get_domain(s, "DOM-001") is None
        assert (
            domain.get_domain(s, "DOM-001", include_deleted=True) is not None
        )


def test_soft_delete_is_idempotent(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s:
        domain.delete_domain(s, "DOM-001")
    with session_scope() as s:
        stored = domain.get_domain(s, "DOM-001", include_deleted=True)
    with session_scope() as s:
        second = domain.delete_domain(s, "DOM-001")
    # Re-DELETE on an already-soft-deleted row is a no-op: it returns
    # the record with its original ``domain_deleted_at`` unchanged.
    assert second["domain_deleted_at"] is not None
    assert second["domain_deleted_at"] == stored["domain_deleted_at"]


def test_restore_clears_deleted_at(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s:
        domain.delete_domain(s, "DOM-001")
    with session_scope() as s:
        restored = domain.restore_domain(s, "DOM-001")
    assert restored["domain_deleted_at"] is None
    with session_scope() as s:
        assert len(domain.list_domains(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        domain.create_domain(s, name="X", purpose="p", description="d")
    with session_scope() as s, pytest.raises(UnprocessableError):
        domain.restore_domain(s, "DOM-001")


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        domain.delete_domain(s, "DOM-404")
