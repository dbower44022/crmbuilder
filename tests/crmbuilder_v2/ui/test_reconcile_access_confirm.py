"""The access-publish confirmation in the reconcile grid — PI-417 (REQ-521)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.ui.panels import reconcile_grid as rg
from crmbuilder_v2.ui.panels.reconcile_grid import (
    AccessPublishDeclined,
    ReconcileGridPanel,
)
from PySide6.QtWidgets import QMessageBox

from .conftest import build_client
from .test_reconcile_grid import _handler

_YES = QMessageBox.StandardButton.Yes
_CANCEL = QMessageBox.StandardButton.Cancel

_WIDENING = {
    "summary": "Publishing role Mentor Role to INST-001 changes 1 access setting(s).",
    "changes": [{"description": "Mentor Role: Account.read own → all"}],
    "removals": [],
    "removes_access": False,
    "requires_confirmation": True,
}
_REMOVING = {
    "summary": "Publishing role Mentor Role to INST-001 changes 1 access setting(s).",
    "changes": [{"description": "Mentor Role: Account.read all → team"}],
    "removals": [{"description": "Mentor Role: Account.read all → team"}],
    "removes_access": True,
    "requires_confirmation": True,
}


class _AccessClient:
    """Records the publish call and serves a canned assessment."""

    def __init__(self, inner, assessment):
        self._inner = inner
        self._assessment = assessment
        self.publishes: list[dict] = []
        self.assessed: list[dict] = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def reconcile_assess_access_publish(self, **kw):
        self.assessed.append(kw)
        return self._assessment

    def reconcile_publish(self, **kw):
        self.publishes.append(kw)
        return {"transaction": {"id": 7}}


def _panel(qtbot, assessment):
    client = _AccessClient(build_client(_handler), assessment)
    panel = ReconcileGridPanel(client)
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    return panel, client


def _answers(monkeypatch, *replies):
    """Answer the confirmation boxes in order, recording the text shown."""
    seen: list[str] = []
    queue = list(replies)

    def _reply(parent, title, text, *args, **kwargs):
        seen.append(f"{title}\n{text}")
        return queue.pop(0)

    monkeypatch.setattr(rg.CopyableMessageBox, "question", staticmethod(_reply))
    monkeypatch.setattr(rg.CopyableMessageBox, "warning", staticmethod(_reply))
    return seen


_ROW = {"member_type": "role", "member_identifier": "ROL-001", "attribute": None}
_OP = {"kind": "publish", "location": "instance_a"}


def test_a_widening_publish_asks_once_and_names_its_target_and_effect(
    qtbot, monkeypatch
):
    panel, client = _panel(qtbot, _WIDENING)
    seen = _answers(monkeypatch, _YES)
    panel._execute_op(_ROW, _OP)
    assert len(seen) == 1
    assert "Account.read own → all" in seen[0]
    assert client.publishes[0]["confirm_access_change"] is True
    assert client.publishes[0]["confirm_access_removal"] is False


def test_declining_the_first_question_publishes_nothing(qtbot, monkeypatch):
    panel, client = _panel(qtbot, _WIDENING)
    _answers(monkeypatch, _CANCEL)
    with pytest.raises(AccessPublishDeclined):
        panel._execute_op(_ROW, _OP)
    assert client.publishes == []


def test_a_removal_asks_a_second_separate_question(qtbot, monkeypatch):
    panel, client = _panel(qtbot, _REMOVING)
    seen = _answers(monkeypatch, _YES, _YES)
    panel._execute_op(_ROW, _OP)
    assert len(seen) == 2
    assert "removes access" in seen[1] or "removes" in seen[1].lower()
    assert "Account.read all → team" in seen[1]
    assert client.publishes[0]["confirm_access_removal"] is True


def test_agreeing_to_the_change_is_not_agreeing_to_the_removal(qtbot, monkeypatch):
    """The operator says yes to the publish and no to losing access; nothing
    is published — the removal is never applied on the strength of the first
    answer."""
    panel, client = _panel(qtbot, _REMOVING)
    _answers(monkeypatch, _YES, _CANCEL)
    with pytest.raises(AccessPublishDeclined):
        panel._execute_op(_ROW, _OP)
    assert client.publishes == []


def test_a_field_publish_is_not_put_through_the_access_gate(qtbot, monkeypatch):
    panel, client = _panel(qtbot, _REMOVING)
    seen = _answers(monkeypatch, _YES, _YES)
    panel._execute_op(
        {"member_type": "field", "member_identifier": "FLD-001", "attribute": None},
        _OP,
    )
    assert seen == []
    assert client.assessed == []
    assert client.publishes[0]["confirm_access_change"] is False
