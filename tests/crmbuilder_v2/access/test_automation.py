"""Automation repository tests — PRJ-025 PI-189 slice 2.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
trigger vocab, condition validation, action-list validation, and the
entity existence/liveness surfaces.
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
from crmbuilder_v2.access.repositories import automation, entity
from crmbuilder_v2.access.vocab import (
    AUTOMATION_ACTION_TYPES,
    AUTOMATION_TRIGGERS,
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "automation_identifier": "VARCHAR",
    "automation_name": "VARCHAR",
    "automation_entity": "VARCHAR",
    "automation_trigger": "VARCHAR",
    "automation_condition": "JSON",
    "automation_actions": "JSON",
    "automation_description": "TEXT",
    "automation_notes": "TEXT",
    "automation_status": "VARCHAR",
    "automation_created_at": "DATETIME",
    "automation_updated_at": "DATETIME",
    "automation_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}

_ACTIONS = [{"type": "set_field", "field": "stage", "value": "won"}]
_COND = {"field": "amount", "op": "gte", "value": 1000}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_automations_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "automations" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("automations")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("automations")
    assert pk["constrained_columns"] == [
        "automation_identifier",
        "engagement_id",
    ]


def test_automation_registered_in_vocab():
    assert "automation" in ENTITY_TYPES
    assert "automation" in CHANGE_LOG_ENTITY_TYPES
    assert AUTOMATION_TRIGGERS == {
        "on_create",
        "on_update",
        "on_delete",
        "scheduled",
        "manual",
    }
    assert AUTOMATION_ACTION_TYPES == {
        "set_field",
        "send_notification",
        "create_record",
        "update_related",
        "webhook",
    }


def test_create_and_get_automation(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "Opportunity")
        row = automation.create_automation(
            s,
            name="Mark won",
            entity=e,
            trigger="on_update",
            actions=_ACTIONS,
            condition=_COND,
        )
    assert row["automation_identifier"] == "AUT-001"
    assert row["automation_status"] == "candidate"
    assert row["automation_trigger"] == "on_update"
    assert row["automation_actions"] == _ACTIONS
    assert row["automation_condition"] == _COND
    with session_scope() as s:
        got = automation.get_automation(s, "AUT-001")
        assert got["automation_entity"] == e


def test_create_without_condition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        row = automation.create_automation(
            s, name="a", entity=e, trigger="manual", actions=_ACTIONS
        )
        assert row["automation_condition"] is None


def test_create_rejects_bad_trigger(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            automation.create_automation(
                s, name="a", entity=e, trigger="on_login", actions=_ACTIONS
            )
        assert "automation_trigger" in str(exc.value)


def test_create_rejects_empty_actions(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            automation.create_automation(
                s, name="a", entity=e, trigger="manual", actions=[]
            )
        assert "automation_actions" in str(exc.value)


def test_create_rejects_bad_action_type(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            automation.create_automation(
                s,
                name="a",
                entity=e,
                trigger="manual",
                actions=[{"type": "launch_rockets"}],
            )
        assert "automation_actions" in str(exc.value)


def test_create_rejects_non_object_action(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError):
            automation.create_automation(
                s, name="a", entity=e, trigger="manual", actions=["set_field"]
            )


def test_create_rejects_malformed_condition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        with pytest.raises(UnprocessableError) as exc:
            automation.create_automation(
                s,
                name="a",
                entity=e,
                trigger="manual",
                actions=_ACTIONS,
                condition={"op": "eq", "value": 1},
            )
        assert "automation_condition" in str(exc.value)


def test_create_rejects_dead_entity(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        entity.delete_entity(s, e)
        with pytest.raises(UnprocessableError) as exc:
            automation.create_automation(
                s, name="a", entity=e, trigger="manual", actions=_ACTIONS
            )
        assert "soft-deleted" in str(exc.value)


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        automation.create_automation(
            s,
            name="a",
            entity=e,
            trigger="manual",
            actions=_ACTIONS,
            identifier="AUT-050",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        automation.create_automation(
            s,
            name="dup",
            entity=e,
            trigger="manual",
            actions=_ACTIONS,
            identifier="AUT-050",
        )


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        automation.create_automation(
            s,
            name="a",
            entity=e,
            trigger="manual",
            actions=_ACTIONS,
            identifier="AUT-001",
        )
    with session_scope() as s:
        row = automation.patch_automation(s, "AUT-001", status="confirmed")
        assert row["automation_status"] == "confirmed"
    with session_scope() as s, pytest.raises(StatusTransitionError):
        automation.patch_automation(s, "AUT-001", status="candidate")


def test_patch_actions_revalidated(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        automation.create_automation(
            s,
            name="a",
            entity=e,
            trigger="manual",
            actions=_ACTIONS,
            identifier="AUT-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        automation.patch_automation(
            s, "AUT-001", actions=[{"type": "nope"}]
        )


def test_patch_rejects_unknown_field(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        automation.create_automation(
            s,
            name="a",
            entity=e,
            trigger="manual",
            actions=_ACTIONS,
            identifier="AUT-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        automation.patch_automation(s, "AUT-001", bogus="x")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        e = _seed_entity(s, "E")
        automation.create_automation(
            s,
            name="a",
            entity=e,
            trigger="manual",
            actions=_ACTIONS,
            identifier="AUT-001",
        )
    with session_scope() as s:
        automation.delete_automation(s, "AUT-001")
        assert automation.get_automation(s, "AUT-001") is None
        assert (
            automation.get_automation(s, "AUT-001", include_deleted=True)
            is not None
        )
    with session_scope() as s:
        automation.restore_automation(s, "AUT-001")
        assert automation.get_automation(s, "AUT-001") is not None
    with session_scope() as s, pytest.raises(UnprocessableError):
        automation.restore_automation(s, "AUT-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        automation.delete_automation(s, "AUT-404")


def test_list_filters_by_entity_and_trigger(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        automation.create_automation(
            s, name="a1", entity=a, trigger="on_create", actions=_ACTIONS
        )
        automation.create_automation(
            s, name="a2", entity=b, trigger="manual", actions=_ACTIONS
        )
    with session_scope() as s:
        assert len(automation.list_automations(s)) == 2
        assert len(automation.list_automations(s, entity=a)) == 1
        assert len(automation.list_automations(s, trigger="manual")) == 1
