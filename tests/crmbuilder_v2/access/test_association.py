"""Association repository tests — PRJ-025 PI-189 slice 1.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
and the validation surfaces (bad cardinality / status, dead-or-missing
endpoint entity, disallowed status transition).
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
from crmbuilder_v2.access.repositories import association, entity
from crmbuilder_v2.access.vocab import (
    ASSOCIATION_CARDINALITIES,
    ASSOCIATION_STATUSES,
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "association_identifier": "VARCHAR",
    "association_name": "VARCHAR",
    "association_source_entity": "VARCHAR",
    "association_target_entity": "VARCHAR",
    "association_cardinality": "VARCHAR",
    "association_source_role": "VARCHAR",
    "association_target_role": "VARCHAR",
    "association_description": "TEXT",
    "association_notes": "TEXT",
    "association_status": "VARCHAR",
    "association_created_at": "DATETIME",
    "association_updated_at": "DATETIME",
    "association_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_associations_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "associations" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("associations")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("associations")
    assert pk["constrained_columns"] == [
        "association_identifier",
        "engagement_id",
    ]


def test_association_registered_in_vocab():
    assert "association" in ENTITY_TYPES
    assert "association" in CHANGE_LOG_ENTITY_TYPES
    assert ASSOCIATION_CARDINALITIES == {
        "one_to_one",
        "one_to_many",
        "many_to_many",
    }
    assert ASSOCIATION_STATUSES == {
        "candidate",
        "confirmed",
        "deferred",
        "rejected",
    }


def test_create_and_get_association(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "Mentor")
        b = _seed_entity(s, "Mentee")
        row = association.create_association(
            s,
            name="Mentor assignment",
            source_entity=a,
            target_entity=b,
            cardinality="many_to_many",
            source_role="mentor",
            target_role="mentee",
        )
    assert row["association_identifier"] == "ASN-001"
    assert row["association_status"] == "candidate"
    assert row["association_source_entity"] == a
    assert row["association_target_entity"] == b
    with session_scope() as s:
        got = association.get_association(s, "ASN-001")
        assert got["association_source_role"] == "mentor"


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_many",
            identifier="ASN-050",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        association.create_association(
            s,
            name="dup",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-050",
        )


def test_create_rejects_bad_cardinality(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        with pytest.raises(UnprocessableError):
            association.create_association(
                s,
                name="bad",
                source_entity=a,
                target_entity=b,
                cardinality="one_to_three",
            )


def test_create_rejects_bad_status(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        with pytest.raises(UnprocessableError):
            association.create_association(
                s,
                name="bad",
                source_entity=a,
                target_entity=b,
                cardinality="one_to_one",
                status="archived",
            )


def test_create_rejects_missing_source_entity(v2_env):
    with session_scope() as s:
        b = _seed_entity(s, "B")
        with pytest.raises(UnprocessableError) as exc:
            association.create_association(
                s,
                name="bad",
                source_entity="ENT-999",
                target_entity=b,
                cardinality="one_to_one",
            )
        assert "association_source_entity" in str(exc.value)


def test_create_rejects_soft_deleted_target_entity(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        entity.delete_entity(s, b)
        with pytest.raises(UnprocessableError) as exc:
            association.create_association(
                s,
                name="bad",
                source_entity=a,
                target_entity=b,
                cardinality="one_to_one",
            )
        assert "soft-deleted" in str(exc.value)


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-001",
        )
    # candidate -> confirmed allowed.
    with session_scope() as s:
        row = association.patch_association(s, "ASN-001", status="confirmed")
        assert row["association_status"] == "confirmed"
    # confirmed -> candidate is NOT allowed.
    with session_scope() as s, pytest.raises(StatusTransitionError):
        association.patch_association(s, "ASN-001", status="candidate")


def test_patch_rejects_unknown_field(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        association.patch_association(s, "ASN-001", bogus="x")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-001",
        )
    with session_scope() as s:
        association.delete_association(s, "ASN-001")
        assert association.get_association(s, "ASN-001") is None
        assert (
            association.get_association(s, "ASN-001", include_deleted=True)
            is not None
        )
    with session_scope() as s:
        association.restore_association(s, "ASN-001")
        assert association.get_association(s, "ASN-001") is not None
    # Restoring a live row is a 422.
    with session_scope() as s, pytest.raises(UnprocessableError):
        association.restore_association(s, "ASN-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        association.delete_association(s, "ASN-404")


def test_list_filters_by_endpoint(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        c = _seed_entity(s, "C")
        association.create_association(
            s, name="ab", source_entity=a, target_entity=b,
            cardinality="one_to_one",
        )
        association.create_association(
            s, name="ac", source_entity=a, target_entity=c,
            cardinality="one_to_one",
        )
    with session_scope() as s:
        assert len(association.list_associations(s)) == 2
        assert len(association.list_associations(s, target_entity=c)) == 1
