"""Inline pipeline progress display (Section 14.7.4).

Shows the six stages of generation with visual progress indicators.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.toast import show_toast
from automation.ui.documents.generation_logic import (
    STAGE_LABELS,
    GenerationProgress,
    GenerationStage,
    GenerationState,
)

_STAGE_COMPLETE_STYLE = "font-size: 10px; color: #2E7D32; font-weight: bold;"
_STAGE_CURRENT_STYLE = "font-size: 10px; color: #1565C0; font-weight: bold;"
_STAGE_PENDING_STYLE = "font-size: 10px; color: #BDBDBD;"
_STAGE_PAUSED_STYLE = "font-size: 10px; color: #E65100; font-weight: bold;"

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 4px 10px; font-size: 11px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)


class GenerationFlow(QWidget):
    """Inline pipeline progress display.

    :param progress: The current generation progress.
    :param parent: Parent widget.
    """

    def __init__(self, progress: GenerationProgress, parent=None) -> None:
        super().__init__(parent)
        self._progress = progress

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 4, 8, 4)

        # Stage indicators
        self._stage_row = QHBoxLayout()
        self._stage_labels: dict[GenerationStage, QLabel] = {}
        for stage in progress.applicable_stages:
            label = QLabel(STAGE_LABELS[stage])
            self._stage_labels[stage] = label
            self._stage_row.addWidget(label)
            # Arrow separator
            if stage != progress.applicable_stages[-1]:
                arrow = QLabel("→")
                arrow.setStyleSheet("font-size: 10px; color: #BDBDBD;")
                self._stage_row.addWidget(arrow)
        self._stage_row.addStretch()
        layout.addLayout(self._stage_row)

        # Warning area
        self._warning_area = QWidget()
        self._warning_area.setVisible(False)
        warning_layout = QVBoxLayout(self._warning_area)
        warning_layout.setContentsMargins(0, 4, 0, 4)
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet("font-size: 11px; color: #E65100;")
        self._warning_label.setWordWrap(True)
        warning_layout.addWidget(self._warning_label)

        btn_row = QHBoxLayout()
        self._proceed_btn = QPushButton("Proceed")
        self._proceed_btn.setStyleSheet(_PRIMARY_STYLE)
        btn_row.addWidget(self._proceed_btn)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(
            "QPushButton { padding: 4px 10px; font-size: 11px; }"
        )
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        warning_layout.addLayout(btn_row)
        layout.addWidget(self._warning_area)

        # Completion area
        self._completion_area = QWidget()
        self._completion_area.setVisible(False)
        completion_layout = QVBoxLayout(self._completion_area)
        completion_layout.setContentsMargins(0, 4, 0, 4)
        self._completion_label = QLabel()
        self._completion_label.setStyleSheet("font-size: 11px; color: #2E7D32;")
        completion_layout.addWidget(self._completion_label)

        completion_actions = QHBoxLayout()
        self._open_file_btn = QPushButton("Open File")
        self._open_file_btn.setStyleSheet(_PRIMARY_STYLE)
        self._open_file_btn.clicked.connect(self._on_open_file)
        completion_actions.addWidget(self._open_file_btn)
        self._push_btn = QPushButton("Push to Remote")
        self._push_btn.setStyleSheet(_PRIMARY_STYLE)
        completion_actions.addWidget(self._push_btn)
        completion_actions.addStretch()
        completion_layout.addLayout(completion_actions)
        layout.addWidget(self._completion_area)

        # Error area
        self._error_label = QLabel()
        self._error_label.setStyleSheet("font-size: 11px; color: #C62828;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        self._update_display()

    def update_progress(self, progress: GenerationProgress) -> None:
        """Update the display with new progress.

        :param progress: Updated generation progress.
        """
        self._progress = progress
        self._update_display()

    def _update_display(self) -> None:
        """Refresh the visual state of all stage indicators."""
        p = self._progress

        for stage, label in self._stage_labels.items():
            if stage in p.completed_stages:
                label.setStyleSheet(_STAGE_COMPLETE_STYLE)
                label.setText(f"✓ {STAGE_LABELS[stage]}")
            elif stage == p.current_stage:
                if p.state == GenerationState.PAUSED_WARNINGS:
                    label.setStyleSheet(_STAGE_PAUSED_STYLE)
                    label.setText(f"⚠ {STAGE_LABELS[stage]}")
                else:
                    label.setStyleSheet(_STAGE_CURRENT_STYLE)
                    label.setText(f"● {STAGE_LABELS[stage]}")
            else:
                label.setStyleSheet(_STAGE_PENDING_STYLE)
                label.setText(STAGE_LABELS[stage])

        # Warning area
        self._warning_area.setVisible(p.state == GenerationState.PAUSED_WARNINGS)
        if p.warnings:
            self._warning_label.setText(
                "Validation warnings:\n" + "\n".join(f"  • {w}" for w in p.warnings)
            )

        # Completion area
        self._completion_area.setVisible(p.state == GenerationState.COMPLETED)
        if p.state == GenerationState.COMPLETED:
            parts = []
            if p.file_path:
                parts.append(f"File: {p.file_path}")
            if p.git_commit_hash:
                parts.append(f"Commit: {p.git_commit_hash[:7]}")
            if p.warnings:
                parts.append(f"Warnings accepted: {len(p.warnings)}")
            self._completion_label.setText("Generation complete. " + " | ".join(parts))

        # Error area
        self._error_label.setVisible(p.state == GenerationState.FAILED)
        if p.error:
            self._error_label.setText(f"Generation failed: {p.error}")

    def _on_open_file(self) -> None:
        """Open the generated file in the system default application."""
        if self._progress.file_path:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._progress.file_path))
        else:
            show_toast(self, "No file path available")
