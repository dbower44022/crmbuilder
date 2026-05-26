"""Field repository tests — v0.5+ (PI-004 first slice).

Covers ``field.md`` §3.7 acceptance criteria 1–5, 7, 8, 9, 15, 16 plus
field-specific assertions on the access-layer atomicity and
cardinality-violation surfaces.
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
from crmbuilder_v2.access.repositories import (
    entity,
    field,
    references,
)
from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _kinds_for_pair,
)
from sqlalchemy import inspect

# Expected ``fields`` columns and their SQLite affinities (criterion 1).
_EXPECTED_COLUMNS = {
    "field_identifier": "VARCHAR",
    "field_name": "VARCHAR",
    "field_description": "TEXT",
    "field_type": "VARCHAR",
    "field_required": "BOOLEAN",
    "field_notes": "TEXT",
    "field_status": "VARCHAR",
    "field_previous_parent_entity_identifier": "VARCHAR",
    "field_created_at": "DATETIME",
    "field_updated_at": "DATETIME",
    "field_deleted_at": "DATETIME",
}


def _seed_entity(s, name: str = "Contact") -> str:
    row = entity.create_entity(s, name=name, description="seed entity")
    return row["entity_identifier"]


# ---------------------------------------------------------------------------
# Criterion 1 — schema shape
# ---------------------------------------------------------------------------


def test_fields_table_has_expected_columns_with_correct_types(v2_env):
    inspector = inspect(get_engine())
    assert "fields" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("fields")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = inspector.get_pk_constraint("fields")
    assert pk["constrained_columns"] == ["field_identifier"]
    # Optional-content nullability per the spec.
    assert columns["field_deleted_at"]["nullable"] is True
    assert columns["field_notes"]["nullable"] is True
    assert columns["field_previous_parent_entity_identifier"]["nullable"] is True
    assert columns["field_name"]["nullable"] is False
    assert columns["field_description"]["nullable"] is False
    assert columns["field_required"]["nullable"] is False


# ---------------------------------------------------------------------------
# Criterion 1, 15 — vocab and CHECK registration
# ---------------------------------------------------------------------------


def test_field_kind_registered_and_constrained():
    assert "field" in ENTITY_TYPES
    assert "field_belongs_to_entity" in REFERENCE_RELATIONSHIPS
    kinds = _kinds_for_pair("field", "entity")
    assert "field_belongs_to_entity" in kinds
    assert "is_about" in kinds
    assert "references" in kinds
    # Reverse pair should NOT admit the kind.
    assert "field_belongs_to_entity" not in _kinds_for_pair("entity", "field")


# ---------------------------------------------------------------------------
# Criterion 1, 16 — atomic POST creates row + edge
# ---------------------------------------------------------------------------


def test_create_field_with_explicit_identifier_and_edge_atomically(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        row = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="status",
            description="lifecycle status of a contact",
            type="enum",
            identifier="FLD-001",
        )
    assert row["field_identifier"] == "FLD-001"
    with session_scope() as s:
        touching = references.list_touching(
            s, entity_type="field", entity_id="FLD-001"
        )
        assert len(touching["as_source"]) == 1
        edge = touching["as_source"][0]
        assert edge["relationship"] == "field_belongs_to_entity"
        assert edge["target_id"] == ent_id


def test_create_field_server_assigns_identifier(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        row = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="status",
            description="d",
            type="enum",
        )
    assert row["field_identifier"] == "FLD-001"


# ---------------------------------------------------------------------------
# Criterion 4 — type enum validation
# ---------------------------------------------------------------------------


def test_create_field_rejects_invalid_field_type(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="bogus_type",
        )
    assert any(e.field == "field_type" for e in exc.value.errors)


# ---------------------------------------------------------------------------
# Criterion 5 — status enum and transition validation
# ---------------------------------------------------------------------------


def test_create_field_rejects_invalid_status(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
            status="archived",
        )
    assert any(e.field == "field_status" for e in exc.value.errors)


def test_patch_field_rejects_invalid_status_transition(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
            status="confirmed",
        )
    with session_scope() as s, pytest.raises(StatusTransitionError) as exc:
        field.patch_field(s, "FLD-001", status="candidate")
    assert exc.value.from_status == "confirmed"
    assert exc.value.to_status == "candidate"


# ---------------------------------------------------------------------------
# Criterion 16 — parent-entity validation on POST
# ---------------------------------------------------------------------------


def test_create_field_rejects_missing_parent_entity_identifier(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier="",
            name="x",
            description="d",
            type="text",
        )
    assert any(
        e.field == "field_belongs_to_entity_identifier"
        for e in exc.value.errors
    )


def test_create_field_rejects_nonexistent_parent_entity(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier="ENT-999",
            name="x",
            description="d",
            type="text",
        )
    assert any(
        e.field == "field_belongs_to_entity_identifier"
        and "not found" in e.message
        for e in exc.value.errors
    )


def test_create_field_rejects_soft_deleted_parent_entity(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        entity.delete_entity(s, ent_id)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
        )
    assert any(
        e.field == "field_belongs_to_entity_identifier"
        and "soft-deleted" in e.message
        for e in exc.value.errors
    )


# ---------------------------------------------------------------------------
# Criterion 3 — per-entity name uniqueness
# ---------------------------------------------------------------------------


def test_field_name_uniqueness_is_per_entity_scoped(v2_env):
    """Two fields named 'status' on two different entities both succeed.

    A second 'status' on the same entity is rejected.
    """
    with session_scope() as s:
        ent_contact = _seed_entity(s, "Contact")
        ent_mentor = _seed_entity(s, "Mentor")
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_contact,
            name="status",
            description="contact status",
            type="enum",
        )
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_mentor,
            name="status",
            description="mentor status",
            type="enum",
        )
    # Both succeed.
    with session_scope() as s:
        assert len(field.list_fields(s)) == 2
    # Second 'status' on Contact fails with duplicate.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_contact,
            name="STATUS",  # case-insensitive collision
            description="another",
            type="enum",
        )
    assert any(
        e.field == "field_name" and e.code == "duplicate"
        for e in exc.value.errors
    )


# ---------------------------------------------------------------------------
# Criterion 9 — soft-delete / restore atomic round-trip with edge
# ---------------------------------------------------------------------------


def test_delete_field_soft_deletes_row_and_edge_atomically(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="email",
            description="d",
            type="text",
        )
    with session_scope() as s:
        field.delete_field(s, "FLD-001")
    with session_scope() as s:
        # Row is gone from default list / get.
        assert field.list_fields(s) == []
        assert field.get_field(s, "FLD-001") is None
        # Row resurfaces with include_deleted.
        soft = field.get_field(s, "FLD-001", include_deleted=True)
        assert soft is not None
        assert soft["field_deleted_at"] is not None
        # Stash column holds the previously-attached parent.
        assert soft["field_previous_parent_entity_identifier"] == ent_id
        # Edge is gone.
        edges = references.list_touching(
            s, entity_type="field", entity_id="FLD-001"
        )
        assert edges["as_source"] == []


def test_restore_field_clears_deletion_and_restores_edge_atomically(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="email",
            description="d",
            type="text",
        )
    with session_scope() as s:
        field.delete_field(s, "FLD-001")
    with session_scope() as s:
        restored = field.restore_field(s, "FLD-001")
    assert restored["field_deleted_at"] is None
    assert restored["field_previous_parent_entity_identifier"] is None
    with session_scope() as s:
        # Row is back in default list.
        assert len(field.list_fields(s)) == 1
        # Edge is restored.
        edges = references.list_touching(
            s, entity_type="field", entity_id="FLD-001"
        )
        assert len(edges["as_source"]) == 1
        assert (
            edges["as_source"][0]["relationship"] == "field_belongs_to_entity"
        )
        assert edges["as_source"][0]["target_id"] == ent_id


def test_restore_field_rejects_when_parent_entity_is_soft_deleted(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="email",
            description="d",
            type="text",
        )
    with session_scope() as s:
        field.delete_field(s, "FLD-001")
        entity.delete_entity(s, ent_id)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        field.restore_field(s, "FLD-001")
    assert any(
        e.code == "parent_entity_soft_deleted" for e in exc.value.errors
    )


# ---------------------------------------------------------------------------
# Criterion 16 — references cardinality guards (POST + DELETE)
# ---------------------------------------------------------------------------


def test_cannot_create_second_field_belongs_to_entity_edge_for_live_field(
    v2_env,
):
    """A field already has its edge from create_field. POSTing a second
    edge of the same kind must be rejected with cardinality_violation."""
    with session_scope() as s:
        ent_a = _seed_entity(s, "Contact")
        ent_b = _seed_entity(s, "Mentor")
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_a,
            name="x",
            description="d",
            type="text",
        )
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        references.create(
            s,
            source_type="field",
            source_id="FLD-001",
            target_type="entity",
            target_id=ent_b,
            relationship="field_belongs_to_entity",
        )
    assert any(e.code == "cardinality_violation" for e in exc.value.errors)


def test_cannot_delete_only_field_belongs_to_entity_edge_of_live_field(
    v2_env,
):
    """The single live edge of a live field is locked against DELETE
    via the references API — soft-delete the field instead."""
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
        )
        # Find the edge.
        edges = references.list_touching(
            s, entity_type="field", entity_id="FLD-001"
        )
        edge_id = edges["as_source"][0]["id"]
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        references.delete_by_id(s, edge_id)
    assert any(e.code == "cardinality_violation" for e in exc.value.errors)


def test_delete_field_path_can_remove_the_edge_via_skip_flag(v2_env):
    """The internal _skip_cardinality_check=True path used by
    delete_field successfully removes the otherwise-locked edge."""
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
        )
    # delete_field uses the skip flag internally; the operation must succeed.
    with session_scope() as s:
        field.delete_field(s, "FLD-001")
    with session_scope() as s:
        edges = references.list_touching(
            s, entity_type="field", entity_id="FLD-001"
        )
        assert edges["as_source"] == []


# ---------------------------------------------------------------------------
# Filter and method smoke
# ---------------------------------------------------------------------------


def test_list_fields_filtered_by_entity_identifier(v2_env):
    with session_scope() as s:
        ent_contact = _seed_entity(s, "Contact")
        ent_mentor = _seed_entity(s, "Mentor")
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_contact,
            name="email",
            description="d",
            type="text",
        )
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_contact,
            name="phone",
            description="d",
            type="text",
        )
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_mentor,
            name="expertise",
            description="d",
            type="multi_enum",
        )
    with session_scope() as s:
        contact_fields = field.list_fields(s, entity_identifier=ent_contact)
        mentor_fields = field.list_fields(s, entity_identifier=ent_mentor)
    assert {f["field_name"] for f in contact_fields} == {"email", "phone"}
    assert {f["field_name"] for f in mentor_fields} == {"expertise"}


def test_eight_repository_methods_exist():
    for name in (
        "list_fields",
        "get_field",
        "create_field",
        "update_field",
        "patch_field",
        "delete_field",
        "restore_field",
        "next_field_identifier",
    ):
        assert callable(getattr(field, name)), name


def test_next_field_identifier_on_empty_db(v2_env):
    with session_scope() as s:
        assert field.next_field_identifier(s) == "FLD-001"


def test_next_field_identifier_increments(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="a",
            description="d",
            type="text",
        )
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="b",
            description="d",
            type="text",
        )
    with session_scope() as s:
        assert field.next_field_identifier(s) == "FLD-003"


def test_patch_field_unknown_field_rejected(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        field.patch_field(s, "FLD-001", bogus="value")


def test_patch_field_unknown_patchable_rejects_parent_entity_key(v2_env):
    """``field_belongs_to_entity_identifier`` is not patchable — the
    rejection happens at the PATCH unknown-field validator."""
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        field.patch_field(
            s, "FLD-001", field_belongs_to_entity_identifier="ENT-002"
        )


def test_explicit_identifier_collision_raises_conflict(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="x",
            description="d",
            type="text",
            identifier="FLD-005",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="y",
            description="d",
            type="text",
            identifier="FLD-005",
        )


def test_update_field_full_replace(v2_env):
    with session_scope() as s:
        ent_id = _seed_entity(s)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=ent_id,
            name="old",
            description="od",
            type="text",
        )
    with session_scope() as s:
        row = field.update_field(
            s,
            "FLD-001",
            field_identifier="FLD-001",
            name="new",
            description="nd",
            type="long_text",
            required=True,
            notes="now noted",
            status="confirmed",
        )
    assert row["field_name"] == "new"
    assert row["field_type"] == "long_text"
    assert row["field_required"] is True
    assert row["field_status"] == "confirmed"


def test_delete_missing_raises_not_found(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        field.delete_field(s, "FLD-404")
