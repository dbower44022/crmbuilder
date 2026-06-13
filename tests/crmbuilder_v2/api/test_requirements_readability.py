"""Requirements-provenance Phase 5 — origin-at-create + the readability gate.

- ``requirement_origin`` is recordable at create (defaults to ``human_defined``,
  accepts ``ai_derived``, rejects anything else), which makes the AI-derived
  drift re-open reachable end-to-end through the API;
- a requirement cannot be *activated* unless its statement is review-ready: no
  embedded governance identifiers, no retired-approach history, not a multi-idea
  run-on, and with a substantive acceptance criterion.
"""

from __future__ import annotations


def _make(client, **over):
    body = {
        "requirement_name": over.pop("requirement_name", "A capability"),
        "requirement_description": over.pop(
            "requirement_description", "What the system must do."
        ),
        "requirement_acceptance_summary": over.pop(
            "requirement_acceptance_summary", "Verifiable when it happens."
        ),
    }
    body.update(over)
    return client.post("/requirements", json=body)


def _ok_make(client, **over):
    r = _make(client, **over)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _ref(client, st, si, tt, ti, rel):
    return client.post(
        "/references",
        json={
            "source_type": st, "source_id": si,
            "target_type": tt, "target_id": ti, "relationship": rel,
        },
    )


def _approve(client, rid):
    assert _ref(client, "requirement", rid, "conversation", "CNV-001",
                "requirement_defined_in_conversation").status_code == 201
    assert _ref(client, "requirement", rid, "topic", "TOP-001",
                "requirement_belongs_to_topic").status_code == 201
    return _ref(client, "requirement", rid, "decision", "DEC-001",
                "requirement_approved_by_decision")


def _status(client, rid):
    return client.get(f"/requirements/{rid}").json()["data"]["requirement_status"]


# ---- origin at create -------------------------------------------------------

def test_origin_defaults_to_human_defined(client):
    assert _ok_make(client)["requirement_origin"] == "human_defined"


def test_origin_can_be_set_ai_derived(client):
    rec = _ok_make(client, requirement_origin="ai_derived")
    assert rec["requirement_origin"] == "ai_derived"


def test_invalid_origin_rejected(client):
    r = _make(client, requirement_origin="robot")
    assert r.status_code == 422, r.text


# ---- readability gate at activation ----------------------------------------

def test_readable_requirement_can_be_activated(client):
    rid = _ok_make(client)["requirement_identifier"]
    assert _approve(client, rid).status_code == 201
    assert _status(client, rid) == "confirmed"


def test_identifier_in_statement_blocks_activation(client):
    rid = _ok_make(
        client,
        requirement_description="Implement the thing per DEC-373 and PI-122.",
    )["requirement_identifier"]
    r = _approve(client, rid)
    assert r.status_code == 422, r.text
    assert "identifier" in r.text
    assert _status(client, rid) == "candidate"  # rolled back, not activated


def test_history_in_statement_blocks_activation(client):
    rid = _ok_make(
        client,
        requirement_description="Replace the shelved batch orchestrator approach.",
    )["requirement_identifier"]
    assert _approve(client, rid).status_code == 422
    assert _status(client, rid) == "candidate"


def test_runon_statement_blocks_activation(client):
    rid = _ok_make(
        client, requirement_description=("track many things " * 30),
    )["requirement_identifier"]
    assert _approve(client, rid).status_code == 422
    assert _status(client, rid) == "candidate"


def test_weak_acceptance_blocks_activation(client):
    rid = _ok_make(
        client, requirement_acceptance_summary="ok",
    )["requirement_identifier"]
    assert _approve(client, rid).status_code == 422
    assert _status(client, rid) == "candidate"


# ---- origin drives the AI-derived drift re-open, end-to-end via the API ------

def test_ai_derived_child_reopens_on_parent_edit_via_api(client):
    pid = _ok_make(client, requirement_name="Parent")["requirement_identifier"]
    cid = _ok_make(
        client, requirement_name="Child", requirement_origin="ai_derived"
    )["requirement_identifier"]
    _ref(client, "requirement", cid, "requirement", pid,
         "requirement_refines_requirement")
    _ref(client, "requirement", pid, "conversation", "CNV-001",
         "requirement_defined_in_conversation")
    _ref(client, "requirement", pid, "topic", "TOP-001",
         "requirement_belongs_to_topic")
    # child inherits parent's provenance + topic; readable statement → activates
    assert _ref(client, "requirement", cid, "decision", "DEC-001",
                "requirement_approved_by_decision").status_code == 201
    assert _status(client, cid) == "confirmed"
    # editing the parent re-opens the AI-derived child
    client.patch(f"/requirements/{pid}",
                 json={"requirement_description": "a changed meaning"})
    child = client.get(f"/requirements/{cid}").json()["data"]
    assert child["requirement_status"] == "candidate"
    assert child["requirement_review_state"] == "needs_review"
