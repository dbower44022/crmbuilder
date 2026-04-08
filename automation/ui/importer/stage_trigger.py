"""Stage 7 — Trigger (Section 14.5.7).

Displays downstream trigger results with checkmarks, including
impact analysis using the shared presentation format.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from automation.importer.triggers import TriggerResult


class TriggerStep(QWidget):
    """A single trigger step with checkmark on completion.

    :param label: Description of the trigger.
    :param parent: Parent widget.
    """

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)

        self._check = QLabel("\u2713")
        self._check.setStyleSheet("font-size: 14px; color: #2E7D32; font-weight: bold;")
        self._check.setVisible(False)
        layout.addWidget(self._check)

        self._spinner = QLabel("\u25cb")
        self._spinner.setStyleSheet("font-size: 14px; color: #757575;")
        layout.addWidget(self._spinner)

        self._label = QLabel(label)
        self._label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._label, stretch=1)

    def mark_complete(self) -> None:
        """Show the checkmark."""
        self._check.setVisible(True)
        self._spinner.setVisible(False)

    def mark_error(self, message: str) -> None:
        """Show an error indicator."""
        self._spinner.setText("\u2717")
        self._spinner.setStyleSheet("font-size: 14px; color: #C62828; font-weight: bold;")
        self._label.setText(f"{self._label.text()} — {message}")
        self._label.setStyleSheet("font-size: 12px; color: #C62828;")


class StageTrigger(QWidget):
    """Stage 7 — Trigger: display downstream trigger results.

    :param trigger_result: The TriggerResult from ImportProcessor.trigger().
    :param parent: Parent widget.
    """

    return_requested = Signal()

    def __init__(self, trigger_result: TriggerResult, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Downstream Triggers")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1F3864; padding: 8px 0;"
        )
        layout.addWidget(header)

        # Graph construction
        if trigger_result.graph_constructed:
            step = TriggerStep("Dependency graph construction")
            step.mark_complete()
            layout.addWidget(step)

        # Work item completion
        if trigger_result.work_item_completed:
            step = TriggerStep("Work item marked complete")
            step.mark_complete()
            layout.addWidget(step)

        # Downstream recalculation
        if trigger_result.downstream_affected:
            count = len(trigger_result.downstream_affected)
            step = TriggerStep(
                f"Downstream status recalculation ({count} item(s) affected)"
            )
            step.mark_complete()
            layout.addWidget(step)

        # Impact analysis
        if trigger_result.impact_analysis_queued:
            step = TriggerStep("Impact analysis queued")
            step.mark_complete()
            layout.addWidget(step)

        # Errors
        if trigger_result.errors:
            for err in trigger_result.errors:
                step = TriggerStep("Trigger")
                step.mark_error(err)
                layout.addWidget(step)

            warning = QLabel(
                "Trigger errors do not affect committed data. "
                "You may retry or return to the work item."
            )
            warning.setStyleSheet(
                "font-size: 11px; color: #E65100; padding: 8px; "
                "background-color: #FFF3E0; border-radius: 4px;"
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)

        if not trigger_result.graph_constructed and \
           not trigger_result.work_item_completed and \
           not trigger_result.downstream_affected and \
           not trigger_result.impact_analysis_queued and \
           not trigger_result.errors:
            no_triggers = QLabel("No downstream triggers were executed.")
            no_triggers.setStyleSheet("font-size: 12px; color: #757575; padding: 8px;")
            layout.addWidget(no_triggers)

        layout.addSpacing(16)

        # Return link
        return_btn = QPushButton("Return to Work Item")
        return_btn.setStyleSheet(
            "font-size: 12px; border: none; color: #1565C0; "
            "text-decoration: underline; padding: 8px;"
        )
        return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return_btn.clicked.connect(self.return_requested.emit)
        layout.addWidget(return_btn)

        layout.addStretch()
