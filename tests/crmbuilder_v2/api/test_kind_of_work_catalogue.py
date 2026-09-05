"""PI-488 / REQ-569 — the catalogue of kinds of work, version 0.1.

The nine entries from the plan's Part 6 render as process bodies in the Gate 2
shape (DEC-1060): steps carry the ordered phase segments, triggers carry at
least three recognition phrases, every segment names a lifecycle domain, and
a segment whose profile does not yet exist names its planned area and is
marked pending. Written to a store they read back as nine catalogue entries.
"""

from __future__ import annotations

import json

from crmbuilder_v2 import kind_of_work_catalogue as kw
from crmbuilder_v2.access.repositories import session_opening as so

_SUMMARY = "s" * 200


def test_nine_entries_in_plan_order_with_phrases_and_segments():
    bodies = kw.entries_as_process_bodies()
    assert len(bodies) == 9
    assert bodies[0]["process_name"] == "Start working with a new organisation"
    assert bodies[-1]["process_name"] == "Ask a question about the system or its records"
    for body in bodies:
        entry = so.parse_catalogue_entry({**body, "process_identifier": "PROC-000"})
        assert entry is not None, body["process_name"]
        assert entry["catalogue_version"] == so.CATALOGUE_VERSION
        assert len(entry["trigger_phrases"]) >= 3, body["process_name"]
        if body["process_name"].startswith("Ask a question"):
            assert entry["segments"] == []
            continue
        assert len(entry["segments"]) >= 1, body["process_name"]
        for seg in entry["segments"]:
            assert seg["domain"] in kw.DOM.values()
            assert seg["status"] in so.SEGMENT_STATUSES
            assert seg["label"] and seg["area"]
            if seg["status"] == "active":
                assert seg["profile"] in (kw.REQUIREMENTS_INTERVIEWER, kw.RELEASE_OPERATOR)
            else:
                assert seg["profile"] is None
        assert [s["position"] for s in entry["segments"]] == list(range(1, len(entry["segments"]) + 1))
    # The entry point is the first segment's domain (DEC-1060).
    for body in bodies:
        entry = so.parse_catalogue_entry({**body, "process_identifier": "PROC-000"})
        if entry["segments"]:
            assert body["process_domain_identifier"] == entry["segments"][0]["domain"]


def test_define_new_business_processes_route():
    body = next(b for b in kw.entries_as_process_bodies() if b["process_name"] == "Define new business processes")
    entry = so.parse_catalogue_entry({**body, "process_identifier": "PROC-000"})
    assert [(s["label"], s["status"]) for s in entry["segments"]] == [
        ("Requirements Interviewer", "active"), ("Solution Designer", "pending"),
    ]
    assert entry["segments"][0]["profile"] == "AGP-039"
    assert "define new business processes" in json.loads(body["process_triggers"])


def test_every_plan_example_classifies_to_its_entry():
    entries = [
        so.parse_catalogue_entry({**b, "process_identifier": f"PROC-{i:03d}"})
        for i, b in enumerate(kw.entries_as_process_bodies(), start=1)
    ]
    cases = {
        "define new business processes": "Define new business processes",
        "I want to add a field to the intake screen": "Add or change a field or screen in an existing application",
        "upgrade the platform to the latest version": "Upgrade the platform to the latest version",
        "the login page is not working": "Fix something that is not working",
        "what is the status of REQ-568": "Ask a question about the system or its records",
    }
    for answer, expected in cases.items():
        result = so.classify(answer, entries)
        assert result["entry"] is not None and result["entry"]["name"] == expected, (answer, result["ranked"][:2])
    assert so.classify("teach the mentoring app to send birthday cards", entries)["entry"] is None


def test_write_catalogue_over_the_api(client):
    """Written through the REST API, the nine entries read back as the catalogue."""
    for key, ident in kw.DOM.items():
        r = client.post("/domains", json={"domain_identifier": ident, "domain_name": key,
                                          "domain_purpose": "p", "domain_description": "d"})
        assert r.status_code == 201, r.text
    for pid, area in ((kw.REQUIREMENTS_INTERVIEWER, "requirements-capture"), (kw.RELEASE_OPERATOR, "release-to-production")):
        r = client.post("/agent-profiles", json={"identifier": pid, "area": area, "tier": "orchestrator",
                                                 "description": area, "scope": "system"})
        assert r.status_code == 201, r.text
    base = str(client.base_url)
    calls = []

    def fake_call(_base, _token, _eng, method, path, body=None):
        calls.append((method, path))
        r = getattr(client, method.lower())(path, json=body) if body is not None else client.get(path)
        assert r.status_code in (200, 201), (method, path, r.text)
        return r.json()["data"]

    original = kw._call
    kw._call = fake_call
    try:
        rows = kw.write_catalogue(base, "")
        assert [a for a, _, _ in rows] == ["created"] * 9
        again = kw.write_catalogue(base, "")
        assert [a for a, _, _ in again] == ["refreshed"] * 9
    finally:
        kw._call = original
    opening = client.get("/sessions/opening").json()["data"]
    assert len(opening["catalogue"]) == 9
    assert len(client.get("/processes").json()["data"]) == 9
    d = client.post("/projects", json={"project_name": "P", "project_purpose": "p", "project_description": "d",
                                       "project_status": "in_flight"})
    assert d.status_code == 201
    opened = client.post("/sessions/open", json={"opening_answer": "define new business processes"}).json()["data"]
    assert opened["kind_of_work_name"] == "Define new business processes"
    assert opened["contract"]["segment_profile_id"] == kw.REQUIREMENTS_INTERVIEWER
