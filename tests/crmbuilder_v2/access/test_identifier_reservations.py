"""Identifier reservation tests (PI-078)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError, ValidationError
from crmbuilder_v2.access.models import IdentifierReservation
from crmbuilder_v2.access.repositories import identifier_reservations as res
from crmbuilder_v2.access.repositories import planning_items


def test_reserve_block_from_empty(v2_env):
    with session_scope() as s:
        out = res.reserve(s, entity_type="planning_item", count=3)
    assert out["reserved"] == ["PI-001", "PI-002", "PI-003"]
    assert out["head_after"] == "PI-004"


def test_reservation_accounts_for_existing_rows(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-005", title="x",
            item_type="open_question", status="Draft",
            executive_summary=(
                "This planning item reconciles stale test fixtures with the "
                "current governance schema so the suite validates real "
                "behavior; it carries no production code change and exists "
                "purely to keep the regression net aligned with the PI-073 "
                "and PI-102 data-model decisions now in effect."
            ),
        )
    with session_scope() as s:
        out = res.reserve(s, entity_type="planning_item", count=2)
    assert out["reserved"] == ["PI-006", "PI-007"]


def test_two_reservations_do_not_overlap(v2_env):
    with session_scope() as s:
        first = res.reserve(s, entity_type="planning_item", count=2)
    with session_scope() as s:
        second = res.reserve(s, entity_type="planning_item", count=2)
    assert first["reserved"] == ["PI-001", "PI-002"]
    assert second["reserved"] == ["PI-003", "PI-004"]


def test_active_reservation_blocks_but_expired_does_not(v2_env):
    now = datetime.now(UTC)
    # An expired hold at a high number must NOT block (TTL auto-release).
    with session_scope() as s:
        s.add(
            IdentifierReservation(
                entity_type="planning_item",
                reserved_identifiers=["PI-500"],
                max_number=500,
                reserved_by="CONV-1",
                reserved_at=now - timedelta(hours=2),
                expires_at=now - timedelta(hours=1),
            )
        )
    with session_scope() as s:
        out = res.reserve(s, entity_type="planning_item", count=1)
    assert out["reserved"] == ["PI-001"]

    # An active hold at a high number MUST block.
    with session_scope() as s:
        s.add(
            IdentifierReservation(
                entity_type="planning_item",
                reserved_identifiers=["PI-900"],
                max_number=900,
                reserved_by="CONV-2",
                reserved_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
    with session_scope() as s:
        out = res.reserve(s, entity_type="planning_item", count=1)
    assert out["reserved"] == ["PI-901"]


def test_reserved_by_recorded(v2_env):
    with session_scope() as s:
        out = res.reserve(
            s, entity_type="planning_item", count=1, reserved_by="CONV-77"
        )
    assert out["reserved_by"] == "CONV-77"


def test_session_prefix_and_width(v2_env):
    with session_scope() as s:
        out = res.reserve(s, entity_type="session", count=1)
    assert out["reserved"] == ["SES-001"]


def test_unknown_entity_type_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        res.reserve(s, entity_type="not_a_type", count=1)


@pytest.mark.parametrize("bad", [0, -1, res._MAX_COUNT + 1])
def test_invalid_count_rejected(v2_env, bad):
    with session_scope() as s, pytest.raises(ValidationError):
        res.reserve(s, entity_type="planning_item", count=bad)
