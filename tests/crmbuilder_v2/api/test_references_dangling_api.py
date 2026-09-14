"""GET /references/dangling — the census endpoint (PI-502, REQ-598)."""

from __future__ import annotations


def test_census_endpoint_lists_and_leaves_references_unchanged(client):
    dec = client.post("/decisions", json={
        "title": "A ruling", "decision_date": "2026-09-14", "status": "Active",
        "executive_summary": "s" * 200}).json()["data"]["identifier"]
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import Reference

    with session_scope() as s:
        s.add(Reference(source_type="decision", source_id=dec, target_type="domain",
                        target_id="DOM-404", relationship_kind="is_about",
                        reference_identifier="REF-0001"))
    before = client.get("/references").json()["data"]
    found = client.get("/references/dangling").json()["data"]
    after = client.get("/references").json()["data"]
    assert before == after
    assert [(f["target_id"], f["missing"]) for f in found] == [("DOM-404", ["target"])]
