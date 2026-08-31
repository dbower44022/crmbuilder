"""REQ-543 / PI-440 — one rule per text, version-or-supersede, decision provenance.

Access-layer coverage: the duplicate guard, the source-decision link and its
existence check, wording vs meaning changes, binding migration on supersede,
the severity scale, and the seeder binding profiles to a shared rule.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    decisions,
    governance_rules,
    references,
    registry_resolver,
    registry_seed,
)


def _decision(s, ident="DEC-001") -> str:
    return decisions.create(
        s, identifier=ident, title="ruling", decision_date="2026-01-01", status="Active",
        executive_summary=("A ruling recorded so a governance rule under test can name the "
                           "decision that made it, as every new rule must; the summary itself "
                           "carries no further content and is long enough to satisfy the "
                           "two-hundred-character floor the record type requires."),
    )["identifier"]


def test_duplicate_text_in_scope_is_rejected(v2_env):
    with session_scope() as s:
        governance_rules.create(s, body="Commit with an explicit pathspec.", enforcement="advisory")
        with pytest.raises(UnprocessableError) as exc:
            governance_rules.create(s, body="  commit with an EXPLICIT pathspec. ", enforcement="advisory")
        assert exc.value.errors[0].code == "duplicate_rule_text"
        # a different scope may carry the same text (an engagement override does)
        governance_rules.create(s, body="Commit with an explicit pathspec.", enforcement="advisory",
                                scope="ENG-001", rule_type="commit_hygiene")


def test_source_decision_is_linked_and_must_exist(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as exc:
            governance_rules.create(s, body="x", enforcement="advisory", require_source_decision=True)
        assert exc.value.errors[0].code == "source_decision_required"
        with pytest.raises(NotFoundError):
            governance_rules.create(s, body="x", enforcement="advisory", source_decision="DEC-999")
        dec = _decision(s)
        rule = governance_rules.create(s, body="x", enforcement="advisory", source_decision=dec)
        assert rule["source_decision"] == dec
        edges = references.list_references(s, source_type="governance_rule", source_id=rule["identifier"])
        assert [(e["target_id"], e["relationship"]) for e in edges] == [(dec, "references")]


def test_wording_change_bumps_version_in_place(v2_env):
    with session_scope() as s:
        rule = governance_rules.create(s, body="Never force-push main.", enforcement="advisory")
        with pytest.raises(UnprocessableError) as exc:
            governance_rules.update(s, rule["identifier"], body="Never force push main.")
        assert exc.value.errors[0].code == "change_kind_required"
        after = governance_rules.update(s, rule["identifier"], body="Never force push main.", change="wording")
        assert after["identifier"] == rule["identifier"] and after["version"] == 2
        # a non-text patch needs no change kind
        governance_rules.update(s, rule["identifier"], severity="high")


def test_meaning_change_supersedes_and_rebinds(v2_env):
    with session_scope() as s:
        dec = _decision(s)
        profile = agent_profiles.create(s, area="api", tier="developer", description="d", scope="system")
        rule = governance_rules.create(s, body="Run the tests.", enforcement="advisory", applies_to="ado_agent")
        references.create(s, source_type="agent_profile", source_id=profile["identifier"],
                          target_type="governance_rule", target_id=rule["identifier"],
                          relationship="agent_profile_governed_by_rule")
        with pytest.raises(UnprocessableError):  # meaning needs its decision
            governance_rules.update(s, rule["identifier"], body="Run the tests and the linter.", change="meaning")
        successor = governance_rules.update(
            s, rule["identifier"], body="Run the tests and the linter.", change="meaning", source_decision=dec
        )
        assert successor["identifier"] != rule["identifier"] and successor["version"] == 1
        assert successor["supersedes"] == [rule["identifier"]] and successor["applies_to"] == "ado_agent"
        assert governance_rules.get(s, rule["identifier"])["status"] == "retired"
        contract = registry_resolver.resolve_contract(s, profile["identifier"])
        assert [r["identifier"] for r in contract["advisory_rules"]] == [successor["identifier"]]
        assert references.list_references(s, source_type="governance_rule", source_id=successor["identifier"],
                                          relationship_kind="supersedes")[0]["target_id"] == rule["identifier"]


def test_severity_uses_the_one_scale(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="advisory", severity="warning")
        rule = governance_rules.create(s, body="x", enforcement="advisory", severity="medium")
        with pytest.raises(UnprocessableError):
            governance_rules.update(s, rule["identifier"], severity="error")


def test_seeder_binds_profiles_to_one_shared_rule(v2_env):
    with session_scope() as s:
        _decision(s, "DEC-780")
        registry_seed.seed_system_profiles(s)
        rules = governance_rules.list_all(s, status="active")
        bodies = [governance_rules.normalise_body(r["body"]) for r in rules]
        assert len(bodies) == len(set(bodies))  # one rule per text
        self_verify = [r for r in rules if r["body"].startswith("Self-verify")]
        assert len(self_verify) == 1
        bound = references.list_references(s, target_type="governance_rule",
                                           target_id=self_verify[0]["identifier"],
                                           relationship_kind="agent_profile_governed_by_rule")
        assert len(bound) >= 9  # every build-area developer shares it
        assert {r["severity"] for r in rules if r["severity"]} <= {"high", "medium", "low"}
        assert all(
            references.list_references(s, source_type="governance_rule", source_id=r["identifier"],
                                       relationship_kind="references")
            for r in rules
        )
