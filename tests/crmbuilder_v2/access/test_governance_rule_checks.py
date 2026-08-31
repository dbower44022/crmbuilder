"""REQ-542 / PI-439 — enforced means backed by a check; overrides are recorded."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.access.repositories import governance_rules
from crmbuilder_v2.access.vocab import RULE_CHECK_KINDS

CHECK = {"kind": "forbidden_command", "pattern": r"\brm -rf\b", "message": "no"}


def test_check_vocabulary_is_the_approved_three():
    assert RULE_CHECK_KINDS == {"forbidden_command", "required_trailer", "protected_path"}


def test_enforced_without_a_check_is_rejected(v2_env):
    with session_scope() as s:
        for mode in ("enforced", "enforced_with_override"):
            with pytest.raises(UnprocessableError) as exc:
                governance_rules.create(s, body="x", enforcement=mode)
            assert exc.value.errors[0].code == "enforced_requires_check"
        # advisory needs none
        assert governance_rules.create(s, body="y", enforcement="advisory")["predicate"] is None


def test_agent_rules_may_stay_enforced_without_a_check_provisionally(v2_env):
    """Provisional scope pending Doug's ruling — see validate_predicate."""
    with session_scope() as s:
        rule = governance_rules.create(s, body="self-verify", enforcement="enforced",
                                       applies_to="ado_agent")
        assert rule["predicate"] is None
        # retargeting it at a session audience re-imposes the obligation
        with pytest.raises(UnprocessableError):
            governance_rules.update(s, rule["identifier"], applies_to="claude_code")
        # a supplied predicate is validated regardless of audience
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="enforced", applies_to="ado_agent",
                                    predicate={"kind": "vibes", "pattern": "a"})


def test_malformed_checks_are_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="enforced",
                                    predicate={"kind": "vibes", "pattern": "a"})
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="enforced",
                                    predicate={"kind": "forbidden_command", "pattern": "("})
        with pytest.raises(UnprocessableError):
            governance_rules.create(s, body="x", enforcement="enforced",
                                    predicate={"kind": "required_trailer", "pattern": "PI-\\d+"})


def test_enforced_with_a_check_round_trips_and_update_is_guarded(v2_env):
    with session_scope() as s:
        rule = governance_rules.create(s, body="x", enforcement="enforced", predicate=CHECK)
        assert rule["predicate"] == CHECK
        with pytest.raises(UnprocessableError):
            governance_rules.update(s, rule["identifier"], predicate=None)
        plain = governance_rules.create(s, body="y", enforcement="advisory")
        with pytest.raises(UnprocessableError):
            governance_rules.update(s, plain["identifier"], enforcement="enforced")
        ok = governance_rules.update(s, plain["identifier"], enforcement="enforced", predicate=CHECK)
        assert ok["enforcement"] == "enforced"
        # relabelling to advisory drops the obligation
        assert governance_rules.update(s, rule["identifier"], enforcement="advisory")["enforcement"] == "advisory"


def test_override_is_recorded_only_for_overridable_rules(v2_env):
    with session_scope() as s:
        soft = governance_rules.create(s, body="s", enforcement="enforced_with_override", predicate=CHECK)
        hard = governance_rules.create(s, body="h", enforcement="enforced", predicate=CHECK)
        rec = governance_rules.record_enforcement_override(
            s, soft["identifier"], reason="amending a merge", command="git commit --amend", session_ref="sess"
        )
        assert rec["rule_identifier"] == soft["identifier"] and rec["reason"] == "amending a merge"
        listed = governance_rules.list_enforcement_overrides(s, soft["identifier"])
        assert [r["session_ref"] for r in listed] == ["sess"]
        with pytest.raises(UnprocessableError):
            governance_rules.record_enforcement_override(s, hard["identifier"], reason="please")
        with pytest.raises(NotFoundError):
            governance_rules.list_enforcement_overrides(s, "GVR-999")
