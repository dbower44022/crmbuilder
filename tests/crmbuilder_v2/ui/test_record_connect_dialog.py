"""Tests for RecordConnectDialog — the record-side connection form
(REQ-563 / PI-464, DEC-1042, DEC-1043).

From a known source record the form never asks for the source, offers
only the kinds allowed from that record's type, lists eligible targets
by name with tick boxes, and creates one reference per ticked target on
one save. Already-connected targets are locked; a partial failure keeps
the dialog open with the created rows locked.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from crmbuilder_v2.ui.dialogs.record_connect import RecordConnectDialog
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from .conftest import build_client, envelope_ok

_ENTITIES = [
    {"entity_identifier": "ENT-001", "entity_name": "Contact"},
    {"entity_identifier": "ENT-002", "entity_name": "Account"},
    {"entity_identifier": "ENT-003", "entity_name": "Session"},
]
_PERSONAS = [
    {"persona_identifier": "PER-001", "persona_name": "Mentor coordinator"},
]


def _handler(captured: list[dict[str, Any]], *, fail_targets: set[str] = frozenset()):
    def handler(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if method == "GET" and path == "/entities":
            return httpx.Response(200, json=envelope_ok(_ENTITIES))
        if method == "GET" and path == "/personas":
            return httpx.Response(200, json=envelope_ok(_PERSONAS))
        if method == "GET":
            return httpx.Response(200, json=envelope_ok([]))
        if method == "POST" and path == "/references":
            body = json.loads(request.read())
            if body["target_id"] in fail_targets:
                return httpx.Response(
                    409,
                    json={
                        "data": None,
                        "meta": {},
                        "errors": [{"code": "conflict", "message": "duplicate tuple"}],
                    },
                )
            captured.append(body)
            return httpx.Response(201, json=envelope_ok({"id": 1, **body}))
        return httpx.Response(
            404,
            json={"data": None, "meta": {}, "errors": [{"code": "not_found"}]},
        )

    return handler


def _make(qtbot, *, existing=None, fail_targets=frozenset()):
    captured: list[dict[str, Any]] = []
    client = build_client(_handler(captured, fail_targets=fail_targets))
    dialog = RecordConnectDialog(
        client, source_type="process", source_id="PROC-001", existing=existing
    )
    qtbot.addWidget(dialog)
    return dialog, captured


def _items(dialog):
    return [dialog._list.item(i) for i in range(dialog._list.count())]


def test_form_never_shows_source_fields(qapp, qtbot):
    dialog, _ = _make(qtbot)
    names = {
        w.objectName() for w in dialog.findChildren(object) if hasattr(w, "objectName")
    }
    assert not any("source" in n for n in names)
    assert "PROC-001" in dialog.windowTitle()


def test_kinds_offered_are_only_those_allowed_from_a_process(qapp, qtbot):
    dialog, _ = _make(qtbot)
    kinds = [dialog._kind_combo.itemText(i) for i in range(dialog._kind_combo.count())]
    assert "process_touches_entity" in kinds
    assert "process_performed_by_persona" in kinds
    assert "requirement_approved_by_decision" not in kinds
    assert "field_belongs_to_entity" not in kinds
    assert dialog._kind_combo.currentIndex() == -1


def test_kind_derives_target_type_and_lists_records_by_name(qapp, qtbot):
    dialog, _ = _make(qtbot)
    dialog._kind_combo.setCurrentText("process_touches_entity")
    assert dialog.target_type() == "entity"
    texts = [item.text() for item in _items(dialog)]
    assert texts == ["ENT-001 — Contact", "ENT-002 — Account", "ENT-003 — Session"]
    assert all(item.checkState() == Qt.CheckState.Unchecked for item in _items(dialog))


def test_ticking_several_and_saving_creates_one_reference_each(qapp, qtbot):
    dialog, captured = _make(qtbot)
    dialog._kind_combo.setCurrentText("process_touches_entity")
    items = _items(dialog)
    items[0].setCheckState(Qt.CheckState.Checked)
    items[2].setCheckState(Qt.CheckState.Checked)
    assert dialog.ticked_identifiers() == ["ENT-001", "ENT-003"]
    assert "2 references" in dialog._summary.text()
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert [b["target_id"] for b in captured] == ["ENT-001", "ENT-003"]
    assert all(
        b["source_type"] == "process"
        and b["source_id"] == "PROC-001"
        and b["target_type"] == "entity"
        and b["relationship"] == "process_touches_entity"
        for b in captured
    )
    assert len(dialog.created_references()) == 2


def test_already_connected_targets_are_locked_and_not_resent(qapp, qtbot):
    dialog, captured = _make(
        qtbot, existing={("process_touches_entity", "entity", "ENT-002")}
    )
    dialog._kind_combo.setCurrentText("process_touches_entity")
    locked = _items(dialog)[1]
    assert locked.checkState() == Qt.CheckState.Checked
    assert not (locked.flags() & Qt.ItemFlag.ItemIsEnabled)
    assert "already connected" in locked.text()
    assert dialog.ticked_identifiers() == []
    _items(dialog)[0].setCheckState(Qt.CheckState.Checked)
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert [b["target_id"] for b in captured] == ["ENT-001"]


def test_save_with_nothing_ticked_does_not_post(qapp, qtbot):
    dialog, captured = _make(qtbot)
    dialog._kind_combo.setCurrentText("process_touches_entity")
    dialog._on_save_clicked()
    qtbot.wait(100)
    assert captured == []
    assert dialog._save_btn.isEnabled()


def test_filter_hides_non_matching_rows(qapp, qtbot):
    dialog, _ = _make(qtbot)
    dialog._kind_combo.setCurrentText("process_touches_entity")
    dialog._filter.setText("acc")
    hidden = [item.isHidden() for item in _items(dialog)]
    assert hidden == [True, False, True]


def test_persona_kind_lists_personas(qapp, qtbot):
    dialog, _ = _make(qtbot)
    dialog._kind_combo.setCurrentText("process_performed_by_persona")
    assert dialog.target_type() == "persona"
    assert [item.text() for item in _items(dialog)] == ["PER-001 — Mentor coordinator"]


def test_partial_failure_keeps_dialog_open_and_locks_created(qapp, qtbot, monkeypatch):
    shown: list[tuple[str, str]] = []

    class _StubError:
        def __init__(self, title, message, *_a, **_kw):
            shown.append((title, message))

        def exec(self):  # noqa: A003
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.record_connect.ErrorDialog", _StubError
    )
    dialog, captured = _make(qtbot, fail_targets={"ENT-002"})
    dialog._kind_combo.setCurrentText("process_touches_entity")
    for item in _items(dialog):
        item.setCheckState(Qt.CheckState.Checked)
    dialog._on_save_clicked()
    qtbot.waitUntil(lambda: bool(shown), timeout=2000)
    assert [b["target_id"] for b in captured] == ["ENT-001", "ENT-003"]
    assert "Created 2 of 3" in shown[0][1]
    assert dialog._save_btn.isEnabled()
    assert dialog.result() == 0  # still open
    # Created rows are now locked; the failed one is retryable.
    states = [bool(item.flags() & Qt.ItemFlag.ItemIsEnabled) for item in _items(dialog)]
    assert states == [False, True, False]
    assert len(dialog.created_references()) == 2


def test_references_section_add_opens_record_side_form(qapp, qtbot, monkeypatch):
    """The detail-view affordance opens the record-side form with the
    section's record as source and its outbound keys locked."""
    opened: list[dict[str, Any]] = []

    class _StubDialog:
        def __init__(self, client, *, source_type, source_id, existing, parent=None):
            opened.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "existing": set(existing),
                }
            )

        def exec(self):  # noqa: A003
            return 0

        def created_references(self):
            return []

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.record_connect.RecordConnectDialog", _StubDialog
    )
    client = build_client(_handler([]))
    section = ReferencesSection(
        "process",
        "PROC-001",
        {
            "as_source": [
                {
                    "source_type": "process",
                    "source_id": "PROC-001",
                    "target_type": "entity",
                    "target_id": "ENT-002",
                    "relationship": "process_touches_entity",
                }
            ],
            "as_target": [],
        },
        client=client,
    )
    qtbot.addWidget(section)
    add_btn = section.findChild(QPushButton, "references_section_add_button")
    assert add_btn is not None
    add_btn.click()
    assert opened == [
        {
            "source_type": "process",
            "source_id": "PROC-001",
            "existing": {("process_touches_entity", "entity", "ENT-002")},
        }
    ]
