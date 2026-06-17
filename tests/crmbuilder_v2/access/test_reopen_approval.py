"""Reopen-approval tests — PI-214 (PRJ-034), RW5/§16.8.

Covers pi-214-reopen-approval-architecture.md §7: tier computation (breadth +
depth override + repeat escalation), the approval gate, lead_auto self-auth, and
the impact report.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import reopen
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import releases


def _dev_release(s):
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = "development"
    s.flush()
    return rel


def test_tier_by_breadth_and_depth(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        assert reopen.reopen_tier(s, rel, "ui") == "lead_auto"   # 0 downstream
        assert reopen.reopen_tier(s, rel, "api") == "lead"       # 2 downstream
        assert reopen.reopen_tier(s, rel, "access") == "pm"      # 3 downstream
        assert reopen.reopen_tier(s, rel, "storage") == "human"  # foundational


def test_repeat_escalates_tier(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        reopen.reopen_area(s, rel, "api", "first",
                           approval_decision_identifier="DEC-001")  # lead
        reopen.refreeze_area(s, rel, "api")
        # a second reopen of api escalates lead -> pm.
        assert reopen.reopen_tier(s, rel, "api") == "pm"


def test_gate_requires_approval_above_lead_auto(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        with pytest.raises(ConflictError, match="approval decision"):
            reopen.reopen_area(s, rel, "api", "need")  # lead tier, no decision
        row = reopen.reopen_area(s, rel, "api", "need",
                                 approval_decision_identifier="DEC-007")
        assert row["approval_tier"] == "lead"
        assert row["approval_decision_identifier"] == "DEC-007"


def test_lead_auto_needs_no_approval(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        row = reopen.reopen_area(s, rel, "ui", "tweak")  # empty radius
        assert row["approval_tier"] == "lead_auto"
        assert row["approval_decision_identifier"] is None


def test_impact_report(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        report = reopen.reopen_impact(s, rel, "access")
        assert report["reopen_point"] == "access"
        assert report["downstream_areas"] == ["api", "mcp", "ui"]
        assert report["count"] == 3
        assert report["tier"] == "pm"
        assert report["is_repeat"] is False
