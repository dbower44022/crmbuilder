"""PI-122 slice 4 — promote (with the enforced-rule gate) + curate sweep."""

from __future__ import annotations


def _learning(client, **over) -> str:
    body = {"area": "storage", "tier": "developer", "category": "pattern", "content": "c"}
    body.update(over)
    return client.post("/learnings", json=body).json()["data"]["identifier"]


def _work_task(client) -> str:
    return client.post(
        "/work-tasks", json={"work_task_title": "t", "work_task_area": "storage"}
    ).json()["data"]["work_task_identifier"]


def test_promote_to_skill_links_and_marks_promoted(client):
    lrn = _learning(client, content="sequence by layer rank")
    resp = client.post(
        f"/learnings/{lrn}/promote-to-skill",
        json={"name": "sequence", "kind": "instruction"},
    )
    assert resp.status_code == 201, resp.text
    skill_id = resp.json()["data"]["skill"]["identifier"]
    # The learning is now promoted and linked.
    assert client.get(f"/learnings/{lrn}").json()["data"]["status"] == "promoted"
    refs = client.get(f"/references?source_id={lrn}&relationship=learning_promoted_to").json()["data"]
    assert any(e["target_id"] == skill_id for e in refs)
    # The promoted skill inherits the learning's (system) scope + content.
    skill = client.get(f"/skills/{skill_id}").json()["data"]
    assert skill["scope"] == "system"
    assert skill["description"] == "sequence by layer rank"


def test_promote_to_advisory_rule_is_free(client):
    lrn = _learning(client)
    resp = client.post(
        f"/learnings/{lrn}/promote-to-rule", json={"enforcement": "advisory"}
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["governance_rule"]["enforcement"] == "advisory"


def test_promote_to_enforced_rule_requires_human_review(client):
    lrn = _learning(client)
    blocked = client.post(
        f"/learnings/{lrn}/promote-to-rule", json={"enforcement": "enforced"}
    )
    assert blocked.status_code == 422
    assert blocked.json()["errors"][0]["code"] == "human_review_required"
    # The learning is untouched (not promoted) by the blocked attempt.
    assert client.get(f"/learnings/{lrn}").json()["data"]["status"] == "active"
    # With human approval it goes through.
    ok = client.post(
        f"/learnings/{lrn}/promote-to-rule",
        json={"enforcement": "enforced", "human_approved": True, "severity": "high"},
    )
    assert ok.status_code == 201
    assert ok.json()["data"]["governance_rule"]["enforcement"] == "enforced"


def test_curate_retires_contradicted_zero_confidence(client):
    wtk = _work_task(client)
    # Captured with evidence (confidence 1), then contradicted to 0.
    lrn = client.post(
        "/learnings/capture",
        json={"area": "storage", "tier": "developer", "category": "gotcha", "content": "x",
              "evidence_type": "work_task", "evidence_id": wtk},
    ).json()["data"]["identifier"]
    client.post(f"/learnings/{lrn}/evidence",
                json={"target_type": "work_task", "target_id": wtk, "contradicts": True})
    assert client.get(f"/learnings/{lrn}").json()["data"]["confidence"] == 0

    # A well-evidenced learning that should survive curation.
    survivor = _learning(client, content="keep me")
    client.patch(f"/learnings/{survivor}", json={"confidence": 3})

    result = client.post("/learnings/curate", json={"area": "storage"}).json()["data"]
    assert lrn in result["retired"]
    assert survivor not in result["retired"]
    assert client.get(f"/learnings/{lrn}").json()["data"]["status"] == "stale"
    assert client.get(f"/learnings/{survivor}").json()["data"]["status"] == "active"
