"""PI-202 / REQ-184, DEC-764 (WTK-220) — methodology areas get Architect + Tester.

DEC-764: now that content/authoring work has a real Develop (author records) and
Test (independently verify them), each methodology-* area's system profile catalog
is Architect (Design + Develop) + Tester — no Developer tier. These assert the
seed catalog reflects that.
"""

from __future__ import annotations

from crmbuilder_v2.access.repositories import registry_seed as rs

_METHODOLOGY_AREAS = {
    "methodology-interviews", "methodology-process",
    "methodology-templates", "methodology-product",
}


def _catalog_cells():
    return {(area, tier) for area, tier, *_ in rs._catalog_profiles()}


def test_each_methodology_area_has_architect_and_tester():
    cells = _catalog_cells()
    for area in _METHODOLOGY_AREAS:
        assert (area, "architect") in cells, f"{area} missing architect"
        assert (area, "tester") in cells, f"{area} missing tester"


def test_no_methodology_developer_tier():
    cells = _catalog_cells()
    for area in _METHODOLOGY_AREAS:
        assert (area, "developer") not in cells, f"{area} should have no developer (DEC-764)"


def test_methodology_areas_have_exactly_two_tiers():
    cells = _catalog_cells()
    for area in _METHODOLOGY_AREAS:
        tiers = {t for (a, t) in cells if a == area}
        assert tiers == {"architect", "tester"}, f"{area}: {tiers}"


def test_methodology_architect_spans_design_and_develop():
    desc = rs._METHODOLOGY_ARCHITECT_DESCRIPTION
    assert "Design" in desc and "Develop" in desc
    assert "author" in desc.lower()
    # it no longer claims architect-only / no Tester
    assert "architect tier only" not in desc
    assert "Tester" in desc  # references the separate Tester


def test_methodology_tester_is_independent_review_against_acceptance_criteria():
    desc = rs._METHODOLOGY_TESTER_DESCRIPTION
    assert "Tester" in desc
    assert "acceptance criteria" in desc
    assert "independent" in desc.lower()
    # completeness / correctness / conformance axes (REQ-169)
    assert "completeness" in desc.lower()
    assert "correctness" in desc.lower()
    assert "conformance" in desc.lower()
    # does not sign off — feeds the human gate (DEC-763)
    assert "sign off" in desc.lower() or "sign-off" in desc.lower()
