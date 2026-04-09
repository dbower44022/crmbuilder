"""Record detail form layout (Section 14.8.2).

Shows all column values for the selected record in a read-only form.
FK references shown as clickable links.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automation.ui.browser.browser_logic import (
    RecordDetail as RecordDetailData,
)
from automation.ui.browser.browser_logic import (
    load_record,
    load_related_records,
    resolve_fk_label,
)
from automation.ui.browser.related_records import RelatedRecordsPanel


class RecordDetailView(QWidget):
    """Form layout for record display (Section 14.8.2).

    :param parent: Parent widget.
    """

    navigate_to_record = Signal(str, int)  # table_name, record_id
    edit_requested = Signal()
    delete_requested = Signal()
    new_record_requested = Signal()
    history_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._record: RecordDetailData | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Action bar
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(8, 4, 8, 4)

        self._new_btn = QPushButton("New Record")
        self._new_btn.setStyleSheet(
            "QPushButton { background-color: #FFA726; color: white; "
            "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
            "QPushButton:hover { background-color: #FB8C00; }"
        )
        self._new_btn.clicked.connect(self.new_record_requested.emit)
        action_bar.addWidget(self._new_btn)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        self._edit_btn.clicked.connect(self.edit_requested.emit)
        action_bar.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setStyleSheet(
            "QPushButton { background-color: #C62828; color: white; "
            "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
            "QPushButton:hover { background-color: #B71C1C; }"
        )
        self._delete_btn.clicked.connect(self.delete_requested.emit)
        action_bar.addWidget(self._delete_btn)

        self._history_btn = QPushButton("History")
        self._history_btn.setStyleSheet(
            "QPushButton { padding: 6px 12px; font-size: 12px; }"
        )
        self._history_btn.clicked.connect(self.history_requested.emit)
        action_bar.addWidget(self._history_btn)

        action_bar.addStretch()
        layout.addLayout(action_bar)

        # Scroll area for form + related records
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 0, 8, 8)

        # Title
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F3864; padding: 4px;")
        self._content_layout.addWidget(self._title)

        # Form area
        self._form_widget = QWidget()
        self._form_layout = QFormLayout(self._form_widget)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self._form_widget)

        # Related records area
        self._related_widget = QWidget()
        self._related_layout = QVBoxLayout(self._related_widget)
        self._related_layout.setContentsMargins(0, 8, 0, 0)
        self._content_layout.addWidget(self._related_widget)

        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        layout.addWidget(scroll, stretch=1)

    def load_record(
        self, conn: sqlite3.Connection, table_name: str, record_id: int
    ) -> None:
        """Load and display a record.

        :param conn: Client database connection.
        :param table_name: Table name.
        :param record_id: Record ID.
        """
        self._conn = conn
        self._record = load_record(conn, table_name, record_id)

        self._clear_form()

        if not self._record:
            self._title.setText(f"{table_name} #{record_id} — not found")
            return

        self._title.setText(f"{table_name} #{record_id}")

        # Populate form fields
        for col_info in self._record.columns:
            value = self._record.values.get(col_info.name)
            label = QLabel(col_info.name)
            label.setStyleSheet("font-size: 11px; font-weight: bold; color: #424242;")

            if col_info.is_fk and value is not None:
                # FK link
                fk_label = resolve_fk_label(conn, col_info.fk_table, value)
                link = QPushButton(fk_label)
                link.setStyleSheet(
                    "font-size: 11px; border: none; color: #1565C0; "
                    "text-decoration: underline; padding: 0; text-align: left;"
                )
                link.setCursor(Qt.CursorShape.PointingHandCursor)
                fk_table = col_info.fk_table
                fk_id = value
                link.clicked.connect(
                    lambda checked, t=fk_table, i=fk_id: self.navigate_to_record.emit(t, i)
                )
                self._form_layout.addRow(label, link)
            else:
                # Plain value
                val_label = QLabel(str(value) if value is not None else "—")
                val_label.setStyleSheet("font-size: 11px;")
                val_label.setWordWrap(True)
                self._form_layout.addRow(label, val_label)

        # Related records
        self._load_related(conn, table_name, record_id)

    @property
    def current_record(self) -> RecordDetailData | None:
        """The currently displayed record."""
        return self._record

    def _clear_form(self) -> None:
        """Clear the form layout."""
        while self._form_layout.count():
            child = self._form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        while self._related_layout.count():
            child = self._related_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _load_related(
        self, conn: sqlite3.Connection, table_name: str, record_id: int
    ) -> None:
        """Load and display related records."""
        groups = load_related_records(conn, table_name, record_id)
        if not groups:
            return

        header = QLabel("Related Records")
        header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1F3864; padding: 4px 0;"
        )
        self._related_layout.addWidget(header)

        for group in groups:
            panel = RelatedRecordsPanel(group, conn)
            panel.navigate_to_record.connect(self.navigate_to_record.emit)
            self._related_layout.addWidget(panel)
