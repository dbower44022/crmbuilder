"""Impacts tab (Section 14.3.7).

Shows change impact records where this work item is affected.
Review actions are placeholders for Step 15b.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from automation.ui.common.toast import show_toast
from automation.ui.work_item.work_item_logic import ImpactRow


class ImpactCard(QWidget):
    """A card for a single change impact.

    :param impact: The impact data.
    :param parent: Parent widget.
    """

    def __init__(self, impact: ImpactRow, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Top row
        top = QHBoxLayout()
        desc_label = QLabel(impact.impact_description or "No description")
        desc_label.setStyleSheet("font-size: 12px;")
        desc_label.setWordWrap(True)
        top.addWidget(desc_label, stretch=1)

        # Review status
        if impact.reviewed:
            status_text = "Reviewed"
            if impact.action_required:
                status_text += " (Action Required)"
            status_label = QLabel(status_text)
            status_label.setStyleSheet("font-size: 11px; color: #2E7D32;")
        else:
            status_label = QLabel("Unreviewed")
            status_label.setStyleSheet("font-size: 11px; color: #E65100; font-weight: bold;")
        top.addWidget(status_label)

        layout.addLayout(top)

        # Detail row
        detail = QHBoxLayout()
        table_label = QLabel(f"Table: {impact.affected_table}")
        table_label.setStyleSheet("font-size: 11px; color: #757575;")
        detail.addWidget(table_label)

        if impact.reviewed_at:
            reviewed_label = QLabel(f"Reviewed: {impact.reviewed_at[:10]}")
            reviewed_label.setStyleSheet("font-size: 11px; color: #757575;")
            detail.addWidget(reviewed_label)

        detail.addStretch()

        # Review actions — placeholder for Step 15b
        if not impact.reviewed and impact.requires_review:
            review_btn = QPushButton("Review")
            review_btn.setStyleSheet("font-size: 11px;")
            review_btn.clicked.connect(
                lambda: show_toast(self, "Impact review coming in Step 15b")
            )
            detail.addWidget(review_btn)

        layout.addLayout(detail)


class ImpactsTab(QWidget):
    """Tab showing change impacts affecting this work item.

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def update_impacts(self, impacts: list[ImpactRow]) -> None:
        """Refresh the tab with new impact data.

        :param impacts: Impact rows, unreviewed first.
        """
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if impacts:
            unreviewed = [i for i in impacts if not i.reviewed]
            reviewed = [i for i in impacts if i.reviewed]

            if unreviewed:
                header = QLabel(f"Unreviewed ({len(unreviewed)})")
                header.setStyleSheet(
                    "font-size: 13px; font-weight: bold; color: #E65100; padding: 4px 8px;"
                )
                self._layout.addWidget(header)
                for impact in unreviewed:
                    self._layout.addWidget(ImpactCard(impact))

            if reviewed:
                header = QLabel(f"Reviewed ({len(reviewed)})")
                header.setStyleSheet(
                    "font-size: 13px; font-weight: bold; color: #2E7D32; padding: 4px 8px;"
                )
                self._layout.addWidget(header)
                for impact in reviewed:
                    self._layout.addWidget(ImpactCard(impact))
        else:
            empty = QLabel("No impacts recorded")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._layout.addWidget(empty)

        self._layout.addStretch()
