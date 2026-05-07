"""Planning items repository tests."""

from __future__ import annotations

import pytest

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ValidationError
from crmbuilder_v2.access.repositories import planning_items


def test_create_and_resolve(v2_env):
    with session_scope() as s:
        planning_items.create(
            s,
            identifier="PI-005",
            title="Pacing dimension",
            item_type="planning_dimension",
            status="Open",
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
            status="Open",
        )


def test_upsert(v2_env):
    with session_scope() as s:
        planning_items.upsert(
            s,
            identifier="PI-007",
            title="t1",
            item_type="open_question",
            status="Open",
        )
        planning_items.upsert(
            s,
            identifier="PI-007",
            title="t2",
            item_type="open_question",
            status="Open",
        )
    with session_scope() as s:
        rows = planning_items.list_all(s)
    assert len(rows) == 1
    assert rows[0]["title"] == "t2"
