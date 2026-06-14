"""Access-layer tests — PRJ-025 PI-182 intrinsic design-intent columns.

Covers the new engine-neutral ``field``/``entity`` attributes and the
``field_options`` child collection: create→read round-trips, PATCH/PUT
replacement of options, and validation rejecting bad format / numeric
scale / sort direction.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import entity, field


def _seed_entity(s, name: str = "Contact") -> str:
    return entity.create_entity(s, name=name, description="seed")["entity_identifier"]


# ---------------------------------------------------------------------------
# Field intrinsics
# ---------------------------------------------------------------------------


def test_create_field_round_trips_intrinsics(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        row = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="amount",
            description="a money amount",
            type="number",
            tooltip="Enter dollars",
            usage_summary="Used in totals",
            default_value="0",
            format="currency",
            numeric_scale="decimal",
            max_length=12,
            min="0",
            max="1000000",
            read_only=True,
            unique=True,
            externally_populated=True,
        )
        fid = row["field_identifier"]
    with session_scope() as s:
        got = field.get_field(s, fid)
    assert got["field_tooltip"] == "Enter dollars"
    assert got["field_usage_summary"] == "Used in totals"
    assert got["field_default_value"] == "0"
    assert got["field_format"] == "currency"
    assert got["field_numeric_scale"] == "decimal"
    assert got["field_max_length"] == 12
    assert got["field_min"] == "0"
    assert got["field_max"] == "1000000"
    assert got["field_read_only"] is True
    assert got["field_unique"] is True
    assert got["field_externally_populated"] is True


def test_field_intrinsic_defaults(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        row = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="plain",
            description="no intrinsics",
            type="text",
        )
    assert row["field_tooltip"] is None
    assert row["field_format"] is None
    assert row["field_max_length"] is None
    assert row["field_read_only"] is False
    assert row["field_unique"] is False
    assert row["field_externally_populated"] is False
    assert row["field_options"] == []


def test_create_field_rejects_bad_format(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="f",
            description="d",
            type="text",
            format="not_a_format",
        )
    assert exc.value.errors[0].field == "field_format"


def test_create_field_rejects_bad_numeric_scale(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="f",
            description="d",
            type="number",
            numeric_scale="float",
        )
    assert exc.value.errors[0].field == "field_numeric_scale"


def test_create_field_rejects_unknown_intrinsic_kwarg(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="f",
            description="d",
            type="text",
            bogus="x",
        )


def test_patch_field_updates_intrinsics(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        fid = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="f",
            description="d",
            type="text",
        )["field_identifier"]
    with session_scope() as s:
        patched = field.patch_field(
            s, fid, tooltip="help", read_only=True, format="email"
        )
    assert patched["field_tooltip"] == "help"
    assert patched["field_read_only"] is True
    assert patched["field_format"] == "email"
    # Untouched intrinsics stay at their defaults.
    assert patched["field_unique"] is False


# ---------------------------------------------------------------------------
# field_options child collection
# ---------------------------------------------------------------------------


def _opts(*values):
    return [{"option_value": v} for v in values]


def test_create_field_with_options(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        row = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="status",
            description="enum",
            type="enum",
            options=[
                {"option_value": "new", "option_label": "New"},
                {"option_value": "done", "option_label": "Done"},
            ],
        )
        fid = row["field_identifier"]
    # Embedded in the create return and in a fresh GET, in order.
    assert [o["option_value"] for o in row["field_options"]] == ["new", "done"]
    assert row["field_options"][0]["option_label"] == "New"
    assert row["field_options"][0]["option_order"] == 0
    with session_scope() as s:
        got = field.get_field(s, fid)
    assert [o["option_value"] for o in got["field_options"]] == ["new", "done"]


def test_patch_replaces_option_set(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        fid = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="status",
            description="enum",
            type="enum",
            options=_opts("a", "b", "c"),
        )["field_identifier"]
    with session_scope() as s:
        patched = field.patch_field(s, fid, options=_opts("x", "y"))
    assert [o["option_value"] for o in patched["field_options"]] == ["x", "y"]
    # Omitting options on a later PATCH leaves the set unchanged.
    with session_scope() as s:
        again = field.patch_field(s, fid, tooltip="t")
    assert [o["option_value"] for o in again["field_options"]] == ["x", "y"]


def test_patch_clears_option_set_with_empty_list(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        fid = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="status",
            description="enum",
            type="enum",
            options=_opts("a", "b"),
        )["field_identifier"]
    with session_scope() as s:
        patched = field.patch_field(s, fid, options=[])
    assert patched["field_options"] == []


def test_options_explicit_order_preserved(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
        row = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="status",
            description="enum",
            type="enum",
            options=[
                {"option_value": "third", "option_order": 30},
                {"option_value": "first", "option_order": 10},
                {"option_value": "second", "option_order": 20},
            ],
        )
    # Returned in option_order, not insertion order.
    assert [o["option_value"] for o in row["field_options"]] == [
        "first",
        "second",
        "third",
    ]


def test_options_reject_duplicate_value(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="status",
            description="enum",
            type="enum",
            options=_opts("dup", "dup"),
        )


def test_options_reject_empty_value(v2_env):
    with session_scope() as s:
        ent = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError):
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="status",
            description="enum",
            type="enum",
            options=[{"option_value": "   "}],
        )


# ---------------------------------------------------------------------------
# Entity intrinsics
# ---------------------------------------------------------------------------


def test_create_entity_round_trips_intrinsics(v2_env):
    with session_scope() as s:
        row = entity.create_entity(
            s,
            name="Mentor",
            description="d",
            default_sort_field="createdAt",
            default_sort_direction="desc",
            track_activity=True,
        )
        eid = row["entity_identifier"]
    assert row["entity_default_sort_field"] == "createdAt"
    assert row["entity_default_sort_direction"] == "desc"
    assert row["entity_track_activity"] is True
    with session_scope() as s:
        got = entity.get_entity(s, eid)
    assert got["entity_default_sort_direction"] == "desc"


def test_entity_intrinsic_defaults(v2_env):
    with session_scope() as s:
        row = entity.create_entity(s, name="Plain", description="d")
    assert row["entity_default_sort_field"] is None
    assert row["entity_default_sort_direction"] is None
    assert row["entity_track_activity"] is False


def test_create_entity_rejects_bad_sort_direction(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        entity.create_entity(
            s, name="E", description="d", default_sort_direction="sideways"
        )
    assert exc.value.errors[0].field == "entity_default_sort_direction"


def test_patch_entity_updates_intrinsics(v2_env):
    with session_scope() as s:
        eid = entity.create_entity(s, name="E", description="d")[
            "entity_identifier"
        ]
    with session_scope() as s:
        patched = entity.patch_entity(
            s,
            eid,
            default_sort_field="name",
            default_sort_direction="asc",
            track_activity=True,
        )
    assert patched["entity_default_sort_field"] == "name"
    assert patched["entity_default_sort_direction"] == "asc"
    assert patched["entity_track_activity"] is True
