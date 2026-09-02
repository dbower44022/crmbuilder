"""The access-publish gate over the API — PI-417 (REQ-521)."""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import instance_membership as mb


def _seed(client, *, design_read, instance_read):
    """A target instance and a role whose instance value differs from the design."""
    inst = client.post("/instances", json={
        "instance_name": "target", "instance_url": "https://t.example.org",
        "instance_role": "target",
    }).json()["data"]["instance_identifier"]
    role = client.post("/roles", json={
        "role_name": "Mentor Role", "role_status": "confirmed",
        "role_scope_access": {"Account": {"read": design_read}},
    }).json()["data"]["role_identifier"]
    # No write route for memberships — the reconcile run writes them — so the
    # instance's recorded deviation is seeded through the repository.
    with session_scope() as s:
        mb.upsert_membership(
            s, instance_identifier=inst, member_type="role",
            member_identifier=role, state="drifted",
            override={"role_scope_access": {"Account": {"read": instance_read}}},
        )
    return inst, role


def test_the_assessment_endpoint_names_the_target_and_the_effect(client):
    inst, role = _seed(client, design_read="team", instance_read="all")
    r = client.get("/reconcile/assess-access-publish", params={
        "instance": inst, "member_type": "role", "member_identifier": role,
    })
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["target"]["member_name"] == "Mentor Role"
    assert data["removes_access"] is True
    assert data["requires_confirmation"] is True
    assert "Mentor Role" in data["changes"][0]["description"]


def test_an_unconfirmed_access_publish_is_refused_before_it_deploys(client):
    """The refusal must land on the gate, not on the deploy: no live target is
    configured in this test, so reaching the publish service at all would fail
    differently."""
    inst, role = _seed(client, design_read="team", instance_read="all")
    r = client.post("/reconcile/publish", json={
        "instance": inst, "member_type": "role",
        "member_identifier": role, "actor": "Doug",
    })
    assert r.status_code == 409, r.text
    assert "Confirm the change" in r.text


def test_confirming_the_change_is_not_confirming_the_removal(client):
    inst, role = _seed(client, design_read="team", instance_read="all")
    r = client.post("/reconcile/publish", json={
        "instance": inst, "member_type": "role", "member_identifier": role,
        "actor": "Doug", "confirm_access_change": True,
    })
    assert r.status_code == 409, r.text
    body = r.text
    assert "removes access" in body
    # the refusal says which grant would be lost, not just that one would be
    assert "Account.read all → team" in body


def test_a_widening_publish_passes_the_gate_with_one_confirmation(client):
    """It still has to be confirmed, but it is not held back by the removal
    fence — so the refusal it meets next is the deploy's, not the gate's."""
    inst, role = _seed(client, design_read="all", instance_read="team")
    r = client.post("/reconcile/publish", json={
        "instance": inst, "member_type": "role", "member_identifier": role,
        "actor": "Doug", "confirm_access_change": True,
    })
    assert r.status_code != 409 or "Confirm the change" not in r.text
    assert "removes access" not in r.text
