"""Commit REST endpoint tests — UI v0.8, PI-029 slice B."""

from __future__ import annotations


SHA_A = "a" * 40
SHA_B = "b" * 40


def _conv(client, identifier="CONV-001"):
    ws_resp = client.post("/workstreams", json={
        "workstream_name": "WS " + identifier,
        "workstream_purpose": "p",
        "workstream_description": "d",
    })
    wid = ws_resp.json()["data"]["workstream_identifier"]
    client.post("/conversations", json={
        "conversation_title": "C " + identifier,
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": identifier,
        "references": [{
            "source_type": "conversation", "source_id": identifier,
            "target_type": "workstream", "target_id": wid,
            "relationship": "conversation_belongs_to_workstream",
        }],
    })
    return identifier


def _commit_body(sha=SHA_A, conv_id="CONV-001"):
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
        "commit_conversation_id": conv_id,
    }


def test_post_creates_with_autoassigned_identifier(client):
    _conv(client)
    r = client.post("/commits", json=_commit_body())
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["commit_identifier"] == "CM-0001"
    assert body["data"]["commit_sha"] == SHA_A


def test_get_by_identifier(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.get("/commits/CM-0001")
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_get_unknown_returns_404(client):
    r = client.get("/commits/CM-9999")
    assert r.status_code == 404


def test_by_sha_full_hit(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.get(f"/commits/by-sha/{SHA_A}")
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_by_sha_unambiguous_prefix(client):
    _conv(client)
    client.post("/commits", json=_commit_body(sha=SHA_A))
    client.post("/commits", json=_commit_body(sha=SHA_B))
    r = client.get("/commits/by-sha/" + SHA_A[:8])
    assert r.status_code == 200
    assert r.json()["data"]["commit_sha"] == SHA_A


def test_by_sha_ambiguous_returns_409(client):
    _conv(client)
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
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.get(f"/commits/by-sha/{SHA_A.upper()}")
    assert r.status_code == 200


def test_next_identifier_endpoint(client):
    r = client.get("/commits/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"]["next"] == "CM-0001"


def test_list_default_sort_descending(client):
    _conv(client)
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
    _conv(client)
    b1 = _commit_body(sha=SHA_A)
    b2 = _commit_body(sha=SHA_B)
    b2["commit_repository"] = "ClevelandBusinessMentoring"
    client.post("/commits", json=b1)
    client.post("/commits", json=b2)
    r = client.get("/commits?commit_repository=crmbuilder")
    assert len(r.json()["data"]) == 1


def test_delete_then_restore_cycle(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.delete("/commits/CM-0001")
    assert r.status_code == 200
    assert len(client.get("/commits").json()["data"]) == 0
    r = client.post("/commits/CM-0001/restore")
    assert r.status_code == 200
    assert len(client.get("/commits").json()["data"]) == 1


def test_patch_parent_shas(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_parent_shas": ["2" * 40, "3" * 40],
    })
    assert r.status_code == 200
    assert r.json()["data"]["commit_parent_shas"] == ["2" * 40, "3" * 40]


def test_patch_identifier_rejected(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_identifier": "CM-0099",
    })
    assert r.status_code == 422


def test_patch_sha_rejected(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.patch("/commits/CM-0001", json={
        "commit_sha": SHA_B,
    })
    assert r.status_code == 422


def test_duplicate_sha_returns_409(client):
    _conv(client)
    client.post("/commits", json=_commit_body())
    r = client.post("/commits", json=_commit_body())
    assert r.status_code == 409


def test_unknown_conversation_returns_422(client):
    r = client.post("/commits", json=_commit_body(conv_id="CONV-999"))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Derived endpoint: GET /conversations/{conv_id}/commits (DEC-211)
# ---------------------------------------------------------------------------


def test_conversations_commits_lists_scoped(client):
    _conv(client, "CONV-001")
    _conv(client, "CONV-002")
    client.post("/commits", json=_commit_body(sha=SHA_A, conv_id="CONV-001"))
    client.post("/commits", json=_commit_body(sha=SHA_B, conv_id="CONV-002"))
    r = client.get("/conversations/CONV-001/commits")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["commit_sha"] == SHA_A


def test_conversations_commits_empty_returns_200(client):
    _conv(client)
    r = client.get("/conversations/CONV-001/commits")
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_conversations_commits_unknown_returns_404(client):
    r = client.get("/conversations/CONV-999/commits")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "conversation_not_found"
