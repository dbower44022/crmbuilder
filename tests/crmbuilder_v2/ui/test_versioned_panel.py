"""Tests for the VersionedPanel base class.

Exercises the slice-E machinery shared by the Charter and Status
panels: synthetic ``_current_marker`` field, payload-as-form rendering,
and auto-select of the current version on first load.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.base.versioned_panel import VersionedPanel
from PySide6.QtWidgets import QFormLayout, QLabel, QPlainTextEdit


class _FakeVersionedPanel(VersionedPanel):
    """Minimal subclass driven by an injected fetch impl (no client calls)."""

    def __init__(self, fetch_impl, parent=None):
        self._fetch_impl = fetch_impl
        super().__init__(client=None, parent=parent)

    def entity_title(self) -> str:
        return "Versioned"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._fetch_impl()


def _records():
    return [
        {
            "version": 2,
            "is_current": True,
            "created_at": "2026-05-01T12:00:00",
            "payload": {"scope": "v2 scope"},
        },
        {
            "version": 1,
            "is_current": False,
            "created_at": "2026-04-01T12:00:00",
            "payload": {"scope": "v1 scope"},
        },
    ]


def test_current_marker_is_set_correctly(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    assert panel._records[0]["_current_marker"] == "✓"
    assert panel._records[1]["_current_marker"] == ""


def test_render_detail_renders_payload_as_form(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    payload = {
        "name": "short",
        "long_text": "x" * 200,
        "items": [1, 2, 3],
        "config": {"a": 1},
    }
    rendered = panel._render_payload(payload)
    forms = rendered.findChildren(QFormLayout)
    assert len(forms) == 1
    form = forms[0]
    assert form.rowCount() == 4

    # Long string and structured values render as QPlainTextEdit;
    # short string renders as QLabel (the row's field widget).
    long_widgets = rendered.findChildren(QPlainTextEdit)
    # 3 long widgets: long_text, items, config.
    assert len(long_widgets) == 3

    # Assert the short string field is a QLabel containing the value.
    name_field = form.itemAt(0, QFormLayout.ItemRole.FieldRole).widget()
    assert isinstance(name_field, QLabel)
    assert "short" in name_field.text()


def test_default_selection_on_first_load_is_current_version(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._table.currentIndex().isValid()
        and panel._table.currentIndex().row() == 0,
        timeout=2000,
    )

    selected_record = panel._records[panel._table.currentIndex().row()]
    assert selected_record.get("is_current") is True
    assert panel._initial_select_done is True


def test_empty_payload_renders_placeholder(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    rendered = panel._render_payload({})
    labels = rendered.findChildren(QLabel)
    assert any("(empty payload)" in label.text() for label in labels)
