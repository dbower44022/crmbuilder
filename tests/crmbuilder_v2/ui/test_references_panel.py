"""Tests for the ReferencesPanel filter and click-navigation behavior."""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.panels.references import ReferencesPanel


def _refs() -> list[dict[str, Any]]:
    return [
        {
            "source_type": "session",
            "source_id": "SES-004",
            "target_type": "decision",
            "target_id": "DEC-018",
            "relationship": "decided_in",
        },
        {
            "source_type": "decision",
            "source_id": "DEC-018",
            "target_type": "decision",
            "target_id": "DEC-001",
            "relationship": "supersedes",
        },
        {
            "source_type": "session",
            "source_id": "SES-005",
            "target_type": "topic",
            "target_id": "TOP-1",
            "relationship": "discusses",
        },
    ]


class _FakeClient:
    def __init__(self, records):
        self._records = list(records)

    def list_references(self):
        return list(self._records)


def _build_panel(qtbot, records):
    panel = ReferencesPanel(client=_FakeClient(records))
    qtbot.addWidget(panel)
    return panel


def _refresh(panel, qtbot, expected_count):
    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._model.rowCount() == expected_count, timeout=2000
    )


def test_filters_default_to_all_show_all_rows(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)
    assert panel._model.rowCount() == 3


def test_source_filter_narrows_rows(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)

    # Set source filter to "session" — should leave only session-source rows.
    index = panel._source_filter.findText("session")
    assert index >= 0
    panel._source_filter.setCurrentIndex(index)

    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)
    for r in panel._records:
        assert r["source_type"] == "session"


def test_target_filter_narrows_rows(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)

    index = panel._target_filter.findText("decision")
    assert index >= 0
    panel._target_filter.setCurrentIndex(index)

    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)
    for r in panel._records:
        assert r["target_type"] == "decision"


def test_source_cell_click_emits_navigate_requested(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)

    received: list[tuple[str, str]] = []
    panel.navigate_requested.connect(
        lambda entity_type, identifier: received.append(
            (entity_type, identifier)
        )
    )

    # Click the Source cell of row 0 (column 0).
    src_index = panel._model.index(0, 0)
    panel._on_cell_clicked(src_index)

    assert received == [("session", "SES-004")]


def test_target_cell_click_emits_navigate_requested(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)

    received: list[tuple[str, str]] = []
    panel.navigate_requested.connect(
        lambda entity_type, identifier: received.append(
            (entity_type, identifier)
        )
    )

    # Click the Target cell of row 0 (column 2).
    target_index = panel._model.index(0, 2)
    panel._on_cell_clicked(target_index)

    assert received == [("decision", "DEC-018")]


def test_relationship_cell_click_does_not_navigate(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)

    received: list[tuple[str, str]] = []
    panel.navigate_requested.connect(
        lambda entity_type, identifier: received.append(
            (entity_type, identifier)
        )
    )

    # Column 1 is "relationship" — non-navigable.
    rel_index = panel._model.index(0, 1)
    panel._on_cell_clicked(rel_index)

    assert received == []


def test_source_target_display_fields_are_set(qapp, qtbot):
    panel = _build_panel(qtbot, _refs())
    _refresh(panel, qtbot, expected_count=3)

    assert panel._records[0]["_source_display"] == "session:SES-004"
    assert panel._records[0]["_target_display"] == "decision:DEC-018"


def test_references_panel_right_click_invokes_context_menu_factory(
    qtbot, client_stub
):
    """v0.3 slice B: right-click on the master view calls _build_context_menu."""
    from unittest.mock import patch

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu

    panel = ReferencesPanel(client=client_stub)
    qtbot.addWidget(panel)
    # Use return_value=QMenu() so the slot's blocking menu.exec() branch
    # (taken when the factory returns a non-empty menu) is skipped — the
    # smoke test only needs to confirm the factory is invoked.
    empty_menu = QMenu(panel)
    with patch.object(
        panel, "_build_context_menu", return_value=empty_menu
    ) as spy:
        panel._master_view.customContextMenuRequested.emit(QPoint(10, 10))
        assert spy.called
