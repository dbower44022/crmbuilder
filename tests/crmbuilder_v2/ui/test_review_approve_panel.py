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
from crmbuilder_v2.ui.panels.review import ReviewPanel, _ApproveDialog
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QAbstractItemView, QDialog, QPushButton

_EXEC_SUMMARY = "Change decision for the requirements-review end-to-end test. " * 4


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


def _requirement(client, rid) -> dict:
    return client._request("GET", f"/requirements/{rid}")


def _reopen(client, rid) -> None:
    """Drive a confirmed requirement back to candidate/needs_review through the
    governed change-decision path (``requirement_changed_by_decision`` edge), the
    same regression the post-reopen re-approval test exercises (REQ-249)."""
    did = client._request("POST", "/decisions", json_body={
        "title": f"Change {rid}",
        "decision_date": "2026-06-18",
        "status": "Active",
        "executive_summary": _EXEC_SUMMARY,
    })["identifier"]
    _edge(client, rid, "requirement_changed_by_decision", "decision", did)


def _approving_decision(client, rid) -> dict | None:
    """The governed approving decision recorded for ``rid``, via its
    ``requirement_approved_by_decision`` edge (None if none recorded yet)."""
    edges = client._request(
        "GET",
        f"/references?source_id={rid}"
        "&relationship_kind=requirement_approved_by_decision",
    )
    if not edges:
        return None
    return client._request("GET", f"/decisions/{edges[-1]['target_id']}")


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


def test_right_click_offers_approve_action_wired_to_handler(
    review_client, qtbot, monkeypatch
):
    """The right-click context menu on a selected row offers Approve (REQ-251),
    wired to the same handler the upper-right button uses."""
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._fill_approval([
        {"identifier": "REQ-100", "name": "A", "has_provenance": True, "has_topic": True},
    ])
    panel._approval_tree.selectAll()

    called: list[bool] = []
    monkeypatch.setattr(panel, "_on_approve_selected", lambda: called.append(True))

    menu = panel._build_approval_context_menu()
    assert menu is not None
    actions = [a for a in menu.actions() if not a.isSeparator()]
    assert [a.text() for a in actions] == ["Approve selected…"]
    actions[0].trigger()
    assert called == [True]


def test_right_click_with_no_selection_builds_no_menu(review_client, qtbot):
    """With nothing selected the right-click is a no-op — no menu is built."""
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._fill_approval([
        {"identifier": "REQ-100", "name": "A", "has_provenance": True, "has_topic": True},
    ])
    panel._approval_tree.clearSelection()
    assert panel._build_approval_context_menu() is None


def test_multiselect_single_action_confirms_all_via_panel(
    review_client, qtbot, monkeypatch
):
    """Multi-select + a single Approve action confirms every selected candidate
    (REQ-251). Drives the real affordance end-to-end: populate the queue, select
    all, then ``_on_approve_selected`` — the modal auto-accepted — flows the whole
    selection through one governed approval pass."""
    a = _rooted(review_client, "First of two")
    b = _rooted(review_client, "Second of two")
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._fill_approval([
        {"identifier": a, "name": "First of two", "has_provenance": True, "has_topic": True},
        {"identifier": b, "name": "Second of two", "has_provenance": True, "has_topic": True},
    ])
    panel._approval_tree.selectAll()
    assert panel._selected_approval_ids() == [a, b]

    # Auto-accept the modal so the single action runs unattended.
    monkeypatch.setattr(_ApproveDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(_ApproveDialog, "values", lambda self: ("Doug Bower", None))

    panel._on_approve_selected()
    qtbot.waitUntil(lambda: "2 approved" in panel._status_label.text(), timeout=3000)
    assert _requirement(review_client, a)["requirement_status"] == "confirmed"
    assert _requirement(review_client, b)["requirement_status"] == "confirmed"


def test_panel_records_governed_decision_naming_reviewer(review_client, qtbot):
    """Approving in the panel records a governed approving decision that names the
    reviewer and folds in their note, linked by a
    ``requirement_approved_by_decision`` edge — confirmation is *only* via that
    governed path, never a status edit (REQ-251)."""
    rid = _rooted(review_client, "Recorded through the panel")
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._submit_approvals([rid], "Dana Reviewer", "Confirmed scope with the PM.")
    qtbot.waitUntil(lambda: "approved" in panel._status_label.text(), timeout=3000)

    dec = _approving_decision(review_client, rid)
    assert dec is not None
    assert dec["status"] == "Active"
    assert "Dana Reviewer" in dec["context"]
    assert "Dana Reviewer" in dec["executive_summary"]
    assert rid in dec["context"]
    assert "Confirmed scope with the PM." in dec["context"]


def test_panel_mixed_batch_summary_and_gate_failure(review_client, qtbot, monkeypatch):
    """A mixed batch through the panel: the rooted candidate confirms, the unrooted
    one fails its topic gate and stays candidate, and the status summary truthfully
    reports both ('1 approved, 1 failed'). One failure neither blocks nor rolls back
    the other (REQ-251)."""
    good = _rooted(review_client, "Good in batch")
    bad = _make(review_client, "Bad in batch")
    _edge(review_client, bad, "requirement_defined_in_conversation", "conversation", "CNV-001")
    # Don't pop the modal failure box during the test.
    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.review.CopyableMessageBox.warning",
        lambda *a, **k: None,
    )
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._submit_approvals([good, bad], "Doug Bower", None)
    qtbot.waitUntil(lambda: "1 approved" in panel._status_label.text(), timeout=3000)
    assert "1 failed" in panel._status_label.text()
    assert _requirement(review_client, good)["requirement_status"] == "confirmed"
    assert _requirement(review_client, bad)["requirement_status"] == "candidate"


def test_post_reopen_approval_returns_review_state_to_current(review_client, qtbot):
    """REQ-249 — the review_state lifecycle end-to-end through the panel:
    approve → confirmed/current, a governed change-decision reopens it to
    candidate/needs_review, then a second panel approval reconfirms it and returns
    review_state to 'current' (no lingering NEEDS REVIEW flag)."""
    rid = _rooted(review_client, "Reopen then re-approve")
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)

    # First approval: confirmed and review_state current.
    panel._submit_approvals([rid], "Doug Bower", None)
    qtbot.waitUntil(
        lambda: _requirement(review_client, rid)["requirement_status"] == "confirmed",
        timeout=3000,
    )
    assert _requirement(review_client, rid)["requirement_review_state"] == "current"

    # A change decision reopens it: back to candidate and flagged needs_review.
    _reopen(review_client, rid)
    after_reopen = _requirement(review_client, rid)
    assert after_reopen["requirement_status"] == "candidate"
    assert after_reopen["requirement_review_state"] == "needs_review"

    # Second panel approval reconfirms it and clears the needs_review flag.
    panel._submit_approvals([rid], "Doug Bower", None)
    qtbot.waitUntil(
        lambda: _requirement(review_client, rid)["requirement_review_state"] == "current",
        timeout=3000,
    )
    assert _requirement(review_client, rid)["requirement_status"] == "confirmed"
