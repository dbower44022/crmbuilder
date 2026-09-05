"""PI-488 — the session-open and segment-advance operations over REST
(REQ-569..REQ-574, DEC-1060..DEC-1063).

Seeds a small store: a cross-cutting profile bound to two rules, two phase
profiles bound to one rule each, three lifecycle domains, one project and a
three-entry catalogue written as process records in the Gate 2 shape. Then
exercises every acceptance summary: the catalogue read, the confident open,
the empty answer, the unrecognised answer with its recorded miss, the
two-segment advance to completion, the pending-profile segment, and the
cross-cutting set present in every contract.
"""

from __future__ import annotations

import json

import pytest
from crmbuilder_v2.access.repositories import session_opening as so

_SUMMARY = (
    "A decision that exists so the tests can create governance rules that name "
    "their source decision, as every new rule must; it carries no other content "
    "and stands in for whichever real ruling would have made the rules under test."
)


def _post(client, path, body):
    r = client.post(path, json=body)
    assert r.status_code == 201, (path, r.text)
    return r.json()["data"]


def _rule(client, body, **extra):
    return _post(
        client, "/governance-rules",
        {"source_decision": "DEC-001", "body": body, "enforcement": "advisory",
         "applies_to": "claude_code", **extra},
    )["identifier"]


def _profile(client, area, description):
    return _post(
        client, "/agent-profiles",
        {"area": area, "tier": "orchestrator", "description": description, "scope": "system"},
    )["identifier"]


def _bind(client, prof, rule):
    _post(client, f"/agent-profiles/{prof}/bindings",
          {"target_type": "governance_rule", "target_id": rule, "mode": "bind", "scope": "system"})


def _domain(client, name):
    return _post(client, "/domains", {"domain_name": name, "domain_purpose": "p",
                                      "domain_description": "d"})["domain_identifier"]


def _entry(client, name, domain, segments, phrases):
    return _post(
        client, "/processes",
        {"process_name": name, "process_domain_identifier": domain, "process_purpose": f"Kind of work: {name}.",
         "process_steps": so.catalogue_steps_block(segments),
         "process_triggers": json.dumps(phrases)},
    )["process_identifier"]


@pytest.fixture
def seeded(client):
    _post(client, "/decisions", {"identifier": "DEC-001", "title": "Test ruling",
                                 "decision_date": "2026-01-01", "status": "Active",
                                 "executive_summary": _SUMMARY})
    cross_rules = [
        _rule(client, "Record governance in real time.", rule_type="governance_recording"),
        _rule(client, "Every code commit carries a Governed-By trailer.",
              enforcement="enforced_with_override", rule_type="commit_governance",
              predicate={"kind": "required_trailer", "trailer": "Governed-By", "pattern": "PI-\\d+"}),
    ]
    interview_rule = _rule(client, "Inferences require positive support.", rule_type="interview")
    release_rule = _rule(client, "Production deploy is human-only.", enforcement="enforced",
                         rule_type="deploy", predicate={"kind": "forbidden_command", "pattern": "rsync"})
    cross = _profile(client, so.CROSS_CUTTING_AREA, "The cross-cutting rules.")
    for r in cross_rules:
        _bind(client, cross, r)
    interviewer = _profile(client, "requirements-capture", "Requirements Interviewer role text.")
    _bind(client, interviewer, interview_rule)
    operator = _profile(client, "release-to-production", "Release Operator role text.")
    _bind(client, operator, release_rule)
    dom_req = _domain(client, "Requirements Capture")
    dom_spec = _domain(client, "Specification and Approval")
    dom_rel = _domain(client, "Release to Production")
    project = _post(client, "/projects", {"project_name": "Dogfood", "project_purpose": "p",
                                          "project_description": "d", "project_status": "in_flight"})["project_identifier"]
    define = _entry(
        client, "Define new business processes", dom_req,
        [{"position": 1, "domain": dom_req, "profile": interviewer, "area": "requirements-capture",
          "label": "Requirements Interviewer", "status": "active"},
         {"position": 2, "domain": dom_spec, "profile": None, "area": "solution-design",
          "label": "Solution Designer", "status": "pending"}],
        ["define new business processes", "define a business process", "capture requirements",
         "new business process", "interview"],
    )
    upgrade = _entry(
        client, "Upgrade the platform to the latest version", dom_rel,
        [{"position": 1, "domain": dom_rel, "profile": operator, "area": "release-to-production",
          "label": "Release Operator", "status": "active"}],
        ["upgrade the platform", "upgrade to the latest version", "upgrade espocrm", "platform upgrade"],
    )
    question = _entry(client, "Ask a question about the system or its records", dom_req, [],
                      ["ask a question", "question about the system", "what is", "look up a record"])
    # A process that is not a catalogue entry must not appear in the catalogue.
    _post(client, "/processes", {"process_name": "Ordinary process", "process_domain_identifier": dom_req,
                                 "process_purpose": "Not a kind of work.", "process_steps": "1. Do a thing."})
    return {
        "cross": cross, "cross_rules": cross_rules, "interviewer": interviewer, "interview_rule": interview_rule,
        "operator": operator, "release_rule": release_rule, "project": project,
        "define": define, "upgrade": upgrade, "question": question,
    }


def _rule_ids(contract):
    return {r["identifier"] for r in contract["advisory_rules"]} | {r["identifier"] for r in contract["enforced_ruleset"]}


# --- REQ-569: the catalogue -----------------------------------------------------


def test_opening_lists_catalogue_and_cross_cutting(client, seeded):
    r = client.get("/sessions/opening")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["question"] == so.OPENING_QUESTION
    names = [e["name"] for e in data["catalogue"]]
    assert names == ["Define new business processes", "Upgrade the platform to the latest version",
                     "Ask a question about the system or its records"]
    assert 3 <= len(data["examples"]) <= 4
    assert data["cross_cutting"]["profile_id"] == seeded["cross"]
    assert _rule_ids(data["cross_cutting"]) == set(seeded["cross_rules"])
    define = data["catalogue"][0]
    assert [s["status"] for s in define["segments"]] == ["active", "pending"]
    assert define["segments"][1]["area"] == "solution-design"


# --- REQ-570: a confident open ----------------------------------------------------


def test_open_with_answer_returns_first_contract_and_records(client, seeded):
    r = client.post("/sessions/open", json={"opening_answer": "define new business processes",
                                            "project_identifier": seeded["project"]})
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["kind_of_work"] == seeded["define"]
    assert d["confirmation_line"] == (
        "It sounds like you want to define new business processes; I will start with the Requirements Interviewer."
    )
    assert d["follow_up_question"] is None
    assert d["planning_item"] is None
    contract = d["contract"]
    assert contract["segment_profile_id"] == seeded["interviewer"]
    assert contract["cross_cutting_profile_id"] == seeded["cross"]
    assert _rule_ids(contract) == {seeded["interview_rule"], *seeded["cross_rules"]}
    assert "Requirements Interviewer role text." in contract["system_prompt"]
    assert "CROSS-CUTTING RULES" in contract["system_prompt"]

    rec = client.get(f"/sessions/{d['session']['session_identifier']}").json()["data"]
    assert rec["session_opening_answer"] == "define new business processes"
    assert rec["session_kind_of_work"] == seeded["define"]
    assert rec["session_confirmation_line"] == d["confirmation_line"]
    assert rec["session_status"] == "in_flight"
    segs = rec["session_phase_segments"]
    assert [s["profile"] for s in segs] == [seeded["interviewer"], None]
    assert segs[0]["entered_at"] and segs[0]["left_at"] is None
    assert segs[1]["entered_at"] is None
    # The membership edge names the project.
    edges = client.get(f"/references?source_id={rec['session_identifier']}").json()["data"]
    assert [(e["relationship"], e["target_id"]) for e in edges] == [("session_belongs_to_project", seeded["project"])]


def test_same_answer_classifies_the_same_way(client, seeded):
    a = client.post("/sessions/open", json={"opening_answer": "I want to define new business processes"}).json()["data"]
    b = client.post("/sessions/open", json={"opening_answer": "I want to define new business processes"}).json()["data"]
    assert a["kind_of_work"] == b["kind_of_work"] == seeded["define"]
    assert a["confirmation_line"] == b["confirmation_line"]
    assert a["session"]["session_identifier"] != b["session"]["session_identifier"]


def test_open_without_project_uses_latest_in_flight(client, seeded):
    d = client.post("/sessions/open", json={"opening_answer": "upgrade the platform"}).json()["data"]
    edges = client.get(f"/references?source_id={d['session']['session_identifier']}").json()["data"]
    assert edges[0]["target_id"] == seeded["project"]
    assert d["kind_of_work"] == seeded["upgrade"]
    assert d["contract"]["enforced_ruleset"][0]["identifier"] == seeded["release_rule"]


# --- REQ-571: no answer ---------------------------------------------------------


def test_open_without_answer_loads_cross_cutting_only_and_says_so(client, seeded):
    r = client.post("/sessions/open", json={})
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["kind_of_work"] is None
    assert d["first_line"] == so.NO_KIND_OF_WORK_LINE
    assert d["follow_up_question"] is None
    assert d["planning_item"] is None
    assert _rule_ids(d["contract"]) == set(seeded["cross_rules"])
    assert d["contract"]["segment_profile_id"] is None
    rec = client.get(f"/sessions/{d['session']['session_identifier']}").json()["data"]
    assert rec["session_opening_answer"] is None
    assert rec["session_kind_of_work"] is None
    assert rec["session_phase_segments"] == []


def test_question_entry_has_no_segments_and_loads_cross_cutting_only(client, seeded):
    d = client.post("/sessions/open", json={"opening_answer": "ask a question about the system"}).json()["data"]
    assert d["kind_of_work"] == seeded["question"]
    assert "no phase profile applies" in d["confirmation_line"]
    assert _rule_ids(d["contract"]) == set(seeded["cross_rules"])
    assert d["session"]["session_phase_segments"] == []


# --- REQ-572: an unrecognised answer ---------------------------------------------


def test_unrecognised_answer_asks_one_question_and_records_a_miss(client, seeded):
    answer = "teach the mentoring app to send birthday cards"
    d = client.post("/sessions/open", json={"opening_answer": answer}).json()["data"]
    assert d["kind_of_work"] is None
    assert d["follow_up_question"] == so.FOLLOW_UP_QUESTION
    for banned in ("phase", "role", "profile", "interviewer", "operator"):
        assert banned not in d["follow_up_question"].lower()
    assert _rule_ids(d["contract"]) == set(seeded["cross_rules"])
    pi = d["planning_item"]
    assert pi is not None and answer in pi["title"]
    assert pi["status"] == "Draft"
    rec = client.get(f"/sessions/{d['session']['session_identifier']}").json()["data"]
    assert rec["session_opening_answer"] == answer
    assert rec["session_kind_of_work"] is None
    assert rec["session_medium_metadata"]["catalogue_miss_planning_item"] == pi["identifier"]
    items = client.get("/planning-items").json()["data"]
    assert sum(1 for i in items if i["title"].startswith("Catalogue miss:")) == 1


# --- REQ-573: segment-advance ----------------------------------------------------


def test_advance_two_segment_session_to_completion(client, seeded):
    d = client.post("/sessions/open", json={"opening_answer": "define new business processes"}).json()["data"]
    sid = d["session"]["session_identifier"]

    r = client.post(f"/sessions/{sid}/advance-segment")
    assert r.status_code == 200, r.text
    a = r.json()["data"]
    assert a["completed"] is False
    assert a["segment"]["label"] == "Solution Designer"
    assert a["segment"]["status"] == "pending"
    assert "not yet available" in a["first_line"]
    # A pending segment loads the cross-cutting rules only.
    assert _rule_ids(a["contract"]) == set(seeded["cross_rules"])
    segs = a["session"]["session_phase_segments"]
    assert segs[0]["left_at"] and segs[1]["entered_at"] and segs[1]["left_at"] is None

    r = client.post(f"/sessions/{sid}/advance-segment", json={})
    assert r.status_code == 200, r.text
    b = r.json()["data"]
    assert b["completed"] is True and b["contract"] is None and b["segment"] is None
    segs = client.get(f"/sessions/{sid}").json()["data"]["session_phase_segments"]
    assert all(s["entered_at"] and s["left_at"] for s in segs)

    # Advancing a completed session stays completed.
    c = client.post(f"/sessions/{sid}/advance-segment").json()["data"]
    assert c["completed"] is True


def test_advance_without_segments_is_422(client, seeded):
    d = client.post("/sessions/open", json={}).json()["data"]
    r = client.post(f"/sessions/{d['session']['session_identifier']}/advance-segment")
    assert r.status_code == 422
    assert client.post("/sessions/SES-999/advance-segment").status_code == 404


# --- REQ-574: the cross-cutting set in every contract -----------------------------


def test_cross_cutting_set_is_bound_not_listed(client, seeded):
    extra = _rule(client, "A rule added later.", rule_type="later")
    _bind(client, seeded["cross"], extra)
    for answer in ("define new business processes", "upgrade the platform", ""):
        d = client.post("/sessions/open", json={"opening_answer": answer}).json()["data"]
        assert {*seeded["cross_rules"], extra} <= _rule_ids(d["contract"])
    cc = client.get(f"/agent-profiles/{seeded['cross']}/contract").json()["data"]
    assert _rule_ids(cc) == {*seeded["cross_rules"], extra}


def test_open_with_no_cross_cutting_profile_still_opens(client):
    _post(client, "/projects", {"project_name": "P", "project_purpose": "p", "project_description": "d",
                                "project_status": "in_flight"})
    d = client.post("/sessions/open", json={"opening_answer": ""}).json()["data"]
    assert d["contract"]["missing_cross_cutting_profile"] is True
    assert d["first_line"] == so.NO_KIND_OF_WORK_LINE


# --- classification unit checks (DEC-1061) ------------------------------------------


def test_classify_is_deterministic_and_thresholded():
    entries = [
        {"process_identifier": "PROC-001", "name": "Define new business processes",
         "segments": [], "trigger_phrases": ["define new business processes", "capture requirements"]},
        {"process_identifier": "PROC-002", "name": "Fix something that is not working",
         "segments": [], "trigger_phrases": ["fix something", "not working", "broken"]},
    ]
    hit = so.classify("please define new business processes for intake", entries)
    assert hit["entry"]["process_identifier"] == "PROC-001" and hit["confidence"] == 1.0
    partial = so.classify("we need to capture the requirements", entries)
    assert partial["entry"]["process_identifier"] == "PROC-001"
    miss = so.classify("compose a newsletter", entries)
    assert miss["entry"] is None and miss["confidence"] < so.MATCH_THRESHOLD
    assert so.classify("", entries)["entry"] is None
    assert so.classify("fix", entries)["entry"] is None  # one word of three: below threshold
