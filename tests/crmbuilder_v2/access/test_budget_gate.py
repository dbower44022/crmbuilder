"""Pre-launch budget gate tests — REQ-318 (PI-283).

A run launches only when its latest recorded decision is ``approved`` and the
projection that decision approved was within its budget; a later decline (or an
approved-but-over-budget decision) means it may not launch.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import budget_gate
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError


def test_evaluate_within_and_over_budget():
    assert budget_gate.evaluate(5.0, 10.0)["within_budget"] is True
    over = budget_gate.evaluate(12.0, 10.0)
    assert over["within_budget"] is False
    assert over["overage_usd"] == pytest.approx(2.0)


def test_no_decision_is_not_approved(v2_env):
    with session_scope() as s:
        assert budget_gate.run_is_approved(s, "REL-1") is False
        state = budget_gate.gate_state(s, "REL-1")
    assert state["launch_approved"] is False
    assert state["latest_decision"] is None


def test_approved_within_budget_launches(v2_env):
    with session_scope() as s:
        budget_gate.record_decision(
            s, release_identifier="REL-1", budget_usd=10.0, projected_usd=4.0,
            decision="approved", operator="doug")
        assert budget_gate.run_is_approved(s, "REL-1") is True
        assert budget_gate.gate_state(s, "REL-1")["launch_approved"] is True


def test_approved_but_over_budget_does_not_launch(v2_env):
    with session_scope() as s:
        budget_gate.record_decision(
            s, release_identifier="REL-1", budget_usd=10.0, projected_usd=15.0,
            decision="approved", operator="doug")
        assert budget_gate.run_is_approved(s, "REL-1") is False


def test_latest_decision_overrides(v2_env):
    with session_scope() as s:
        budget_gate.record_decision(
            s, release_identifier="REL-1", budget_usd=10.0, projected_usd=4.0,
            decision="approved", operator="doug")
        budget_gate.record_decision(
            s, release_identifier="REL-1", budget_usd=10.0, projected_usd=4.0,
            decision="declined", operator="doug")
        assert budget_gate.run_is_approved(s, "REL-1") is False
        assert budget_gate.gate_state(s, "REL-1")["latest_decision"]["budget_decision"] == "declined"


def test_decision_is_per_run(v2_env):
    with session_scope() as s:
        budget_gate.record_decision(
            s, release_identifier="REL-1", budget_usd=10.0, projected_usd=4.0,
            decision="approved", operator="doug")
        assert budget_gate.run_is_approved(s, "REL-1") is True
        assert budget_gate.run_is_approved(s, "REL-2") is False  # unrelated run


def test_bad_decision_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            budget_gate.record_decision(
                s, release_identifier="REL-1", budget_usd=10.0, projected_usd=4.0,
                decision="maybe", operator="doug")
