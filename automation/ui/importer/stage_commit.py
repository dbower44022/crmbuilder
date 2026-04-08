"""Stage 6 — Commit (Section 14.5.6).

Commit confirmation and result display.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class StageCommit(QWidget):
    """Stage 6 — Commit confirmation.

    :param create_count: Number of records to create.
    :param update_count: Number of records to update.
    :param reject_count: Number of rejected records.
    :param parent: Parent widget.
    """

    confirmed = Signal()
    cancelled = Signal()

    def __init__(
        self,
        create_count: int,
        update_count: int,
        reject_count: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Commit Confirmation")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1F3864; padding: 8px 0;"
        )
        layout.addWidget(header)

        summary = QLabel(
            f"Records to create: {create_count}\n"
            f"Records to update: {update_count}\n"
            f"Records rejected: {reject_count}"
        )
        summary.setStyleSheet(
            "font-size: 12px; padding: 8px; "
            "background-color: #F2F7FB; border-radius: 4px;"
        )
        layout.addWidget(summary)

        # Buttons
        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("Confirm Commit")
        confirm_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 8px 16px; font-size: 13px; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        confirm_btn.clicked.connect(self.confirmed.emit)
        btn_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("font-size: 13px; padding: 8px 16px;")
        cancel_btn.clicked.connect(self.cancelled.emit)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()


class CommitResultDisplay(QWidget):
    """Display commit results after successful commit.

    :param created_count: Records created.
    :param updated_count: Records updated.
    :param rejected_count: Records rejected.
    :param import_status: The AISession import_status.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        created_count: int,
        updated_count: int,
        rejected_count: int,
        import_status: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Commit Successful")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #2E7D32; padding: 8px 0;"
        )
        layout.addWidget(header)

        results = QLabel(
            f"Created: {created_count}\n"
            f"Updated: {updated_count}\n"
            f"Rejected: {rejected_count}\n"
            f"Import status: {import_status}"
        )
        results.setStyleSheet(
            "font-size: 12px; padding: 8px; "
            "background-color: #E8F5E9; border-radius: 4px;"
        )
        layout.addWidget(results)
        layout.addStretch()
