"""Confirmation prompt dialog (Section 14.10.7).

Modal confirmation with OK/Cancel buttons.
"""

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_action(
    parent: QWidget | None,
    title: str,
    message: str,
) -> bool:
    """Show a modal confirmation dialog.

    :param parent: Parent widget for the dialog.
    :param title: Dialog title.
    :param message: Message body.
    :returns: True if the user clicked OK.
    """
    result = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return result == QMessageBox.StandardButton.Ok
