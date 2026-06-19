"""Release planning-item status-counts read endpoint — REQ-242 / WTK-178.

``GET /releases/{id}/planning-item-status-counts`` returns the count of the
release's in-scope planning items per lifecycle status, covering every status
present (and only those present), reachable through the read API.
"""

from __future__ import annotations

_EXEC = "Release status-counts API test executive summary line. " * 6  # ~300 chars


def _release(client, title="Status-counts release"):
    r = client.post(
        "/releases",
        json={"release_title": title, "release_description": "d"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["release_identifier"]


def _project(client, name="Status-counts project"):
    r = client.post(
        "/projects",
        json={
            "project_name": name,
            "project_purpose": "p",
            "project_description": "d",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["project_identifier"]


def _pi(client, title, status="Draft"):
    r = client.post(
        "/planning-items",
        json={
            "title": title,
            "item_type": "pending_work",
            "status": status,
            "executive_summary": _EXEC,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["identifier"]


def _ref(client, st, si, tt, ti, rel):
    r = client.post(
        "/references",
        json={
            "source_type": st,
            "source_id": si,
            "target_type": tt,
            "target_id": ti,
            "relationship": rel,
        },
    )
    assert r.status_code in (200, 201), r.text


def _counts(client, rel):
    r = client.get(f"/releases/{rel}/planning-item-status-counts")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_status_counts_reachable_and_grouped(client):
    rel = _release(client)
    prj = _project(client)
    _ref(client, "project", prj, "release", rel, "project_belongs_to_release")
    for title, status in [
        ("PI-a", "Draft"),
        ("PI-b", "Ready"),
        ("PI-c", "Ready"),
        ("PI-d", "Resolved"),
    ]:
        pi = _pi(client, title, status)
        _ref(
            client, "planning_item", pi, "project", prj,
            "planning_item_belongs_to_project",
        )
    data = _counts(client, rel)
    assert data["release_identifier"] == rel
    assert data["status_counts"] == {"Draft": 1, "Ready": 2, "Resolved": 1}
    assert data["total"] == 4
    # Only present statuses are reported — no zero-filled absent statuses.
    assert "In Progress" not in data["status_counts"]


def test_status_counts_empty_release(client):
    rel = _release(client, title="Empty release")
    data = _counts(client, rel)
    assert data == {
        "release_identifier": rel,
        "status_counts": {},
        "total": 0,
    }


def test_status_counts_unknown_release_404(client):
    r = client.get("/releases/REL-999/planning-item-status-counts")
    assert r.status_code == 404, r.text
