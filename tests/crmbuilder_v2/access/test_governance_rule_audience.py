"""REQ-541 / PI-438 — a governance rule declares its audience and its moment.

Access-layer coverage: defaults, vocabulary rejection, list filters on both the
raw and the effective views, update, the seeder marking profile-bound rules as
agent rules, and the resolver's contract being unchanged by the new fields.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    governance_rules,
    references,
    registry_resolver,
    registry_seed,
)
from crmbuilder_v2.access.vocab import RULE_AUDIENCES, RULE_MOMENTS


def test_vocabularies_match_the_approved_terms():
    assert RULE_AUDIENCES == {"all", "claude_code", "sandbox", "ui", "ado_agent"}
    assert RULE_MOMENTS == {"always", "commit", "deploy", "governance_record", "release"}


def test_defaults_and_explicit_values_round_trip(v2_env):
    with session_scope() as s:
        plain = governance_rules.create(s, body="a rule", enforcement="advisory")
        assert (plain["applies_to"], plain["applies_when"]) == ("all", "always")
        keyed = governance_rules.create(
            s, body="commit with a pathspec", enforcement="advisory",
            applies_to="claude_code", applies_when="commit",
        )
        assert (keyed["applies_to"], keyed["applies_when"]) == ("claude_code", "commit")
        got = governance_rules.get(s, keyed["identifier"])
        assert (got["applies_to"], got["applies_when"]) == ("claude_code", "commit")


def test_bad_audience_or_moment_is_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="advisory", applies_to="robot")
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="advisory", applies_when="lunch")
        rule = governance_rules.create(s, body="y", enforcement="advisory")
        with pytest.raises(UnprocessableError):
            governance_rules.update(s, rule["identifier"], applies_when="never")


def test_list_filters_on_raw_and_effective_views(v2_env):
    with session_scope() as s:
        governance_rules.create(s, body="agent", enforcement="advisory", applies_to="ado_agent")
        governance_rules.create(
            s, body="session commit", enforcement="advisory",
            applies_to="claude_code", applies_when="commit",
        )
        governance_rules.create(s, body="everyone", enforcement="advisory")
        raw = governance_rules.list_all(s, applies_to="claude_code")
        assert [r["body"] for r in raw] == ["session commit"]
        raw = governance_rules.list_all(s, applies_when="always")
        assert [r["body"] for r in raw] == ["agent", "everyone"]
        eff = governance_rules.list_effective(s, engagement_id="ENG-001", applies_when="commit")
        assert [r["body"] for r in eff] == ["session commit"]
        eff = governance_rules.list_effective(s, engagement_id="ENG-001", applies_to="ado_agent")
        assert [r["body"] for r in eff] == ["agent"]


def test_update_changes_audience_and_moment(v2_env):
    with session_scope() as s:
        rule = governance_rules.create(s, body="deploy rule", enforcement="advisory")
        after = governance_rules.update(
            s, rule["identifier"], applies_to="claude_code", applies_when="deploy"
        )
        assert (after["applies_to"], after["applies_when"]) == ("claude_code", "deploy")


def test_seeded_profile_rules_are_agent_rules(v2_env):
    with session_scope() as s:
        registry_seed.seed_system_profiles(s)
        rules = governance_rules.list_all(s, status="active")
        assert rules  # the catalog seeds rules
        assert {r["applies_to"] for r in rules} == {"ado_agent"}
        assert {r["applies_when"] for r in rules} == {"always"}


def test_resolver_contract_ignores_audience_and_moment(v2_env):
    """REQ-541 acceptance: every agent profile resolves the same contract as before.

    Binding decides membership; an unbound ``all`` rule does not leak into a
    contract and a bound rule stays in it whatever its audience says.
    """
    with session_scope() as s:
        profile = agent_profiles.create(
            s, area="api", tier="developer", description="dev", scope="system"
        )
        bound = governance_rules.create(
            s, body="bound session-audience rule", enforcement="advisory",
            applies_to="claude_code", applies_when="commit",
        )
        governance_rules.create(s, body="unbound rule for everyone", enforcement="advisory")
        references.create(
            s, source_type="agent_profile", source_id=profile["identifier"],
            target_type="governance_rule", target_id=bound["identifier"],
            relationship="agent_profile_governed_by_rule",
        )
        contract = registry_resolver.resolve_contract(s, profile["identifier"])
        assert [r["identifier"] for r in contract["advisory_rules"]] == [bound["identifier"]]
