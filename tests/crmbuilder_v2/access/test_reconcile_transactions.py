"""Reconcile transaction-log repository tests — PI-318 (REL-024)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import reconcile_transactions as rt


def _record(s, **over):
    base = dict(
        direction="capture",
        source_ref="INST-001",
        target_ref="design",
        member_type="field",
        member_identifier="FLD-001",
        actor="Doug",
        attribute="field_type",
        before_value="text",
        after_value="varchar",
    )
    base.update(over)
    return rt.record(s, **base)


def test_record_and_get_roundtrip(v2_env):
    with session_scope() as s:
        row = _record(s)
        assert row["status"] == "applied"
        assert row["before_value"] == "text"
        assert row["after_value"] == "varchar"
        again = rt.get(s, row["id"])
        assert again["id"] == row["id"]


def test_bad_direction_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            _record(s, direction="sideways")


def test_list_filters(v2_env):
    with session_scope() as s:
        _record(s, batch_id="B1", member_identifier="FLD-001")
        _record(s, batch_id="B1", member_identifier="FLD-002", direction="publish",
                source_ref="design", target_ref="INST-002")
        _record(s, batch_id="B2", member_identifier="FLD-003")
        assert len(rt.list_transactions(s, batch_id="B1")) == 2
        assert len(rt.list_transactions(s, member_identifier="FLD-003")) == 1
        assert len(rt.list_transactions(s, status="applied")) == 3
        # newest first
        ids = [r["id"] for r in rt.list_transactions(s)]
        assert ids == sorted(ids, reverse=True)


def test_mark_rolled_back_then_double_is_conflict(v2_env):
    with session_scope() as s:
        row = _record(s)
        rolled = rt.mark_rolled_back(s, row["id"], actor="Doug")
        assert rolled["status"] == "rolled_back"
        assert rolled["rolled_back_by"] == "Doug"
        assert rolled["rolled_back_at"] is not None
        with pytest.raises(ConflictError):
            rt.mark_rolled_back(s, row["id"], actor="Doug")


def test_get_missing_raises(v2_env):
    with session_scope() as s:
        with pytest.raises(NotFoundError):
            rt.get(s, 999999)
