"""Finding repository tests — PI-134 reconciliation gate (DEC-400).

Covers the schema shape, identifier format + auto-assignment, the type /
severity / status / resolution-method enums, the open → referred → resolved
lifecycle (only ``resolved`` terminal, server-set ``finding_resolved_at``), the
eight repository methods, inline ``finding_relates_to`` edges, and the
soft-delete / restore round-trip.
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
from crmbuilder_v2.access.repositories import findings
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "finding_identifier",
    "finding_type",
    "finding_severity",
    "finding_status",
    "finding_summary",
    "finding_description",
    "finding_resolution",
    "finding_resolution_method",
    "finding_notes",
    "finding_created_at",
    "finding_updated_at",
    "finding_resolved_at",
    "finding_deleted_at",
    "engagement_id",
}


def _make(s, *, type="conflict", severity="blocking", summary="two specs clash"):
    return findings.create_finding(s, type=type, severity=severity, summary=summary)


def test_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "findings" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("findings")}
    assert cols == _EXPECTED_COLUMNS


def test_create_defaults_to_open(v2_env):
    with session_scope() as s:
        row = _make(s)
        assert row["finding_identifier"] == "FND-001"
        assert row["finding_status"] == "open"
        assert row["finding_resolved_at"] is None


def test_identifier_autoassigns_sequentially(v2_env):
    with session_scope() as s:
        a = _make(s)
        b = _make(s, summary="another")
        assert a["finding_identifier"] == "FND-001"
        assert b["finding_identifier"] == "FND-002"


def test_explicit_identifier_collision_rejected(v2_env):
    with session_scope() as s:
        findings.create_finding(
            s, type="gap", severity="advisory", summary="x", identifier="FND-005"
        )
        with pytest.raises(ConflictError):
            findings.create_finding(
                s, type="gap", severity="advisory", summary="y", identifier="FND-005"
            )


def test_bad_type_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            findings.create_finding(s, type="nope", severity="blocking", summary="x")


def test_bad_severity_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            findings.create_finding(s, type="gap", severity="urgent", summary="x")


def test_bad_resolution_method_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            findings.create_finding(
                s, type="gap", severity="advisory", summary="x",
                resolution_method="ignore",
            )


def test_resolve_sets_timestamp(v2_env):
    with session_scope() as s:
        row = _make(s)
        resolved = findings.patch_finding(
            s, row["finding_identifier"],
            status="resolved", resolution="revised spec A", resolution_method="revise",
        )
        assert resolved["finding_status"] == "resolved"
        assert resolved["finding_resolved_at"] is not None
        assert resolved["finding_resolution_method"] == "revise"


def test_referred_then_resolved(v2_env):
    with session_scope() as s:
        row = _make(s)
        ref = findings.patch_finding(s, row["finding_identifier"], status="referred")
        assert ref["finding_status"] == "referred"
        res = findings.patch_finding(s, row["finding_identifier"], status="resolved")
        assert res["finding_status"] == "resolved"


def test_resolved_is_terminal(v2_env):
    with session_scope() as s:
        row = _make(s)
        findings.patch_finding(s, row["finding_identifier"], status="resolved")
        with pytest.raises(StatusTransitionError):
            findings.patch_finding(s, row["finding_identifier"], status="open")


def test_list_filters_by_status_and_severity(v2_env):
    with session_scope() as s:
        _make(s, severity="blocking")
        _make(s, type="overlap", severity="advisory", summary="adv")
        blocking = findings.list_findings(s, severity="blocking")
        assert [f["finding_severity"] for f in blocking] == ["blocking"]
        open_ = findings.list_findings(s, status="open")
        assert len(open_) == 2


def test_relates_to_edge_inline(v2_env):
    with session_scope() as s:
        # The edge target need not pre-exist for the refs table; the vocab pair
        # (finding, planning_item, finding_relates_to) must be admitted.
        row = findings.create_finding(
            s, type="conflict", severity="blocking", summary="fk mismatch",
            references=[
                {
                    "source_type": "finding",
                    "source_id": "FND-001",
                    "target_type": "planning_item",
                    "target_id": "PI-999",
                    "relationship": "finding_relates_to",
                }
            ],
        )
        assert row["finding_identifier"] == "FND-001"


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        row = _make(s)
        fid = row["finding_identifier"]
        findings.delete_finding(s, fid)
        assert findings.get_finding(s, fid) is None
        assert findings.get_finding(s, fid, include_deleted=True) is not None
        findings.restore_finding(s, fid)
        assert findings.get_finding(s, fid) is not None


def test_get_missing_returns_none_and_row_raises(v2_env):
    with session_scope() as s:
        assert findings.get_finding(s, "FND-404") is None
        with pytest.raises(NotFoundError):
            findings.delete_finding(s, "FND-404")
