"""Pipeline progress indicator (Section 14.5.1).

Seven horizontal pill widgets showing the import pipeline stages.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from automation.ui.importer.import_logic import STAGE_ORDER, ImportStage

_ACTIVE_STYLE = (
    "background-color: #1F3864; color: white; "
    "border-radius: 10px; padding: 4px 12px; font-size: 11px; font-weight: bold;"
)
_COMPLETED_STYLE = (
    "background-color: #F2F7FB; color: #2E7D32; "
    "border-radius: 10px; padding: 4px 12px; font-size: 11px;"
)
_PENDING_STYLE = (
    "background-color: #F5F5F5; color: #9E9E9E; "
    "border-radius: 10px; padding: 4px 12px; font-size: 11px;"
)


class ProgressIndicator(QWidget):
    """Horizontal progress indicator for the 7 pipeline stages.

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._pills: dict[ImportStage, QLabel] = {}
        for stage in STAGE_ORDER:
            pill = QLabel(stage.value)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(_PENDING_STYLE)
            layout.addWidget(pill)
            self._pills[stage] = pill

        # Set initial state
        self.update_stage(ImportStage.RECEIVE, set())

    def update_stage(
        self, current: ImportStage, completed: set[ImportStage]
    ) -> None:
        """Update the indicator to reflect the current stage.

        :param current: The currently active stage.
        :param completed: Set of completed stages.
        """
        for stage, pill in self._pills.items():
            if stage in completed:
                pill.setText(f"\u2713 {stage.value}")
                pill.setStyleSheet(_COMPLETED_STYLE)
            elif stage == current:
                pill.setStyleSheet(_ACTIVE_STYLE)
                pill.setText(stage.value)
            else:
                pill.setText(stage.value)
                pill.setStyleSheet(_PENDING_STYLE)
