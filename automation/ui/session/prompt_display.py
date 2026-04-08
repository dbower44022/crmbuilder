"""Prompt display with collapsible sections (Section 14.4.3).

Six collapsible panels, copy-to-clipboard, and summary bar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.toast import show_toast
from automation.ui.session.session_logic import PromptAnalysis, PromptSection


class CollapsibleSection(QWidget):
    """A collapsible panel for a single prompt section.

    :param section: The prompt section data.
    :param parent: Parent widget.
    """

    def __init__(self, section: PromptSection, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Header with toggle
        header = QHBoxLayout()
        self._toggle = QPushButton(f"+ {section.name}")
        self._toggle.setStyleSheet(
            "QPushButton { text-align: left; font-size: 12px; font-weight: bold; "
            "border: none; padding: 6px 8px; background-color: #F5F5F5; "
            "border-radius: 2px; } "
            "QPushButton:hover { background-color: #EEEEEE; }"
        )
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._on_toggle)
        header.addWidget(self._toggle, stretch=1)

        token_label = QLabel(f"~{section.estimated_tokens:,} tokens")
        token_label.setStyleSheet("font-size: 11px; color: #757575; padding: 0 8px;")
        header.addWidget(token_label)

        layout.addLayout(header)

        # Content (collapsed by default)
        self._content = QPlainTextEdit()
        self._content.setPlainText(section.text)
        self._content.setReadOnly(True)
        self._content.setStyleSheet(
            "font-size: 11px; font-family: monospace; "
            "background-color: #FAFAFA; border: 1px solid #E0E0E0; "
            "padding: 8px;"
        )
        self._content.setVisible(False)
        layout.addWidget(self._content)

        self._section_name = section.name
        self._expanded = False

    def _on_toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        prefix = "-" if self._expanded else "+"
        self._toggle.setText(f"{prefix} {self._section_name}")


class PromptDisplay(QWidget):
    """Displays the assembled prompt with collapsible sections.

    :param analysis: The prompt analysis result.
    :param full_prompt: The complete prompt text for clipboard copy.
    :param parent: Parent widget.
    """

    return_requested = Signal = None  # Set by SessionView

    def __init__(
        self,
        analysis: PromptAnalysis,
        full_prompt: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._full_prompt = full_prompt

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Summary bar
        summary_parts = [
            f"Total: ~{analysis.total_tokens:,} tokens",
            f"Context: {analysis.context_percentage:.1f}% of 200K",
        ]
        summary_text = "  |  ".join(summary_parts)

        summary_label = QLabel(summary_text)
        if analysis.over_capacity:
            summary_label.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #C62828; "
                "padding: 8px; background-color: #FFEBEE; border-radius: 4px;"
            )
        else:
            summary_label.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #1F3864; "
                "padding: 8px; background-color: #F2F7FB; border-radius: 4px;"
            )
        layout.addWidget(summary_label)

        # Reduction strategies
        if analysis.reduction_strategies:
            for strategy in analysis.reduction_strategies:
                strat_label = QLabel(f"  - {strategy}")
                if strategy.startswith("WARNING"):
                    strat_label.setStyleSheet(
                        "font-size: 11px; color: #C62828; padding: 2px 12px;"
                    )
                else:
                    strat_label.setStyleSheet(
                        "font-size: 11px; color: #E65100; padding: 2px 12px;"
                    )
                layout.addWidget(strat_label)

        # Copy to Clipboard button
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setStyleSheet(
            "QPushButton { background-color: #1565C0; color: white; "
            "border-radius: 4px; padding: 8px 16px; font-size: 13px; } "
            "QPushButton:hover { background-color: #0D47A1; }"
        )
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(self._copy_btn)

        # Collapsible sections in scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        sections_widget = QWidget()
        sections_layout = QVBoxLayout(sections_widget)
        sections_layout.setContentsMargins(0, 0, 0, 0)

        for section in analysis.sections:
            sections_layout.addWidget(CollapsibleSection(section))

        sections_layout.addStretch()
        scroll.setWidget(sections_widget)
        layout.addWidget(scroll, stretch=1)

        # Return link
        return_btn = QPushButton("Return to Work Item")
        return_btn.setStyleSheet(
            "font-size: 12px; border: none; color: #1565C0; "
            "text-decoration: underline; padding: 8px;"
        )
        return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return_btn.clicked.connect(self._on_return)
        layout.addWidget(return_btn)

        self._return_callback = None

    def set_return_callback(self, callback) -> None:
        """Set the callback for the return action.

        :param callback: Callable invoked when "Return to Work Item" is clicked.
        """
        self._return_callback = callback

    def _copy_to_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self._full_prompt)
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("Copy to Clipboard"))
        show_toast(self, "Prompt copied to clipboard")

    def _on_return(self) -> None:
        if self._return_callback:
            self._return_callback()
