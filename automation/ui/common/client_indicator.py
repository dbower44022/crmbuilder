"""Client context indicator widget (Section 14.10.11).

Shows the currently selected client in the Requirements tab header.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class ClientIndicator(QLabel):
    """Displays the current client name prominently.

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(
            "font-size: 14px; "
            "font-weight: bold; "
            "color: #1F3864; "
            "padding: 4px 8px;"
        )
        self.set_client_name("")

    def set_client_name(self, name: str) -> None:
        """Update the displayed client name.

        :param name: Client name, or empty string for no selection.
        """
        if name:
            self.setText(f"Client: {name}")
        else:
            self.setText("No client selected")
