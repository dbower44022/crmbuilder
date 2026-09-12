"""The Transitions section of a process's detail view (PI-471, REQ-585).

A process's status lifecycle shown as it is stored: one row per allowed move,
in the process's order, with the values moved from, the value moved to, who may
make the move, what must be recorded before it and what happens automatically
after it. A move still described in words rather than by a record is marked, so
the reader can see what is owed.

The section is where a user adds, edits, reorders and deletes a move. Moving a
row up or down rewrites the whole order in one call, so the stored order and
the shown order never disagree.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.transition_crud import TransitionDialog
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.widgets.form_helpers import (
    destructive_button,
    primary_button,
)

_log = logging.getLogger("crmbuilder_v2.ui.widgets.transitions_section")

#: The columns of the shown table, in order.
COLUMNS = (
    "From",
    "To",
    "Who",
    "Before",
    "Automatically after",
    "By hand after",
)

#: What the From cell says when the move brings the record into being.
NO_RECORD = "(no record)"

_EMPTY = "—"


class TransitionsSection(QWidget):
    """The ordered table of a process's transitions, with its edit buttons."""

    transitions_changed = Signal()

    def __init__(
        self,
        process_identifier: str,
        *,
        client: StorageClient,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._process = process_identifier
        self._rows: list[dict[str, Any]] = []
        self._field_names: dict[str, str] = {}
        self._persona_names: dict[str, str] = {}
        self._consequence_labels: dict[str, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        header = QLabel("Transitions — the allowed status moves")
        header.setObjectName("transitions_section_header")
        header_font = QFont(header.font())
        header_font.setBold(True)
        header.setFont(header_font)
        outer.addWidget(header)

        self.summary = QLabel("")
        self.summary.setObjectName("transitions_section_summary")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("transitions_table")
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.doubleClicked.connect(lambda _index: self.edit_selected())
        outer.addWidget(self.table)

        buttons = QHBoxLayout()
        self.add_button = primary_button("Add move")
        self.add_button.setObjectName("transition_add")
        self.add_button.clicked.connect(self.add)
        buttons.addWidget(self.add_button)
        self.edit_button = QPushButton("Edit")
        self.edit_button.setObjectName("transition_edit")
        self.edit_button.clicked.connect(self.edit_selected)
        buttons.addWidget(self.edit_button)
        self.up_button = QPushButton("Move up")
        self.up_button.setObjectName("transition_move_up")
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        buttons.addWidget(self.up_button)
        self.down_button = QPushButton("Move down")
        self.down_button.setObjectName("transition_move_down")
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        buttons.addWidget(self.down_button)
        self.delete_button = destructive_button("Delete")
        self.delete_button.setObjectName("transition_delete")
        self.delete_button.clicked.connect(self.delete_selected)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self.reload()

    # -- reads -------------------------------------------------------------

    def _load_names(self) -> None:
        """Read the names behind every identifier a row shows.

        A row that printed ``AUT-004`` would send the reader to another record
        to learn what happens after the move, so each consequence is shown as
        what it is, with the identifier in brackets after it.
        """
        try:
            self._field_names = {
                row["field_identifier"]: row["field_name"]
                for row in self._client.list_fields()
            }
            self._persona_names = {
                row["persona_identifier"]: row["persona_name"]
                for row in self._client.list_personas()
            }
            self._consequence_labels = self._read_consequence_labels()
        except (StorageClientError, StorageConnectionError):
            self._field_names = {}
            self._persona_names = {}
            self._consequence_labels = {}

    def _read_consequence_labels(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        for row in self._client.list_automations():
            labels[row["automation_identifier"]] = (
                f"the {row['automation_name']} routine "
                f"({row['automation_identifier']})"
            )
        for row in self._client.list_message_templates():
            labels[row["message_template_identifier"]] = (
                f"the {row['message_template_name']} message "
                f"({row['message_template_identifier']})"
            )
        for row in self._client.list_views():
            labels[row["view_identifier"]] = (
                f"the {row['view_name']} view ({row['view_identifier']})"
            )
        for row in self._client.list_processes():
            labels[row["process_identifier"]] = (
                f"hand-off to the {row['process_name']} process "
                f"({row['process_identifier']})"
            )
        for row in self._client.list_transitions():
            labels[row["transition_identifier"]] = (
                f"the move to {row['transition_to_value']} "
                f"({row['transition_identifier']})"
            )
        return labels

    def reload(self) -> None:
        """Re-read the process's transitions and redraw the table."""
        self._load_names()
        try:
            self._rows = self._client.list_transitions(
                process_identifier=self._process
            )
        except (StorageClientError, StorageConnectionError) as exc:
            self._rows = []
            self.summary.setText(f"Could not read the status moves: {exc}")
            self.table.setRowCount(0)
            return
        self._redraw()

    def _redraw(self) -> None:
        self.table.setRowCount(len(self._rows))
        incomplete = 0
        for position, record in enumerate(self._rows):
            if record.get("transition_consequence_notes"):
                incomplete += 1
            for column, text in enumerate(self._cells(record)):
                item = QTableWidgetItem(text)
                item.setData(
                    Qt.ItemDataRole.UserRole, record["transition_identifier"]
                )
                self.table.setItem(position, column, item)
        if not self._rows:
            self.summary.setText(
                "No status moves are recorded for this process yet. Until "
                "there are, the lifecycle can only be read out of the steps "
                "and the decisions."
            )
        elif incomplete:
            self.summary.setText(
                f"{len(self._rows)} moves, of which {incomplete} still "
                "describe an automatic action in words rather than naming a "
                "record for it."
            )
        else:
            self.summary.setText(
                f"{len(self._rows)} moves. Every automatic action names a "
                "record."
            )

    def _cells(self, record: dict[str, Any]) -> tuple[str, ...]:
        if record["transition_from_kind"] == "record_creation":
            from_cell = NO_RECORD
        else:
            from_cell = ", ".join(record["transition_from_values"])
        if record["transition_actor_kind"] == "system":
            who = "System"
        else:
            identifier = record["transition_actor_persona"]
            who = self._persona_names.get(identifier, identifier)
        occasion = record.get("transition_actor_occasion")
        if occasion:
            who = f"{who}, {occasion}"
        before_parts = [
            self._field_names.get(identifier, identifier)
            for identifier in record["transition_required_fields"]
        ]
        condition = record.get("transition_precondition")
        if condition:
            before_parts.append(condition)
        after_parts = [
            self._consequence_labels.get(identifier, identifier)
            for identifier in record["transition_consequences"]
        ]
        words = record.get("transition_consequence_notes")
        if words:
            after_parts.append(f"{words} (no record yet)")
        return (
            from_cell,
            record["transition_to_value"],
            who,
            ". ".join(before_parts) if before_parts else _EMPTY,
            "; ".join(after_parts) if after_parts else _EMPTY,
            record.get("transition_manual_follow_up") or _EMPTY,
        )

    # -- selection ---------------------------------------------------------

    def selected_row(self) -> int | None:
        rows = {index.row() for index in self.table.selectedIndexes()}
        if len(rows) != 1:
            return None
        return rows.pop()

    def selected_record(self) -> dict[str, Any] | None:
        row = self.selected_row()
        if row is None or row >= len(self._rows):
            return None
        return self._rows[row]

    # -- writes ------------------------------------------------------------

    def add(self) -> None:
        dialog = TransitionDialog(
            self._client, process_identifier=self._process, parent=self
        )
        if dialog.exec():
            self.reload()
            self.transitions_changed.emit()

    def edit_selected(self) -> None:
        record = self.selected_record()
        if record is None:
            self.summary.setText("Select one move to edit it.")
            return
        dialog = TransitionDialog(
            self._client,
            process_identifier=self._process,
            record=record,
            parent=self,
        )
        if dialog.exec():
            self.reload()
            self.transitions_changed.emit()

    def move_selected(self, offset: int) -> None:
        """Move the selected row up or down and rewrite the whole order."""
        row = self.selected_row()
        if row is None:
            self.summary.setText("Select one move to reorder it.")
            return
        target = row + offset
        if target < 0 or target >= len(self._rows):
            return
        order = [r["transition_identifier"] for r in self._rows]
        order[row], order[target] = order[target], order[row]
        try:
            self._client.reorder_transitions(self._process, order)
        except (StorageClientError, StorageConnectionError) as exc:
            ErrorDialog.show_error(
                self,
                title="Could not reorder the status moves",
                message="The order was left as it was.",
                detail=str(exc),
            )
            return
        self.reload()
        self.table.selectRow(target)
        self.transitions_changed.emit()

    def delete_selected(self) -> None:
        record = self.selected_record()
        if record is None:
            self.summary.setText("Select one move to delete it.")
            return
        identifier = record["transition_identifier"]
        confirmed = QMessageBox.question(
            self,
            "Delete this status move?",
            f"The move to {record['transition_to_value']} ({identifier}) "
            "will be removed from this process. It is retained in the store "
            "and can be restored.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            self._client.delete_transition(identifier)
        except (StorageClientError, StorageConnectionError) as exc:
            ErrorDialog.show_error(
                self,
                title="Could not delete the status move",
                message="Nothing was changed.",
                detail=str(exc),
            )
            return
        self.reload()
        self.transitions_changed.emit()
