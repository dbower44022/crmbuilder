"""Plan-freeze inviolability tests — PI-211 (PRJ-034), RW1.

Covers pi-211-plan-freeze-inviolability-architecture.md §5: a frozen plan cannot
be reopened (structural, affirmed) and the traceable correction route
(open_correction_release).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, StatusTransitionError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import references, releases


def _release(s, status="preliminary_planning", title="R"):
    rel = releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]
    if status != "preliminary_planning":
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        row.release_status = status
        s.flush()
    return rel


# ---------------------------------------------------------------------------
# Inviolability (RW1) — structural, affirmed
# ---------------------------------------------------------------------------


def test_ready_cannot_go_back_to_planning(v2_env):
    with session_scope() as s:
        rel = _release(s, status="ready")
        with pytest.raises(StatusTransitionError):
            releases.transition(s, rel, "architecture_planning")
        with pytest.raises(StatusTransitionError):
            releases.transition(s, rel, "reconciliation")


def test_shipped_is_terminal(v2_env):
    with session_scope() as s:
        rel = _release(s, status="shipped")
        with pytest.raises(StatusTransitionError):
            releases.transition(s, rel, "development")


# ---------------------------------------------------------------------------
# Correction route (DEC-507)
# ---------------------------------------------------------------------------


def test_open_correction_creates_linked_successor(v2_env):
    with session_scope() as s:
        prior = _release(s, status="shipped", title="Shipped")
        new = releases.open_correction_release(
            s, prior, title="Correction", description="fix"
        )
        assert new["release_status"] == "preliminary_planning"
        # the corrects edge new -> prior exists
        edges = references.list_references(
            s, source_id=new["release_identifier"],
            relationship_kind="release_corrects_release",
        )
        assert [e["target_id"] for e in edges] == [prior]


def test_correction_rejected_on_unfrozen_prior(v2_env):
    with session_scope() as s:
        prior = _release(s, status="development_planning")
        with pytest.raises(ConflictError, match="not yet.*frozen"):
            releases.open_correction_release(
                s, prior, title="C", description="d"
            )


def test_correction_allowed_on_committed_prior(v2_env):
    with session_scope() as s:
        prior = _release(s, status="architecture_planning", title="Committed")
        new = releases.open_correction_release(
            s, prior, title="C", description="d"
        )
        assert new["release_identifier"] != prior
