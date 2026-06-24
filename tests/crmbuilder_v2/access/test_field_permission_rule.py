"""Field-permission-rule repository tests — PI-051 / REQ-129 (DEC-698).

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
    field_permission_rule as fpr,
)
from crmbuilder_v2.access.repositories import roles as roles_repo
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    FIELD_PERMISSION_LEVELS,
    FIELD_RULE_DEPLOYMENT_STATUSES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "field_permission_rule_identifier": "VARCHAR",
    "field_permission_rule_name": "VARCHAR",
    "field_permission_rule_role": "VARCHAR",
    "field_permission_rule_target_field": "VARCHAR",
    "field_permission_rule_permission_level": "VARCHAR",
    "field_permission_rule_status": "VARCHAR",
    "field_permission_rule_deployment_status": "VARCHAR",
    "field_permission_rule_description": "TEXT",
    "field_permission_rule_notes": "TEXT",
    "field_permission_rule_created_at": "DATETIME",
    "field_permission_rule_updated_at": "DATETIME",
    "field_permission_rule_deleted_at": "DATETIME",
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
    assert "field_permission_rules" in insp.get_table_names()
    columns = {
        c["name"]: c for c in insp.get_columns("field_permission_rules")
    }
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("field_permission_rules")
    assert pk["constrained_columns"] == [
        "field_permission_rule_identifier",
        "engagement_id",
    ]


def test_registered_in_vocab():
    assert "field_permission_rule" in ENTITY_TYPES
    assert "field_permission_rule" in CHANGE_LOG_ENTITY_TYPES
    assert FIELD_PERMISSION_LEVELS == {"read_write", "read_only", "no_access"}
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
        f = _seed_field(s, "backgroundCheck")
        row = fpr.create_field_permission_rule(
            s,
            name="Mentor — backgroundCheck",
            role=r,
            target_field=f,
            permission_level="read_only",
        )
    assert row["field_permission_rule_identifier"] == "FPR-001"
    assert row["field_permission_rule_status"] == "candidate"
    assert row["field_permission_rule_deployment_status"] == "pending"
    with session_scope() as s:
        got = fpr.get_field_permission_rule(s, "FPR-001")
        assert got["field_permission_rule_permission_level"] == "read_only"


def test_create_rejects_bad_permission_level(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        with pytest.raises(UnprocessableError):
            fpr.create_field_permission_rule(
                s,
                name="x",
                role=r,
                target_field=f,
                permission_level="write_only",
            )


def test_create_rejects_dead_role(v2_env):
    with session_scope() as s:
        f = _seed_field(s, "fld")
        with pytest.raises(UnprocessableError):
            fpr.create_field_permission_rule(
                s,
                name="x",
                role="ROL-999",
                target_field=f,
                permission_level="read_only",
            )


def test_create_rejects_dead_field(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        with pytest.raises(UnprocessableError):
            fpr.create_field_permission_rule(
                s,
                name="x",
                role=r,
                target_field="FLD-999",
                permission_level="read_only",
            )


def test_duplicate_role_field_pair_rejected(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r, target_field=f, permission_level="read_only"
        )
        with pytest.raises(ConflictError):
            fpr.create_field_permission_rule(
                s,
                name="b",
                role=r,
                target_field=f,
                permission_level="no_access",
            )


def test_distinct_pair_allowed(v2_env):
    with session_scope() as s:
        r1 = _seed_role(s, "Mentor")
        r2 = _seed_role(s, "Admin")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r1, target_field=f, permission_level="read_only"
        )
        fpr.create_field_permission_rule(
            s, name="b", role=r2, target_field=f, permission_level="no_access"
        )
        assert len(fpr.list_field_permission_rules(s)) == 2


def test_bad_status_transition_rejected(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r, target_field=f, permission_level="read_only"
        )
        fpr.patch_field_permission_rule(s, "FPR-001", status="confirmed")
        with pytest.raises(StatusTransitionError):
            # confirmed -> candidate is not allowed.
            fpr.patch_field_permission_rule(s, "FPR-001", status="candidate")


def test_deploy_before_confirmed_rejected(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r, target_field=f, permission_level="read_only"
        )
        # status is candidate; cannot move deployment_status off pending.
        with pytest.raises(UnprocessableError):
            fpr.patch_field_permission_rule(
                s, "FPR-001", deployment_status="deployed"
            )


def test_deploy_allowed_when_confirmed(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r, target_field=f, permission_level="read_only"
        )
        fpr.patch_field_permission_rule(s, "FPR-001", status="confirmed")
        row = fpr.patch_field_permission_rule(
            s, "FPR-001", deployment_status="deployed"
        )
        assert row["field_permission_rule_deployment_status"] == "deployed"


def test_create_deployed_requires_confirmed(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        # candidate + non-pending deployment_status on create is rejected.
        with pytest.raises(UnprocessableError):
            fpr.create_field_permission_rule(
                s,
                name="a",
                role=r,
                target_field=f,
                permission_level="read_only",
                deployment_status="deployed",
            )
        # confirmed + deployed on create is accepted.
        row = fpr.create_field_permission_rule(
            s,
            name="b",
            role=r,
            target_field=f,
            permission_level="read_only",
            status="confirmed",
            deployment_status="deployed",
        )
        assert row["field_permission_rule_status"] == "confirmed"


def test_update_round_trip(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r, target_field=f, permission_level="read_only"
        )
        row = fpr.update_field_permission_rule(
            s,
            "FPR-001",
            name="renamed",
            role=r,
            target_field=f,
            permission_level="read_write",
            status="confirmed",
            deployment_status="pending",
        )
        assert row["field_permission_rule_name"] == "renamed"
        assert row["field_permission_rule_permission_level"] == "read_write"
        assert row["field_permission_rule_status"] == "confirmed"


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        r = _seed_role(s, "Mentor")
        f = _seed_field(s, "fld")
        fpr.create_field_permission_rule(
            s, name="a", role=r, target_field=f, permission_level="read_only"
        )
        fpr.delete_field_permission_rule(s, "FPR-001")
        assert fpr.get_field_permission_rule(s, "FPR-001") is None
        # the cell is now free — a replacement is allowed.
        fpr.create_field_permission_rule(
            s, name="b", role=r, target_field=f, permission_level="no_access"
        )
    with session_scope() as s:
        # restoring FPR-001 now collides with the live FPR-002.
        with pytest.raises(ConflictError):
            fpr.restore_field_permission_rule(s, "FPR-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        fpr.update_field_permission_rule(
            s,
            "FPR-404",
            name="x",
            role="ROL-001",
            target_field="FLD-001",
            permission_level="read_only",
            status="candidate",
            deployment_status="pending",
        )


def test_next_identifier(v2_env):
    with session_scope() as s:
        assert fpr.next_field_permission_rule_identifier(s) == "FPR-001"
