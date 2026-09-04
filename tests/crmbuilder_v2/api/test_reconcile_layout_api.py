"""Layout actionability over the API — PI-418 (REQ-519 / REQ-520).

The comparison rows say which layouts can be acted on and why the others
cannot; the capture route honours the same answer.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo

DESIGN = [{"label": "", "rows": [["name"]]}]
LIVE = [{"label": "", "rows": [["name", "cPhone"]]}]


def _seed(layout_type):
    """Two instances and one confirmed layout the first instance holds
    differently. Memberships have no write route (the audit writes them), and
    the layout create body types content as a mapping while a record-view
    payload is a list, so both are seeded through the repositories."""
    with session_scope() as s:
        a = inst_repo.create_instance(
            s, name="a", url="https://a.example.org", role="target"
        )["instance_identifier"]
        b = inst_repo.create_instance(
            s, name="b", url="https://b.example.org", role="target"
        )["instance_identifier"]
        eid = entity_repo.create_entity(
            s, name="Contact", description="x", status="confirmed"
        )["entity_identifier"]
        lid = layout_repo.create_layout(
            s, entity_identifier=eid, layout_type=layout_type,
            content=DESIGN, status="confirmed",
        )["layout_identifier"]
        for inst, state, override in (
            (a, "drifted", {"layout_content": LIVE}), (b, "present", None),
        ):
            mb.upsert_membership(
                s, instance_identifier=inst, member_type="entity",
                member_identifier=eid, state="present", override=None,
            )
            mb.upsert_membership(
                s, instance_identifier=inst, member_type="layout",
                member_identifier=lid, state=state, override=override,
            )
    return a, b, lid


def _layout_row(client, a, b, lid):
    r = client.get("/reconcile/compare", params={"instance_a": a, "instance_b": b})
    assert r.status_code == 200, r.text
    for group in r.json()["data"]["groups"]:
        for og in group.get("object_groups", []):
            for row in og["rows"]:
                if row["member_identifier"] == lid and row["kind"] == "attribute":
                    return row
    raise AssertionError("layout row not in the comparison")


def test_an_ordinary_layout_row_is_actionable_both_ways_and_captures(client):
    a, b, lid = _seed("detail")
    row = _layout_row(client, a, b, lid)
    assert row["capturable"] is True and row["publishable"] is True
    assert row["capability_reason"] is None

    r = client.post("/reconcile/capture-member", json={
        "instance": a, "member_type": "layout", "member_identifier": lid,
        "attribute": "layout_content", "actor": "Doug",
    })
    assert r.status_code == 201, r.text
    assert r.json()["data"]["member"]["layout_content"] == LIVE
    assert client.get(f"/layouts/{lid}").json()["data"]["layout_content"] == LIVE


def test_a_portal_layout_row_is_view_only_with_its_reason_and_refuses_capture(client):
    a, b, lid = _seed("detail_portal")
    row = _layout_row(client, a, b, lid)
    assert row["differs"] is True
    assert row["capturable"] is False and row["publishable"] is False
    assert "portal" in row["capability_reason"]

    r = client.post("/reconcile/capture-member", json={
        "instance": a, "member_type": "layout", "member_identifier": lid,
        "attribute": "layout_content", "actor": "Doug",
    })
    assert r.status_code == 409, r.text
    assert "portal" in r.text
    assert client.get(f"/layouts/{lid}").json()["data"]["layout_content"] == DESIGN


def test_a_layout_publishes_with_its_entity_s_program(client):
    """The publish scope routes a layout to its entity's generated program
    (REQ-376), which now carries the layout: block (PI-427)."""
    a, b, lid = _seed("list")
    r = client.get("/reconcile/publish-scope", params={
        "member_type": "layout", "member_identifier": lid,
    })
    if r.status_code == 404:  # no dedicated scope endpoint — resolve in-process
        from crmbuilder_v2.access import reconcile_apply

        with session_scope() as s:
            scope = reconcile_apply.publish_scope_for_member(s, "layout", lid)
    else:
        scope = r.json()["data"]
    assert scope["entity_name"] == "Contact"
    assert scope["filename"] == "Contact.yaml"
