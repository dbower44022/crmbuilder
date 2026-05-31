"""Engagement-area repository + two-tier area validation tests (PI-112)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import engagement_areas, planning_items
from crmbuilder_v2.access.vocab import SYSTEM_AREAS

_EXEC = "PI-112 engagement-area test executive summary. " * 6


def _pi(s, ident, area):
    planning_items.create(
        s, identifier=ident, title="t", item_type="pending_work",
        status="Open", executive_summary=_EXEC, area=area,
    )


def test_valid_area_names_is_system_when_no_engagement_areas(v2_env):
    with session_scope() as s:
        assert engagement_areas.valid_area_names(s) == SYSTEM_AREAS


def test_system_area_accepted_old_prefix_rejected(v2_env):
    with session_scope() as s:
        _pi(s, "PI-001", ["storage", "api"])  # System areas, prefix dropped
        assert planning_items.get(s, "PI-001")["area"] == ["storage", "api"]
    with session_scope() as s, pytest.raises(ValidationError):
        _pi(s, "PI-002", ["v2-storage"])  # legacy prefixed label no longer valid


def test_engagement_area_extends_valid_set(v2_env):
    with session_scope() as s:
        # 'mr' is not a System area, so it is rejected until registered.
        with pytest.raises(ValidationError):
            _pi(s, "PI-003", ["mr"])
    with session_scope() as s:
        engagement_areas.create_engagement_area(s, "mr", description="Mentor Recruitment")
    with session_scope() as s:
        assert "mr" in engagement_areas.valid_area_names(s)
        _pi(s, "PI-004", ["mr", "api"])  # engagement + system, both valid
        assert planning_items.get(s, "PI-004")["area"] == ["mr", "api"]


def test_create_rejects_system_name_bad_format_and_duplicate(v2_env):
    with session_scope() as s:
        # A System area name is reserved for the global tier.
        with pytest.raises(UnprocessableError):
            engagement_areas.create_engagement_area(s, "storage")
        # Bad grammar.
        with pytest.raises(UnprocessableError):
            engagement_areas.create_engagement_area(s, "Bad Area")
    with session_scope() as s:
        engagement_areas.create_engagement_area(s, "fu")
    with session_scope() as s, pytest.raises(ConflictError):
        engagement_areas.create_engagement_area(s, "fu")


def test_list_and_delete(v2_env):
    with session_scope() as s:
        engagement_areas.create_engagement_area(s, "cr")
        engagement_areas.create_engagement_area(s, "mn")
    with session_scope() as s:
        names = [r["engagement_area_name"] for r in engagement_areas.list_engagement_areas(s)]
        assert names == ["cr", "mn"]  # ordered by name
    with session_scope() as s:
        engagement_areas.delete_engagement_area(s, "cr")
    with session_scope() as s:
        assert "cr" not in engagement_areas.valid_area_names(s)
        with pytest.raises(NotFoundError):
            engagement_areas.delete_engagement_area(s, "cr")
