"""Tests for GroupingTreeModel — two-level group-by tree (PI-117)."""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.widgets.grouping_tree_model import (
    NONE_GROUP,
    GroupingTreeModel,
)
from PySide6.QtCore import QModelIndex, Qt

_HEADERS = ["Relationship", "Identifier"]


def _cell(row: dict[str, Any], col: int):
    key = ("rel", "ident")[col]
    return row.get(key) or "—"


def _group_by_rel(row: dict[str, Any]) -> str:
    return row.get("rel") or NONE_GROUP


def _rows() -> list[dict[str, Any]]:
    # Pre-sorted (arrival) order encodes the active multi-sort.
    return [
        {"rel": "Decided in", "ident": "SES-002"},
        {"rel": "Decided in", "ident": "SES-003"},
        {"rel": "Is about", "ident": "TOP-1"},
        {"rel": "", "ident": "X-9"},  # missing group key → "(none)"
    ]


def _build():
    return GroupingTreeModel(_rows(), _HEADERS, _group_by_rel, _cell)


def test_group_count_equals_distinct_keys(qapp):
    model = _build()
    # Decided in, Is about, (none).
    assert model.rowCount(QModelIndex()) == 3
    assert model.group_count() == 3


def test_group_label_shows_value_and_count(qapp):
    model = _build()
    labels = [
        model.data(model.index(g, 0, QModelIndex()), Qt.ItemDataRole.DisplayRole)
        for g in range(model.group_count())
    ]
    assert labels == ["Decided in (2)", "Is about (1)", "(none) (1)"]


def test_none_group_sorts_last(qapp):
    model = _build()
    last = model.data(
        model.index(model.group_count() - 1, 0, QModelIndex()),
        Qt.ItemDataRole.DisplayRole,
    )
    assert last.startswith(NONE_GROUP)


def test_child_order_preserves_input_order(qapp):
    model = _build()
    group0 = model.index(0, 0, QModelIndex())  # Decided in
    assert model.rowCount(group0) == 2
    idents = [
        model.data(
            model.index(c, 1, group0), Qt.ItemDataRole.DisplayRole
        )
        for c in range(model.rowCount(group0))
    ]
    assert idents == ["SES-002", "SES-003"]


def test_row_dict_maps_child_to_underlying_row(qapp):
    model = _build()
    group1 = model.index(1, 0, QModelIndex())  # Is about
    child = model.index(0, 0, group1)
    row = model.row_dict(child)
    assert row is not None
    assert row["ident"] == "TOP-1"


def test_row_dict_none_for_group_node(qapp):
    model = _build()
    group0 = model.index(0, 0, QModelIndex())
    assert model.row_dict(group0) is None
    assert model.is_group_index(group0)


def test_parent_of_child_is_its_group(qapp):
    model = _build()
    group0 = model.index(0, 0, QModelIndex())
    child = model.index(1, 0, group0)
    parent = model.parent(child)
    assert parent.isValid()
    assert parent.row() == 0
    assert model.is_group_index(parent)


def test_set_rows_rebuilds(qapp):
    model = _build()
    model.set_rows(
        [
            {"rel": "Blocks", "ident": "PI-1"},
        ]
    )
    assert model.group_count() == 1
    assert model.group_label(0) == "Blocks (1)"
