"""Tests for ReferencesSection widget.

PRJ-015 references-grid rewrite. The widget renders a record's references
as a single sortable/filterable ``QTableView`` (columns: Direction,
Relationship, Identifier, Type, Title, Status, Created, Updated) instead of
the prior list of kind-labeled rich-text link labels. Navigation is via row
double-click; the per-row right-click menu (Delete + Go to) and the
``Add reference`` button are preserved. Title/Status/Created/Updated come
from the ``other_summary`` block the access layer attaches to each edge.
"""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

# Column indices (mirror _COLUMNS order in the widget).
_COL_DIRECTION = 0
_COL_RELATIONSHIP = 1
_COL_IDENTIFIER = 2
_COL_TITLE = 4
_COL_STATUS = 5


def _payload(*, as_target=None, as_source=None) -> dict:
    return {
        "as_target": list(as_target or ()),
        "as_source": list(as_source or ()),
    }


def _label_texts(widget) -> list[str]:
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _grid_cells(section) -> list[dict[str, str]]:
    """Display strings per grid row, keyed by column header."""
    proxy = section._proxy
    src = proxy.sourceModel()
    headers = [
        src.headerData(c, Qt.Orientation.Horizontal)
        for c in range(proxy.columnCount())
    ]
    return [
        {
            headers[c]: proxy.data(proxy.index(r, c))
            for c in range(proxy.columnCount())
        }
        for r in range(proxy.rowCount())
    ]


def _double_click_row(section, identifier: str) -> bool:
    proxy = section._proxy
    for r in range(proxy.rowCount()):
        if proxy.data(proxy.index(r, _COL_IDENTIFIER)) == identifier:
            section._table.doubleClicked.emit(proxy.index(r, _COL_DIRECTION))
            return True
    return False


def test_empty_payload_renders_none_placeholder(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(section)
    texts = _label_texts(section)
    assert any("References" in t for t in texts)
    assert any("(none)" in t for t in texts)


def test_inbound_row_renders_with_kind_label(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
                "other_summary": {
                    "identifier": "SES-002",
                    "entity_type": "session",
                    "title": "Storage v0.1 build",
                    "status": "complete",
                    "created_at": "2026-05-09T10:00:00+00:00",
                    "updated_at": "2026-05-10T11:30:00+00:00",
                },
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    cells = _grid_cells(section)
    assert len(cells) == 1
    row = cells[0]
    assert row["Direction"] == "In"
    assert row["Relationship"] == "Decided in"
    assert row["Identifier"] == "SES-002"
    assert row["Type"] == "Session"
    # Enrichment surfaces the far side's title/status/dates.
    assert row["Title"] == "Storage v0.1 build"
    assert row["Status"] == "complete"
    assert row["Created"] == "2026-05-09 10:00"
    assert row["Updated"] == "2026-05-10 11:30"


def test_outbound_supersedes_renders_kind_label(qapp, qtbot):
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "supersedes",
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-018", payload)
    qtbot.addWidget(section)
    cells = _grid_cells(section)
    assert any(
        r["Relationship"] == "Supersedes" and r["Identifier"] == "DEC-007"
        for r in cells
    )
    # No other_summary supplied → title/status render as the dash sentinel.
    assert cells[0]["Title"] == "—"


def test_missing_summary_renders_dashes_not_crash(qapp, qtbot):
    """An edge whose far side has no summary (e.g. version-keyed singleton)
    still renders identifier + type, with dashes for the unknown fields."""
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "charter",
                "target_id": "1",
                "relationship": "covers",
                "other_summary": None,
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-018", payload)
    qtbot.addWidget(section)
    row = _grid_cells(section)[0]
    assert row["Identifier"] == "1"
    assert row["Type"] == "Charter"
    assert row["Title"] == "—"
    assert row["Status"] == "—"


def test_multiple_kinds_render_as_distinct_rows(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "session",
                "source_id": "SES-003",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "topic",
                "source_id": "TOP-1",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "is_about",
            },
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    cells = _grid_cells(section)
    assert len(cells) == 3
    relationships = {r["Relationship"] for r in cells}
    assert relationships == {"Decided in", "Cited by"}
    identifiers = {r["Identifier"] for r in cells}
    assert identifiers == {"SES-002", "SES-003", "TOP-1"}


def test_exclude_relationships_filters_outbound(qapp, qtbot):
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "supersedes",
            },
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "topic",
                "target_id": "TOP-1",
                "relationship": "is_about",
            },
        ]
    )
    section = ReferencesSection(
        "decision",
        "DEC-018",
        payload,
        exclude_relationships={"supersedes"},
    )
    qtbot.addWidget(section)
    cells = _grid_cells(section)
    relationships = {r["Relationship"] for r in cells}
    assert "Supersedes" not in relationships
    assert relationships == {"Is about"}
    assert cells[0]["Identifier"] == "TOP-1"


def test_excluded_relationship_with_no_remaining_renders_none(qapp, qtbot):
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "supersedes",
            }
        ]
    )
    section = ReferencesSection(
        "decision",
        "DEC-018",
        payload,
        exclude_relationships={"supersedes"},
    )
    qtbot.addWidget(section)
    assert any("(none)" in t for t in _label_texts(section))


def _two_row_payload() -> dict:
    return _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "topic",
                "source_id": "TOP-9",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "is_about",
            },
        ]
    )


def test_filter_box_narrows_visible_rows(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _two_row_payload())
    qtbot.addWidget(section)
    assert section._proxy.rowCount() == 2
    # Typing is debounced; wait for the settled filterChanged emission.
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("TOP-9")
    assert section._proxy.rowCount() == 1
    assert section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER)) == "TOP-9"
    # Clearing restores the full list immediately (no debounce).
    section._filter.setText("")
    assert section._proxy.rowCount() == 2


def test_filter_debounce_applies_once_after_burst(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _two_row_payload())
    qtbot.addWidget(section)
    applied: list[str] = []
    section._filter.filterChanged.connect(applied.append)
    # A burst of keystrokes inside the debounce window.
    for text in ("T", "TO", "TOP", "TOP-9"):
        section._filter.setText(text)
    assert applied == []  # nothing applied yet
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        pass
    assert applied == ["TOP-9"]
    assert section._proxy.rowCount() == 1


def test_no_match_shows_empty_state_and_hides_table(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _two_row_payload())
    qtbot.addWidget(section)
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("nomatchwhatsoever")
    assert section._proxy.rowCount() == 0
    assert section._empty_state.isVisibleTo(section)
    assert section._empty_state.text() == 'No links match "nomatchwhatsoever".'
    assert not section._table.isVisibleTo(section)


def test_clearing_dismisses_empty_state_and_restores_table(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _two_row_payload())
    qtbot.addWidget(section)
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("zzz")
    assert section._empty_state.isVisibleTo(section)
    section._filter.setText("")  # immediate restore
    assert not section._empty_state.isVisibleTo(section)
    assert section._table.isVisibleTo(section)
    assert section._proxy.rowCount() == 2


def test_long_query_is_elided_in_empty_state(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _two_row_payload())
    qtbot.addWidget(section)
    long_query = "x" * 80
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText(long_query)
    text = section._empty_state.text()
    assert text.endswith('…".')
    assert long_query not in text  # truncated, not echoed in full


def test_sort_by_identifier_column(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-050",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    section._table.sortByColumn(_COL_IDENTIFIER, Qt.SortOrder.AscendingOrder)
    first = section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER))
    assert first == "SES-002"


def test_double_click_emits_navigate_requested(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    received: list[tuple[str, str]] = []
    section.navigate_requested.connect(lambda t, i: received.append((t, i)))
    assert _double_click_row(section, "SES-002")
    assert received == [("session", "SES-002")]


def test_table_has_custom_context_menu_policy(qapp, qtbot):
    from unittest.mock import MagicMock

    section = ReferencesSection(
        "decision",
        "DEC-007",
        _payload(as_source=[_ref_outbound()]),
        client=MagicMock(),
    )
    qtbot.addWidget(section)
    assert (
        section._table.contextMenuPolicy()
        == Qt.ContextMenuPolicy.CustomContextMenu
    )


# ---------------------------------------------------------------------------
# Write surface (Add reference + per-row right-click delete) — unchanged API
# ---------------------------------------------------------------------------


def _ref_outbound(target_id: str = "DEC-007", ref_id: int = 7) -> dict:
    return {
        "id": ref_id,
        "source_type": "session",
        "source_id": "SES-001",
        "target_type": "decision",
        "target_id": target_id,
        "relationship": "decided_in",
    }


def test_add_reference_button_absent_when_no_client(qapp, qtbot):
    from PySide6.QtWidgets import QPushButton

    section = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(section)
    assert (
        section.findChild(QPushButton, "references_section_add_button")
        is None
    )


def test_add_reference_button_renders_when_client_supplied(qapp, qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QPushButton

    section = ReferencesSection(
        "decision", "DEC-001", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    btn = section.findChild(QPushButton, "references_section_add_button")
    assert btn is not None
    assert btn.text() == "Add reference"


def test_set_add_enabled_hides_button(qapp, qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QPushButton

    section = ReferencesSection(
        "decision", "DEC-001", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    btn = section.findChild(QPushButton, "references_section_add_button")
    section.set_add_enabled(False)
    assert not btn.isVisible()


def test_add_reference_click_opens_create_dialog_with_pre_populated_source(
    qapp, qtbot, monkeypatch
):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog, QPushButton

    captured = {}

    class _StubDialog:
        def __init__(self, client, *, pre_populated_source=None, parent=None):
            captured["pre_populated_source"] = pre_populated_source
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_create.ReferenceCreateDialog",
        _StubDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-018", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    btn = section.findChild(QPushButton, "references_section_add_button")
    btn.click()
    assert captured["pre_populated_source"] == ("decision", "DEC-018")
    assert captured["parent"] is section


def test_add_reference_dialog_accept_emits_references_changed(
    qapp, qtbot, monkeypatch
):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog

    class _AcceptDialog:
        def __init__(self, *_a, **_kw):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_create.ReferenceCreateDialog",
        _AcceptDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-018", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    with qtbot.waitSignal(section.references_changed, timeout=2000):
        section._on_add_clicked()


def test_delete_reference_action_opens_delete_dialog(qapp, qtbot, monkeypatch):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog

    captured = {}

    class _StubDialog:
        def __init__(self, client, *, reference_id, edge, parent=None):
            captured["reference_id"] = reference_id
            captured["edge"] = edge
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_delete.ReferenceDeleteDialog",
        _StubDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-007", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    section._on_delete_clicked(_ref_outbound(target_id="DEC-007", ref_id=42))
    assert captured["reference_id"] == 42
    assert captured["edge"] == "SES-001 → DEC-007: decided_in"
    assert captured["parent"] is section


def test_delete_reference_dialog_accept_emits_references_changed(
    qapp, qtbot, monkeypatch
):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog

    class _AcceptDialog:
        def __init__(self, *_a, **_kw):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_delete.ReferenceDeleteDialog",
        _AcceptDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-007", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    with qtbot.waitSignal(section.references_changed, timeout=2000):
        section._on_delete_clicked(_ref_outbound(ref_id=99))
        assert True


# ---------------------------------------------------------------------------
# GridContract seam (PI-120 / WTK-076): the same grid, a second configuration.
# The References default must stay byte-identical; a non-references contract
# (Work Tasks, via WorkTaskGridSection) drives its own columns/menu/no-Add.
# ---------------------------------------------------------------------------


def _grid_headers(section) -> list[str]:
    model = section._model
    return [
        model.headerData(c, Qt.Orientation.Horizontal)
        for c in range(model.columnCount())
    ]


def _work_task_rows():
    return [
        {
            "identifier": "WTK-001",
            "title": "Storage layer",
            "area": "storage",
            "status": "Complete",
            "claim_state": "Claimed · AGP-dev",
            "other_type": "work_task",
            "other_id": "WTK-001",
        },
        {
            "identifier": "WTK-002",
            "title": "API layer",
            "area": "api",
            "status": "Ready",
            "claim_state": "Unclaimed",
            "other_type": "work_task",
            "other_id": "WTK-002",
        },
    ]


def test_references_default_contract_headers_unchanged(qapp, qtbot):
    section = ReferencesSection(
        "decision",
        "DEC-001",
        _payload(
            as_target=[
                {
                    "source_type": "session",
                    "source_id": "SES-002",
                    "target_type": "decision",
                    "target_id": "DEC-001",
                    "relationship": "decided_in",
                    "other_summary": {"title": "x", "status": "complete"},
                }
            ]
        ),
    )
    qtbot.addWidget(section)
    assert _grid_headers(section) == [
        "Direction",
        "Relationship",
        "Identifier",
        "Type",
        "Title",
        "Status",
        "Created",
        "Updated",
    ]


def test_work_task_grid_section_renders_own_columns_and_rows(qapp, qtbot):
    from crmbuilder_v2.ui.widgets.references_section import WorkTaskGridSection

    section = WorkTaskGridSection("workstream", "WSK-001", _work_task_rows())
    qtbot.addWidget(section)
    assert _grid_headers(section) == [
        "Identifier",
        "Title",
        "Area",
        "Status",
        "Claim state",
    ]
    cells = _grid_cells(section)
    by_id = {row["Identifier"]: row for row in cells}
    assert by_id["WTK-001"]["Area"] == "storage"
    assert by_id["WTK-001"]["Claim state"] == "Claimed · AGP-dev"
    assert by_id["WTK-002"]["Claim state"] == "Unclaimed"


def test_work_task_grid_section_row_menu_is_read_only(qapp, qtbot):
    from crmbuilder_v2.ui.widgets.references_section import WorkTaskGridSection

    section = WorkTaskGridSection("workstream", "WSK-001", _work_task_rows())
    qtbot.addWidget(section)
    menu = section._build_row_menu(section._table, _work_task_rows()[0])
    labels = [a.text() for a in menu.actions()]
    assert labels == ["Go to WTK-001", "Copy identifier"]
    # No edge-delete affordance on read-only Work Task rows.
    assert "Delete reference" not in labels


def test_work_task_grid_section_has_no_add_button(qapp, qtbot):
    from unittest.mock import MagicMock

    from crmbuilder_v2.ui.widgets.references_section import WorkTaskGridSection

    # Even with a client (needed for the inline preview fetch) the Work Task
    # grid suppresses the Add affordance — it is read-only.
    section = WorkTaskGridSection(
        "workstream", "WSK-001", _work_task_rows(), client=MagicMock()
    )
    qtbot.addWidget(section)
    from PySide6.QtWidgets import QPushButton

    assert (
        section.findChild(QPushButton, "references_section_add_button") is None
    )


def test_work_task_grid_section_double_click_navigates(qapp, qtbot):
    from crmbuilder_v2.ui.widgets.references_section import WorkTaskGridSection

    section = WorkTaskGridSection("workstream", "WSK-001", _work_task_rows())
    qtbot.addWidget(section)
    with qtbot.waitSignal(section.navigate_requested, timeout=2000) as blocker:
        proxy = section._proxy
        for r in range(proxy.rowCount()):
            if proxy.data(proxy.index(r, 0)) == "WTK-001":
                section._table.doubleClicked.emit(proxy.index(r, 0))
                break
    assert blocker.args == ["work_task", "WTK-001"]
