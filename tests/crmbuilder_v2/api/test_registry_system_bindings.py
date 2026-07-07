"""REQ-472 / PI-396 — registry-native bindings: system baseline + overlay.

A system-scoped binding row reaches EVERY engagement's resolved contract with
no per-engagement binding step; an engagement ``disable`` row masks the
baseline for that engagement only; disable + an engagement ``bind`` row =
replace. Per-engagement reference-edge bindings keep working unchanged.
"""

from __future__ import annotations


def _profile(client, area="ui", tier="developer", description="UI dev."):
    return client.post(
        "/agent-profiles",
        json={"area": area, "tier": tier, "description": description},
    ).json()["data"]["identifier"]


def _skill(client, name, description, scope=None):
    payload = {"name": name, "kind": "instruction", "description": description}
    if scope is not None:
        payload["scope"] = scope
    return client.post("/skills", json=payload).json()["data"]["identifier"]


def _engagement(client, code):
    return client.post(
        "/engagements",
        json={"engagement_code": code, "engagement_name": code, "engagement_purpose": "p"},
    ).json()["data"]["engagement_identifier"]


def _bind(client, prof, target_id, *, target_type="skill", mode="bind", scope=None):
    payload = {"target_type": target_type, "target_id": target_id, "mode": mode}
    if scope is not None:
        payload["scope"] = scope
    return client.post(f"/agent-profiles/{prof}/bindings", json=payload)


def _prompt(client, prof, engagement):
    r = client.get(f"/agent-profiles/{prof}/contract?engagement={engagement}")
    return r.json()["data"]["system_prompt"]


def test_system_binding_resolves_for_every_engagement(client):
    prof = _profile(client)
    skl = _skill(client, "standard", "the system standard text")
    r = _bind(client, prof, skl, scope="system")
    assert r.status_code == 201, r.text
    assert r.json()["data"]["scope"] == "system"

    # ENG-001 (seeded) and a brand-new engagement with NO binding step both
    # inherit the baseline binding.
    assert "the system standard text" in _prompt(client, prof, "ENG-001")
    eng2 = _engagement(client, "FRESH")
    assert "the system standard text" in _prompt(client, prof, eng2)

    # The bindings endpoint surfaces the row with its scope and mode.
    rows = client.get(f"/agent-profiles/{prof}/bindings").json()["data"][
        "registry_bindings"
    ]
    assert [(b["target_id"], b["mode"], b["scope"]) for b in rows] == [
        (skl, "bind", "system")
    ]


def test_engagement_disable_masks_baseline_for_that_engagement_only(client):
    prof = _profile(client)
    skl = _skill(client, "standard", "baseline standard body")
    assert _bind(client, prof, skl, scope="system").status_code == 201
    eng2 = _engagement(client, "OPTOUT")
    assert _bind(client, prof, skl, mode="disable", scope=eng2).status_code == 201

    assert "baseline standard body" not in _prompt(client, prof, eng2)
    assert "baseline standard body" in _prompt(client, prof, "ENG-001")


def test_disable_plus_engagement_bind_replaces_the_standard(client):
    prof = _profile(client)
    original = _skill(client, "standard", "original standard body")
    assert _bind(client, prof, original, scope="system").status_code == 201
    eng2 = _engagement(client, "REPLACER")
    replacement = _skill(client, "custom standard", "replacement standard body", scope=eng2)
    assert _bind(client, prof, original, mode="disable", scope=eng2).status_code == 201
    assert _bind(client, prof, replacement, scope=eng2).status_code == 201

    prompt = _prompt(client, prof, eng2)
    assert "original standard body" not in prompt
    assert "replacement standard body" in prompt
    # Other engagements keep the baseline and never see the overlay.
    prompt_one = _prompt(client, prof, "ENG-001")
    assert "original standard body" in prompt_one
    assert "replacement standard body" not in prompt_one


def test_reference_edges_compose_and_dedupe_with_baseline(client):
    prof = _profile(client)
    tool = client.post(
        "/skills",
        json={"name": "scope", "kind": "tool", "description": "Record Work Tasks.",
              "backing_callable": "POST /workstreams/{id}/scope"},
    ).json()["data"]["identifier"]
    # Bound BOTH ways: legacy reference edge and system baseline row.
    assert client.post(
        "/references",
        json={"source_type": "agent_profile", "source_id": prof,
              "target_type": "skill", "target_id": tool,
              "relationship": "agent_profile_has_skill"},
    ).status_code == 201
    assert _bind(client, prof, tool, scope="system").status_code == 201

    contract = client.get(f"/agent-profiles/{prof}/contract").json()["data"]
    assert [t["identifier"] for t in contract["tools"]] == [tool]


def test_binding_validation_and_delete(client):
    prof = _profile(client)
    skl = _skill(client, "standard", "body")

    # A system-scoped disable is rejected: delete the baseline row instead.
    assert _bind(client, prof, skl, mode="disable").status_code == 422
    # Vocabulary violations and unknown targets.
    assert _bind(client, prof, skl, target_type="learning").status_code == 422
    assert _bind(client, prof, "SKL-999").status_code == 404
    assert client.post(
        "/agent-profiles/AGP-999/bindings",
        json={"target_type": "skill", "target_id": skl},
    ).status_code == 404

    created = _bind(client, prof, skl, scope="system")
    assert created.status_code == 201
    # Exact duplicate is a conflict.
    assert _bind(client, prof, skl, scope="system").status_code == 409

    binding_id = created.json()["data"]["id"]
    assert client.delete(
        f"/agent-profiles/{prof}/bindings/{binding_id}"
    ).status_code == 200
    assert "body" not in _prompt(client, prof, "ENG-001")
    # Deleting again is a 404.
    assert client.delete(
        f"/agent-profiles/{prof}/bindings/{binding_id}"
    ).status_code == 404
