"""Reference Entry contextual-loader tests — REL-016 / PI-066 (REQ-401).

Covers ``search_reference_entries``: keyword/statement matching against
``trigger_keywords`` + ``applies_to``, overlap ranking, kind narrowing, the
system|engagement scope merge, the no-terms scoped-list fallback, and status
filtering.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    reference_entries,
    reference_entry_seed,
)


def _seed(s):
    reference_entry_seed.seed_reference_entries(s)


def test_matches_by_statement_keyword(v2_env):
    with session_scope() as s:
        _seed(s)
    with session_scope() as s:
        hits = reference_entries.search_reference_entries(
            s, text="We run a nonprofit mentoring program for youth."
        )
    names = {h["name"] for h in hits}
    # All three mentoring entries (domain knowledge, structure, inventory) match.
    assert "Nonprofit Mentoring Organization" in names
    # A foundation-only entry should not match a mentoring statement.
    assert "Charitable Foundation" not in names


def test_kind_narrowing(v2_env):
    with session_scope() as s:
        _seed(s)
    with session_scope() as s:
        hits = reference_entries.search_reference_entries(
            s, text="mentoring", kind="domain_knowledge"
        )
    assert all(h["kind"] == "domain_knowledge" for h in hits)
    assert {h["name"] for h in hits} == {"Nonprofit Mentoring Organization"}


def test_explicit_keywords(v2_env):
    with session_scope() as s:
        _seed(s)
    with session_scope() as s:
        hits = reference_entries.search_reference_entries(
            s, keywords=["grantmaking", "grantee"]
        )
    assert {h["name"] for h in hits} >= {
        "Charitable Foundation",
        "Charitable Foundation — Structure",
        "Charitable Foundation — Inventory",
    }
    assert "Nonprofit Mentoring Organization" not in {h["name"] for h in hits}


def test_ranking_by_overlap(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s,
            name="High",
            kind="domain_knowledge",
            content={"body": "x"},
            trigger_keywords=["mentoring", "mentor", "mentee"],
            applies_to="nonprofit mentoring",
        )
        reference_entries.create(
            s,
            name="Low",
            kind="domain_knowledge",
            content={"body": "x"},
            trigger_keywords=["mentoring"],
        )
    with session_scope() as s:
        hits = reference_entries.search_reference_entries(
            s, text="mentoring mentor mentee nonprofit mentoring"
        )
    assert [h["name"] for h in hits] == ["High", "Low"]


def test_no_terms_returns_all_scoped(v2_env):
    with session_scope() as s:
        _seed(s)
    with session_scope() as s:
        allrows = reference_entries.search_reference_entries(s)
    assert len(allrows) == 9


def test_scope_merge_system_plus_engagement(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s,
            name="SysMentor",
            kind="domain_knowledge",
            content={"body": "x"},
            trigger_keywords=["mentoring"],
        )
        reference_entries.create(
            s,
            name="EngMentor",
            kind="domain_knowledge",
            content={"body": "x"},
            trigger_keywords=["mentoring"],
            scope="ENG-001",
        )
    with session_scope() as s:
        # Active ENG-001 sees both system + its own; None sees only system.
        both = reference_entries.search_reference_entries(
            s, text="mentoring", engagement_id="ENG-001"
        )
        sys_only = reference_entries.search_reference_entries(
            s, text="mentoring", engagement_id=None
        )
    assert {h["name"] for h in both} == {"SysMentor", "EngMentor"}
    assert {h["name"] for h in sys_only} == {"SysMentor"}


def test_retired_excluded_by_default(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s,
            name="Old",
            kind="domain_knowledge",
            content={"body": "x"},
            trigger_keywords=["mentoring"],
            status="retired",
        )
    with session_scope() as s:
        active = reference_entries.search_reference_entries(s, text="mentoring")
        retired = reference_entries.search_reference_entries(
            s, text="mentoring", status="retired"
        )
    assert active == []
    assert {h["name"] for h in retired} == {"Old"}
