"""Pre-commit confirmation dialog (Section 14.6.4).

Modal dialog showing the impact set of a proposed direct edit.
Implemented in Step 15b; called by the Data Browser in Step 15c.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automation.impact.precommit import ProposedImpact
from automation.ui.impact.impact_logic import (
    ImpactDisplayRow,
    ImpactSummary,
    group_impacts_by_table,
)
from automation.ui.impact.shared_presentation import (
    ImpactSummaryHeader,
    ImpactTableGroup,
)


class PrecommitConfirmDialog(QDialog):
    """Pre-commit impact confirmation dialog.

    Shows the proposed impacts and collects a rationale. Returns the
    rationale on accept, or None on cancel.

    Step 15c's Data Browser will call this. Step 15b implements and
    tests it with hand-built ProposedImpact lists.

    :param proposed_impacts: List of ProposedImpact from
        ImpactAnalysisEngine.analyze_proposed_change().
    :param parent: Parent widget.
    """

    def __init__(
        self,
        proposed_impacts: list[ProposedImpact],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Change — Impact Analysis")
        self.setMinimumSize(600, 400)
        self._rationale: str | None = None

        layout = QVBoxLayout(self)

        # Convert ProposedImpact to ImpactDisplayRow for shared presentation
        display_rows = _to_display_rows(proposed_impacts)

        if display_rows:
            # Count affected tables
            tables = {r.affected_table for r in display_rows}
            scope_label = QLabel(
                f"This change affects {len(display_rows)} downstream "
                f"record{'s' if len(display_rows) != 1 else ''} across "
                f"{len(tables)} table{'s' if len(tables) != 1 else ''}."
            )
            scope_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #1F3864; padding: 8px;"
            )
            scope_label.setWordWrap(True)
            layout.addWidget(scope_label)

            # Impact display in scrollable area (no review status — pre-commit)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(0, 0, 0, 0)

            # Summary header without reviewed count
            summary = ImpactSummary(
                total=len(display_rows),
                requires_review=sum(1 for r in display_rows if r.requires_review),
                informational=sum(1 for r in display_rows if not r.requires_review),
                reviewed=0,
            )
            content_layout.addWidget(ImpactSummaryHeader(summary, show_reviewed=False))

            # Grouped by table
            groups = group_impacts_by_table(display_rows)
            for table_name in sorted(groups.keys()):
                review_list, info_list = groups[table_name]
                content_layout.addWidget(
                    ImpactTableGroup(
                        table_name, review_list, info_list,
                        show_review_status=False,
                    )
                )
            content_layout.addStretch()
            scroll.setWidget(content)
            layout.addWidget(scroll, stretch=1)

            # Rationale (required when impacts exist)
            rationale_label = QLabel("Rationale (required):")
            rationale_label.setStyleSheet("font-size: 12px; font-weight: bold; padding-top: 8px;")
            layout.addWidget(rationale_label)
        else:
            empty = QLabel("No downstream records are affected by this change.")
            empty.setStyleSheet("font-size: 13px; color: #757575; padding: 16px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)

            # Rationale (optional when no impacts)
            rationale_label = QLabel("Rationale (optional):")
            rationale_label.setStyleSheet("font-size: 12px; padding-top: 8px;")
            layout.addWidget(rationale_label)

        self._rationale_edit = QPlainTextEdit()
        self._rationale_edit.setPlaceholderText("Explain the reason for this change...")
        self._rationale_edit.setMaximumHeight(80)
        layout.addWidget(self._rationale_edit)

        self._has_impacts = bool(display_rows)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirm")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        """Validate rationale and accept."""
        text = self._rationale_edit.toPlainText().strip()
        if self._has_impacts and not text:
            from automation.ui.common.error_display import show_warning
            show_warning(
                self, "Rationale Required",
                "A rationale is required when downstream records are affected."
            )
            return
        self._rationale = text or None
        self.accept()

    def get_rationale(self) -> str | None:
        """Return the entered rationale after dialog acceptance.

        :returns: The rationale text, or None if dialog was cancelled.
        """
        return self._rationale


def _to_display_rows(proposed: list[ProposedImpact]) -> list[ImpactDisplayRow]:
    """Convert ProposedImpact objects to ImpactDisplayRow for display."""
    return [
        ImpactDisplayRow(
            id=0,
            change_log_id=0,
            affected_table=p.affected_table,
            affected_record_id=p.affected_record_id,
            impact_description=p.impact_description,
            requires_review=p.requires_review,
            reviewed=False,
            reviewed_at=None,
            action_required=False,
            source_summary="Proposed change",
        )
        for p in proposed
    ]
