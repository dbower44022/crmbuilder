"""PI-229 / REQ-251 — the Requirements Review panel's Approve action.

End-to-end against a real in-memory API: the panel's multi-select Approve
records a governed approving decision per requirement and confirms each (a
rooted candidate confirms; an unrooted one fails and stays candidate, with the
reason surfaced). The reviewer completes the review IN the panel — no
hand-assembled interface calls, no status edit.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels.review import ReviewPanel
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QAbstractItemView, QPushButton


@pytest.fixture
def review_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _make(client, name) -> str:
    return client._request("POST", "/requirements", json_body={
        "requirement_name": name,
        "requirement_description": "What the system must do for its users.",
        "requirement_acceptance_summary": "Verifiable when the thing happens for a user.",
    })["requirement_identifier"]


def _edge(client, rid, rel, ttype, tgt):
    client._request("POST", "/references", json_body={
        "source_type": "requirement", "source_id": rid,
        "target_type": ttype, "target_id": tgt, "relationship": rel})


def _rooted(client, name) -> str:
    rid = _make(client, name)
    _edge(client, rid, "requirement_defined_in_conversation", "conversation", "CNV-001")
    _edge(client, rid, "requirement_belongs_to_topic", "topic", "TOP-001")
    return rid


def test_approve_button_and_multiselect_present(review_client, qtbot):
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    assert panel.findChild(QPushButton, "approve_selected_button") is not None
    assert (
        panel._approval_tree.selectionMode()
        == QAbstractItemView.SelectionMode.ExtendedSelection
    )


def test_approve_confirms_a_rooted_candidate_via_panel(review_client, qtbot):
    rid = _rooted(review_client, "Approvable via panel")
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._submit_approvals([rid], "Doug Bower", None)
    qtbot.waitUntil(lambda: "approved" in panel._status_label.text(), timeout=3000)
    rec = review_client._request("GET", f"/requirements/{rid}")
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_approved_at"] is not None


def test_approve_failure_surfaces_and_stays_candidate(review_client, qtbot, monkeypatch):
    rid = _make(review_client, "No topic via panel")
    _edge(review_client, rid, "requirement_defined_in_conversation", "conversation", "CNV-001")
    # Don't pop the modal failure box during the test.
    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.review.CopyableMessageBox.warning",
        lambda *a, **k: None,
    )
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._submit_approvals([rid], "Doug Bower", None)
    qtbot.waitUntil(lambda: "failed" in panel._status_label.text(), timeout=3000)
    assert review_client._request("GET", f"/requirements/{rid}")[
        "requirement_status"] == "candidate"


def test_selected_ids_dedupe_and_read_column_zero(review_client, qtbot):
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._fill_approval([
        {"identifier": "REQ-100", "name": "A", "has_provenance": True, "has_topic": True},
        {"identifier": "REQ-101", "name": "B", "has_provenance": True, "has_topic": False},
    ])
    panel._approval_tree.selectAll()
    assert panel._selected_approval_ids() == ["REQ-100", "REQ-101"]
