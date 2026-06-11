"""WTK-077 verification — the Work Task grid IS the References grid.

WTK-076 (PI-120) renders a Workstream's child Work Tasks as an inline grid by
parameterizing :class:`ReferencesSection` behind a ``GridContract`` seam rather
than forking it (:class:`WorkTaskGridSection`). WTK-076's own tests already
cover the five-field column model, the empty case, navigation, the read-only
row menu, the suppressed Add affordance, and the unchanged References-default
headers.

This suite closes the remaining acceptance-criterion gap from the design's
verification approach (``pi-120-...`` §5.4 / AC3): the *inherited grid feature
stack* must still function for Work Task rows — proving the section is the same
grid, not a stripped re-implementation:

- PI-116 — the debounced filter narrows rows.
- PI-117 — multi-column sort routing applies, and the Group-by combo offers the
  Work Task contract's own options (Area / Status / Claim state) and swaps to
  the grouped tree.
- PI-118 — the inline preview's field extractor names the far-side Work Task
  record (with ``area`` as the subtitle, per the contract).
- PI-119 — the header is ``Interactive`` (drag-resizable) with Title on
  ``Stretch`` and every section floored at ``_MIN_SECTION_WIDTH``.

Offscreen Qt, the established pattern for these widget tests.
"""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.references_section import (
    _MIN_SECTION_WIDTH,
    WorkTaskGridSection,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

# Column indices mirror _WORK_TASK_COLUMNS: 0 Identifier, 1 Title (Stretch),
# 2 Area, 3 Status, 4 Claim state.
_COL_IDENTIFIER = 0
_COL_TITLE = 1
_COL_AREA = 2
_NON_TITLE_COLUMNS = (0, 2, 3, 4)

# Group-by combo option indices mirror _WORK_TASK_GROUP_OPTIONS:
# 0 (none), 1 Area, 2 Status, 3 Claim state.
_GROUP_AREA = 1


def _rows():
    return [
        {
            "identifier": "WTK-001",
            "title": "Storage layer migration",
            "area": "storage",
            "status": "Complete",
            "claim_state": "Claimed · AGP-dev-storage",
            "other_type": "work_task",
            "other_id": "WTK-001",
        },
        {
            "identifier": "WTK-002",
            "title": "API endpoints",
            "area": "api",
            "status": "Ready",
            "claim_state": "Unclaimed",
            "other_type": "work_task",
            "other_id": "WTK-002",
        },
        {
            "identifier": "WTK-003",
            "title": "Access repository",
            "area": "storage",
            "status": "In Progress",
            "claim_state": "Claimed · AGP-dev-access",
            "other_type": "work_task",
            "other_id": "WTK-003",
        },
    ]


def _section(qtbot):
    section = WorkTaskGridSection("workstream", "WSK-001", _rows())
    qtbot.addWidget(section)
    return section


# ---------------------------------------------------------------------------
# PI-119 — interactive drag-resize, Title on Stretch (AC3 / §5.4)
# ---------------------------------------------------------------------------


def test_non_title_columns_are_interactive(qapp, qtbot):
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    for col in _NON_TITLE_COLUMNS:
        assert (
            header.sectionResizeMode(col)
            == QHeaderView.ResizeMode.Interactive
        ), f"column {col} should be Interactive (drag-resizable)"


def test_title_column_stays_stretch(qapp, qtbot):
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    assert (
        header.sectionResizeMode(_COL_TITLE)
        == QHeaderView.ResizeMode.Stretch
    )


def test_resize_section_takes_effect(qapp, qtbot):
    # A Stretch column ignores resizeSection; an Interactive one honors it —
    # the decisive PI-119 behavior, exercised on the Work Task contract.
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    header.resizeSection(_COL_AREA, 173)
    assert header.sectionSize(_COL_AREA) == 173


def test_minimum_section_size_floor(qapp, qtbot):
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    assert header.minimumSectionSize() == _MIN_SECTION_WIDTH


# ---------------------------------------------------------------------------
# PI-117 — multi-column sort + grouping with the Work Task contract's options
# ---------------------------------------------------------------------------


def test_group_combo_offers_work_task_options(qapp, qtbot):
    section = _section(qtbot)
    combo = section._group_combo
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert labels == ["(none)", "Area", "Status", "Claim state"]


def test_grouping_swaps_to_tree_and_buckets_by_area(qapp, qtbot):
    section = _section(qtbot)
    assert section._stack.currentWidget() is section._table
    section._group_combo.setCurrentIndex(_GROUP_AREA)
    assert section._stack.currentWidget() is section._tree
    assert section._group_model is not None
    # Two Area buckets: storage (WTK-001, WTK-003) and api (WTK-002).
    assert section._group_model.group_count() == 2


def test_sort_routing_applies_on_work_task_grid(qapp, qtbot):
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    header._route_click(_COL_IDENTIFIER, Qt.KeyboardModifier.NoModifier)
    keys = section._proxy.sort_keys()
    assert keys and keys[0][0] == _COL_IDENTIFIER
    assert header.indicator_for(_COL_IDENTIFIER) is not None


# ---------------------------------------------------------------------------
# PI-116 — debounced filter narrows rows
# ---------------------------------------------------------------------------


def test_filter_narrows_work_task_rows(qapp, qtbot):
    section = _section(qtbot)
    assert section._proxy.rowCount() == 3
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("WTK-002")
    assert section._proxy.rowCount() == 1
    assert (
        section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER))
        == "WTK-002"
    )


# ---------------------------------------------------------------------------
# PI-118 — inline preview names the far-side Work Task record
# ---------------------------------------------------------------------------


def test_preview_extractor_names_work_task_with_area_subtitle(qapp, qtbot):
    section = _section(qtbot)
    # The shared PreviewController is installed and points at the Work Task
    # contract's extractor: (entity_type, identifier, title, subtitle=area).
    assert section._preview is not None
    entity_type, identifier, title, subtitle = section._preview._extractor(
        _rows()[0], _COL_IDENTIFIER
    )
    assert entity_type == "work_task"
    assert identifier == "WTK-001"
    assert title == "Storage layer migration"
    assert subtitle == "storage"
