"""PI-122 slice 1 — agent_profile / skill / governance_rule catalog repos."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    governance_rules,
    skills,
)

# v2_env seeds ENG-001 (used as an engagement-overlay scope).


def test_agent_profile_create_system_and_engagement_scope(v2_env):
    with session_scope() as s:
        sys_p = agent_profiles.create(
            s, area="storage", tier="architect", description="Storage architect."
        )
        assert sys_p["identifier"] == "AGP-001"
        assert sys_p["scope"] == "system"
        assert sys_p["engagement_id"] is None

        eng_p = agent_profiles.create(
            s, area="storage", tier="developer", description="Storage dev (CBM).",
            scope="ENG-001",
        )
        assert eng_p["scope"] == "ENG-001"
        assert eng_p["engagement_id"] == "ENG-001"


def test_agent_profile_rejects_bad_tier_and_unknown_scope(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            agent_profiles.create(s, area="storage", tier="wizard", description="x")
        with pytest.raises(ValidationError):
            agent_profiles.create(
                s, area="storage", tier="architect", description="x", scope="ENG-999"
            )


def test_agent_profile_list_filters_and_update(v2_env):
    with session_scope() as s:
        agent_profiles.create(s, area="storage", tier="architect", description="a")
        agent_profiles.create(s, area="api", tier="developer", description="b")
        assert len(agent_profiles.list_all(s)) == 2
        assert len(agent_profiles.list_all(s, area="storage")) == 1
        assert len(agent_profiles.list_all(s, tier="developer")) == 1
        assert len(agent_profiles.list_all(s, scope="system")) == 2

        updated = agent_profiles.update(s, "AGP-001", status="retired")
        assert updated["status"] == "retired"
        with pytest.raises(UnprocessableError):
            agent_profiles.update(s, "AGP-001", tier="nope")


def test_skill_round_trip_with_io_contract(v2_env):
    with session_scope() as s:
        skill = skills.create(
            s,
            name="scope code change by area",
            kind="tool",
            description="Record the phase's Work Tasks.",
            io_contract={"type": "object"},
            backing_callable="POST /workstreams/{id}/scope",
        )
        assert skill["identifier"] == "SKL-001"
        assert skill["kind"] == "tool"
        assert skill["io_contract"] == {"type": "object"}
        got = skills.get(s, "SKL-001")
        assert got["backing_callable"] == "POST /workstreams/{id}/scope"
        with pytest.raises(UnprocessableError):
            skills.create(s, name="x", kind="weird", description="y")


def test_governance_rule_enforcement_modes(v2_env):
    with session_scope() as s:
        rule = governance_rules.create(
            s,
            body="A destructive migration contradicting an Architecture decision "
                 "sets Needs Attention.",
            enforcement="enforced_with_override",
            severity="high",
        )
        assert rule["identifier"] == "GVR-001"
        assert rule["enforcement"] == "enforced_with_override"
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="suggested")


def test_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        skills.create(s, identifier="SKL-050", name="n", kind="instruction", description="d")
        with pytest.raises(ConflictError):
            skills.create(s, identifier="SKL-050", name="n2", kind="instruction", description="d2")
        with pytest.raises(UnprocessableError):
            skills.create(s, identifier="BAD-1", name="n", kind="instruction", description="d")


def test_delete(v2_env):
    with session_scope() as s:
        governance_rules.create(s, identifier="GVR-001", body="b", enforcement="advisory")
        governance_rules.delete(s, "GVR-001")
        with pytest.raises(NotFoundError):
            governance_rules.get(s, "GVR-001")
