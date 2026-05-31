"""Planning items repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import planning_items

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def test_create_and_resolve(v2_env):
    with session_scope() as s:
        planning_items.create(
            s,
            identifier="PI-005",
            title="Pacing dimension",
            item_type="planning_dimension",
            status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s:
        planning_items.update(
            s,
            "PI-005",
            status="Resolved",
            resolution_reference="DEC-013",
        )
    with session_scope() as s:
        row = planning_items.get(s, "PI-005")
    assert row["status"] == "Resolved"
    assert row["resolution_reference"] == "DEC-013"


def test_invalid_type(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        planning_items.create(
            s,
            identifier="PI-001",
            title="Bad",
            item_type="not_a_type",
            status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_upsert(v2_env):
    with session_scope() as s:
        planning_items.upsert(
            s,
            identifier="PI-007",
            title="t1",
            item_type="open_question",
            status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
        planning_items.upsert(
            s,
            identifier="PI-007",
            title="t2",
            item_type="open_question",
            status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s:
        rows = planning_items.list_all(s)
    assert len(rows) == 1
    assert rows[0]["title"] == "t2"


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    with session_scope() as s:
        row = planning_items.create(
            s, title="Auto", item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["identifier"] == "PI-001"
    with session_scope() as s:
        row2 = planning_items.create(
            s, title="Auto2", item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row2["identifier"] == "PI-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        row = planning_items.create(
            s, identifier="PI-042", title="Explicit",
            item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["identifier"] == "PI-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        planning_items.create(
            s, identifier="PI-1", title="Bad",
            item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_create_with_empty_string_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        planning_items.create(
            s, identifier="", title="Bad",
            item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-001", title="First",
            item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s, pytest.raises(ConflictError):
        planning_items.create(
            s, identifier="PI-001", title="Second",
            item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-001", title="First",
            item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    monkeypatch.setattr(
        planning_items, "compute_next_identifier", lambda _s: "PI-001"
    )
    with session_scope() as s:
        row = planning_items.create(
            s, title="Second", item_type="open_question", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["identifier"] == "PI-002"


# ---------------------------------------------------------------------------
# PI-076 — multi-valued, vocabulary-checked ``area`` field
# ---------------------------------------------------------------------------


def test_create_with_valid_area(v2_env):
    with session_scope() as s:
        row = planning_items.create(
            s, identifier="PI-010", title="Cross-cutting",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
            area=["access", "api"],
        )
    assert row["area"] == ["access", "api"]
    with session_scope() as s:
        fetched = planning_items.get(s, "PI-010")
    assert fetched["area"] == ["access", "api"]


def test_create_without_area_defaults_to_none(v2_env):
    with session_scope() as s:
        row = planning_items.create(
            s, identifier="PI-011", title="No area",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["area"] is None


def test_create_with_unknown_area_value_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        planning_items.create(
            s, identifier="PI-012", title="Bad area",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
            area=["access", "not-an-area"],
        )


def test_create_with_empty_area_list_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        planning_items.create(
            s, identifier="PI-013", title="Empty area",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
            area=[],
        )


def test_create_with_duplicate_area_values_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        planning_items.create(
            s, identifier="PI-014", title="Dup area",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
            area=["api", "api"],
        )


def test_create_with_non_string_area_element_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        planning_items.create(
            s, identifier="PI-015", title="Non-string area",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
            area=["api", 7],
        )


def test_update_area(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-016", title="Updatable",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
            area=["ui"],
        )
    with session_scope() as s:
        row = planning_items.update(s, "PI-016", area=["ui", "mcp"])
    assert row["area"] == ["ui", "mcp"]


def test_update_with_unknown_area_value_rejected(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-017", title="Updatable",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s, pytest.raises(ValidationError):
        planning_items.update(s, "PI-017", area=["bogus"])


def test_db_check_rejects_empty_array_directly(v2_env):
    """Belt-and-braces: the structural CHECK rejects an empty array even
    when the access-layer validator is bypassed (direct ORM insert)."""
    from sqlalchemy.exc import IntegrityError

    from crmbuilder_v2.access.models import PlanningItem

    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                PlanningItem(
                    identifier="PI-099",
                    title="Direct bad",
                    item_type="open_question",
                    description="",
                    status="Draft",
                    area=[],
                )
            )
            s.flush()


# ---------------------------------------------------------------------------
# PI-077 — claim / release (claimed_by / claimed_at)
# ---------------------------------------------------------------------------


def _seed(identifier: str = "PI-030") -> None:
    with session_scope() as s:
        planning_items.create(
            s, identifier=identifier, title="Claimable",
            item_type="pending_work", status="Draft",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_claim_sets_both_fields(v2_env):
    _seed("PI-030")
    with session_scope() as s:
        row = planning_items.claim_planning_item(s, "PI-030", "CONV-100")
    assert row["claimed_by"] == "CONV-100"
    assert row["claimed_at"] is not None


def test_claim_idempotent_for_same_claimant(v2_env):
    _seed("PI-031")
    with session_scope() as s:
        planning_items.claim_planning_item(s, "PI-031", "CONV-100")
    # Re-claim by the same claimant must not raise and must retain the claim.
    with session_scope() as s:
        again = planning_items.claim_planning_item(s, "PI-031", "CONV-100")
    assert again["claimed_by"] == "CONV-100"
    assert again["claimed_at"] is not None


def test_claim_conflict_for_different_claimant(v2_env):
    _seed("PI-032")
    with session_scope() as s:
        planning_items.claim_planning_item(s, "PI-032", "CONV-100")
    with session_scope() as s, pytest.raises(ConflictError):
        planning_items.claim_planning_item(s, "PI-032", "CONV-200")


def test_release_clears_fields(v2_env):
    _seed("PI-033")
    with session_scope() as s:
        planning_items.claim_planning_item(s, "PI-033", "CONV-100")
    with session_scope() as s:
        row = planning_items.release_planning_item(s, "PI-033", "CONV-100")
    assert row["claimed_by"] is None
    assert row["claimed_at"] is None


def test_release_wrong_claimant_raises_conflict(v2_env):
    _seed("PI-034")
    with session_scope() as s:
        planning_items.claim_planning_item(s, "PI-034", "CONV-100")
    with session_scope() as s, pytest.raises(ConflictError):
        planning_items.release_planning_item(s, "PI-034", "CONV-200")


def test_release_unclaimed_is_idempotent(v2_env):
    _seed("PI-035")
    with session_scope() as s:
        row = planning_items.release_planning_item(s, "PI-035")
    assert row["claimed_by"] is None


def test_db_check_rejects_half_claim(v2_env):
    """Belt-and-braces: the pairing CHECK rejects claimed_by without
    claimed_at when the access layer is bypassed (direct ORM insert)."""
    from datetime import UTC, datetime

    from sqlalchemy.exc import IntegrityError

    from crmbuilder_v2.access.models import PlanningItem

    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                PlanningItem(
                    identifier="PI-098",
                    title="Half claim",
                    item_type="open_question",
                    description="",
                    status="Draft",
                    claimed_by="CONV-1",
                    claimed_at=None,
                )
            )
            s.flush()

    # The inverse half is rejected too.
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                PlanningItem(
                    identifier="PI-097",
                    title="Half claim 2",
                    item_type="open_question",
                    description="",
                    status="Draft",
                    claimed_by=None,
                    claimed_at=datetime.now(UTC),
                )
            )
            s.flush()
