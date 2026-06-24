"""PI-301 (DEC-677) — capability_description round-trip + search_agents pre-filter.

Proves (1) the new searchable capability object round-trips through the access repo,
and (2) ``search_agents`` is a strict, deterministic structured pre-filter: it never
crosses the area anchor (the safety backstop), respects status, applies the
technology-agnostic rule, and orders by ``needs`` overlap deterministically.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import agent_profiles


def _cap(summary, *, specialties=None, builds=None, constraints=None):
    return {
        "summary": summary,
        "specialties": specialties or [],
        "builds": builds or [],
        "constraints": constraints or [],
    }


def test_capability_description_round_trips(v2_env):
    cap = _cap(
        "Builds PySide6 desktop panels.",
        specialties=["forms", "tables"],
        builds=["dialogs", "panels"],
        constraints=["never raw QMessageBox"],
    )
    with session_scope() as s:
        created = agent_profiles.create(
            s, area="ui", tier="developer", description="Qt desktop UI dev.",
            technology="qt-desktop", scope="system", capability_description=cap,
        )
        assert created["capability_description"] == cap
        fetched = agent_profiles.get(s, created["identifier"])
        assert fetched["capability_description"] == cap


def test_capability_description_defaults_to_null(v2_env):
    with session_scope() as s:
        created = agent_profiles.create(
            s, area="ui", tier="developer", description="UI dev with no capability doc.",
            scope="system",
        )
        assert created["capability_description"] is None
        assert agent_profiles.get(s, created["identifier"])["capability_description"] is None


def test_search_never_crosses_the_area_anchor(v2_env):
    # The hard backstop: an agent in another area is never returned.
    with session_scope() as s:
        ui = agent_profiles.create(
            s, area="ui", tier="developer", description="UI dev.", scope="system")
        agent_profiles.create(
            s, area="access", tier="developer", description="Access dev.", scope="system")
        results = agent_profiles.search_agents(s, area="ui")
        ids = {r["identifier"] for r in results}
        assert ui["identifier"] in ids
        assert all(r["area"] == "ui" for r in results)
        assert len(ids) == 1


def test_search_respects_status(v2_env):
    with session_scope() as s:
        active = agent_profiles.create(
            s, area="ui", tier="developer", description="Active UI dev.",
            status="active", scope="system")
        agent_profiles.create(
            s, area="ui", tier="developer", description="Retired UI dev.",
            status="retired", scope="system")
        results = agent_profiles.search_agents(s, area="ui", status="active")
        ids = {r["identifier"] for r in results}
        assert ids == {active["identifier"]}


def test_search_technology_rule(v2_env):
    # technology given → exact-match AND technology-agnostic (NULL) are returned;
    # a different non-null technology is excluded.
    with session_scope() as s:
        qt = agent_profiles.create(
            s, area="ui", tier="developer", description="Qt UI dev.",
            technology="qt-desktop", scope="system")
        web = agent_profiles.create(
            s, area="ui", tier="developer", description="Web UI dev.",
            technology="web", scope="system")
        agnostic = agent_profiles.create(
            s, area="ui", tier="developer", description="Any-tech UI dev.",
            technology=None, scope="system")

        matched = {r["identifier"] for r in
                   agent_profiles.search_agents(s, area="ui", technology="qt-desktop")}
        assert qt["identifier"] in matched
        assert agnostic["identifier"] in matched  # NULL = always eligible
        assert web["identifier"] not in matched

        # technology=None → no technology filter; all three returned.
        all_ids = {r["identifier"] for r in agent_profiles.search_agents(s, area="ui")}
        assert all_ids == {qt["identifier"], web["identifier"], agnostic["identifier"]}


def test_search_needs_ordering_is_deterministic(v2_env):
    with session_scope() as s:
        forms = agent_profiles.create(
            s, area="ui", tier="developer", description="Forms specialist.",
            scope="system",
            capability_description=_cap("Forms.", specialties=["forms"], builds=["dialogs"]))
        charts = agent_profiles.create(
            s, area="ui", tier="developer", description="Charts specialist.",
            scope="system",
            capability_description=_cap("Charts.", specialties=["charts"], builds=["graphs"]))

        # ``charts`` overlaps the need; it ranks first.
        ranked = agent_profiles.search_agents(s, area="ui", needs=["charts", "graphs"])
        assert ranked[0]["identifier"] == charts["identifier"]
        # ``forms`` overlaps this need; it ranks first.
        ranked2 = agent_profiles.search_agents(s, area="ui", needs=["forms", "dialogs"])
        assert ranked2[0]["identifier"] == forms["identifier"]

        # No needs → stable identifier order (the deterministic default).
        default = agent_profiles.search_agents(s, area="ui")
        assert [r["identifier"] for r in default] == sorted(
            [forms["identifier"], charts["identifier"]])
        # Needs with zero overlap → identifier order preserved (stable sort).
        no_overlap = agent_profiles.search_agents(s, area="ui", needs=["nonexistent"])
        assert [r["identifier"] for r in no_overlap] == [
            r["identifier"] for r in default]


def test_search_tier_filter(v2_env):
    # tier given → only that tier; tier None (default) → no tier filter.
    with session_scope() as s:
        dev = agent_profiles.create(
            s, area="ui", tier="developer", description="UI dev.", scope="system")
        arch = agent_profiles.create(
            s, area="ui", tier="architect", description="UI architect.", scope="system")

        devs = {r["identifier"] for r in
                agent_profiles.search_agents(s, area="ui", tier="developer")}
        assert devs == {dev["identifier"]}

        architects = {r["identifier"] for r in
                      agent_profiles.search_agents(s, area="ui", tier="architect")}
        assert architects == {arch["identifier"]}

        both = {r["identifier"] for r in agent_profiles.search_agents(s, area="ui")}
        assert both == {dev["identifier"], arch["identifier"]}
