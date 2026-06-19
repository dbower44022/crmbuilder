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


# Lifecycle order the endpoint reports present statuses in (REQ-242).
_LIFECYCLE = (
    "Draft",
    "Decomposed",
    "Ready",
    "In Progress",
    "In Review",
    "Resolved",
    "Deferred",
    "Cancelled",
)


def _scope_pi(client, prj, title, status):
    pi = _pi(client, title, status)
    _ref(
        client, "planning_item", pi, "project", prj,
        "planning_item_belongs_to_project",
    )
    return pi


def test_status_counts_covers_every_lifecycle_status(client):
    # One in-scope PI in each of the eight lifecycle statuses: every status
    # present is reported (none dropped), each with its true count, and the
    # output is ordered by lifecycle through the JSON boundary.
    rel = _release(client, title="Every-status release")
    prj = _project(client, name="Every-status project")
    _ref(client, "project", prj, "release", rel, "project_belongs_to_release")
    for i, status in enumerate(_LIFECYCLE):
        _scope_pi(client, prj, f"PI-{i}-{status}", status)
    data = _counts(client, rel)
    assert data["status_counts"] == dict.fromkeys(_LIFECYCLE, 1)
    assert list(data["status_counts"]) == list(_LIFECYCLE)
    assert data["total"] == len(_LIFECYCLE)


def test_status_counts_orders_present_statuses_by_lifecycle(client):
    # Inserting out of lifecycle order still serializes in lifecycle order;
    # absent statuses (Decomposed, Ready, ...) are omitted, not zero-filled.
    rel = _release(client, title="Ordering release")
    prj = _project(client, name="Ordering project")
    _ref(client, "project", prj, "release", rel, "project_belongs_to_release")
    for title, status in [
        ("PI-late", "Cancelled"),
        ("PI-early", "Draft"),
        ("PI-mid", "In Progress"),
    ]:
        _scope_pi(client, prj, title, status)
    data = _counts(client, rel)
    assert list(data["status_counts"]) == ["Draft", "In Progress", "Cancelled"]
    assert "Ready" not in data["status_counts"]
    assert data["total"] == 3


def test_status_counts_aggregates_across_projects_in_release(client):
    # A release's count spans every in-scope project, summing matching statuses.
    rel = _release(client, title="Multi-project release")
    prj_a = _project(client, name="Project A")
    prj_b = _project(client, name="Project B")
    for prj in (prj_a, prj_b):
        _ref(client, "project", prj, "release", rel, "project_belongs_to_release")
    _scope_pi(client, prj_a, "A-draft", "Draft")
    _scope_pi(client, prj_a, "A-ready", "Ready")
    _scope_pi(client, prj_b, "B-ready", "Ready")
    _scope_pi(client, prj_b, "B-resolved", "Resolved")
    data = _counts(client, rel)
    assert data["status_counts"] == {"Draft": 1, "Ready": 2, "Resolved": 1}
    assert data["total"] == 4


def test_status_counts_excludes_out_of_scope_planning_items(client):
    # Only PIs reachable through this release's scope are counted: a PI in an
    # unlinked project and a PI in another release's project are both excluded.
    rel = _release(client, title="Scoped release")
    prj = _project(client, name="In-scope project")
    _ref(client, "project", prj, "release", rel, "project_belongs_to_release")
    _scope_pi(client, prj, "in-scope", "Ready")

    # A project (and its PI) belonging to no release.
    orphan_prj = _project(client, name="Orphan project")
    _scope_pi(client, orphan_prj, "orphan-pi", "Draft")

    # A project (and its PI) belonging to a different release.
    other_rel = _release(client, title="Other release")
    other_prj = _project(client, name="Other project")
    _ref(
        client, "project", other_prj, "release", other_rel,
        "project_belongs_to_release",
    )
    _scope_pi(client, other_prj, "other-pi", "Resolved")

    data = _counts(client, rel)
    assert data["status_counts"] == {"Ready": 1}
    assert data["total"] == 1
