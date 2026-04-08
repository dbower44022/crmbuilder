"""Error and warning presentation (Section 14.10.8).

Helpers for showing errors and warnings in the UI.
"""

from PySide6.QtWidgets import QMessageBox, QWidget


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    """Show a modal error dialog.

    :param parent: Parent widget.
    :param title: Dialog title.
    :param message: Error message.
    """
    QMessageBox.critical(parent, title, message)


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    """Show a modal warning dialog.

    :param parent: Parent widget.
    :param title: Dialog title.
    :param message: Warning message.
    """
    QMessageBox.warning(parent, title, message)


def show_info(parent: QWidget | None, title: str, message: str) -> None:
    """Show a modal informational dialog.

    :param parent: Parent widget.
    :param title: Dialog title.
    :param message: Info message.
    """
    QMessageBox.information(parent, title, message)
