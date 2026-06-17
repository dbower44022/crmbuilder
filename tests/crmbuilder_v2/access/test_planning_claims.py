"""Two-temperature planning tests — PI-207 (PRJ-031), §5.1/§11.8.

Covers pi-207-two-temperature-planning-architecture.md §6: the temperature
classifier and the single-threaded-by-area planning claim (refused outside the
committed window, refused on area overlap, parallel across areas, holder-only
release, area validation). Release statuses are set via the ORM to isolate the
claim substrate from the transition gates (those live in test_release).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import planning_claims as pc
from crmbuilder_v2.access.repositories import releases


def _release(s, status="reconciliation"):
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    if status != "preliminary_planning":
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        row.release_status = status
        s.flush()
    return rel


@pytest.mark.parametrize(
    "status,temp",
    [
        ("preliminary_planning", "conceptual"),
        ("development_planning", "conceptual"),
        ("reconciliation", "committed"),
        ("architecture_planning", "committed"),
        ("ready", None),
        ("development", None),
        ("shipped", None),
    ],
)
def test_temperature(status, temp):
    assert pc.temperature(status) == temp


def test_claim_refused_when_conceptual(v2_env):
    with session_scope() as s:
        rel = _release(s, status="development_planning")
        with pytest.raises(ConflictError, match="committed planning window"):
            pc.claim_area(s, rel, "storage", "agent-1")


def test_claim_refused_when_out_of_planning_regime(v2_env):
    with session_scope() as s:
        rel = _release(s, status="development")
        with pytest.raises(ConflictError, match="committed planning window"):
            pc.claim_area(s, rel, "storage", "agent-1")


def test_claim_succeeds_in_committed_window(v2_env):
    with session_scope() as s:
        rel = _release(s, status="reconciliation")
        out = pc.claim_area(s, rel, "storage", "agent-1")
        assert out["area"] == "storage"
        assert out["claimed_by"] == "agent-1"


def test_second_claim_same_area_refused(v2_env):
    with session_scope() as s:
        rel = _release(s, status="reconciliation")
        pc.claim_area(s, rel, "storage", "agent-1")
        with pytest.raises(ConflictError, match="already claimed"):
            pc.claim_area(s, rel, "storage", "agent-2")


def test_different_areas_claimable_in_parallel(v2_env):
    with session_scope() as s:
        rel = _release(s, status="architecture_planning")
        pc.claim_area(s, rel, "storage", "agent-1")
        out = pc.claim_area(s, rel, "access", "agent-2")
        assert out["area"] == "access"
        assert {c["area"] for c in pc.area_claims(s, rel)} == {"storage", "access"}


def test_release_then_reclaim(v2_env):
    with session_scope() as s:
        rel = _release(s, status="reconciliation")
        pc.claim_area(s, rel, "storage", "agent-1")
        pc.release_area(s, rel, "storage", "agent-1")
        # now reclaimable by another agent
        out = pc.claim_area(s, rel, "storage", "agent-2")
        assert out["claimed_by"] == "agent-2"


def test_only_holder_may_release(v2_env):
    with session_scope() as s:
        rel = _release(s, status="reconciliation")
        pc.claim_area(s, rel, "storage", "agent-1")
        with pytest.raises(ConflictError, match="only the holder"):
            pc.release_area(s, rel, "storage", "agent-2")


def test_release_missing_claim_404(v2_env):
    with session_scope() as s:
        rel = _release(s, status="reconciliation")
        with pytest.raises(NotFoundError):
            pc.release_area(s, rel, "storage", "agent-1")


def test_invalid_area_rejected(v2_env):
    with session_scope() as s:
        rel = _release(s, status="reconciliation")
        with pytest.raises(UnprocessableError):
            pc.claim_area(s, rel, "not-an-area", "agent-1")
