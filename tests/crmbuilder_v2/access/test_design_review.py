"""Design Review gate — PI-246 (PRJ-041 / REQ-295), Phase 4c.

One **consolidated** human sign-off over the whole set of a release's per-area
implementation + testable specs (reusing the PI-238 freshness-checked sign-off
machinery via a new ``design`` stage). The per-area Develop stage does not proceed
until a fresh Design Review sign-off exists; revising any area's spec — or adding a
new area — voids the prior sign-off and re-opens review.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import (
    area_specs,
    release_signoffs,
    releases,
)


def _rel_with_specs(s, areas):
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    for a in areas:
        area_specs.author_spec(s, rel, a, implementation=f"impl {a}",
                               testable=f"checks {a}")
    return rel


def _signoff(s, rel):
    return release_signoffs.create_signoff(
        s, rel, stage="design", reviewer="reviewer", attestation="reviewed all specs")


def test_design_signoff_fresh_then_stale_on_spec_revision(v2_env):
    with session_scope() as s:
        rel = _rel_with_specs(s, ["storage", "api"])
        _signoff(s, rel)
        assert release_signoffs.fresh_signoff(s, rel, "design") is not None
        # revising any one area's spec voids the consolidated sign-off
        area_specs.author_spec(s, rel, "storage", implementation="impl v2",
                               testable="checks v2", trigger_kind="revision")
        assert release_signoffs.fresh_signoff(s, rel, "design") is None


def test_design_signoff_stale_when_a_new_area_is_added(v2_env):
    with session_scope() as s:
        rel = _rel_with_specs(s, ["storage"])
        _signoff(s, rel)
        assert release_signoffs.fresh_signoff(s, rel, "design") is not None
        # the review is over the WHOLE set — a new area's spec changes the set
        area_specs.author_spec(s, rel, "api", implementation="impl api",
                               testable="checks api")
        assert release_signoffs.fresh_signoff(s, rel, "design") is None


def test_require_design_review_gate_blocks_then_allows(v2_env):
    with session_scope() as s:
        rel = _rel_with_specs(s, ["storage", "api"])
        with pytest.raises(ConflictError, match="Design Review"):
            orch.require_design_review_signoff(s, rel)
        _signoff(s, rel)
        orch.require_design_review_signoff(s, rel)  # no raise once signed fresh


def test_require_design_review_blocks_again_after_revision(v2_env):
    with session_scope() as s:
        rel = _rel_with_specs(s, ["storage"])
        _signoff(s, rel)
        orch.require_design_review_signoff(s, rel)  # ok
        area_specs.author_spec(s, rel, "storage", implementation="v2",
                               testable="v2", trigger_kind="design_review")
        with pytest.raises(ConflictError, match="Design Review"):
            orch.require_design_review_signoff(s, rel)


def test_design_review_status(v2_env):
    with session_scope() as s:
        rel = _rel_with_specs(s, ["storage"])
        assert orch.design_review_status(s, rel)["is_signed_fresh"] is False
        _signoff(s, rel)
        assert orch.design_review_status(s, rel)["is_signed_fresh"] is True
