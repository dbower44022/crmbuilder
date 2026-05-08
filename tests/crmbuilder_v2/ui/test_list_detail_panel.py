"""Tests for the master/detail base panel."""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageConnectionError,
)
from PySide6.QtWidgets import QLabel, QWidget


class _FakePanel(ListDetailPanel):
    """Minimal subclass driving the base via injected fetch behavior."""

    def __init__(self, fetch_impl, columns=None, parent=None):
        self._fetch_impl = fetch_impl
        self._columns = columns or [
            ColumnSpec(field="identifier", title="ID", width=80),
            ColumnSpec(field="title", title="Title"),
        ]
        super().__init__(client=None, parent=parent)  # client unused via _fetch_impl

    def entity_title(self) -> str:
        return "Fakes"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._fetch_impl()

    def list_columns(self) -> list[ColumnSpec]:
        return self._columns

    def render_detail(self, record: dict[str, Any]) -> QWidget:
        label = QLabel(record.get("title", ""))
        return label


def test_construction_builds_layout(qapp, qtbot):
    panel = _FakePanel(fetch_impl=lambda: [])
    qtbot.addWidget(panel)

    # Table model exists; toolbar exposes refresh button + status label.
    assert panel._model is not None
    assert panel._refresh_button.text() == "Refresh"
    assert panel._table.model() is panel._model
    assert panel._detail_stack.count() >= 1


def test_refresh_populates_table(qapp, qtbot):
    records = [
        {"identifier": "DEC-001", "title": "First"},
        {"identifier": "DEC-002", "title": "Second"},
    ]
    panel = _FakePanel(fetch_impl=lambda: records)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)
    assert panel._status_label.text() == "2 records"


def test_connection_error_promotes_signal(qapp, qtbot):
    def boom():
        raise StorageConnectionError("unreachable")

    panel = _FakePanel(fetch_impl=boom)
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.connection_lost, timeout=2000) as blocker:
        panel.refresh()
    assert blocker.args == ["unreachable"]
    qtbot.waitUntil(
        lambda: panel._status_label.text() == "Connection lost", timeout=2000
    )


def test_domain_error_stays_inline(qapp, qtbot):
    def boom():
        raise NotFoundError(errors=[], message="missing")

    panel = _FakePanel(fetch_impl=boom)
    qtbot.addWidget(panel)

    received_signals: list[str] = []
    panel.connection_lost.connect(received_signals.append)

    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._status_label.text().startswith("Error:"), timeout=2000
    )
    assert "missing" in panel._status_label.text()
    assert received_signals == []


def test_set_enabled_state_disables_then_refreshes(qapp, qtbot):
    fetch_calls = {"count": 0}

    def fetch():
        fetch_calls["count"] += 1
        return [{"identifier": "DEC-001", "title": "One"}]

    panel = _FakePanel(fetch_impl=fetch)
    qtbot.addWidget(panel)

    panel.set_enabled_state(False)
    assert panel._table.isEnabled() is False
    assert panel._toolbar_widget.isEnabled() is False

    panel.set_enabled_state(True)
    qtbot.waitUntil(lambda: fetch_calls["count"] >= 1, timeout=2000)
    assert panel._table.isEnabled() is True


@pytest.mark.parametrize(
    "long_message",
    ["x" * 200],
)
def test_long_error_message_is_truncated(qapp, qtbot, long_message):
    def boom():
        raise NotFoundError(errors=[], message=long_message)

    panel = _FakePanel(fetch_impl=boom)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._status_label.text().startswith("Error:"), timeout=2000
    )
    assert len(panel._status_label.text()) <= 80
