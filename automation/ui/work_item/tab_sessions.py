"""Sessions tab (Section 14.3.5).

Read-only display of AI session records.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.work_item.work_item_logic import SessionRow


class SessionCard(QWidget):
    """An expandable card for a single AI session.

    :param session: The session data.
    :param work_item_id: The owning work item ID (used for navigation).
    :param parent: Parent widget.
    """

    generate_requested = Signal(int)  # Emits work_item_id

    def __init__(self, session: SessionRow, work_item_id: int = 0, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._work_item_id = work_item_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Summary row
        summary = QHBoxLayout()
        type_label = QLabel(session.session_type.title())
        type_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        summary.addWidget(type_label)

        date_label = QLabel(session.started_at[:10] if session.started_at else "")
        date_label.setStyleSheet("font-size: 11px; color: #757575;")
        summary.addWidget(date_label)

        status_label = QLabel(session.import_status)
        status_label.setStyleSheet("font-size: 11px; color: #757575;")
        summary.addWidget(status_label)

        summary.addStretch()

        # Expand/collapse
        self._toggle_btn = QPushButton("Expand")
        self._toggle_btn.setStyleSheet("font-size: 11px;")
        self._toggle_btn.clicked.connect(self._toggle)
        summary.addWidget(self._toggle_btn)

        layout.addLayout(summary)

        # Detail area (hidden by default)
        self._detail = QWidget()
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(0, 4, 0, 0)

        if session.notes:
            notes_label = QLabel(f"Notes: {session.notes}")
            notes_label.setStyleSheet("font-size: 11px; color: #424242;")
            notes_label.setWordWrap(True)
            detail_layout.addWidget(notes_label)

        # Prompt context summary (truncated)
        prompt_preview = session.generated_prompt[:200]
        if len(session.generated_prompt) > 200:
            prompt_preview += "..."
        prompt_label = QLabel(f"Prompt: {prompt_preview}")
        prompt_label.setStyleSheet("font-size: 11px; color: #757575;")
        prompt_label.setWordWrap(True)
        detail_layout.addWidget(prompt_label)

        # View Raw Output button
        if session.raw_output:
            view_btn = QPushButton("View Raw Output")
            view_btn.setStyleSheet("font-size: 11px;")
            view_btn.clicked.connect(self._show_raw_output)
            detail_layout.addWidget(view_btn)

        # Generate Prompt for unprocessed clarification sessions
        if session.session_type == "clarification" and session.import_status == "pending":
            gen_btn = QPushButton("Generate Prompt")
            gen_btn.setStyleSheet("font-size: 11px;")
            gen_btn.clicked.connect(
                lambda: self.generate_requested.emit(self._work_item_id)
            )
            detail_layout.addWidget(gen_btn)

        self._detail.setVisible(False)
        layout.addWidget(self._detail)

    def _toggle(self) -> None:
        visible = not self._detail.isVisible()
        self._detail.setVisible(visible)
        self._toggle_btn.setText("Collapse" if visible else "Expand")

    def _show_raw_output(self) -> None:
        """Show raw output in a scrollable text display."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Raw Session Output")
        dialog.setMinimumSize(600, 400)
        dlayout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setPlainText(self._session.raw_output or "")
        text.setReadOnly(True)
        dlayout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        dlayout.addWidget(buttons)
        dialog.exec()


class SessionsTab(QWidget):
    """Tab showing AI session history.

    :param parent: Parent widget.
    """

    navigate_to_session = Signal(int)  # Emits work_item_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def update_sessions(self, sessions: list[SessionRow], work_item_id: int = 0) -> None:
        """Refresh the tab with new session data.

        :param sessions: Session rows, descending by date.
        :param work_item_id: The owning work item ID (for navigation).
        """
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if sessions:
            for session in sessions:
                card = SessionCard(session, work_item_id)
                card.generate_requested.connect(self.navigate_to_session.emit)
                self._layout.addWidget(card)
        else:
            empty = QLabel("No sessions recorded")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._layout.addWidget(empty)

        self._layout.addStretch()
