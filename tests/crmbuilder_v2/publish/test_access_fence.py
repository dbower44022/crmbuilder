"""The access fence on the whole-design publish route — PI-466 (REQ-521, DEC-982).

Every test here starts at ``publish.service.publish`` with a real design
client and the real generation (LSN-071): the security program is rendered,
parsed and assessed through the very path a publish runs. Only the live
target is stubbed — its roles and teams are served from a dict, and the
deploy engine records what it was handed instead of writing anywhere.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.publish import service
from crmbuilder_v2.publish.access import assess_publish_access

from espo_impl.core.deploy_pipeline import DeployOutcome
from tests.crmbuilder_v2.adapters.test_espocrm_model import _entity, _field
from tests.crmbuilder_v2.publish.test_service import _RecordingDesignClient

_TARGET = {"instance_identifier": "INST-009", "instance_url": "https://x"}

#: The design: one confirmed role that lets a Mentor read everything but
#: delete nothing, and one confirmed team.
_DESIGN_SCOPE = {
    "Contact": {
        "read": "all", "edit": "team", "delete": "no",
        "create": "yes", "stream": "all",
    }
}
_DESIGN_PERMS = {"exportPermission": "yes", "assignmentPermission": "team"}


def _design_client(*, roles=True, teams=True):
    return _RecordingDesignClient(
        entities=[_entity()],
        fields=[_field()],
        roles=[{
            "role_identifier": "ROL-001", "role_name": "Mentor",
            "role_status": "confirmed",
            "role_scope_access": _DESIGN_SCOPE,
            "role_system_permissions": _DESIGN_PERMS,
        }] if roles else [],
        teams=[{
            "team_identifier": "TEA-001", "team_name": "Mentors",
            "team_status": "confirmed",
        }] if teams else [],
    )


def _live_role(scope, perms=None):
    """A Role record as EspoCRM lists it: the matrix under ``data``, the
    system permissions as ``*Permission`` columns."""
    return {"id": "r1", "name": "Mentor", "data": scope, **(perms or {})}


#: The instance grants more than the design: delete on everything, export.
_WIDER_LIVE = _live_role(
    {"Contact": {
        "read": "all", "edit": "team", "delete": "all",
        "create": "yes", "stream": "all",
    }},
    {"exportPermission": "yes", "assignmentPermission": "all"},
)
#: The instance grants less: the design only widens.
_NARROWER_LIVE = _live_role(
    {"Contact": {
        "read": "own", "edit": "own", "delete": "no",
        "create": "yes", "stream": "all",
    }},
    {"exportPermission": "no", "assignmentPermission": "team"},
)


@pytest.fixture
def target(monkeypatch):
    """The stubbed live target. ``state['roles']`` is the list ``GET /Role``
    serves (``None`` makes the read fail); ``state['deployed']`` records the
    programs the deploy engine was handed for a real write, and
    ``state['previewed']`` those it dry-ran."""
    state = {"roles": [], "teams": [], "deployed": [], "previewed": []}

    class _StubTarget:
        def get_entity_field_list(self, entity):
            return 404, None

        def get_roles(self):
            if state["roles"] is None:
                return 500, None
            return 200, {"total": len(state["roles"]), "list": state["roles"]}

        def get_teams(self):
            return 200, {"total": len(state["teams"]), "list": state["teams"]}

    monkeypatch.setattr(service, "EspoAdminClient", lambda profile: _StubTarget())
    monkeypatch.setattr(service, "gather_server_fields", lambda c, n: ({}, []))
    monkeypatch.setattr(
        service, "capture_target_backup", lambda c, n: {"entities": {}}
    )

    def _deploy(program, client, field_mgr, output_fn, **kw):
        state["previewed" if kw.get("dry_run") else "deployed"].append(program)
        return DeployOutcome(report=object())

    monkeypatch.setattr(service, "deploy_pipeline", _deploy)
    return state


def _publish(design=None, **kw):
    return service.publish(
        _TARGET, design or _design_client(), api_key="K",
        rendered_at="2026-09-04T00:00:00Z", **kw,
    )


# -- the preview states the effect --------------------------------------------


def test_the_preview_states_each_roles_effect_against_the_live_target(target):
    target["roles"] = [_WIDER_LIVE]
    res = _publish(preview=True)

    access = res.access
    assert access["assessed"] is True and access["known"] is True
    assert access["target"] == "INST-009"
    role = access["roles"][0]
    assert role["target"]["member_name"] == "Mentor"
    assert role["live_state"] == "present"
    # the same words the reconcile route's assessment uses
    assert "Mentor: Contact.delete all → no" in [
        c["description"] for c in role["changes"]
    ]
    assert "Mentor: assignmentPermission all → team" in [
        c["description"] for c in role["changes"]
    ]
    assert access["removes_access"] is True
    assert [c["description"] for c in access["removals"]] == [
        "Mentor: Contact.delete all → no",
        "Mentor: assignmentPermission all → team",
    ]
    assert "2 of which take access away" in access["summary"]
    # the team is stated too: absent on the target, so it is created
    team = access["teams"][0]
    assert team["live_state"] == "absent"
    assert team["removes_access"] is False
    assert "grouped for sharing" in team["summary"]
    # a preview dry-runs the engine and writes nothing, whatever the effect
    assert target["deployed"] == []
    assert len(target["previewed"]) == 2


def test_a_role_the_target_does_not_hold_is_all_new_and_never_a_removal(target):
    target["roles"] = []
    res = _publish(preview=True)
    role = res.access["roles"][0]
    assert role["live_state"] == "absent"
    assert role["removes_access"] is False
    assert all(c["before"] is None for c in role["changes"])


def test_a_publish_with_no_security_program_says_access_is_untouched(target):
    res = _publish(_design_client(roles=False, teams=False), preview=True)
    assert res.access["assessed"] is False
    assert res.access["requires_confirmation"] is False
    assert "left as it is" in res.access["summary"]


# -- the automatic run refuses lowered access ---------------------------------


def test_an_automatic_run_declines_the_removal_by_name(target):
    target["roles"] = [_WIDER_LIVE]
    res = _publish()

    assert res.aborted is True
    assert target["deployed"] == []
    kinds = {d["kind"] for d in res.declined_changes}
    assert kinds == {"removal"}
    constructs = {d["construct"] for d in res.declined_changes}
    assert constructs == {"role Mentor (security.yaml)"}
    assert "Contact.delete all → no" in res.abort_reason
    assert "assignmentPermission all → team" in res.abort_reason
    assert "approved plan fingerprint" in res.abort_reason


def test_an_additive_only_access_change_proceeds_automatically(target):
    target["roles"] = [_NARROWER_LIVE]
    res = _publish()

    assert res.aborted is False
    assert res.access["removes_access"] is False
    assert len(res.access["changes"]) > 0
    assert [p.roles[0].name for p in target["deployed"] if p.roles] == ["Mentor"]


def test_an_unreachable_target_reports_unknown_and_refuses_the_automatic_run(
    target,
):
    target["roles"] = None
    res = _publish()

    assert res.access["known"] is False
    assert "could not read the target's roles" in res.access["reason"]
    assert res.access["roles"][0]["live_state"] == "unknown"
    assert res.access["removes_access"] is False  # nothing is guessed
    assert res.aborted is True
    assert res.declined_changes == []
    assert "unknown" in res.abort_reason
    assert target["deployed"] == []


def test_an_unreachable_target_is_stated_on_the_preview_not_guessed(target):
    target["roles"] = None
    res = _publish(preview=True)
    assert res.aborted is False
    assert res.access["known"] is False
    assert "could not be determined" in res.access["summary"]


# -- the reviewed run needs the separate word ---------------------------------


def _reviewed_fingerprint(target):
    """The plan identity a preview hands the operator."""
    return _publish(preview=True).plan_fingerprint


def test_a_reviewed_run_carrying_a_removal_is_refused_without_the_word(target):
    target["roles"] = [_WIDER_LIVE]
    fp = _reviewed_fingerprint(target)
    res = _publish(expected_plan_fingerprint=fp)

    assert res.aborted is True
    assert res.access_removal_unconfirmed is True
    assert res.plan_moved is False
    assert "confirm_access_removal" in res.abort_reason
    assert "Mentor: Contact.delete all → no" in res.abort_reason
    assert target["deployed"] == []


def test_a_reviewed_run_with_the_word_proceeds_and_deploys_the_roles(target):
    target["roles"] = [_WIDER_LIVE]
    fp = _reviewed_fingerprint(target)
    res = _publish(expected_plan_fingerprint=fp, confirm_access_removal=True)

    assert res.aborted is False
    assert res.access_removal_unconfirmed is False
    assert res.access["removes_access"] is True  # still stated, now confirmed
    security = [p for p in target["deployed"] if p.roles]
    assert [r.name for r in security[0].roles] == ["Mentor"]
    assert [t.name for t in security[0].teams] == ["Mentors"]
    assert all(p.deployed for p in res.programs)


def test_a_reviewed_additive_run_needs_no_removal_word(target):
    target["roles"] = [_NARROWER_LIVE]
    fp = _reviewed_fingerprint(target)
    res = _publish(expected_plan_fingerprint=fp)
    assert res.aborted is False
    assert any(p.roles for p in target["deployed"])


def test_the_plan_gate_still_comes_first(target):
    """A moved plan is reported as moved, not as an access refusal."""
    target["roles"] = [_WIDER_LIVE]
    res = _publish(expected_plan_fingerprint="not-the-plan")
    assert res.plan_moved is True
    assert res.access_removal_unconfirmed is False


# -- the screen and the assessment on their own -------------------------------


def test_automatic_apply_declines_folds_access_removals_in(target):
    programs = service.parse_programs(
        service.generate_design_yaml(
            _design_client(), rendered_at="2026-09-04T00:00:00Z"
        )
    )
    client = service.EspoAdminClient(None)
    target["roles"] = [_WIDER_LIVE]
    access = assess_publish_access(
        programs, _design_client(), client, target_identifier="INST-009"
    )
    declined = service.automatic_apply_declines(programs, client, access=access)
    assert [d["attribute"] for d in declined] == [
        "role_scope_access", "role_system_permissions"
    ]
    assert declined[0]["design"] == "no" and declined[0]["instance"] == "all"
    assert "takes away access" in declined[0]["reason"]
    # without the section the screen is the pre-PI-466 one
    assert service.automatic_apply_declines(programs, client) == []
