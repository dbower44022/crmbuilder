"""Commit REST endpoint tests — UI v0.8, PI-029 slice B.

Updated for the PI-073 / DEC-314 redesign: commits attribute to a
*session* via the renamed ``commit_session_id`` FK (formerly
``commit_conversation_id`` pointing at the old conversation entity).
The derived listing endpoint moved from ``/conversations/{id}/commits``
to ``/sessions/{id}/commits`` accordingly.
"""

from __future__ import annotations


SHA_A = "a" * 40
SHA_B = "b" * 40

_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _session(client, identifier="SES-001"):
    """Create a session a commit can attribute to and return its identifier.

    Commits attribute at session grain under PI-073; ``commit_session_id``
    must point at an existing session row. We supply an explicit
    ``SES-NNN`` identifier so the commit-body builder can reference it. A
    session requires exactly one ``session_belongs_to_project`` edge,
    so we create a workstream first and attach the membership edge.
    """
    ws_resp = client.post("/projects", json={
        "project_name": "WS " + identifier,
        "project_purpose": "p",
        "project_description": "d",
    })
    wid = ws_resp.json()["data"]["project_identifier"]
    resp = client.post("/sessions", json={
        "session_identifier": identifier,
        "session_title": "Session " + identifier,
        "session_description": "d",
        "session_medium": "chat",
        "session_executive_summary": _EXEC_SUMMARY,
        "references": [{
            "source_type": "session", "source_id": identifier,
            "target_type": "project", "target_id": wid,
            "relationship": "session_belongs_to_project",
        }],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["session_identifier"]


def _commit_body(sha=SHA_A, session_id="SES-001"):
    return {
        "commit_sha": sha,
        "commit_message_first_line": "first line",
        "commit_message_full": "first line\n\nbody",
        "commit_author_name": "Doug Bower",
        "commit_author_email": "doug@dougbower.com",
        "commit_committed_at": "2026-05-23T20:45:12-04:00",
        "commit_repository": "crmbuilder",
        "commit_branch": "main",
        "commit_parent_shas": ["1" * 40],
        "commit_files_changed_count": 3,
        "commit_session_id": session_id,
    }


def test_post_creates_with_autoassigned_identifier(client):
    _session(client)
    r = client.post("/commits", json=_commit_body())
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["commit_identifier"] == "CM-0001"
    assert body["data"]["commit_sha"] == SHA_A


def test_get_by_identifier(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.get("/commits/CM-0001")
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_get_unknown_returns_404(client):
    r = client.get("/commits/CM-9999")
    assert r.status_code == 404


def test_by_sha_full_hit(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.get(f"/commits/by-sha/{SHA_A}")
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_by_sha_unambiguous_prefix(client):
    _session(client)
    client.post("/commits", json=_commit_body(sha=SHA_A))
    client.post("/commits", json=_commit_body(sha=SHA_B))
    r = client.get("/commits/by-sha/" + SHA_A[:8])
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_by_sha_ambiguous_returns_409(client):
    _session(client)
    s1 = "abcd" + "0" * 36
    s2 = "abcd" + "1" * 36
    client.post("/commits", json=_commit_body(sha=s1))
    client.post("/commits", json=_commit_body(sha=s2))
    r = client.get("/commits/by-sha/abcd")
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "ambiguous_sha_prefix"
    assert set(detail["candidates"]) == {s1, s2}


def test_by_sha_miss_returns_404(client):
    r = client.get("/commits/by-sha/" + "f" * 40)
    assert r.status_code == 404


def test_by_sha_too_short_returns_422(client):
    r = client.get("/commits/by-sha/abc")
    assert r.status_code == 422


def test_by_sha_uppercase_normalized(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.get(f"/commits/by-sha/{SHA_A.upper()}")
    assert r.status_code == 200


def test_next_identifier_endpoint(client):
    r = client.get("/commits/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"]["next"] == "CM-0001"


def test_list_default_sort_descending(client):
    _session(client)
    body1 = _commit_body(sha=SHA_A)
    body1["commit_committed_at"] = "2026-05-20T10:00:00-04:00"
    body2 = _commit_body(sha=SHA_B)
    body2["commit_committed_at"] = "2026-05-23T10:00:00-04:00"
    client.post("/commits", json=body1)
    client.post("/commits", json=body2)
    r = client.get("/commits")
    data = r.json()["data"]
    assert data[0]["commit_sha"] == SHA_B
    assert data[1]["commit_sha"] == SHA_A


def test_list_filter_by_repository(client):
    _session(client)
    b1 = _commit_body(sha=SHA_A)
    b2 = _commit_body(sha=SHA_B)
    b2["commit_repository"] = "ClevelandBusinessMentoring"
    client.post("/commits", json=b1)
    client.post("/commits", json=b2)
    r = client.get("/commits?commit_repository=crmbuilder")
    assert len(r.json()["data"]) == 1


def test_delete_then_restore_cycle(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.delete("/commits/CM-0001")
    assert r.status_code == 200
    assert len(client.get("/commits").json()["data"]) == 0
    r = client.post("/commits/CM-0001/restore")
    assert r.status_code == 200
    assert len(client.get("/commits").json()["data"]) == 1


def test_patch_parent_shas(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_parent_shas": ["2" * 40, "3" * 40],
    })
    assert r.status_code == 200
    assert r.json()["data"]["commit_parent_shas"] == ["2" * 40, "3" * 40]


def test_patch_identifier_rejected(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_identifier": "CM-0099",
    })
    assert r.status_code == 422


def test_patch_sha_rejected(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_sha": SHA_B,
    })
    assert r.status_code == 422


def test_duplicate_sha_returns_409(client):
    _session(client)
    client.post("/commits", json=_commit_body())
    r = client.post("/commits", json=_commit_body())
    assert r.status_code == 409


def test_unknown_session_returns_422(client):
    r = client.post("/commits", json=_commit_body(session_id="SES-999"))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Derived endpoint: GET /sessions/{session_id}/commits (DEC-211, moved
# from /conversations/{id}/commits under the PI-073 redesign)
# ---------------------------------------------------------------------------


def test_sessions_commits_lists_scoped(client):
    _session(client, "SES-001")
    _session(client, "SES-002")
    client.post("/commits", json=_commit_body(sha=SHA_A, session_id="SES-001"))
    client.post("/commits", json=_commit_body(sha=SHA_B, session_id="SES-002"))
    r = client.get("/sessions/SES-001/commits")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["commit_sha"] == SHA_A


def test_sessions_commits_empty_returns_200(client):
    _session(client)
    r = client.get("/sessions/SES-001/commits")
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_sessions_commits_unknown_returns_404(client):
    r = client.get("/sessions/SES-999/commits")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "session_not_found"
