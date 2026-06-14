"""Dedup-rule repository tests — PRJ-025 PI-189 slice 3.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
non-empty match_fields, normalize-token validation, on-match vocab, and the
deduped-entity existence/liveness surfaces.
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
from crmbuilder_v2.access.repositories import dedup_rule, entity
from crmbuilder_v2.access.vocab import CHANGE_LOG_ENTITY_TYPES, ENTITY_TYPES
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "dedup_rule_identifier": "VARCHAR",
    "dedup_rule_name": "VARCHAR",
    "dedup_rule_entity": "VARCHAR",
    "dedup_rule_match_fields": "JSON",
    "dedup_rule_normalize": "JSON",
    "dedup_rule_on_match": "VARCHAR",
    "dedup_rule_message": "TEXT",
    "dedup_rule_description": "TEXT",
    "dedup_rule_notes": "TEXT",
    "dedup_rule_status": "VARCHAR",
    "dedup_rule_created_at": "DATETIME",
    "dedup_rule_updated_at": "DATETIME",
    "dedup_rule_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_dedup_rules_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "dedup_rules" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("dedup_rules")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("dedup_rules")
    assert pk["constrained_columns"] == [
        "dedup_rule_identifier",
        "engagement_id",
    ]


def test_dedup_rule_registered_in_vocab():
    assert "dedup_rule" in ENTITY_TYPES
    assert "dedup_rule" in CHANGE_LOG_ENTITY_TYPES


def test_create_and_get_dedup_rule(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "Contact")
        row = dedup_rule.create_dedup_rule(
            s,
            name="Email match",
            entity=e,
            match_fields=["email", "FLD-003"],
            on_match="block",
            normalize={"email": "lowercase", "FLD-003": "trim"},
            message="Duplicate contact",
        )
    assert row["dedup_rule_identifier"] == "DUP-001"
    assert row["dedup_rule_status"] == "candidate"
    assert row["dedup_rule_match_fields"] == ["email", "FLD-003"]
    assert row["dedup_rule_normalize"] == {
        "email": "lowercase",
        "FLD-003": "trim",
    }
    assert row["dedup_rule_on_match"] == "block"
    with session_scope() as s:
        got = dedup_rule.get_dedup_rule(s, "DUP-001")
        assert got["dedup_rule_message"] == "Duplicate contact"


def test_create_without_normalize(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        row = dedup_rule.create_dedup_rule(
            s, name="d", entity=e, match_fields=["email"], on_match="warn"
        )
        assert row["dedup_rule_normalize"] is None
        assert row["dedup_rule_on_match"] == "warn"


def test_create_rejects_empty_match_fields(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            dedup_rule.create_dedup_rule(
                s, name="d", entity=e, match_fields=[], on_match="block"
            )
        assert "dedup_rule_match_fields" in str(exc.value)


def test_create_rejects_non_string_match_field(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError):
            dedup_rule.create_dedup_rule(
                s,
                name="d",
                entity=e,
                match_fields=["email", 7],
                on_match="block",
            )


def test_create_rejects_bad_on_match(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            dedup_rule.create_dedup_rule(
                s,
                name="d",
                entity=e,
                match_fields=["email"],
                on_match="explode",
            )
        assert "dedup_rule_on_match" in str(exc.value)


def test_create_rejects_bad_normalize_token(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            dedup_rule.create_dedup_rule(
                s,
                name="d",
                entity=e,
                match_fields=["email"],
                on_match="block",
                normalize={"email": "shout"},
            )
        assert "dedup_rule_normalize" in str(exc.value)


def test_create_rejects_dead_entity(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        entity.delete_entity(s, e)
        with pytest.raises(UnprocessableError) as exc:
            dedup_rule.create_dedup_rule(
                s, name="d", entity=e, match_fields=["email"], on_match="block"
            )
        assert "soft-deleted" in str(exc.value)


def test_create_rejects_missing_entity(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        dedup_rule.create_dedup_rule(
            s,
            name="d",
            entity="ENT-999",
            match_fields=["email"],
            on_match="block",
        )


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        dedup_rule.create_dedup_rule(
            s,
            name="d",
            entity=e,
            match_fields=["email"],
            on_match="block",
            identifier="DUP-050",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        dedup_rule.create_dedup_rule(
            s,
            name="dup",
            entity=e,
            match_fields=["email"],
            on_match="block",
            identifier="DUP-050",
        )


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        dedup_rule.create_dedup_rule(
            s,
            name="d",
            entity=e,
            match_fields=["email"],
            on_match="block",
            identifier="DUP-001",
        )
    with session_scope() as s:
        row = dedup_rule.patch_dedup_rule(s, "DUP-001", status="confirmed")
        assert row["dedup_rule_status"] == "confirmed"
    with session_scope() as s, pytest.raises(StatusTransitionError):
        dedup_rule.patch_dedup_rule(s, "DUP-001", status="candidate")


def test_patch_rejects_unknown_field(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        dedup_rule.create_dedup_rule(
            s,
            name="d",
            entity=e,
            match_fields=["email"],
            on_match="block",
            identifier="DUP-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        dedup_rule.patch_dedup_rule(s, "DUP-001", bogus="x")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        dedup_rule.create_dedup_rule(
            s,
            name="d",
            entity=e,
            match_fields=["email"],
            on_match="block",
            identifier="DUP-001",
        )
    with session_scope() as s:
        dedup_rule.delete_dedup_rule(s, "DUP-001")
        assert dedup_rule.get_dedup_rule(s, "DUP-001") is None
        assert (
            dedup_rule.get_dedup_rule(s, "DUP-001", include_deleted=True)
            is not None
        )
    with session_scope() as s:
        dedup_rule.restore_dedup_rule(s, "DUP-001")
        assert dedup_rule.get_dedup_rule(s, "DUP-001") is not None
    with session_scope() as s, pytest.raises(UnprocessableError):
        dedup_rule.restore_dedup_rule(s, "DUP-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        dedup_rule.delete_dedup_rule(s, "DUP-404")


def test_list_filters_by_entity(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        dedup_rule.create_dedup_rule(
            s, name="da", entity=a, match_fields=["email"], on_match="block"
        )
        dedup_rule.create_dedup_rule(
            s, name="db", entity=b, match_fields=["email"], on_match="warn"
        )
    with session_scope() as s:
        assert len(dedup_rule.list_dedup_rules(s)) == 2
        assert len(dedup_rule.list_dedup_rules(s, entity=b)) == 1
