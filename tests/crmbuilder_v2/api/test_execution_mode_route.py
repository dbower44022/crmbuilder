"""API tests — PI-183 ADO execution_mode gate over REST.

Covers: setting execution_mode on project + PI create/patch; the
approve-dispatch endpoint (the only write path for dispatch_approved); the
backlog interactive + pending_approval partitions; and the dispatcher refusing
interactive / unapproved ado_with_approval items.
"""

from __future__ import annotations

_EXEC = "ADO execution_mode route test executive summary, above the floor. " * 4


def _data(r):
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


def _project(client, ident, *, execution_mode=None):
    body = {
        "project_identifier": ident, "project_name": f"P {ident}",
        "project_purpose": "p", "project_description": "d",
        "project_status": "planned",
    }
    if execution_mode is not None:
        body["project_execution_mode"] = execution_mode
    assert client.post("/projects", json=body).status_code == 201
    return ident


def _pi(client, ident, project_id, *, execution_mode=None):
    body = {
        "identifier": ident, "title": f"PI {ident}", "item_type": "pending_work",
        "status": "Draft", "executive_summary": _EXEC,
    }
    if execution_mode is not None:
        body["execution_mode"] = execution_mode
    assert client.post("/planning-items", json=body).status_code == 201
    client.post("/references", json={
        "source_type": "planning_item", "source_id": ident,
        "target_type": "project", "target_id": project_id,
        "relationship": "planning_item_belongs_to_project"})
    return ident


def test_create_defaults_to_ado(client):
    _project(client, "PRJ-960")
    _pi(client, "PI-960", "PRJ-960")
    assert _data(client.get("/projects/PRJ-960"))["project_execution_mode"] == "ado"
    assert _data(client.get("/planning-items/PI-960"))["execution_mode"] == "ado"
    assert _data(client.get("/planning-items/PI-960"))["dispatch_approved"] is False


def test_create_with_mode_and_patch(client):
    _project(client, "PRJ-961", execution_mode="interactive")
    assert _data(client.get("/projects/PRJ-961"))["project_execution_mode"] == "interactive"
    _pi(client, "PI-961", "PRJ-961", execution_mode="ado_with_approval")
    # PATCH the PI's mode.
    r = client.patch("/planning-items/PI-961", json={"execution_mode": "ado"})
    assert r.status_code == 200, r.text
    assert _data(client.get("/planning-items/PI-961"))["execution_mode"] == "ado"
    # PATCH the project's mode.
    r = client.patch("/projects/PRJ-961", json={"project_execution_mode": "ado"})
    assert r.status_code == 200, r.text
    assert _data(client.get("/projects/PRJ-961"))["project_execution_mode"] == "ado"


def test_invalid_mode_rejected(client):
    r = client.post("/projects", json={
        "project_identifier": "PRJ-962", "project_name": "x", "project_purpose": "p",
        "project_description": "d", "project_execution_mode": "bogus",
    })
    # Validated in the access layer (require_in -> ValidationError -> 400),
    # consistent with status / item_type enum validation.
    assert r.status_code == 400, r.text
    assert r.json()["errors"][0]["field"] == "execution_mode"


def test_interactive_backlog_and_dispatch_refusal(client):
    _project(client, "PRJ-963")
    _pi(client, "PI-963", "PRJ-963", execution_mode="interactive")
    backlog = _data(client.get("/projects/PRJ-963/backlog"))
    assert backlog["interactive"] == ["PI-963"]
    assert backlog["eligible"] == []
    # The dispatcher hard-refuses it.
    r = client.post("/planning-items/PI-963/dispatch")
    assert r.status_code == 409, r.text


def test_approve_dispatch_endpoint(client):
    _project(client, "PRJ-964")
    _pi(client, "PI-964", "PRJ-964", execution_mode="ado_with_approval")
    backlog = _data(client.get("/projects/PRJ-964/backlog"))
    assert backlog["pending_approval"] == ["PI-964"]
    assert backlog["eligible"] == []
    # Dispatch refused before approval.
    assert client.post("/planning-items/PI-964/dispatch").status_code == 409
    # Approve — the only write path for dispatch_approved.
    appr = _data(client.post("/planning-items/PI-964/approve-dispatch"))
    assert appr["dispatch_approved"] is True
    # Idempotent.
    assert client.post("/planning-items/PI-964/approve-dispatch").status_code == 201
    # Now eligible and dispatchable.
    backlog = _data(client.get("/projects/PRJ-964/backlog"))
    assert backlog["eligible"] == ["PI-964"]
    assert backlog["pending_approval"] == []
    assert client.post("/planning-items/PI-964/dispatch").status_code == 201


def test_dispatch_approved_not_settable_via_patch(client):
    """REQ-155: a PI update cannot set dispatch_approved (the field is not in
    the update schema, so it is silently ignored / unknown)."""
    _project(client, "PRJ-965")
    _pi(client, "PI-965", "PRJ-965", execution_mode="ado_with_approval")
    # The update schema has no dispatch_approved field; sending it is ignored.
    client.patch("/planning-items/PI-965", json={"dispatch_approved": True})
    assert _data(client.get("/planning-items/PI-965"))["dispatch_approved"] is False
