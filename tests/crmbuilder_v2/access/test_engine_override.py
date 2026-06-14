"""Engine-override repository tests — PRJ-025 PI-189 slice 1.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
JSON value round-trip, and the validation surfaces (bad engine /
subject_type, uniqueness-tuple conflict).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import engine_override
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    OVERRIDE_SUBJECT_TYPES,
    TARGET_ENGINES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "override_identifier": "VARCHAR",
    "override_target_engine": "VARCHAR",
    "override_subject_type": "VARCHAR",
    "override_subject_identifier": "VARCHAR",
    "override_attribute": "VARCHAR",
    "override_value": "JSON",
    "override_notes": "TEXT",
    "override_created_at": "DATETIME",
    "override_updated_at": "DATETIME",
    "override_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def test_engine_overrides_table_has_expected_columns(v2_env):
    insp = inspect(get_engine())
    assert "engine_overrides" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("engine_overrides")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("engine_overrides")
    assert pk["constrained_columns"] == [
        "override_identifier",
        "engagement_id",
    ]


def test_engine_override_registered_in_vocab():
    assert "engine_override" in ENTITY_TYPES
    assert "engine_override" in CHANGE_LOG_ENTITY_TYPES
    assert TARGET_ENGINES == {"espocrm", "hubspot"}
    assert OVERRIDE_SUBJECT_TYPES == {"entity", "field", "association"}


def test_create_and_get_with_json_value(v2_env):
    with session_scope() as s:
        row = engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="field",
            subject_identifier="FLD-001",
            attribute="formula",
            value={"expr": "string\\concatenate(name, ' x')"},
            notes="pin the formula",
        )
    assert row["override_identifier"] == "OVR-001"
    assert row["override_value"] == {"expr": "string\\concatenate(name, ' x')"}
    with session_scope() as s:
        got = engine_override.get_engine_override(s, "OVR-001")
        assert got["override_attribute"] == "formula"


def test_create_rejects_bad_engine(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        engine_override.create_engine_override(
            s,
            target_engine="salesforce",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
        )


def test_create_rejects_bad_subject_type(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="process",
            subject_identifier="PROC-001",
            attribute="x",
        )


def test_uniqueness_tuple_conflict(v2_env):
    with session_scope() as s:
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            value="CMentor",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            value="CMentorX",
        )
    # A different attribute on the same subject is fine.
    with session_scope() as s:
        row = engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="icon",
            value="fas-user",
        )
        assert row["override_identifier"] == "OVR-002"
    # Same tuple but a different engine is fine.
    with session_scope() as s:
        engine_override.create_engine_override(
            s,
            target_engine="hubspot",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            value="mentor",
        )


def test_update_revalidates_uniqueness(v2_env):
    with session_scope() as s:
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            identifier="OVR-001",
        )
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="icon",
            identifier="OVR-002",
        )
    # Patching OVR-002's attribute to collide with OVR-001 is a 409.
    with session_scope() as s, pytest.raises(ConflictError):
        engine_override.patch_engine_override(
            s, "OVR-002", attribute="internal_name"
        )


def test_patch_rejects_unknown_field(v2_env):
    with session_scope() as s:
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            identifier="OVR-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        engine_override.patch_engine_override(s, "OVR-001", bogus="x")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            identifier="OVR-001",
        )
    with session_scope() as s:
        engine_override.delete_engine_override(s, "OVR-001")
        assert engine_override.get_engine_override(s, "OVR-001") is None
    with session_scope() as s:
        engine_override.restore_engine_override(s, "OVR-001")
        assert engine_override.get_engine_override(s, "OVR-001") is not None
    with session_scope() as s, pytest.raises(UnprocessableError):
        engine_override.restore_engine_override(s, "OVR-001")


def test_soft_deleted_tuple_still_blocks_create(v2_env):
    """The uniqueness key spans soft-deleted rows: a soft-deleted override
    still reserves its tuple, so re-creating the same tuple is a 409."""
    with session_scope() as s:
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
            identifier="OVR-001",
        )
    with session_scope() as s:
        engine_override.delete_engine_override(s, "OVR-001")
    with session_scope() as s, pytest.raises(ConflictError):
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="entity",
            subject_identifier="ENT-001",
            attribute="internal_name",
        )


def test_delete_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        engine_override.delete_engine_override(s, "OVR-404")
