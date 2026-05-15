"""Process repository tests — UI v0.4 slice D.

Covers ``process.md`` section 3.7 acceptance criteria 1–9: schema
migration shape, identifier-format constraint, case-insensitive
engagement-global name uniqueness, classification enum + transition
validation, domain-FK validation, the eight repository methods (happy
path + at least one error case each), identifier auto-assignment under
concurrency, and the soft-delete / restore round-trip.

Process-specific assertions per the slice prompt: the one-way
``unclassified`` classification gate, domain-FK validation rejecting
missing/soft-deleted/mal-formed targets, and soft-deleting a process
leaving its ``process_hands_off_to_process`` references in place.
"""

from __future__ import annotations

import threading

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ClassificationTransitionError,
    ConflictError,
    InvalidDomainReferenceError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import domain, process, references
from sqlalchemy import inspect

# Expected ``processes`` columns and their SQLite affinities (criterion 1).
_EXPECTED_COLUMNS = {
    "process_identifier": "VARCHAR",
    "process_name": "VARCHAR",
    "process_domain_identifier": "VARCHAR",
    "process_purpose": "TEXT",
    "process_classification": "VARCHAR",
    "process_classification_rationale": "TEXT",
    "process_notes": "TEXT",
    "process_created_at": "DATETIME",
    "process_updated_at": "DATETIME",
    "process_deleted_at": "DATETIME",
}


def _seed_domain(s, name: str = "Mentoring") -> str:
    """Create a live domain and return its identifier."""
    row = domain.create_domain(s, name=name, purpose="p", description="d")
    return row["domain_identifier"]


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_processes_table_has_ten_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "processes" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("processes")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = inspector.get_pk_constraint("processes")
    assert pk["constrained_columns"] == ["process_identifier"]
    assert columns["process_deleted_at"]["nullable"] is True
    assert columns["process_classification_rationale"]["nullable"] is True
    assert columns["process_notes"]["nullable"] is True
    assert columns["process_name"]["nullable"] is False
    assert columns["process_domain_identifier"]["nullable"] is False
    # No process_status column per DEC-056.
    assert "process_status" not in columns


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        process.create_process(
            s,
            name="Bad",
            domain_identifier=dom,
            purpose="p",
            identifier="PROC-1",
        )


def test_well_formed_explicit_identifier_accepted(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    with session_scope() as s:
        row = process.create_process(
            s,
            name="Explicit",
            domain_identifier=dom,
            purpose="p",
            identifier="PROC-042",
        )
    assert row["process_identifier"] == "PROC-042"


# ---------------------------------------------------------------------------
# Criterion 3 — engagement-global case-insensitive name uniqueness
# ---------------------------------------------------------------------------


def test_case_insensitive_name_uniqueness_is_engagement_global(v2_env):
    """Name uniqueness ignores domain — a clash across domains still fails."""
    with session_scope() as s:
        dom_a = _seed_domain(s, "Mentoring")
        dom_b = _seed_domain(s, "Fundraising")
        process.create_process(
            s, name="Recruit", domain_identifier=dom_a, purpose="p"
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        process.create_process(
            s, name="recruit", domain_identifier=dom_b, purpose="p"
        )


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s, name="Recruit", domain_identifier=dom, purpose="p"
        )
    with session_scope() as s:
        process.delete_process(s, "PROC-001")
    with session_scope() as s:
        row = process.create_process(
            s, name="RECRUIT", domain_identifier=dom, purpose="p"
        )
    assert row["process_name"] == "RECRUIT"


# ---------------------------------------------------------------------------
# Criterion 4 — classification enum + transition validation
# ---------------------------------------------------------------------------


def test_classification_enum_rejects_unknown_value(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        process.create_process(
            s,
            name="X",
            domain_identifier=dom,
            purpose="p",
            classification="critical",
        )


def test_default_classification_is_unclassified(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    with session_scope() as s:
        row = process.create_process(
            s, name="X", domain_identifier=dom, purpose="p"
        )
    assert row["process_classification"] == "unclassified"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("unclassified", "mission_critical"),
        ("unclassified", "supporting"),
        ("unclassified", "deferred"),
        ("mission_critical", "supporting"),
        ("mission_critical", "deferred"),
        ("supporting", "mission_critical"),
        ("supporting", "deferred"),
        ("deferred", "mission_critical"),
        ("deferred", "supporting"),
    ],
)
def test_valid_classification_transitions_permitted(v2_env, start, target):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s,
            name="T",
            domain_identifier=dom,
            purpose="p",
            classification=start,
        )
    with session_scope() as s:
        row = process.patch_process(s, "PROC-001", classification=target)
    assert row["process_classification"] == target


@pytest.mark.parametrize(
    "start", ["mission_critical", "supporting", "deferred"]
)
def test_regression_to_unclassified_rejected(v2_env, start):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s,
            name="T",
            domain_identifier=dom,
            purpose="p",
            classification=start,
        )
    with session_scope() as s, pytest.raises(
        ClassificationTransitionError
    ) as exc:
        process.patch_process(s, "PROC-001", classification="unclassified")
    assert exc.value.from_classification == start
    assert exc.value.to_classification == "unclassified"


# ---------------------------------------------------------------------------
# Criterion 5 — domain-FK validation
# ---------------------------------------------------------------------------


def test_create_with_nonexistent_domain_rejected(v2_env):
    with session_scope() as s, pytest.raises(
        InvalidDomainReferenceError
    ) as exc:
        process.create_process(
            s, name="X", domain_identifier="DOM-404", purpose="p"
        )
    assert exc.value.domain_identifier == "DOM-404"


def test_create_with_malformed_domain_rejected(v2_env):
    with session_scope() as s, pytest.raises(InvalidDomainReferenceError):
        process.create_process(
            s, name="X", domain_identifier="not-a-dom", purpose="p"
        )


def test_create_with_soft_deleted_domain_rejected(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    with session_scope() as s:
        domain.delete_domain(s, dom)
    with session_scope() as s, pytest.raises(InvalidDomainReferenceError):
        process.create_process(
            s, name="X", domain_identifier=dom, purpose="p"
        )


def test_create_with_live_domain_succeeds(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    with session_scope() as s:
        row = process.create_process(
            s, name="X", domain_identifier=dom, purpose="p"
        )
    assert row["process_domain_identifier"] == dom


def test_patch_with_invalid_domain_rejected(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s, name="X", domain_identifier=dom, purpose="p"
        )
    with session_scope() as s, pytest.raises(InvalidDomainReferenceError):
        process.patch_process(s, "PROC-001", domain_identifier="DOM-404")


def test_patch_re_affiliates_to_a_different_live_domain(v2_env):
    with session_scope() as s:
        dom_a = _seed_domain(s, "Mentoring")
        dom_b = _seed_domain(s, "Fundraising")
        process.create_process(
            s, name="X", domain_identifier=dom_a, purpose="p"
        )
    with session_scope() as s:
        row = process.patch_process(s, "PROC-001", domain_identifier=dom_b)
    assert row["process_domain_identifier"] == dom_b


# ---------------------------------------------------------------------------
# Criterion 6 — the eight repository methods (happy path + an error case)
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_processes",
        "get_process",
        "create_process",
        "update_process",
        "patch_process",
        "delete_process",
        "restore_process",
        "next_process_identifier",
    ):
        assert callable(getattr(process, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        created = process.create_process(
            s,
            name="Mentor Recruit",
            domain_identifier=dom,
            purpose="Bring mentors into the program",
            classification="mission_critical",
            classification_rationale="Mission stalls without mentors",
            notes="consultant scratchpad",
        )
    assert created["process_identifier"] == "PROC-001"
    with session_scope() as s:
        fetched = process.get_process(s, "PROC-001")
    assert fetched["process_name"] == "Mentor Recruit"
    assert fetched["process_classification"] == "mission_critical"
    assert fetched["process_classification_rationale"] == (
        "Mission stalls without mentors"
    )


def test_get_process_missing_returns_none(v2_env):
    with session_scope() as s:
        assert process.get_process(s, "PROC-404") is None


def test_list_processes_orders_by_identifier(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="B", domain_identifier=dom, purpose="p")
        process.create_process(s, name="A", domain_identifier=dom, purpose="p")
        process.create_process(s, name="C", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        ids = [p["process_identifier"] for p in process.list_processes(s)]
    assert ids == ["PROC-001", "PROC-002", "PROC-003"]


def test_update_process_full_replace(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s, name="Old", domain_identifier=dom, purpose="op"
        )
    with session_scope() as s:
        row = process.update_process(
            s,
            "PROC-001",
            process_identifier="PROC-001",
            name="New",
            domain_identifier=dom,
            purpose="np",
            classification="supporting",
            classification_rationale="not on the critical path",
            notes="now has notes",
        )
    assert row["process_name"] == "New"
    assert row["process_classification"] == "supporting"
    assert row["process_notes"] == "now has notes"


def test_update_process_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s, pytest.raises(UnprocessableError):
        process.update_process(
            s,
            "PROC-001",
            process_identifier="PROC-999",
            name="X",
            domain_identifier=dom,
            purpose="p",
            classification="unclassified",
        )


def test_patch_process_partial(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        row = process.patch_process(s, "PROC-001", purpose="updated purpose")
    assert row["process_purpose"] == "updated purpose"
    assert row["process_name"] == "X"


def test_patch_process_unknown_field_rejected(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s, pytest.raises(UnprocessableError):
        process.patch_process(s, "PROC-001", bogus="value")


def test_patch_process_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        process.patch_process(s, "PROC-404", purpose="x")


def test_create_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s,
            name="First",
            domain_identifier=dom,
            purpose="p",
            identifier="PROC-001",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        process.create_process(
            s,
            name="Second",
            domain_identifier=dom,
            purpose="p",
            identifier="PROC-001",
        )


# ---------------------------------------------------------------------------
# Criterion 8 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_process_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert process.next_process_identifier(s) == "PROC-001"


def test_next_process_identifier_increments(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="A", domain_identifier=dom, purpose="p")
        process.create_process(s, name="B", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        assert process.next_process_identifier(s) == "PROC-003"


def test_next_process_identifier_skips_soft_deleted(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="A", domain_identifier=dom, purpose="p")
        process.create_process(s, name="B", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        process.delete_process(s, "PROC-002")
    with session_scope() as s:
        assert process.next_process_identifier(s) == "PROC-003"


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s,
            name="First",
            domain_identifier=dom,
            purpose="p",
            identifier="PROC-001",
        )
    monkeypatch.setattr(
        process, "next_process_identifier", lambda _s: "PROC-001"
    )
    with session_scope() as s:
        row = process.create_process(
            s, name="Second", domain_identifier=dom, purpose="p"
        )
    assert row["process_identifier"] == "PROC-002"


def test_concurrent_creates_assign_distinct_identifiers(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
    results: list[str] = []
    errors: list[Exception] = []

    def worker(index: int) -> None:
        try:
            with session_scope() as s:
                row = process.create_process(
                    s,
                    name=f"Concurrent process {index}",
                    domain_identifier=dom,
                    purpose="p",
                )
            results.append(row["process_identifier"])
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
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        deleted = process.delete_process(s, "PROC-001")
    assert deleted["process_deleted_at"] is not None
    with session_scope() as s:
        assert process.list_processes(s) == []
        assert len(process.list_processes(s, include_deleted=True)) == 1
        assert process.get_process(s, "PROC-001") is None
        assert (
            process.get_process(s, "PROC-001", include_deleted=True)
            is not None
        )


def test_soft_delete_is_idempotent(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        process.delete_process(s, "PROC-001")
    with session_scope() as s:
        stored = process.get_process(s, "PROC-001", include_deleted=True)
    with session_scope() as s:
        second = process.delete_process(s, "PROC-001")
    assert second["process_deleted_at"] is not None
    assert second["process_deleted_at"] == stored["process_deleted_at"]


def test_restore_clears_deleted_at(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s:
        process.delete_process(s, "PROC-001")
    with session_scope() as s:
        restored = process.restore_process(s, "PROC-001")
    assert restored["process_deleted_at"] is None
    with session_scope() as s:
        assert len(process.list_processes(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(s, name="X", domain_identifier=dom, purpose="p")
    with session_scope() as s, pytest.raises(UnprocessableError):
        process.restore_process(s, "PROC-001")


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        process.delete_process(s, "PROC-404")


# ---------------------------------------------------------------------------
# Criterion 7 / 14 — soft-delete does not cascade handoff references
# ---------------------------------------------------------------------------


def test_soft_delete_does_not_cascade_handoff_references(v2_env):
    """Soft-deleting a process leaves its handoff edges in place.

    Per ``process.md`` section 3.4.5 the ``process_hands_off_to_process``
    references — inbound and outbound — persist in the ``refs`` table;
    they surface via the show-deleted toggle on either side.
    """
    with session_scope() as s:
        dom = _seed_domain(s)
        process.create_process(
            s, name="Upstream", domain_identifier=dom, purpose="p"
        )
        process.create_process(
            s, name="Downstream", domain_identifier=dom, purpose="p"
        )
        references.create(
            s,
            source_type="process",
            source_id="PROC-001",
            target_type="process",
            target_id="PROC-002",
            relationship="process_hands_off_to_process",
        )
    # Soft-delete the producer (source side of the handoff).
    with session_scope() as s:
        process.delete_process(s, "PROC-001")
    with session_scope() as s:
        from_source = references.list_touching(
            s, entity_type="process", entity_id="PROC-001"
        )
        assert len(from_source["as_source"]) == 1
        from_target = references.list_touching(
            s, entity_type="process", entity_id="PROC-002"
        )
        assert len(from_target["as_target"]) == 1
