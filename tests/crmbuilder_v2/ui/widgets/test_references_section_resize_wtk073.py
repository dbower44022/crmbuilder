"""Tests for PI-119 / WTK-073 interactive drag-resize on ReferencesSection.

Covers the delta WTK-073 adds: the embedded link grid's flat-table header
flips from ``ResizeToContents`` to ``Interactive`` (keeping col 4 *Title* on
``Stretch``), seeds content widths once, and floors every section at
``_MIN_SECTION_WIDTH``. The design (``pi-119-link-panel-column-resize-ui-design``)
is explicit that this must preserve PI-117 multi-sort, PI-117 grouping, and the
PI-116 filter, and must not regress ``test_context_menus`` — so the suite drives
the same routing/grouping/filter entry points after resize-enablement to prove
they still work.
"""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.references_section import (
    _MIN_SECTION_WIDTH,
    ReferencesSection,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView

# Column indices (mirror _COLUMNS): col 4 is Title (the Stretch column).
_COL_RELATIONSHIP = 1
_COL_IDENTIFIER = 2
_COL_TITLE = 4
_NON_TITLE_COLUMNS = (0, 1, 2, 3, 5, 6, 7)

# Group-by combo option index (mirror _GROUP_OPTIONS): 1 == relationship.
_GROUP_RELATIONSHIP = 1


def _row(source_id, rel, source_type):
    return {
        "source_type": source_type,
        "source_id": source_id,
        "target_type": "decision",
        "target_id": "DEC-001",
        "relationship": rel,
        "other_summary": {
            "identifier": source_id,
            "entity_type": source_type,
            "title": f"{source_id} title",
            "status": "complete",
            "created_at": "2026-01-01T10:00:00+00:00",
            "updated_at": "2026-01-02T10:00:00+00:00",
        },
    }


def _payload():
    return {
        "as_target": [
            _row("SES-002", "decided_in", "session"),
            _row("SES-001", "decided_in", "session"),
            _row("TOP-1", "is_about", "topic"),
        ],
        "as_source": [],
    }


def _section(qtbot):
    section = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(section)
    return section


# ---------------------------------------------------------------------------
# AC1–AC3: drag-resize is enabled and bounded
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
    """Behavioral proof: a ``ResizeToContents`` section silently ignores
    ``resizeSection``; an ``Interactive`` one honors it. This is the decisive
    check that drag-resize actually works."""
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    header.resizeSection(_COL_IDENTIFIER, 200)
    assert header.sectionSize(_COL_IDENTIFIER) == 200


def test_minimum_section_size_floor(qapp, qtbot):
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    assert header.minimumSectionSize() == _MIN_SECTION_WIDTH
    # An over-drag below the floor is clamped, not honored — the column can
    # never be hidden and the sort glyph can never be clipped away.
    header.resizeSection(_COL_IDENTIFIER, 1)
    assert header.sectionSize(_COL_IDENTIFIER) >= _MIN_SECTION_WIDTH


# ---------------------------------------------------------------------------
# AC4: multi-key sort preserved (C1)
# ---------------------------------------------------------------------------


def test_sort_routing_survives_resize_enablement(qapp, qtbot):
    section = _section(qtbot)
    header = section._table.horizontalHeader()
    # Drive the tests'-exposed routing entry: an unmodified click sets primary.
    header._route_click(_COL_IDENTIFIER, Qt.KeyboardModifier.NoModifier)
    keys = section._proxy.sort_keys()
    assert keys and keys[0][0] == _COL_IDENTIFIER
    # The precedence glyph still resolves for the sorted column.
    assert header.indicator_for(_COL_IDENTIFIER) is not None


# ---------------------------------------------------------------------------
# AC5: grouping + filter preserved (C2, C3)
# ---------------------------------------------------------------------------


def test_grouping_still_swaps_to_tree(qapp, qtbot):
    section = _section(qtbot)
    assert section._stack.currentWidget() is section._table
    section._group_combo.setCurrentIndex(_GROUP_RELATIONSHIP)
    assert section._stack.currentWidget() is section._tree
    assert section._group_model is not None


def test_filter_still_narrows_rows(qapp, qtbot):
    section = _section(qtbot)
    assert section._proxy.rowCount() == 3
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("TOP-1")
    assert section._proxy.rowCount() == 1
    assert (
        section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER)) == "TOP-1"
    )
