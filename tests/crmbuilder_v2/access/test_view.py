"""View repository tests — PRJ-025 PI-189 slice 2.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
non-empty columns, filter-condition validation, sort_direction vocab, and the
listed-entity existence/liveness surfaces.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import entity, view
from crmbuilder_v2.access.vocab import CHANGE_LOG_ENTITY_TYPES, ENTITY_TYPES
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "view_identifier": "VARCHAR",
    "view_name": "VARCHAR",
    "view_entity": "VARCHAR",
    "view_columns": "JSON",
    "view_filter": "JSON",
    "view_sort_field": "VARCHAR",
    "view_sort_direction": "VARCHAR",
    "view_description": "TEXT",
    "view_notes": "TEXT",
    "view_status": "VARCHAR",
    "view_created_at": "DATETIME",
    "view_updated_at": "DATETIME",
    "view_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}

_FILTER = {"all": [{"field": "stage", "op": "eq", "value": "open"}]}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_views_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "views" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("views")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("views")
    assert pk["constrained_columns"] == ["view_identifier", "engagement_id"]


def test_view_registered_in_vocab():
    assert "view" in ENTITY_TYPES
    assert "view" in CHANGE_LOG_ENTITY_TYPES


def test_create_and_get_view(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "Opportunity")
        row = view.create_view(
            s,
            name="Open opps",
            entity=e,
            columns=["name", "stage", "FLD-003"],
            filter=_FILTER,
            sort_field="amount",
            sort_direction="desc",
        )
    assert row["view_identifier"] == "VEW-001"
    assert row["view_status"] == "candidate"
    assert row["view_columns"] == ["name", "stage", "FLD-003"]
    assert row["view_filter"] == _FILTER
    assert row["view_sort_direction"] == "desc"
    with session_scope() as s:
        got = view.get_view(s, "VEW-001")
        assert got["view_sort_field"] == "amount"


def test_create_without_filter_or_sort(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        row = view.create_view(s, name="v", entity=e, columns=["name"])
        assert row["view_filter"] is None
        assert row["view_sort_direction"] is None


def test_create_rejects_empty_columns(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            view.create_view(s, name="v", entity=e, columns=[])
        assert "view_columns" in str(exc.value)


def test_create_rejects_non_string_column(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError):
            view.create_view(s, name="v", entity=e, columns=["name", 7])


def test_create_rejects_malformed_filter(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            view.create_view(
                s,
                name="v",
                entity=e,
                columns=["name"],
                filter={"any": []},
            )
        assert "view_filter" in str(exc.value)


def test_create_rejects_bad_sort_direction(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            view.create_view(
                s,
                name="v",
                entity=e,
                columns=["name"],
                sort_direction="sideways",
            )
        assert "view_sort_direction" in str(exc.value)


def test_create_rejects_dead_entity(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        entity.delete_entity(s, e)
        with pytest.raises(UnprocessableError) as exc:
            view.create_view(s, name="v", entity=e, columns=["name"])
        assert "soft-deleted" in str(exc.value)


def test_create_rejects_missing_entity(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        view.create_view(s, name="v", entity="ENT-999", columns=["name"])


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        view.create_view(
            s, name="v", entity=e, columns=["name"], identifier="VEW-050"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        view.create_view(
            s, name="dup", entity=e, columns=["name"], identifier="VEW-050"
        )


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        view.create_view(
            s, name="v", entity=e, columns=["name"], identifier="VEW-001"
        )
    with session_scope() as s:
        row = view.patch_view(s, "VEW-001", status="confirmed")
        assert row["view_status"] == "confirmed"
    with session_scope() as s, pytest.raises(StatusTransitionError):
        view.patch_view(s, "VEW-001", status="candidate")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        view.create_view(
            s, name="v", entity=e, columns=["name"], identifier="VEW-001"
        )
    with session_scope() as s:
        view.delete_view(s, "VEW-001")
        assert view.get_view(s, "VEW-001") is None
        assert view.get_view(s, "VEW-001", include_deleted=True) is not None
    with session_scope() as s:
        view.restore_view(s, "VEW-001")
        assert view.get_view(s, "VEW-001") is not None
    with session_scope() as s, pytest.raises(UnprocessableError):
        view.restore_view(s, "VEW-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        view.delete_view(s, "VEW-404")


def test_list_filters_by_entity(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        view.create_view(s, name="va", entity=a, columns=["name"])
        view.create_view(s, name="vb", entity=b, columns=["name"])
    with session_scope() as s:
        assert len(view.list_views(s)) == 2
        assert len(view.list_views(s, entity=b)) == 1
