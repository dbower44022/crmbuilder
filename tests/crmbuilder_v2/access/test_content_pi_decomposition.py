"""PI-202 / REQ-186 (WTK-218) — content PIs decompose to the same shape.

DEC-444 ruled that content/authoring work runs the same four-step Process with
content meanings, and REQ-186 rules there is **no shape change** for content
Planning Items: a content PI decomposes into the same active Design → Develop →
Test phases (never collapsed to Design-only). Decomposition is content-agnostic —
the content-vs-software distinction is a *verification* concern (REQ-187), not a
decomposition-shape one. These tests lock that in, so a future "content →
Design-only" special case would fail loudly.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import decomposition, planning_items

_EXEC = "Content PI decomposition test executive summary, well over the floor. " * 5

# Methodology-* areas mark a Planning Item as content (REQ-185).
_CONTENT_AREAS = ["methodology-process"]


def _content_pi(s, ident, title="Author the methodology rules"):
    planning_items.create(
        s, identifier=ident, title=title, item_type="pending_work",
        status="Draft", executive_summary=_EXEC, area=_CONTENT_AREAS,
    )
    return ident


def test_content_pi_decomposes_to_all_three_active_phases(v2_env):
    with session_scope() as s:
        pid = _content_pi(s, ident="PI-820")
        created = decomposition.decompose_planning_item(s, pid)
    # Same shape as software: the three work-step phases, in order — not Design-only.
    assert [w["workstream_phase_type"] for w in created] == list(
        decomposition.PHASE_SEQUENCE
    )
    assert [w["workstream_phase_type"] for w in created] == ["Design", "Develop", "Test"]
    # All active (Planned), none skipped / Not Applicable for being non-software.
    assert all(w["workstream_status"] == "Planned" for w in created)
    assert len(created) == 3


def test_content_pi_decomposition_matches_software_shape(v2_env):
    # A content PI and a software PI produce the identical phase sequence —
    # decomposition does not branch on content vs software (REQ-186).
    with session_scope() as s:
        content = _content_pi(s, ident="PI-821")
        planning_items.create(
            s, identifier="PI-822", title="Build the thing",
            item_type="pending_work", status="Draft", executive_summary=_EXEC,
            area=["access"],
        )
        content_phases = [
            w["workstream_phase_type"]
            for w in decomposition.decompose_planning_item(s, content)
        ]
        software_phases = [
            w["workstream_phase_type"]
            for w in decomposition.decompose_planning_item(s, "PI-822")
        ]
    assert content_phases == software_phases == ["Design", "Develop", "Test"]
