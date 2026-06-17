"""Cascade re-validation tests — PI-213 (PRJ-034), RW4.

Covers pi-213-cascade-revalidation-architecture.md §6: the cascade set at reopen,
revalidate_area, outstanding_revalidations, and the deployment->shipped ship gate
(no exemption).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import reopen
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import releases


def _dev_release(s, status="development"):
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    if status != "preliminary_planning":
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        row.release_status = status
        s.flush()
    return rel


def _set_status(s, rel, status):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    s.flush()


def test_reopen_populates_cascade(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        r = reopen.reopen_area(s, rel, "storage", "need", approval_decision_identifier="DEC-001")
        # storage's downstream = access, api, mcp, ui
        assert set(r["cascade_areas"]) == {"access", "api", "mcp", "ui"}
        assert r["revalidated_areas"] == []
        assert reopen.outstanding_revalidations(s, rel) == {"access", "api", "mcp", "ui"}


def test_revalidate_reduces_outstanding(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        r = reopen.reopen_area(s, rel, "api", "need", approval_decision_identifier="DEC-001")  # downstream = mcp, ui
        assert set(r["cascade_areas"]) == {"mcp", "ui"}
        reopen.revalidate_area(s, r["id"], "mcp")
        assert reopen.outstanding_revalidations(s, rel) == {"ui"}
        reopen.revalidate_area(s, r["id"], "ui")
        assert reopen.outstanding_revalidations(s, rel) == set()


def test_revalidate_rejects_non_cascade_and_double(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        r = reopen.reopen_area(s, rel, "api", "need", approval_decision_identifier="DEC-001")
        with pytest.raises(ConflictError, match="not in the cascade"):
            reopen.revalidate_area(s, r["id"], "storage")  # upstream, not downstream
        reopen.revalidate_area(s, r["id"], "mcp")
        with pytest.raises(ConflictError, match="already re-validated"):
            reopen.revalidate_area(s, r["id"], "mcp")


def test_ship_gate_blocks_until_all_revalidated(v2_env):
    with session_scope() as s:
        rel = _dev_release(s, status="development")
        r = reopen.reopen_area(s, rel, "api", "need", approval_decision_identifier="DEC-001")  # downstream mcp, ui
        reopen.refreeze_area(s, rel, "api")  # re-freeze upstream
        # drive to deployment (qa/test passes recorded along the way)
        _set_status(s, rel, "deployment")
        # cannot ship: mcp, ui not re-validated
        with pytest.raises(ConflictError, match="re-validate"):
            releases.transition(s, rel, "shipped")
        reopen.revalidate_area(s, r["id"], "mcp")
        with pytest.raises(ConflictError, match="re-validate"):
            releases.transition(s, rel, "shipped")  # ui still outstanding (no exemption)
        reopen.revalidate_area(s, r["id"], "ui")
        assert releases.transition(s, rel, "shipped")["release_status"] == "shipped"


def test_ship_unaffected_without_reopen(v2_env):
    with session_scope() as s:
        rel = _dev_release(s, status="deployment")
        assert releases.transition(s, rel, "shipped")["release_status"] == "shipped"
