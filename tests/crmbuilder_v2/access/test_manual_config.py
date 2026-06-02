"""Manual config repository tests — PI-004 cohort (v0.5+).

Covers ``manual_config.md`` §3.7 acceptance criteria 1–10 / 15:
schema migration shape, identifier-format constraint, case-insensitive
global name uniqueness, category enum, four-status enum + transition
validation (including the new terminal ``completed``), the §3.5.3
cross-field invariant on transition into ``completed``, the eight
repository methods (happy path + at least one error case each),
identifier auto-assignment under concurrency, soft-delete / restore
round-trip, and vocab-registration smoke for all four outbound
relationship kinds.
"""

from __future__ import annotations

import threading

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    CompletedStatusRequiresCompletionFieldsError,
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import manual_config
from sqlalchemy import inspect


def _seed_kwargs(**overrides):
    """Defaults for a manual_config create call."""
    base = {
        "name": "Saved view: Mentors needing dues invoice",
        "category": "saved_view",
        "description": "Operator must hand-edit clientDefs/Contact.json.",
        "instructions": (
            "1. Admin → Entity Manager → Contact → Saved Views. "
            "2. Add the JSON snippet. 3. Save. 4. Clear Cache."
        ),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_manual_configs_table_has_twelve_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "manual_configs" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("manual_configs")}
    expected = {
        "manual_config_identifier": "VARCHAR",
        "manual_config_name": "VARCHAR",
        "manual_config_category": "VARCHAR",
        "manual_config_description": "TEXT",
        "manual_config_instructions": "TEXT",
        "manual_config_notes": "TEXT",
        "manual_config_status": "VARCHAR",
        "manual_config_completed_at": "DATETIME",
        "manual_config_completed_by": "TEXT",
        "manual_config_created_at": "DATETIME",
        "manual_config_updated_at": "DATETIME",
        "manual_config_deleted_at": "DATETIME",
        "engagement_id": "VARCHAR",
    }
    assert set(columns) == set(expected)
    for name, affinity in expected.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = inspector.get_pk_constraint("manual_configs")
    assert pk["constrained_columns"] == ["manual_config_identifier"]
    # Completion fields are nullable at storage; cross-field invariant
    # is enforced at the access layer per §3.5.3.
    assert columns["manual_config_completed_at"]["nullable"] is True
    assert columns["manual_config_completed_by"]["nullable"] is True
    assert columns["manual_config_notes"]["nullable"] is True
    assert columns["manual_config_deleted_at"]["nullable"] is True
    assert columns["manual_config_name"]["nullable"] is False
    assert columns["manual_config_category"]["nullable"] is False
    assert columns["manual_config_description"]["nullable"] is False
    assert columns["manual_config_instructions"]["nullable"] is False
    assert columns["manual_config_status"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criterion 2 — identifier format constraint
# ---------------------------------------------------------------------------


def test_create_assigns_identifier_when_omitted(v2_env):
    with session_scope() as s:
        row = manual_config.create_manual_config(s, **_seed_kwargs())
    assert row["manual_config_identifier"] == "MCF-001"


def test_create_explicit_identifier_persists(v2_env):
    with session_scope() as s:
        row = manual_config.create_manual_config(
            s, **_seed_kwargs(identifier="MCF-042")
        )
    assert row["manual_config_identifier"] == "MCF-042"


def test_create_explicit_identifier_format_validation(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.create_manual_config(
            s, **_seed_kwargs(identifier="MCF-1")
        )


def test_create_explicit_identifier_collision(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(
            s, **_seed_kwargs(identifier="MCF-001")
        )
    with session_scope() as s, pytest.raises(ConflictError):
        manual_config.create_manual_config(
            s, **_seed_kwargs(name="Second", identifier="MCF-001")
        )


# ---------------------------------------------------------------------------
# Criterion 3 — case-insensitive global name uniqueness
# ---------------------------------------------------------------------------


def test_create_duplicate_name_case_insensitive(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(
            s, **_seed_kwargs(name="Saved view foo")
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.create_manual_config(
            s, **_seed_kwargs(name="SAVED VIEW FOO")
        )


def test_name_uniqueness_ignores_soft_deleted(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(
            s, **_seed_kwargs(name="Saved view bar")
        )
    with session_scope() as s:
        manual_config.delete_manual_config(s, "MCF-001")
    with session_scope() as s:
        row = manual_config.create_manual_config(
            s, **_seed_kwargs(name="SAVED VIEW BAR")
        )
    assert row["manual_config_name"] == "SAVED VIEW BAR"


# ---------------------------------------------------------------------------
# Criterion 4 — category enum
# ---------------------------------------------------------------------------


def test_create_invalid_category(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.create_manual_config(
            s, **_seed_kwargs(category="bogus_category")
        )


@pytest.mark.parametrize(
    "category",
    [
        "saved_view",
        "duplicate_check",
        "workflow",
        "deferred_options_enum",
        "role_permission",
        "dynamic_logic",
        "other",
    ],
)
def test_all_seven_categories_accepted(v2_env, category):
    with session_scope() as s:
        row = manual_config.create_manual_config(
            s, **_seed_kwargs(name=f"X-{category}", category=category)
        )
    assert row["manual_config_category"] == category


# ---------------------------------------------------------------------------
# Criterion 5 — four-status enum + transition validation
# ---------------------------------------------------------------------------


def test_status_enum_rejects_unknown_value(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.create_manual_config(
            s, **_seed_kwargs(status="archived")
        )


def test_default_status_is_candidate(v2_env):
    with session_scope() as s:
        row = manual_config.create_manual_config(s, **_seed_kwargs())
    assert row["manual_config_status"] == "candidate"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("candidate", "confirmed"),
        ("candidate", "deferred"),
        ("confirmed", "deferred"),
        ("deferred", "confirmed"),
    ],
)
def test_valid_non_completed_transitions_permitted(v2_env, start, target):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status=start))
    with session_scope() as s:
        row = manual_config.patch_manual_config(s, "MCF-001", status=target)
    assert row["manual_config_status"] == target


def test_patch_candidate_to_completed_invalid_transition(v2_env):
    """Direct ``candidate → completed`` is rejected per §3.4.1."""
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        manual_config.patch_manual_config(
            s,
            "MCF-001",
            status="completed",
            completed_by="doug@example.com",
        )
    assert exc.value.from_status == "candidate"
    assert exc.value.to_status == "completed"


def test_patch_completed_to_anything_terminal(v2_env):
    """``completed`` is terminal — any non-no-op transition rejected."""
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
        manual_config.patch_manual_config(s, "MCF-001", status="confirmed")
        manual_config.patch_manual_config(
            s,
            "MCF-001",
            status="completed",
            completed_by="doug@example.com",
        )
    for target in ("candidate", "confirmed", "deferred"):
        with session_scope() as s, pytest.raises(StatusTransitionError):
            manual_config.patch_manual_config(s, "MCF-001", status=target)


def test_regression_to_candidate_rejected_from_confirmed(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="confirmed"))
    with session_scope() as s, pytest.raises(StatusTransitionError):
        manual_config.patch_manual_config(s, "MCF-001", status="candidate")


def test_deferred_to_completed_invalid(v2_env):
    """``deferred → completed`` skips required intermediate per §3.4.1."""
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="deferred"))
    with session_scope() as s, pytest.raises(StatusTransitionError):
        manual_config.patch_manual_config(
            s,
            "MCF-001",
            status="completed",
            completed_by="doug@example.com",
        )


# ---------------------------------------------------------------------------
# Criterion 6 — cross-field invariant on transition into ``completed``
# ---------------------------------------------------------------------------


def test_create_completed_without_completion_by(v2_env):
    """POST status=completed missing completed_by → dedicated error."""
    with session_scope() as s, pytest.raises(
        CompletedStatusRequiresCompletionFieldsError
    ) as exc:
        manual_config.create_manual_config(
            s, **_seed_kwargs(status="completed")
        )
    assert exc.value.missing == ["manual_config_completed_by"]


def test_create_completed_with_completion_fields_succeeds(v2_env):
    """POST status=completed with completed_by; completed_at server-defaulted."""
    with session_scope() as s:
        row = manual_config.create_manual_config(
            s,
            **_seed_kwargs(
                status="completed",
                completed_by="doug@example.com",
            ),
        )
    assert row["manual_config_status"] == "completed"
    assert row["manual_config_completed_by"] == "doug@example.com"
    assert row["manual_config_completed_at"] is not None


def test_patch_confirmed_to_completed_succeeds_with_fields(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="confirmed"))
    with session_scope() as s:
        row = manual_config.patch_manual_config(
            s,
            "MCF-001",
            status="completed",
            completed_by="doug@example.com",
        )
    assert row["manual_config_status"] == "completed"
    assert row["manual_config_completed_by"] == "doug@example.com"
    assert row["manual_config_completed_at"] is not None


def test_patch_confirmed_to_completed_without_completion_by(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="confirmed"))
    with session_scope() as s, pytest.raises(
        CompletedStatusRequiresCompletionFieldsError
    ) as exc:
        manual_config.patch_manual_config(
            s, "MCF-001", status="completed"
        )
    assert exc.value.missing == ["manual_config_completed_by"]


def test_patch_completed_by_only_on_record_already_completed(v2_env):
    """PATCH editing completed_by on an already-completed record succeeds."""
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="confirmed"))
        manual_config.patch_manual_config(
            s, "MCF-001", status="completed", completed_by="initial@x.com"
        )
    with session_scope() as s:
        row = manual_config.patch_manual_config(
            s, "MCF-001", completed_by="updated@x.com"
        )
    assert row["manual_config_completed_by"] == "updated@x.com"
    assert row["manual_config_status"] == "completed"


def test_patch_completion_fields_permitted_on_non_completed(v2_env):
    """Setting completion fields on a non-completed record is permitted (discouraged)."""
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="confirmed"))
    with session_scope() as s:
        row = manual_config.patch_manual_config(
            s, "MCF-001", completed_by="early@x.com"
        )
    # Permissive — the row carries the value without the status moving.
    assert row["manual_config_completed_by"] == "early@x.com"
    assert row["manual_config_status"] == "confirmed"


# ---------------------------------------------------------------------------
# Criterion 7 — the eight repository methods
# ---------------------------------------------------------------------------


def test_eight_repository_methods_exist():
    for name in (
        "list_manual_configs",
        "get_manual_config",
        "create_manual_config",
        "update_manual_config",
        "patch_manual_config",
        "delete_manual_config",
        "restore_manual_config",
        "next_manual_config_identifier",
    ):
        assert callable(getattr(manual_config, name)), name


def test_create_and_get_round_trip(v2_env):
    with session_scope() as s:
        created = manual_config.create_manual_config(
            s, **_seed_kwargs(notes="consultant scratchpad")
        )
    with session_scope() as s:
        fetched = manual_config.get_manual_config(
            s, created["manual_config_identifier"]
        )
    assert (
        fetched["manual_config_name"]
        == "Saved view: Mentors needing dues invoice"
    )
    assert fetched["manual_config_notes"] == "consultant scratchpad"


def test_update_manual_config_full_replace(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(name="Old"))
    with session_scope() as s:
        row = manual_config.update_manual_config(
            s,
            "MCF-001",
            manual_config_identifier="MCF-001",
            name="New",
            category="workflow",
            description="new description",
            instructions="new instructions",
            notes="now noted",
            status="confirmed",
        )
    assert row["manual_config_name"] == "New"
    assert row["manual_config_category"] == "workflow"
    assert row["manual_config_status"] == "confirmed"


def test_update_manual_config_identifier_mismatch_rejected(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.update_manual_config(
            s,
            "MCF-001",
            manual_config_identifier="MCF-999",
            name="X",
            category="other",
            description="d",
            instructions="i",
            status="candidate",
        )


def test_patch_manual_config_partial(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
    with session_scope() as s:
        row = manual_config.patch_manual_config(
            s, "MCF-001", description="sharpened description"
        )
    assert row["manual_config_description"] == "sharpened description"


def test_patch_manual_config_unknown_field_rejected(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.patch_manual_config(s, "MCF-001", bogus="value")


def test_get_missing_returns_none(v2_env):
    with session_scope() as s:
        assert manual_config.get_manual_config(s, "MCF-404") is None


def test_patch_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        manual_config.patch_manual_config(s, "MCF-404", description="x")


def test_list_orders_by_identifier(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(name="B"))
        manual_config.create_manual_config(s, **_seed_kwargs(name="A"))
        manual_config.create_manual_config(s, **_seed_kwargs(name="C"))
    with session_scope() as s:
        ids = [
            r["manual_config_identifier"]
            for r in manual_config.list_manual_configs(s)
        ]
    assert ids == ["MCF-001", "MCF-002", "MCF-003"]


# ---------------------------------------------------------------------------
# Criterion 9 — identifier auto-assignment under concurrency
# ---------------------------------------------------------------------------


def test_next_manual_config_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert manual_config.next_manual_config_identifier(s) == "MCF-001"


def test_concurrent_identifier_autoassign(v2_env):
    """Eight simultaneous create calls never share an identifier."""
    results: list[str] = []
    errors: list[Exception] = []

    def worker(index: int) -> None:
        try:
            with session_scope() as s:
                row = manual_config.create_manual_config(
                    s, **_seed_kwargs(name=f"Concurrent manual_config {index}")
                )
            results.append(row["manual_config_identifier"])
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
# Criterion 10 — soft-delete and restore round-trip
# ---------------------------------------------------------------------------


def test_delete_and_restore_round_trip(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
    with session_scope() as s:
        deleted = manual_config.delete_manual_config(s, "MCF-001")
    assert deleted["manual_config_deleted_at"] is not None
    with session_scope() as s:
        assert manual_config.list_manual_configs(s) == []
        assert (
            len(
                manual_config.list_manual_configs(s, include_deleted=True)
            )
            == 1
        )
        assert manual_config.get_manual_config(s, "MCF-001") is None
    with session_scope() as s:
        restored = manual_config.restore_manual_config(s, "MCF-001")
    assert restored["manual_config_deleted_at"] is None
    with session_scope() as s:
        assert len(manual_config.list_manual_configs(s)) == 1


def test_restore_on_live_record_rejected(v2_env):
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs())
    with session_scope() as s, pytest.raises(UnprocessableError):
        manual_config.restore_manual_config(s, "MCF-001")


def test_delete_completed_record_preserves_completion_fields(v2_env):
    """Soft-deleting a completed record keeps its completion fields."""
    with session_scope() as s:
        manual_config.create_manual_config(s, **_seed_kwargs(status="confirmed"))
        manual_config.patch_manual_config(
            s, "MCF-001", status="completed", completed_by="doug@x.com"
        )
    with session_scope() as s:
        manual_config.delete_manual_config(s, "MCF-001")
    with session_scope() as s:
        fetched = manual_config.get_manual_config(
            s, "MCF-001", include_deleted=True
        )
    assert fetched["manual_config_status"] == "completed"
    assert fetched["manual_config_completed_by"] == "doug@x.com"
    assert fetched["manual_config_completed_at"] is not None


# ---------------------------------------------------------------------------
# Criterion 15 — vocab registrations for the four outbound kinds
# ---------------------------------------------------------------------------


def test_manual_config_in_entity_types():
    from crmbuilder_v2.access.vocab import ENTITY_TYPES

    assert "manual_config" in ENTITY_TYPES


def test_all_four_relationship_kinds_registered():
    from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS

    for kind in (
        "manual_config_scopes_to_domain",
        "manual_config_touches_entity",
        "manual_config_touches_field",
        "manual_config_realizes_requirement",
    ):
        assert kind in REFERENCE_RELATIONSHIPS


def test_kinds_for_pair_admits_all_four_live_targets():
    from crmbuilder_v2.access.vocab import _kinds_for_pair

    assert "manual_config_scopes_to_domain" in _kinds_for_pair(
        "manual_config", "domain"
    )
    assert "manual_config_touches_entity" in _kinds_for_pair(
        "manual_config", "entity"
    )
    assert "manual_config_touches_field" in _kinds_for_pair(
        "manual_config", "field"
    )
    assert "manual_config_realizes_requirement" in _kinds_for_pair(
        "manual_config", "requirement"
    )
