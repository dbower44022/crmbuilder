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


# ----------------------------------------------------------------------
# REQ-528 (PI-434): header-click sorting + generic filter selector
# ----------------------------------------------------------------------

_GRID_RECORDS = [
    {"identifier": "DEC-002", "title": "banana", "status": "draft"},
    {"identifier": "DEC-001", "title": "Apple", "status": "active"},
    {"identifier": "DEC-003", "title": "cherry", "status": "active"},
]

_GRID_COLUMNS = [
    ColumnSpec(field="identifier", title="ID", width=80),
    ColumnSpec(field="title", title="Title"),
    ColumnSpec(field="status", title="Status", width=80),
]


def _loaded_panel(qtbot, records=None):
    rows = records if records is not None else _GRID_RECORDS
    panel = _FakePanel(
        fetch_impl=lambda: list(rows), columns=list(_GRID_COLUMNS)
    )
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._model.rowCount() == len(rows), timeout=2000
    )
    return panel


def _column_values(panel, col):
    return [
        panel._model.data(panel._model.index(row, col))
        for row in range(panel._model.rowCount())
    ]


def test_header_sections_are_clickable(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    assert panel._table.horizontalHeader().sectionsClickable()


def test_header_click_sorts_ascending_then_descending(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    panel._on_header_section_clicked(1)
    # Case-insensitive, per the shared compare_values comparator.
    assert _column_values(panel, 1) == ["Apple", "banana", "cherry"]
    header = panel._table.horizontalHeader()
    assert header.isSortIndicatorShown()
    assert header.sortIndicatorSection() == 1
    panel._on_header_section_clicked(1)
    assert _column_values(panel, 1) == ["cherry", "banana", "Apple"]


def test_sort_preserves_selection_and_survives_refresh(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    assert panel._select_by_identifier("DEC-001")
    panel._on_header_section_clicked(0)
    # Selection follows the record to its new row.
    assert panel._currently_selected_identifier() == "DEC-001"
    assert _column_values(panel, 0) == ["DEC-001", "DEC-002", "DEC-003"]
    panel.refresh()
    qtbot.waitUntil(
        lambda: _column_values(panel, 0)
        == ["DEC-001", "DEC-002", "DEC-003"],
        timeout=2000,
    )


def test_filter_strip_lists_columns(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    combo = panel._filter_column_combo
    assert combo is not None
    titles = [combo.itemText(i) for i in range(combo.count())]
    assert titles == ["ID", "Title", "Status"]


def test_filter_selector_narrows_and_restores(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    panel._filter_column_combo.setCurrentIndex(2)  # Status
    values = [
        panel._filter_value_combo.itemText(i)
        for i in range(panel._filter_value_combo.count())
    ]
    assert values == ["All", "active", "draft"]
    panel._filter_value_combo.setCurrentText("active")
    assert panel._model.rowCount() == 2
    assert panel._status_label.text() == "2 of 3 records"
    panel._filter_value_combo.setCurrentText("All")
    assert panel._model.rowCount() == 3
    assert panel._status_label.text() == "3 records"


def test_filter_composes_with_search_and_sort(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    panel._filter_column_combo.setCurrentIndex(2)
    panel._filter_value_combo.setCurrentText("active")
    panel._on_header_section_clicked(1)
    assert _column_values(panel, 1) == ["Apple", "cherry"]
    panel._on_search_changed("cherry")
    assert _column_values(panel, 1) == ["cherry"]
    assert panel._status_label.text() == "1 of 3 records"
    panel._on_search_changed("")
    assert panel._model.rowCount() == 2


def test_filter_selection_preserved_across_refresh(qapp, qtbot):
    panel = _loaded_panel(qtbot)
    panel._filter_column_combo.setCurrentIndex(2)
    panel._filter_value_combo.setCurrentText("active")
    assert panel._model.rowCount() == 2
    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._status_label.text() == "2 of 3 records",
        timeout=2000,
    )
    assert panel._filter_value_combo.currentText() == "active"
    assert panel._model.rowCount() == 2


def test_topics_tree_opts_out_of_column_filter():
    from crmbuilder_v2.ui.panels.topics import TopicsPanel

    assert TopicsPanel._column_filter_enabled is False


# ----------------------------------------------------------------------
# REQ-534 (PI-436): control line — filter | search | ranked actions
# ----------------------------------------------------------------------

from PySide6.QtWidgets import QMenu, QPushButton  # noqa: E402


class _ActionPanel(_FakePanel):
    """Fake panel with a toolbar ``New Fake`` button and a row context menu
    carrying Edit / Delete, mirroring the real entity panels."""

    def __init__(self, *args, **kwargs):
        self.edited: list[dict] = []
        self.deleted: list[dict] = []
        self.created = 0
        super().__init__(*args, **kwargs)
        self._new_button = QPushButton("New Fake")
        self._new_button.clicked.connect(self._on_new)
        self._action_layout.addWidget(self._new_button)

    def _on_new(self):
        self.created += 1

    def _build_context_menu(self, index):
        menu = QMenu(self)
        record = self._record_at_index(index)
        if record is None:
            menu.addAction("New fake").triggered.connect(self._on_new)
            return menu
        menu.addAction("Edit").triggered.connect(
            lambda _c=False, r=record: self.edited.append(r)
        )
        menu.addAction("Delete").triggered.connect(
            lambda _c=False, r=record: self.deleted.append(r)
        )
        return menu


class _PriorityPanel(_ActionPanel):
    _action_priority = ("View", "Edit")


def _action_panel(qtbot, cls=_ActionPanel):
    panel = cls(fetch_impl=lambda: list(_GRID_RECORDS), columns=list(_GRID_COLUMNS))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 3, timeout=2000)
    return panel


def _menu_labels(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def test_control_line_order_filter_search_actions(qapp, qtbot):
    panel = _action_panel(qtbot)
    layout = panel._control_row_layout
    widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
    # filter strip | stretch | search | stretch | action cluster
    assert widgets[0] is panel._filter_strip
    assert widgets[1] is None and widgets[3] is None
    assert widgets[2] is panel._search_input
    assert widgets[-1].objectName() == "grid_action_cluster"
    # Header row still carries title/refresh/count above the control line.
    assert panel._status_label.text() == "3 records"


def test_default_ranking_is_toolbar_then_edit_then_view(qapp, qtbot):
    panel = _action_panel(qtbot)
    ranked = panel._arrange_control_actions()
    assert [label for label, _ in ranked] == ["New Fake", "Edit", "View"]
    assert not panel._new_button.isHidden()
    assert not panel._edit_button.isHidden()
    assert panel._view_button.isHidden()  # rank 3 lives in the dropdown
    assert not panel._actions_button.isHidden()


def test_action_priority_reranks(qapp, qtbot):
    panel = _action_panel(qtbot, cls=_PriorityPanel)
    ranked = panel._arrange_control_actions()
    assert [label for label, _ in ranked] == ["View", "Edit", "New Fake"]
    assert panel._new_button.isHidden()


def test_actions_dropdown_leads_with_top_two_then_all_actions(qapp, qtbot):
    panel = _action_panel(qtbot)
    panel._select_by_identifier("DEC-001")
    panel._rebuild_actions_menu()
    labels = _menu_labels(panel._actions_menu)
    assert labels[:2] == ["New Fake", "Edit"]
    assert "View" in labels
    assert "Delete" in labels
    assert labels.count("Edit") == 1  # context-menu Edit deduplicated


def test_dropdown_entry_triggers_hidden_action(qapp, qtbot):
    panel = _action_panel(qtbot, cls=_PriorityPanel)
    panel._rebuild_actions_menu()
    new_action = next(
        a for a in panel._actions_menu.actions() if a.text() == "New Fake"
    )
    new_action.trigger()
    assert panel.created == 1


def test_edit_button_runs_context_menu_edit(qapp, qtbot):
    panel = _action_panel(qtbot)
    panel._select_by_identifier("DEC-002")
    panel._edit_button.click()
    assert [r["identifier"] for r in panel.edited] == ["DEC-002"]


def test_edit_without_selection_writes_guard_message(qapp, qtbot):
    panel = _action_panel(qtbot)
    panel._edit_button.click()
    assert panel._status_label.text() == "Select a record to edit."
    assert panel.edited == []


def test_edit_on_read_only_list_explains(qapp, qtbot):
    panel = _loaded_panel(qtbot)  # plain _FakePanel: empty context menu
    panel._select_by_identifier("DEC-001")
    panel._edit_button.click()
    assert "cannot be edited" in panel._status_label.text()


def test_view_emits_open_requested_with_entity_type(qapp, qtbot):
    panel = _action_panel(qtbot)
    panel.view_entity_type = "decision"
    panel._select_by_identifier("DEC-003")
    with qtbot.waitSignal(panel.open_requested, timeout=1000) as blocker:
        panel._view_button.click()
    assert blocker.args == ["decision", "DEC-003"]


def test_view_without_entity_type_or_selection_explains(qapp, qtbot):
    panel = _action_panel(qtbot)
    panel._view_button.click()
    assert panel._status_label.text() == "Select a record to view."
    panel._select_by_identifier("DEC-001")
    panel._view_button.click()
    assert panel._status_label.text() == "No detail window is available for this list."


def test_registry_stamps_view_entity_type(qapp, qtbot):
    from crmbuilder_v2.ui.panel_registry import build_panel

    panel = build_panel("Decisions", None)
    qtbot.addWidget(panel)
    assert panel.view_entity_type == "decision"
