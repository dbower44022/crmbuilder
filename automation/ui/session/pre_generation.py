"""Pre-generation configuration (Section 14.4.1).

Displays configuration options before prompt generation,
varying by session type (initial, revision, clarification).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.impact.impact_logic import get_revision_reason


class PreGenerationConfig(QWidget):
    """Pre-generation configuration panel.

    :param work_item_id: The work item ID.
    :param session_type: "initial", "revision", or "clarification".
    :param item_type: The work item type.
    :param phase_name: The phase display name.
    :param work_item_name: Human-readable work item name.
    :param parent: Parent widget.
    """

    generate_requested = Signal(str, str, str)  # (session_type, revision_reason, clarification_topic)

    def __init__(
        self,
        work_item_id: int,
        session_type: str,
        item_type: str,
        phase_name: str,
        work_item_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_type = session_type

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header info
        info_label = QLabel(
            f"<b>{work_item_name}</b><br>"
            f"Type: {item_type.replace('_', ' ').title()} | Phase: {phase_name}"
        )
        info_label.setStyleSheet("font-size: 13px; padding: 8px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._revision_edit: QPlainTextEdit | None = None
        self._change_edit: QPlainTextEdit | None = None
        self._clarification_edit: QPlainTextEdit | None = None

        if session_type == "initial":
            desc = QLabel("Generate an initial prompt for this work item.")
            desc.setStyleSheet("font-size: 12px; color: #424242; padding: 4px 8px;")
            layout.addWidget(desc)

        elif session_type == "revision":
            # Show revision reason (from ISS-013 cache or editable)
            stored_reason = get_revision_reason(work_item_id) or ""

            reason_label = QLabel("Revision Reason:")
            reason_label.setStyleSheet("font-size: 12px; font-weight: bold; padding-top: 8px;")
            layout.addWidget(reason_label)

            self._revision_edit = QPlainTextEdit()
            self._revision_edit.setPlainText(stored_reason)
            self._revision_edit.setPlaceholderText(
                "Why is this work item being revised?"
            )
            self._revision_edit.setMaximumHeight(80)
            layout.addWidget(self._revision_edit)

            change_label = QLabel("Change Instructions:")
            change_label.setStyleSheet("font-size: 12px; font-weight: bold; padding-top: 4px;")
            layout.addWidget(change_label)

            self._change_edit = QPlainTextEdit()
            self._change_edit.setPlaceholderText(
                "What specifically needs to change in this revision?"
            )
            self._change_edit.setMaximumHeight(80)
            layout.addWidget(self._change_edit)

        elif session_type == "clarification":
            topic_label = QLabel("Clarification Topic:")
            topic_label.setStyleSheet("font-size: 12px; font-weight: bold; padding-top: 8px;")
            layout.addWidget(topic_label)

            self._clarification_edit = QPlainTextEdit()
            self._clarification_edit.setPlaceholderText(
                "What question or topic needs clarification?"
            )
            self._clarification_edit.setMaximumHeight(100)
            layout.addWidget(self._clarification_edit)

        # Generate button
        layout.addSpacing(8)
        gen_btn = QPushButton("Generate Prompt")
        gen_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 8px 16px; font-size: 13px; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        gen_btn.clicked.connect(self._on_generate)
        layout.addWidget(gen_btn)

        layout.addStretch()

    def _on_generate(self) -> None:
        """Emit the generate_requested signal with collected parameters."""
        revision_reason = ""
        clarification_topic = ""

        if self._session_type == "revision":
            revision_reason = (
                self._revision_edit.toPlainText().strip() if self._revision_edit else ""
            )
            if self._change_edit:
                change_text = self._change_edit.toPlainText().strip()
                if change_text:
                    if revision_reason:
                        revision_reason += f"\n\nChange instructions: {change_text}"
                    else:
                        revision_reason = change_text

        elif self._session_type == "clarification":
            clarification_topic = (
                self._clarification_edit.toPlainText().strip()
                if self._clarification_edit else ""
            )

        self.generate_requested.emit(
            self._session_type, revision_reason, clarification_topic
        )
