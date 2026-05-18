"""Tests for the master/detail base panel."""

from __future__ import annotations

from typing import Any

import pytest
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageConnectionError,
)
from PySide6.QtWidgets import QLabel, QSplitter, QWidget


class _FakePanel(ListDetailPanel):
    """Minimal subclass driving the base via injected fetch behavior."""

    def __init__(
        self,
        fetch_impl,
        columns=None,
        parent=None,
        extras_impl=None,
        render_impl=None,
    ):
        self._fetch_impl = fetch_impl
        self._extras_impl = extras_impl
        self._render_impl = render_impl
        self._columns = columns or [
            ColumnSpec(field="identifier", title="ID", width=80),
            ColumnSpec(field="title", title="Title"),
        ]
        # Capture rendered details for assertions.
        self.rendered_calls: list[tuple[dict[str, Any], dict[str, Any]]] = []
        super().__init__(client=None, parent=parent)  # client unused via _fetch_impl

    def entity_title(self) -> str:
        return "Fakes"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._fetch_impl()

    def list_columns(self) -> list[ColumnSpec]:
        return self._columns

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        if self._extras_impl is None:
            return {}
        return self._extras_impl(record)

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        self.rendered_calls.append((dict(record), dict(extras)))
        if self._render_impl is not None:
            return self._render_impl(record, extras)
        label = QLabel(record.get("title", ""))
        return label


def test_construction_builds_layout(qapp, qtbot):
    panel = _FakePanel(fetch_impl=lambda: [])
    qtbot.addWidget(panel)

    # Table model exists; toolbar exposes refresh button + status label.
    # v0.6 slice D: refresh is an icon-only button (Lucide rotate-ccw)
    # so it carries no visible text — verify via the tooltip and
    # buttonCategory property instead.
    assert panel._model is not None
    assert panel._refresh_button.toolTip() == "Refresh"
    assert panel._refresh_button.property("buttonCategory") == "icon-only"
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


# ----------------------------------------------------------------------
# Slice D additions: fetch_detail_extras, navigation, select-by-id
# ----------------------------------------------------------------------


def _populate(panel, records, qtbot):
    """Refresh and wait until records land in the model."""
    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._model.rowCount() == len(records), timeout=2000
    )


def test_fetch_detail_extras_runs_in_worker_and_feeds_render(qapp, qtbot):
    records = [{"identifier": "DEC-001", "title": "First"}]
    extras = {"references": [{"target_type": "session", "target_id": "SES-1"}]}

    extras_calls: list[dict[str, Any]] = []

    def extras_impl(record):
        extras_calls.append(record)
        return extras

    panel = _FakePanel(
        fetch_impl=lambda: records,
        extras_impl=extras_impl,
    )
    qtbot.addWidget(panel)
    _populate(panel, records, qtbot)

    panel._select_row(0)
    qtbot.waitUntil(lambda: len(panel.rendered_calls) >= 1, timeout=2000)

    assert extras_calls and extras_calls[0]["identifier"] == "DEC-001"
    rendered_record, rendered_extras = panel.rendered_calls[-1]
    assert rendered_record == records[0]
    assert rendered_extras == extras


def test_fetch_detail_extras_connection_error_emits_signal(qapp, qtbot):
    records = [{"identifier": "DEC-001", "title": "First"}]

    def extras_impl(_record):
        raise StorageConnectionError("unreachable")

    panel = _FakePanel(fetch_impl=lambda: records, extras_impl=extras_impl)
    qtbot.addWidget(panel)
    _populate(panel, records, qtbot)

    with qtbot.waitSignal(panel.connection_lost, timeout=2000) as blocker:
        panel._select_row(0)
    assert "unreachable" in blocker.args[0]


def test_fetch_detail_extras_domain_error_renders_with_empty_extras(
    qapp, qtbot
):
    records = [{"identifier": "DEC-001", "title": "First"}]

    def extras_impl(_record):
        raise NotFoundError(errors=[], message="missing references")

    panel = _FakePanel(fetch_impl=lambda: records, extras_impl=extras_impl)
    qtbot.addWidget(panel)
    _populate(panel, records, qtbot)

    panel._select_row(0)
    qtbot.waitUntil(lambda: len(panel.rendered_calls) >= 1, timeout=2000)

    rendered_record, rendered_extras = panel.rendered_calls[-1]
    assert rendered_record == records[0]
    assert rendered_extras == {}

    # The detail pane should now contain a wrapper widget with an
    # inline error indicator above the rendered detail.
    current = panel._detail_stack.currentWidget()
    indicators = current.findChildren(QLabel, "detail_extras_error")
    assert indicators, "expected a detail_extras_error indicator label"
    assert "missing references" in indicators[0].text()


def test_emit_link_navigation_parses_href(qapp, qtbot):
    panel = _FakePanel(fetch_impl=lambda: [])
    qtbot.addWidget(panel)

    received: list[tuple[str, str]] = []
    panel.navigate_requested.connect(
        lambda entity_type, identifier: received.append(
            (entity_type, identifier)
        )
    )

    panel._emit_link_navigation("session:SES-004")
    panel._emit_link_navigation("decision:DEC-018")
    panel._emit_link_navigation("malformed-no-colon")
    panel._emit_link_navigation(":missing-entity-type")
    panel._emit_link_navigation("missing-identifier:")

    assert received == [
        ("session", "SES-004"),
        ("decision", "DEC-018"),
    ]


def test_select_record_by_identifier_finds_loaded_row(qapp, qtbot):
    records = [
        {"identifier": "DEC-001", "title": "First"},
        {"identifier": "DEC-002", "title": "Second"},
    ]
    panel = _FakePanel(fetch_impl=lambda: records)
    qtbot.addWidget(panel)
    _populate(panel, records, qtbot)

    found = panel.select_record_by_identifier("DEC-002")
    assert found is True
    selected = panel._table.currentIndex()
    assert selected.isValid()
    assert selected.row() == 1
    # Drain the detail-extras worker triggered by the selection.
    qtbot.waitUntil(lambda: len(panel.rendered_calls) >= 1, timeout=2000)


class _ListOnlyFakePanel(_FakePanel):
    """Subclass that opts out of the detail pane via ``_has_detail_pane``."""

    _has_detail_pane = False


def test_list_only_panel_renders_without_detail_pane(qapp, qtbot):
    records = [{"identifier": "REF-001", "title": "ref"}]
    panel = _ListOnlyFakePanel(fetch_impl=lambda: records)
    qtbot.addWidget(panel)

    # No splitter exists in a list-only layout.
    splitters = panel.findChildren(QSplitter)
    assert splitters == []
    # The detail-stack helper attribute is None.
    assert panel._detail_stack is None
    assert panel._empty_detail is None
    assert panel._loading_detail is None

    # Selecting a row does not invoke the detail-extras flow.
    _populate(panel, records, qtbot)
    panel._select_row(0)
    qtbot.wait(50)
    assert panel.rendered_calls == []


def test_select_record_by_identifier_pre_refresh_triggers_fetch_and_selects(
    qapp, qtbot
):
    records = [
        {"identifier": "DEC-001", "title": "First"},
        {"identifier": "DEC-007", "title": "Seventh"},
    ]
    panel = _FakePanel(fetch_impl=lambda: records)
    qtbot.addWidget(panel)
    # Note: no _populate() call — we exercise the pre-refresh path.

    found = panel.select_record_by_identifier("DEC-007")
    assert found is False
    assert panel._pending_select_identifier == "DEC-007"

    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)
    qtbot.waitUntil(
        lambda: panel._table.currentIndex().isValid()
        and panel._table.currentIndex().row() == 1,
        timeout=2000,
    )
    # The pending identifier is cleared once consumed.
    assert panel._pending_select_identifier is None
    # Drain the detail-extras worker triggered by the selection.
    qtbot.waitUntil(lambda: len(panel.rendered_calls) >= 1, timeout=2000)
