"""Schema-level tests for the PI-051 FieldVisibilityRule model (WTK-203).

Exercises the model directly via the ``v2_env`` fixture (which uses
``Base.metadata.create_all`` rather than the Alembic chain) so the tests run
regardless of whether the catalog YAMLs are present. The full Alembic chain is
exercised in ``tests/crmbuilder_v2/migration/test_0082_field_visibility_rule.py``.

The role and target_field scoping is a plain validated column (WTK-199 §4); the
access-layer resolution (live ROL-/FLD- of correct type) is a separate
access-area concern and is not asserted here — these tests cover only the
storage shape, the CHECK constraints, and the partial-unique contradiction guard.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.vocab import (
    FIELD_VISIBILITY_RULE_DEPLOYMENT_STATUSES,
)
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

_INSERT = (
    "INSERT INTO field_visibility_rules "
    "(field_visibility_rule_identifier, field_visibility_rule_visible, "
    "field_visibility_rule_role, field_visibility_rule_target_field, "
    "field_visibility_rule_deployment_status, field_visibility_rule_created_at, "
    "field_visibility_rule_updated_at, engagement_id) VALUES "
    "(:ident, :visible, :role, :field, :status, CURRENT_TIMESTAMP, "
    "CURRENT_TIMESTAMP, 'ENG-001')"
)


def _insert(s, **kw) -> None:
    params = {
        "ident": "FVR-001",
        "visible": 1,
        "role": "ROL-001",
        "field": "FLD-001",
        "status": "pending",
    }
    params.update(kw)
    s.execute(text(_INSERT), params)


# --- vocab ------------------------------------------------------------------


def test_deployment_status_vocab_is_the_designed_set():
    """The §4 value set, exactly — pending is the authored default."""
    assert FIELD_VISIBILITY_RULE_DEPLOYMENT_STATUSES == frozenset(
        {
            "pending",
            "deployed",
            "not_supported",
            "manual_required",
            "drift",
            "error",
        }
    )


# --- schema shape -----------------------------------------------------------


def test_table_exists_after_create_all(v2_env):
    with session_scope() as s:
        names = inspect(s.get_bind()).get_table_names()
    assert "field_visibility_rules" in names


def test_table_has_expected_columns(v2_env):
    with session_scope() as s:
        cols = {
            c["name"]
            for c in inspect(s.get_bind()).get_columns("field_visibility_rules")
        }
    expected = {
        "field_visibility_rule_identifier",
        "field_visibility_rule_visible",
        "field_visibility_rule_role",
        "field_visibility_rule_target_field",
        "field_visibility_rule_deployment_status",
        "field_visibility_rule_description",
        "field_visibility_rule_notes",
        "field_visibility_rule_created_at",
        "field_visibility_rule_updated_at",
        "field_visibility_rule_deleted_at",
        "engagement_id",
    }
    assert expected <= cols, f"missing columns: {sorted(expected - cols)}"


def test_partial_unique_index_on_role_and_field(v2_env):
    """A live-row unique index spans (engagement_id, role, target_field)."""
    with session_scope() as s:
        idx = inspect(s.get_bind()).get_indexes("field_visibility_rules")
    uq = [
        i
        for i in idx
        if i["unique"]
        and i["column_names"]
        == [
            "engagement_id",
            "field_visibility_rule_role",
            "field_visibility_rule_target_field",
        ]
    ]
    assert len(uq) == 1, f"expected the (role, field) unique index; got {idx}"


# --- inserts + CHECK constraints -------------------------------------------


def test_insert_minimal_row_succeeds(v2_env):
    with session_scope() as s:
        _insert(s)
        row = s.execute(
            text(
                "SELECT field_visibility_rule_deployment_status AS st, "
                "field_visibility_rule_deleted_at AS deleted "
                "FROM field_visibility_rules WHERE "
                "field_visibility_rule_identifier = 'FVR-001'"
            )
        ).one()
    assert row.st == "pending"
    assert row.deleted is None


def test_identifier_format_check_rejects_wrong_width(v2_env):
    with session_scope() as s:
        sp = s.begin_nested()
        with pytest.raises(IntegrityError):
            _insert(s, ident="FVR-0001")
        sp.rollback()


def test_identifier_format_check_rejects_wrong_prefix(v2_env):
    with session_scope() as s:
        sp = s.begin_nested()
        with pytest.raises(IntegrityError):
            _insert(s, ident="FPR-001")
        sp.rollback()


def test_deployment_status_check_rejects_unknown_value(v2_env):
    with session_scope() as s:
        sp = s.begin_nested()
        with pytest.raises(IntegrityError):
            _insert(s, status="published")
        sp.rollback()


def test_visible_bool_check_rejects_out_of_domain(v2_env):
    """``visible`` stores 0/1 only; a 2 is rejected by the boolean-domain CHECK."""
    with session_scope() as s:
        sp = s.begin_nested()
        with pytest.raises(IntegrityError):
            _insert(s, visible=2)
        sp.rollback()


def test_partial_unique_blocks_second_live_rule_for_same_pair(v2_env):
    """Two live rules for the same (role, field) is a representable-nowhere case."""
    with session_scope() as s:
        _insert(s, ident="FVR-001", visible=1)
        sp = s.begin_nested()
        with pytest.raises(IntegrityError):
            _insert(s, ident="FVR-002", visible=0)
        sp.rollback()


def test_soft_deleted_row_frees_the_pair(v2_env):
    """A soft-deleted rule no longer occupies the (role, field) unique slot."""
    with session_scope() as s:
        _insert(s, ident="FVR-001")
        s.execute(
            text(
                "UPDATE field_visibility_rules SET "
                "field_visibility_rule_deleted_at = CURRENT_TIMESTAMP "
                "WHERE field_visibility_rule_identifier = 'FVR-001'"
            )
        )
        # Same (role, field) now inserts cleanly — the partial index ignores
        # the soft-deleted row.
        _insert(s, ident="FVR-002")
        count = s.execute(
            text("SELECT COUNT(*) FROM field_visibility_rules")
        ).scalar_one()
    assert count == 2
