"""Rule repository tests — PRJ-025 PI-189 slice 2.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
condition validation, and the subject existence/liveness/type-match surfaces.
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
from crmbuilder_v2.access.repositories import entity, field, rule
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    RULE_EFFECTS,
    RULE_SUBJECT_TYPES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "rule_identifier": "VARCHAR",
    "rule_name": "VARCHAR",
    "rule_subject_type": "VARCHAR",
    "rule_subject_identifier": "VARCHAR",
    "rule_effect": "VARCHAR",
    "rule_condition": "JSON",
    "rule_message": "TEXT",
    "rule_description": "TEXT",
    "rule_notes": "TEXT",
    "rule_status": "VARCHAR",
    "rule_created_at": "DATETIME",
    "rule_updated_at": "DATETIME",
    "rule_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}

_COND = {"field": "stage", "op": "eq", "value": "won"}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def _seed_field(s, entity_id: str, name: str) -> str:
    return field.create_field(
        s,
        field_belongs_to_entity_identifier=entity_id,
        name=name,
        description="seed",
        type="text",
    )["field_identifier"]


def test_rules_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "rules" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("rules")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("rules")
    assert pk["constrained_columns"] == ["rule_identifier", "engagement_id"]


def test_rule_registered_in_vocab():
    assert "rule" in ENTITY_TYPES
    assert "rule" in CHANGE_LOG_ENTITY_TYPES
    assert RULE_SUBJECT_TYPES == {"field", "entity"}
    assert RULE_EFFECTS == {"required_when", "visible_when", "valid_when"}


def test_create_and_get_rule_on_field(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "Opportunity")
        f = _seed_field(s, e, "stage")
        row = rule.create_rule(
            s,
            name="Stage required when won",
            subject_type="field",
            subject_identifier=f,
            effect="required_when",
            condition=_COND,
        )
    assert row["rule_identifier"] == "RUL-001"
    assert row["rule_status"] == "candidate"
    assert row["rule_subject_identifier"] == f
    assert row["rule_condition"] == _COND
    with session_scope() as s:
        got = rule.get_rule(s, "RUL-001")
        assert got["rule_effect"] == "required_when"


def test_create_rule_on_entity(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "Opportunity")
        row = rule.create_rule(
            s,
            name="entity invariant",
            subject_type="entity",
            subject_identifier=e,
            effect="valid_when",
            condition=_COND,
            message="Stage must be set",
        )
        assert row["rule_message"] == "Stage must be set"


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        rule.create_rule(
            s,
            name="r",
            subject_type="field",
            subject_identifier=f,
            effect="visible_when",
            condition=_COND,
            identifier="RUL-050",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        rule.create_rule(
            s,
            name="dup",
            subject_type="field",
            subject_identifier=f,
            effect="visible_when",
            condition=_COND,
            identifier="RUL-050",
        )


def test_create_rejects_bad_effect(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        with pytest.raises(UnprocessableError):
            rule.create_rule(
                s,
                name="bad",
                subject_type="field",
                subject_identifier=f,
                effect="nope_when",
                condition=_COND,
            )


def test_create_rejects_bad_subject_type(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        rule.create_rule(
            s,
            name="bad",
            subject_type="widget",
            subject_identifier="FLD-001",
            effect="required_when",
            condition=_COND,
        )


def test_create_rejects_malformed_condition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        with pytest.raises(UnprocessableError) as exc:
            rule.create_rule(
                s,
                name="bad",
                subject_type="field",
                subject_identifier=f,
                effect="required_when",
                condition={"field": "x", "op": "matches", "value": 1},
            )
        assert "rule_condition" in str(exc.value)


def test_create_rejects_missing_subject(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        rule.create_rule(
            s,
            name="bad",
            subject_type="field",
            subject_identifier="FLD-999",
            effect="required_when",
            condition=_COND,
        )
    assert "rule_subject_identifier" in str(exc.value)


def test_create_rejects_subject_type_mismatch(v2_env):
    # An entity id given when subject_type=field must not resolve.
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError):
            rule.create_rule(
                s,
                name="bad",
                subject_type="field",
                subject_identifier=e,  # ENT-NNN, not a field
                effect="required_when",
                condition=_COND,
            )


def test_create_rejects_soft_deleted_subject(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        field.delete_field(s, f)
        with pytest.raises(UnprocessableError) as exc:
            rule.create_rule(
                s,
                name="bad",
                subject_type="field",
                subject_identifier=f,
                effect="required_when",
                condition=_COND,
            )
        assert "soft-deleted" in str(exc.value)


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        rule.create_rule(
            s,
            name="r",
            subject_type="field",
            subject_identifier=f,
            effect="required_when",
            condition=_COND,
            identifier="RUL-001",
        )
    with session_scope() as s:
        row = rule.patch_rule(s, "RUL-001", status="confirmed")
        assert row["rule_status"] == "confirmed"
    with session_scope() as s, pytest.raises(StatusTransitionError):
        rule.patch_rule(s, "RUL-001", status="candidate")


def test_patch_condition_revalidated(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        rule.create_rule(
            s,
            name="r",
            subject_type="field",
            subject_identifier=f,
            effect="required_when",
            condition=_COND,
            identifier="RUL-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        rule.patch_rule(s, "RUL-001", condition={"all": []})


def test_patch_rejects_unknown_field(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        rule.create_rule(
            s,
            name="r",
            subject_type="field",
            subject_identifier=f,
            effect="required_when",
            condition=_COND,
            identifier="RUL-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        rule.patch_rule(s, "RUL-001", bogus="x")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f = _seed_field(s, e, "fld")
        rule.create_rule(
            s,
            name="r",
            subject_type="field",
            subject_identifier=f,
            effect="required_when",
            condition=_COND,
            identifier="RUL-001",
        )
    with session_scope() as s:
        rule.delete_rule(s, "RUL-001")
        assert rule.get_rule(s, "RUL-001") is None
        assert rule.get_rule(s, "RUL-001", include_deleted=True) is not None
    with session_scope() as s:
        rule.restore_rule(s, "RUL-001")
        assert rule.get_rule(s, "RUL-001") is not None
    with session_scope() as s, pytest.raises(UnprocessableError):
        rule.restore_rule(s, "RUL-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        rule.delete_rule(s, "RUL-404")


def test_list_filters_by_subject_and_effect(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        f1 = _seed_field(s, e, "a")
        f2 = _seed_field(s, e, "b")
        rule.create_rule(
            s, name="r1", subject_type="field", subject_identifier=f1,
            effect="required_when", condition=_COND,
        )
        rule.create_rule(
            s, name="r2", subject_type="field", subject_identifier=f2,
            effect="visible_when", condition=_COND,
        )
    with session_scope() as s:
        assert len(rule.list_rules(s)) == 2
        assert len(rule.list_rules(s, subject_identifier=f1)) == 1
        assert len(rule.list_rules(s, effect="visible_when")) == 1
