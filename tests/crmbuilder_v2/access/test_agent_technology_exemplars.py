"""PI-271 — strict, technology-variant agent contracts (REQ-278/280/281).

Exemplars proving the contract infrastructure end to end: two build-area profiles
in the SAME area but different technologies coexist (REQ-281), each carries its own
hard, enforced constraints (REQ-280), and the resolver composes each into a strict
contract (REQ-278). Routing/refusal (REQ-273) is covered in the dispatcher tests.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    governance_rules,
    references,
    registry_resolver,
)


def _profile_with_rule(s, *, area, technology, description, rule_body):
    prof = agent_profiles.create(
        s, area=area, tier="developer", description=description,
        technology=technology, scope="system",
    )
    rule = governance_rules.create(
        s, body=rule_body, enforcement="enforced", scope="system",
    )
    references.create(
        s, source_type="agent_profile", source_id=prof["identifier"],
        target_type="governance_rule", target_id=rule["identifier"],
        relationship="agent_profile_governed_by_rule",
    )
    return prof


def test_technology_variants_coexist_in_one_area(v2_env):
    # REQ-281: a qt-desktop and a web ui profile coexist as distinct rows.
    with session_scope() as s:
        qt = agent_profiles.create(
            s, area="ui", tier="developer", description="Qt desktop UI dev.",
            technology="qt-desktop", scope="system")
        web = agent_profiles.create(
            s, area="ui", tier="developer", description="Web UI dev.",
            technology="web", scope="system")
        assert qt["technology"] == "qt-desktop"
        assert web["technology"] == "web"
        assert qt["identifier"] != web["identifier"]
        ui_devs = agent_profiles.list_all(s, area="ui", tier="developer")
        techs = {p["technology"] for p in ui_devs}
        assert {"qt-desktop", "web"} <= techs


def test_each_variant_resolves_to_a_strict_contract_with_hard_constraints(v2_env):
    # REQ-278 (strict contract) + REQ-280 (hard, enforced area constraints).
    with session_scope() as s:
        qt = _profile_with_rule(
            s, area="ui", technology="qt-desktop",
            description="Qt desktop UI developer. Build only with PySide6/Qt.",
            rule_body="Use CopyableMessageBox, never a raw QMessageBox; test Qt offscreen.")
        web = _profile_with_rule(
            s, area="ui", technology="web",
            description="Web UI developer. Build only with the chosen web framework.",
            rule_body="Use the project's web framework only; never a desktop toolkit.")

        qt_contract = registry_resolver.resolve_contract(s, qt["identifier"])
        web_contract = registry_resolver.resolve_contract(s, web["identifier"])

        # Each carries its own enforced (hard) constraint — REQ-280.
        qt_rules = " ".join(r["body"] for r in qt_contract["enforced_ruleset"])
        web_rules = " ".join(r["body"] for r in web_contract["enforced_ruleset"])
        assert "CopyableMessageBox" in qt_rules and "offscreen" in qt_rules
        assert "web framework" in web_rules
        # The two technology variants resolve to genuinely different contracts.
        assert qt_contract["system_prompt"] != web_contract["system_prompt"]
        assert "PySide6/Qt" in qt_contract["system_prompt"]
        # REQ-278: a contract carries a non-empty role/system prompt + a ruleset.
        assert qt_contract["system_prompt"]
        assert qt_contract["enforced_ruleset"]
