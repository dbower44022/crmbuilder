"""Transition REST endpoint tests — PI-471, REQ-577 to REQ-586.

Exercises the ``/transitions`` routes and the two process-scoped routes
through the TestClient, the ``{data, meta, errors}`` envelope, and the
validation surfaces a caller meets. The thirteen-row Mentor Application table
is entered through the API here, which is the path the connector's create tool
and the client engagement's migration take.
"""

from __future__ import annotations

from tests.crmbuilder_v2.access._mentor_application import (
    MENTOR_STATUS_OPTIONS,
    PRE_ACTIVE,
)


def _seed(client) -> dict:
    """Build the process, its entities, the status field and the persona."""
    dom = client.post(
        "/domains",
        json={
            "domain_name": "Mentor Recruiting",
            "domain_purpose": "Bring new mentors in.",
            "domain_description": "Recruiting and onboarding mentors.",
        },
    ).json()["data"]["domain_identifier"]
    proc = client.post(
        "/processes",
        json={
            "process_name": "Mentor Application",
            "process_domain_identifier": dom,
            "process_purpose": "Application to active.",
        },
    ).json()["data"]["process_identifier"]

    def _entity(name: str) -> str:
        return client.post(
            "/entities",
            json={"entity_name": name, "entity_description": name},
        ).json()["data"]["entity_identifier"]

    profile = _entity("MentorProfile")
    submission = _entity("IntakeSubmission")
    for target in (profile, submission):
        resp = client.post(
            "/references",
            json={
                "source_type": "process",
                "source_id": proc,
                "target_type": "entity",
                "target_id": target,
                "relationship": "process_touches_entity",
            },
        )
        assert resp.status_code in (200, 201), resp.text

    status_field = client.post(
        "/fields",
        json={
            "field_belongs_to_entity_identifier": profile,
            "field_name": "mentorStatus",
            "field_description": "Where the mentor is.",
            "field_type": "enum",
            "field_options": [
                {"option_value": value, "option_order": index}
                for index, value in enumerate(MENTOR_STATUS_OPTIONS)
            ],
        },
    ).json()["data"]["field_identifier"]

    decline_reason = client.post(
        "/fields",
        json={
            "field_belongs_to_entity_identifier": profile,
            "field_name": "declineReason",
            "field_description": "Why the applicant was declined.",
            "field_type": "text",
        },
    ).json()["data"]["field_identifier"]

    team = client.post(
        "/personas",
        json={
            "persona_name": "Mentor Administration Team",
            "persona_role_summary": "Reviews and votes.",
        },
    ).json()["data"]["persona_identifier"]

    return {
        "process": proc,
        "profile": profile,
        "status_field": status_field,
        "decline_reason": decline_reason,
        "team": team,
    }


def _body(seed: dict, **overrides) -> dict:
    body = {
        "transition_process": seed["process"],
        "transition_field": seed["status_field"],
        "transition_from_values": ["Candidate"],
        "transition_to_value": "Under Review",
        "transition_actor_kind": "persona",
        "transition_actor_persona": seed["team"],
    }
    body.update(overrides)
    return body


def test_create_get_list_transition(client):
    seed = _seed(client)
    resp = client.post("/transitions", json=_body(seed))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    identifier = body["data"]["transition_identifier"]
    assert identifier == "TRN-001"
    assert body["data"]["transition_status"] == "candidate"
    assert body["data"]["transition_from_kind"] == "values"
    assert body["data"]["transition_order"] == 0

    got = client.get(f"/transitions/{identifier}")
    assert got.status_code == 200
    assert got.json()["data"]["transition_to_value"] == "Under Review"

    listed = client.get("/transitions", params={"process": seed["process"]})
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/transitions/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "TRN-001"


def test_create_refuses_a_value_the_status_field_does_not_offer(client):
    seed = _seed(client)
    resp = client.post(
        "/transitions", json=_body(seed, transition_to_value="Retired")
    )
    assert resp.status_code == 422, resp.text
    codes = {e["code"] for e in resp.json()["errors"]}
    assert "to_value_not_an_option" in codes


def test_create_refuses_a_system_move_that_names_a_persona(client):
    seed = _seed(client)
    resp = client.post(
        "/transitions",
        json=_body(seed, transition_actor_kind="system"),
    )
    assert resp.status_code == 422, resp.text
    codes = {e["code"] for e in resp.json()["errors"]}
    assert "forbidden_for_system_actor" in codes


def test_create_from_record_creation(client):
    seed = _seed(client)
    resp = client.post(
        "/transitions",
        json=_body(
            seed,
            transition_from_kind="record_creation",
            transition_from_values=None,
            transition_to_value="Candidate",
            transition_actor_kind="system",
            transition_actor_persona=None,
            transition_actor_occasion="the intake application",
        ),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["transition_from_kind"] == "record_creation"
    assert data["transition_from_values"] == []


def test_patch_put_delete_restore(client):
    seed = _seed(client)
    identifier = client.post("/transitions", json=_body(seed)).json()["data"][
        "transition_identifier"
    ]

    patched = client.patch(
        f"/transitions/{identifier}",
        json={"transition_status": "confirmed"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["transition_status"] == "confirmed"

    replaced = client.put(
        f"/transitions/{identifier}",
        json=_body(
            seed,
            transition_to_value="Declined",
            transition_status="confirmed",
            transition_required_fields=[seed["decline_reason"]],
        ),
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["transition_required_fields"] == [
        seed["decline_reason"]
    ]

    deleted = client.delete(f"/transitions/{identifier}")
    assert deleted.status_code == 200
    assert client.get(f"/transitions/{identifier}").status_code == 404
    restored = client.post(f"/transitions/{identifier}/restore")
    assert restored.status_code == 200
    assert client.get(f"/transitions/{identifier}").status_code == 200


def test_disallowed_status_move_is_refused(client):
    seed = _seed(client)
    identifier = client.post("/transitions", json=_body(seed)).json()["data"][
        "transition_identifier"
    ]
    client.patch(
        f"/transitions/{identifier}", json={"transition_status": "confirmed"}
    )
    resp = client.patch(
        f"/transitions/{identifier}", json={"transition_status": "rejected"}
    )
    assert resp.status_code == 422, resp.text


def test_process_scoped_list_and_reorder(client):
    seed = _seed(client)
    first = client.post("/transitions", json=_body(seed)).json()["data"][
        "transition_identifier"
    ]
    second = client.post(
        "/transitions",
        json=_body(
            seed,
            transition_to_value="Declined",
            transition_required_fields=[seed["decline_reason"]],
        ),
    ).json()["data"]["transition_identifier"]

    listed = client.get(f"/processes/{seed['process']}/transitions")
    assert listed.status_code == 200
    assert [r["transition_identifier"] for r in listed.json()["data"]] == [
        first,
        second,
    ]

    reordered = client.post(
        f"/processes/{seed['process']}/transitions/order",
        json={"ordered_identifiers": [second, first]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [
        r["transition_identifier"] for r in reordered.json()["data"]
    ] == [second, first]

    partial = client.post(
        f"/processes/{seed['process']}/transitions/order",
        json={"ordered_identifiers": [second]},
    )
    assert partial.status_code == 422
    codes = {e["code"] for e in partial.json()["errors"]}
    assert "incomplete_order" in codes


def test_incompleteness_report_route(client):
    seed = _seed(client)
    client.post("/transitions", json=_body(seed))
    client.post(
        "/transitions",
        json=_body(
            seed,
            transition_to_value="Declined",
            transition_required_fields=[seed["decline_reason"]],
            transition_consequence_notes="A decline notice is sent, but no "
            "message template record exists for it yet.",
            transition_manual_follow_up="A member may also write by hand.",
        ),
    )
    resp = client.get("/transitions/incomplete")
    assert resp.status_code == 200, resp.text
    report = resp.json()["data"]
    assert len(report) == 1
    assert report[0]["transition_to_value"] == "Declined"


def test_a_set_from_side_survives_the_round_trip(client):
    """DEC-1065: the two 'any pre-Active status' rows stay one rule each."""
    seed = _seed(client)
    resp = client.post(
        "/transitions",
        json=_body(
            seed,
            transition_from_values=list(PRE_ACTIVE),
            transition_to_value="Dormant",
        ),
    )
    assert resp.status_code == 201, resp.text
    identifier = resp.json()["data"]["transition_identifier"]
    got = client.get(f"/transitions/{identifier}").json()["data"]
    assert got["transition_from_values"] == PRE_ACTIVE


def test_missing_transition_is_404(client):
    resp = client.get("/transitions/TRN-999")
    assert resp.status_code == 404
