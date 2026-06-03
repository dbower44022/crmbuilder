"""PI-122 slice 3 — learning entity, capture/evidence, resolver injection."""

from __future__ import annotations


def _seed_work_task(client) -> str:
    """Create a Workstream-less Work Task to use as learning evidence."""
    r = client.post(
        "/work-tasks",
        json={"work_task_title": "evidence task", "work_task_area": "storage"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["work_task_identifier"]


def test_capture_with_evidence_sets_confidence_and_edge(client):
    wtk = _seed_work_task(client)
    r = client.post(
        "/learnings/capture",
        json={"area": "storage", "tier": "developer", "category": "gotcha",
              "content": "Adding an ENTITY_TYPE must rebuild change_log + refs CHECKs.",
              "evidence_type": "work_task", "evidence_id": wtk},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["identifier"] == "LRN-001"
    assert data["confidence"] == 1
    # The derived-from edge exists.
    refs = client.get(f"/references?source_id={data['identifier']}&relationship=learning_derived_from").json()["data"]
    assert any(e["target_id"] == wtk for e in refs)


def test_capture_without_evidence_is_hunch(client):
    r = client.post(
        "/learnings/capture",
        json={"area": "api", "tier": "architect", "category": "pattern",
              "content": "Prefer additive replanning."},
    )
    assert r.json()["data"]["confidence"] == 0


def test_evidence_accumulation_and_contradiction(client):
    wtk1 = _seed_work_task(client)
    wtk2 = _seed_work_task(client)
    wtk3 = _seed_work_task(client)
    lrn = client.post(
        "/learnings/capture",
        json={"area": "storage", "tier": "developer", "category": "constraint",
              "content": "x", "evidence_type": "work_task", "evidence_id": wtk1},
    ).json()["data"]["identifier"]
    # Supporting evidence raises confidence.
    up = client.post(f"/learnings/{lrn}/evidence",
                     json={"target_type": "work_task", "target_id": wtk2})
    assert up.json()["data"]["confidence"] == 2
    # Contradicting evidence lowers it.
    down = client.post(f"/learnings/{lrn}/evidence",
                       json={"target_type": "work_task", "target_id": wtk3, "contradicts": True})
    assert down.json()["data"]["confidence"] == 1


def test_resolver_injects_active_area_tier_learnings(client):
    prof = client.post(
        "/agent-profiles",
        json={"area": "storage", "tier": "developer", "description": "Storage dev."},
    ).json()["data"]["identifier"]
    client.post("/learnings", json={"area": "storage", "tier": "developer",
                "category": "gotcha", "content": "match me"})
    # Different area/tier — must NOT be injected.
    client.post("/learnings", json={"area": "api", "tier": "developer",
                "category": "gotcha", "content": "other area"})
    client.post("/learnings", json={"area": "storage", "tier": "architect",
                "category": "gotcha", "content": "other tier"})
    contract = client.get(f"/agent-profiles/{prof}/contract").json()["data"]
    contents = [lrn["content"] for lrn in contract["active_learnings"]]
    assert contents == ["match me"]


def test_orchestrator_profile_gets_no_learnings(client):
    prof = client.post(
        "/agent-profiles",
        json={"area": "storage", "tier": "orchestrator", "description": "PM."},
    ).json()["data"]["identifier"]
    client.post("/learnings", json={"area": "storage", "tier": "developer",
                "category": "gotcha", "content": "z"})
    contract = client.get(f"/agent-profiles/{prof}/contract").json()["data"]
    assert contract["active_learnings"] == []


def test_learning_bad_vocab_is_422(client):
    r = client.post("/learnings", json={"area": "storage", "tier": "wizard",
                    "category": "gotcha", "content": "x"})
    assert r.status_code == 422
