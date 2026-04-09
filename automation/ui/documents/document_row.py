"""Single document entry widget (Section 14.7.1).

Displays one document in the inventory with status, actions, and
optional staleness expansion.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.status_badges import StatusBadge
from automation.ui.common.toast import show_toast
from automation.ui.documents.documents_logic import DocumentEntry, DocumentStatus

_STATUS_COLORS = {
    DocumentStatus.STALE: ("#E65100", "#FFF3E0"),
    DocumentStatus.CURRENT: ("#2E7D32", "#E8F5E9"),
    DocumentStatus.DRAFT_ONLY: ("#1565C0", "#E3F2FD"),
    DocumentStatus.NOT_GENERATED: ("#757575", "#F5F5F5"),
}

_STATUS_LABELS = {
    DocumentStatus.STALE: "Stale",
    DocumentStatus.CURRENT: "Current",
    DocumentStatus.DRAFT_ONLY: "Draft Only",
    DocumentStatus.NOT_GENERATED: "Not Generated",
}

# Warm orange for secondary buttons per feedback_button_styling.md
_ACTION_STYLE = (
    "QPushButton { background-color: #FFA726; color: white; "
    "border-radius: 4px; padding: 4px 10px; font-size: 11px; } "
    "QPushButton:hover { background-color: #FB8C00; }"
)


class DocumentRow(QWidget):
    """A single document entry in the inventory.

    :param entry: The document entry data.
    :param parent: Parent widget.
    """

    generate_final_requested = Signal(int)  # work_item_id
    generate_draft_requested = Signal(int)  # work_item_id
    selection_changed = Signal()

    def __init__(self, entry: DocumentEntry, parent=None) -> None:
        super().__init__(parent)
        self._entry = entry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Main row
        row = QHBoxLayout()

        # Checkbox for batch selection
        self._checkbox = QCheckBox()
        self._checkbox.stateChanged.connect(lambda: self.selection_changed.emit())
        row.addWidget(self._checkbox)

        # Document name (human-readable-first)
        name_label = QLabel(entry.document_name)
        name_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        row.addWidget(name_label)

        # Work item status badge
        wi_badge = StatusBadge()
        wi_badge.set_status(entry.work_item_status)
        row.addWidget(wi_badge)

        # Document status badge
        fg, bg = _STATUS_COLORS.get(entry.document_status, ("#757575", "#F5F5F5"))
        doc_status_label = QLabel(_STATUS_LABELS.get(entry.document_status, "Unknown"))
        doc_status_label.setStyleSheet(
            f"font-size: 11px; color: {fg}; background-color: {bg}; "
            f"padding: 2px 6px; border-radius: 3px;"
        )
        row.addWidget(doc_status_label)

        # Last generated timestamp
        if entry.last_generated_at:
            ts_label = QLabel(entry.last_generated_at[:16])
            ts_label.setStyleSheet("font-size: 10px; color: #757575;")
            row.addWidget(ts_label)

        # File path
        if entry.file_path:
            path_label = QLabel(entry.file_path)
            path_label.setStyleSheet("font-size: 10px; color: #9E9E9E;")
            path_label.setMaximumWidth(200)
            path_label.setToolTip(entry.file_path)
            row.addWidget(path_label)

        row.addStretch()

        # Action buttons — never disabled per Section 14.10.6
        gen_final_btn = QPushButton("Generate Final")
        gen_final_btn.setStyleSheet(_ACTION_STYLE)
        gen_final_btn.clicked.connect(self._on_generate_final)
        row.addWidget(gen_final_btn)

        gen_draft_btn = QPushButton("Generate Draft")
        gen_draft_btn.setStyleSheet(_ACTION_STYLE)
        gen_draft_btn.clicked.connect(self._on_generate_draft)
        row.addWidget(gen_draft_btn)

        layout.addLayout(row)

        # Staleness expansion (shown only for stale documents)
        if entry.document_status == DocumentStatus.STALE and entry.change_count > 0:
            from automation.ui.documents.staleness_expansion import StalenessExpansion
            self._staleness = StalenessExpansion(entry)
            layout.addWidget(self._staleness)

        self.setStyleSheet(
            "DocumentRow { border-bottom: 1px solid #E0E0E0; }"
        )

    @property
    def is_selected(self) -> bool:
        """Whether this row's checkbox is checked."""
        return self._checkbox.isChecked()

    @is_selected.setter
    def is_selected(self, value: bool) -> None:
        self._checkbox.setChecked(value)

    @property
    def entry(self) -> DocumentEntry:
        """The document entry data."""
        return self._entry

    def _on_generate_final(self) -> None:
        """Handle Generate Final click."""
        if self._entry.work_item_status != "complete":
            show_toast(
                self,
                "Generate Final requires the work item to be in 'complete' status. "
                f"Current status: {self._entry.work_item_status}",
            )
            return
        self.generate_final_requested.emit(self._entry.work_item_id)

    def _on_generate_draft(self) -> None:
        """Handle Generate Draft click."""
        if self._entry.work_item_status != "in_progress":
            show_toast(
                self,
                "Generate Draft requires the work item to be in 'in_progress' status. "
                f"Current status: {self._entry.work_item_status}",
            )
            return
        self.generate_draft_requested.emit(self._entry.work_item_id)
