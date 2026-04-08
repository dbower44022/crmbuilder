"""Staleness indicator widget (Section 14.10.4).

Shows a visual badge when a completed work item has a stale document.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class StalenessIndicator(QLabel):
    """A badge showing whether a work item's documents are stale.

    :param is_stale: Whether the item is stale.
    :param parent: Optional parent widget.
    """

    def __init__(self, is_stale: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_stale(is_stale)

    def set_stale(self, is_stale: bool) -> None:
        """Update the staleness state.

        :param is_stale: True if the item's documents are stale.
        """
        if is_stale:
            self.setText(" Stale ")
            self.setStyleSheet(
                "background-color: #FFF3E0; "
                "color: #E65100; "
                "border-radius: 4px; "
                "padding: 2px 6px; "
                "font-weight: bold; "
                "font-size: 11px;"
            )
            self.setVisible(True)
        else:
            self.setText("")
            self.setVisible(False)
