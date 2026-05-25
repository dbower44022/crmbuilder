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


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    with session_scope() as s:
        row = planning_items.create(
            s, title="Auto", item_type="open_question", status="Open"
        )
    assert row["identifier"] == "PI-001"
    with session_scope() as s:
        row2 = planning_items.create(
            s, title="Auto2", item_type="open_question", status="Open"
        )
    assert row2["identifier"] == "PI-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        row = planning_items.create(
            s, identifier="PI-042", title="Explicit",
            item_type="open_question", status="Open",
        )
    assert row["identifier"] == "PI-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        planning_items.create(
            s, identifier="PI-1", title="Bad",
            item_type="open_question", status="Open",
        )


def test_create_with_empty_string_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        planning_items.create(
            s, identifier="", title="Bad",
            item_type="open_question", status="Open",
        )


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-001", title="First",
            item_type="open_question", status="Open",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        planning_items.create(
            s, identifier="PI-001", title="Second",
            item_type="open_question", status="Open",
        )


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-001", title="First",
            item_type="open_question", status="Open",
        )
    monkeypatch.setattr(
        planning_items, "compute_next_identifier", lambda _s: "PI-001"
    )
    with session_scope() as s:
        row = planning_items.create(
            s, title="Second", item_type="open_question", status="Open"
        )
    assert row["identifier"] == "PI-002"
