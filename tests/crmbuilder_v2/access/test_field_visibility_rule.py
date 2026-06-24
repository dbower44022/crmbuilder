"""Field-visibility-rule repository tests — PI-051 / REQ-128 (DEC-698).

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore, the
role/target_field live-resolution surfaces, the (role, field) uniqueness guard,
the status-transition gate, and the confirmed-before-deploy invariant.
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
)
from crmbuilder_v2.access.repositories import (
    field_visibility_rule as fvr,
)
from crmbuilder_v2.access.repositories import roles as roles_repo
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    FIELD_RULE_DEPLOYMENT_STATUSES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "field_visibility_rule_identifier": "VARCHAR",
    "field_visibility_rule_name": "VARCHAR",
    "field_visibility_rule_role": "VARCHAR",
    "field_visibility_rule_target_field": "VARCHAR",
    "field_visibility_rule_visible": "BOOLEAN",
    "field_visibility_rule_status": "VARCHAR",
    "field_visibility_rule_deployment_status": "VARCHAR",
    "field_visibility_rule_description": "TEXT",
    "field_visibility_rule_notes": "TEXT",
    "field_visibility_rule_created_at": "DATETIME",
    "field_visibility_rule_updated_at": "DATETIME",
    "field_visibility_rule_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def _seed_field(s, name: str) -> str:
    e = entity.create_entity(s, name=f"Ent-{name}", description="seed")[
        "entity_identifier"
    ]
    return field.create_field(
        s,
        field_belongs_to_entity_identifier=e,
        name=name,
        description="seed",
        type="text",
    )["field_identifier"]


def _seed_role(s, name: str) -> str:
    return roles_repo.create_role(s, name=name)["role_identifier"]


def test_table_has_expected_columns(v2_env):
    insp = inspect(get_engine())
    assert "field_visibility_rules" in insp.get_table_names()
    columns = {
        c["name"]: c for c in insp.get_columns("field_visibility_rules")
    }
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("field_visibility_rules")
    assert pk["constrained_columns"] == [
        "field_visibility_rule_identifier",
        "engagement_id",
    ]


def test_registered_in_vocab():
    assert "field_visibility_rule" in ENTITY_TYPES
    assert "field_visibility_rule" in CHANGE_LOG_ENTITY_TYPES
    assert FIELD_RULE_DEPLOYMENT_STATUSES == {
        "pending",
        "deployed",
        "not_supported",
        "manual_required",
        "drift",
        "error",
    }


def test_create_and_get(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "salaryBand")
        row = fvr.create_field_visibility_rule(
            s,
            name="Mentor — salaryBand hidden",
            role=r,
            target_field=f,
            visible=False,
        )
    assert row["field_visibility_rule_identifier"] == "FVR-001"
    assert row["field_visibility_rule_status"] == "candidate"
    assert row["field_visibility_rule_deployment_status"] == "pending"
    assert row["field_visibility_rule_visible"] is False
    with session_scope() as s:
        got = fvr.get_field_visibility_rule(s, "FVR-001")
        assert got["field_visibility_rule_visible"] is False


def test_create_rejects_non_bool_visible(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        with pytest.raises(UnprocessableError):
            fvr.create_field_visibility_rule(
                s, name="x", role=r, target_field=f, visible="yes"
            )


def test_create_rejects_dead_role(v2_env):
    with session_scope() as s:
        f = _seed_field(s, "fld")
        with pytest.raises(UnprocessableError):
            fvr.create_field_visibility_rule(
                s, name="x", role="ROL-999", target_field=f, visible=True
            )


def test_create_rejects_dead_field(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        with pytest.raises(UnprocessableError):
            fvr.create_field_visibility_rule(
                s, name="x", role=r, target_field="FLD-999", visible=True
            )


def test_duplicate_role_field_pair_rejected(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r, target_field=f, visible=True
        )
        with pytest.raises(ConflictError):
            fvr.create_field_visibility_rule(
                s, name="b", role=r, target_field=f, visible=False
            )


def test_distinct_pair_allowed(v2_env):
    with session_scope() as s:
        r1 = _seed_role(s, "Mentor")
        r2 = _seed_role(s, "Admin")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r1, target_field=f, visible=True
        )
        fvr.create_field_visibility_rule(
            s, name="b", role=r2, target_field=f, visible=False
        )
        assert len(fvr.list_field_visibility_rules(s)) == 2


def test_bad_status_transition_rejected(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r, target_field=f, visible=True
        )
        fvr.patch_field_visibility_rule(s, "FVR-001", status="rejected")
        with pytest.raises(StatusTransitionError):
            # rejected is terminal.
            fvr.patch_field_visibility_rule(s, "FVR-001", status="confirmed")


def test_deploy_before_confirmed_rejected(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r, target_field=f, visible=True
        )
        with pytest.raises(UnprocessableError):
            fvr.patch_field_visibility_rule(
                s, "FVR-001", deployment_status="not_supported"
            )


def test_deploy_allowed_when_confirmed(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r, target_field=f, visible=True
        )
        fvr.patch_field_visibility_rule(s, "FVR-001", status="confirmed")
        row = fvr.patch_field_visibility_rule(
            s, "FVR-001", deployment_status="not_supported"
        )
        assert (
            row["field_visibility_rule_deployment_status"] == "not_supported"
        )


def test_update_round_trip(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r, target_field=f, visible=True
        )
        row = fvr.update_field_visibility_rule(
            s,
            "FVR-001",
            name="renamed",
            role=r,
            target_field=f,
            visible=False,
            status="confirmed",
            deployment_status="pending",
        )
        assert row["field_visibility_rule_name"] == "renamed"
        assert row["field_visibility_rule_visible"] is False
        assert row["field_visibility_rule_status"] == "confirmed"


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fvr.create_field_visibility_rule(
            s, name="a", role=r, target_field=f, visible=True
        )
        fvr.delete_field_visibility_rule(s, "FVR-001")
        assert fvr.get_field_visibility_rule(s, "FVR-001") is None
    with session_scope() as s:
        restored = fvr.restore_field_visibility_rule(s, "FVR-001")
        assert restored["field_visibility_rule_deleted_at"] is None


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        fvr.update_field_visibility_rule(
            s,
            "FVR-404",
            name="x",
            role="ROL-001",
            target_field="FLD-001",
            visible=True,
            status="candidate",
            deployment_status="pending",
        )


def test_next_identifier(v2_env):
    with session_scope() as s:
        assert fvr.next_field_visibility_rule_identifier(s) == "FVR-001"
