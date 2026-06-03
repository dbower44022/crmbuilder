"""PI-122 slice 5 — cross-engagement learning (the DEC-373 multiplier)."""

from __future__ import annotations


def _make_engagement(client, code: str):
    return client.post(
        "/engagements",
        json={"engagement_code": code, "engagement_name": code, "engagement_purpose": "p"},
    )


def _eng_learning(client, scope, content):
    return client.post(
        "/learnings",
        json={"area": "storage", "tier": "developer", "category": "gotcha",
              "content": content, "scope": scope},
    ).json()["data"]["identifier"]


def test_cross_engagement_candidate_and_promotion(client):
    # v2_env seeds ENG-001; add ENG-002.
    r = _make_engagement(client, "BRAVO")
    assert r.status_code == 201, r.text
    eng2 = r.json()["data"]["engagement_identifier"]

    same = "Contact is heavily extended — check existing fields before scoping."
    a = _eng_learning(client, "ENG-001", same)
    _eng_learning(client, eng2, same)
    # A non-recurring engagement learning — should not be a candidate.
    _eng_learning(client, "ENG-001", "one-off observation")

    cands = client.get("/learnings/cross-engagement-candidates").json()["data"]
    matching = [c for c in cands if c["content"] == same]
    assert len(matching) == 1
    assert set(matching[0]["engagements"]) == {"ENG-001", eng2}
    assert "one-off observation" not in [c["content"] for c in cands]

    # Promote one of them to system scope.
    promoted = client.post(f"/learnings/{a}/promote-to-system")
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["data"]["scope"] == "system"
    # Re-promoting a system learning is rejected.
    assert client.post(f"/learnings/{a}/promote-to-system").status_code == 422


def test_single_engagement_not_a_candidate(client):
    _eng_learning(client, "ENG-001", "local only")
    cands = client.get("/learnings/cross-engagement-candidates").json()["data"]
    assert all(c["content"] != "local only" for c in cands)
