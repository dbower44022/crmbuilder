"""Editable ``field_options`` collection editor (PRJ-025 PI-182 UI slice).

A small repeating-row editor for an enum / multi_enum field's option set.
There was no pre-existing in-dialog repeating-row collection editor in the
v2 UI (``references_section`` is a read-only grid; the catalog/sub-row
hits are list panels, not editable in-dialog tables), so this is a fresh
minimal ``QTableWidget``-based widget.

Three columns — Value (editable), Label (editable), Order (read-only,
the 0-based row position). The widget exposes:

* :meth:`set_options` — load a list of ``{"option_value", "option_label",
  "option_order"}`` dicts, sorted by ``option_order``.
* :meth:`options` — return the current set as the same dict shape, with
  ``option_order`` set to the row position (0-based). Fully-blank rows
  (empty value) are dropped so the wire payload never carries an option
  the access layer would reject.

The whole set is sent on save and *replaces* the server-side set
(``field_options`` semantics: a supplied list replaces, omitted/None
leaves unchanged) — the editor therefore always emits the full current
set; the dialog decides whether to include it in the request.

Per the project UI rule, the Add / Remove / Move-up / Move-down buttons
are **never disabled** — clicking one with no valid selection (or at a
list boundary) shows an explanatory message instead of greying out.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_VALUE_COL = 0
_LABEL_COL = 1
_ORDER_COL = 2


class FieldOptionsEditor(QWidget):
    """Editable value/label/order table for a field's option set."""

    options_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self._table = QTableWidget(0, 3)
        self._table.setObjectName("field_options_table")
        self._table.setHorizontalHeaderLabels(["Value", "Label", "Order"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(
            _VALUE_COL, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            _LABEL_COL, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            _ORDER_COL, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.itemChanged.connect(self._on_item_changed)
        outer.addWidget(self._table)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self._add_btn = QPushButton("Add option")
        self._add_btn.setObjectName("field_option_add_button")
        self._add_btn.clicked.connect(self._on_add_clicked)
        button_row.addWidget(self._add_btn)

        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setObjectName("field_option_remove_button")
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(self._remove_btn)

        self._up_btn = QPushButton("Move up")
        self._up_btn.setObjectName("field_option_up_button")
        self._up_btn.clicked.connect(self._on_move_up_clicked)
        button_row.addWidget(self._up_btn)

        self._down_btn = QPushButton("Move down")
        self._down_btn.setObjectName("field_option_down_button")
        self._down_btn.clicked.connect(self._on_move_down_clicked)
        button_row.addWidget(self._down_btn)

        button_row.addStretch(1)
        outer.addLayout(button_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_options(self, options: list[dict[str, Any]] | None) -> None:
        """Load ``options`` (sorted by ``option_order``) into the table."""
        rows = list(options or [])
        rows.sort(key=lambda o: _order_key(o.get("option_order")))
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for opt in rows:
            self._append_row(
                str(opt.get("option_value") or ""),
                "" if opt.get("option_label") is None
                else str(opt.get("option_label")),
            )
        self._table.blockSignals(False)
        self._renumber_order_column()

    def options(self) -> list[dict[str, Any]]:
        """Return the current option set as wire dicts (0-based order).

        Rows whose Value is blank are dropped — the access layer rejects
        an option with an empty ``option_value``. ``option_label`` is
        ``None`` when its cell is blank.
        """
        out: list[dict[str, Any]] = []
        order = 0
        for row in range(self._table.rowCount()):
            value = self._cell_text(row, _VALUE_COL).strip()
            if not value:
                continue
            label = self._cell_text(row, _LABEL_COL).strip()
            out.append(
                {
                    "option_value": value,
                    "option_label": label or None,
                    "option_order": order,
                }
            )
            order += 1
        return out

    # ------------------------------------------------------------------
    # Row helpers
    # ------------------------------------------------------------------

    def _append_row(self, value: str, label: str) -> int:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, _VALUE_COL, QTableWidgetItem(value))
        self._table.setItem(row, _LABEL_COL, QTableWidgetItem(label))
        order_item = QTableWidgetItem(str(row))
        order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, _ORDER_COL, order_item)
        return row

    def _cell_text(self, row: int, col: int) -> str:
        item = self._table.item(row, col)
        return item.text() if item is not None else ""

    def _renumber_order_column(self) -> None:
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _ORDER_COL)
            if item is not None:
                item.setText(str(row))
        self._table.blockSignals(False)

    def _selected_row(self) -> int:
        return self._table.currentRow()

    # ------------------------------------------------------------------
    # Button handlers — never disabled; explain instead (project rule)
    # ------------------------------------------------------------------

    def _on_add_clicked(self) -> None:
        row = self._append_row("", "")
        self._renumber_order_column()
        self._table.setCurrentCell(row, _VALUE_COL)
        self._table.editItem(self._table.item(row, _VALUE_COL))
        self.options_changed.emit()

    def _on_remove_clicked(self) -> None:
        row = self._selected_row()
        if row < 0:
            self._inform("Select an option row to remove first.")
            return
        self._table.removeRow(row)
        self._renumber_order_column()
        self.options_changed.emit()

    def _on_move_up_clicked(self) -> None:
        row = self._selected_row()
        if row < 0:
            self._inform("Select an option row to move first.")
            return
        if row == 0:
            self._inform("That option is already at the top.")
            return
        self._swap_rows(row, row - 1)
        self._table.setCurrentCell(row - 1, _VALUE_COL)
        self.options_changed.emit()

    def _on_move_down_clicked(self) -> None:
        row = self._selected_row()
        if row < 0:
            self._inform("Select an option row to move first.")
            return
        if row >= self._table.rowCount() - 1:
            self._inform("That option is already at the bottom.")
            return
        self._swap_rows(row, row + 1)
        self._table.setCurrentCell(row + 1, _VALUE_COL)
        self.options_changed.emit()

    def _swap_rows(self, a: int, b: int) -> None:
        self._table.blockSignals(True)
        for col in (_VALUE_COL, _LABEL_COL):
            a_text = self._cell_text(a, col)
            b_text = self._cell_text(b, col)
            self._table.item(a, col).setText(b_text)
            self._table.item(b, col).setText(a_text)
        self._table.blockSignals(False)
        self._renumber_order_column()

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        self.options_changed.emit()

    def _inform(self, message: str) -> None:
        CopyableMessageBox.information(self, "Field options", message)


def _order_key(value: Any) -> tuple[int, int]:
    """Sort key tolerant of null / non-int ``option_order`` values."""
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, 0)
