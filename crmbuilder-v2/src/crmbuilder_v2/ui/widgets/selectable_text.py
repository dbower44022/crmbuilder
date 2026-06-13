"""Selectable/copyable text helpers — the PI-124 shared mechanism.

Promotes three existing conventions (the ``about_dialog`` flag set,
the bare ``TextSelectableByMouse`` on identifier labels, and the
guarded clipboard write in ``panels/work_tasks.py`` /
``panels/deposit_events.py``) into one importable place, so every
popup, banner, or message dialog lets an operator select the full
message text and copy it into a bug report. Design spec:
``PRDs/product/crmbuilder-v2/pi-124-selectable-copyable-text-architecture.md``.

All application is additive — flags are OR'd into a widget's existing
flags, never overwritten.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

SELECTABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse
    | Qt.TextInteractionFlag.TextSelectableByKeyboard
)


def make_selectable[W: (QLabel, QMessageBox)](widget: W) -> W:
    """OR the selectable-text flags into ``widget``'s existing flags.

    Returns the widget for chaining. Never overwrites — preserves
    ``LinksAccessibleByMouse`` on link-bearing labels and
    ``TextBrowserInteraction`` where a surface already uses it.

    QMessageBox caveat: ``setTextInteractionFlags`` governs only the
    main text label — the informative-text label takes its flags from
    the style hint when ``setInformativeText`` creates it, so a raw
    QMessageBox keeps a mouse-only informative label.
    ``CopyableMessageBox`` covers both labels — prefer it for new code.
    """
    widget.setTextInteractionFlags(
        widget.textInteractionFlags() | SELECTABLE_TEXT_FLAGS
    )
    return widget


def copy_to_clipboard(text: str) -> bool:
    """Guarded clipboard write; ``False`` when no clipboard exists."""
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        return False
    clipboard.setText(text)
    return True


class CopyableMessageBox(QMessageBox):
    """Drop-in QMessageBox whose message and informative text are selectable.

    The Copy affordance here is the native context menu (Copy /
    Select All) plus Ctrl+C on a selection — no explicit Copy button,
    because QMessageBox's button protocol closes the dialog when any
    button is clicked (including ``ActionRole`` ones), and working
    around that would mean restructuring the dialog. The detailed-text
    pane is a read-only QTextEdit and is selectable without
    intervention.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        make_selectable(self)

    def setInformativeText(self, text: str) -> None:
        """Apply the selectable flags to the informative-text label.

        Qt creates that label with flags from the style hint (not the
        main label's flags), so the box-level flags set in ``__init__``
        don't reach it.
        """
        super().setInformativeText(text)
        label = self.findChild(QLabel, "qt_msgbox_informativelabel")
        if label is not None:
            make_selectable(label)

    @classmethod
    def _show(
        cls,
        icon: QMessageBox.Icon,
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton,
        default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        box = cls(parent)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        box.setDefaultButton(default)
        box.exec()
        clicked = box.clickedButton()
        result = (
            box.standardButton(clicked)
            if clicked is not None
            else QMessageBox.StandardButton.NoButton
        )
        box.deleteLater()
        return result

    @classmethod
    def information(
        cls,
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
    ) -> QMessageBox.StandardButton:
        return cls._show(
            QMessageBox.Icon.Information, parent, title, text, buttons, default
        )

    @classmethod
    def warning(
        cls,
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
    ) -> QMessageBox.StandardButton:
        return cls._show(
            QMessageBox.Icon.Warning, parent, title, text, buttons, default
        )

    @classmethod
    def critical(
        cls,
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
    ) -> QMessageBox.StandardButton:
        return cls._show(
            QMessageBox.Icon.Critical, parent, title, text, buttons, default
        )

    @classmethod
    def question(
        cls,
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
    ) -> QMessageBox.StandardButton:
        return cls._show(
            QMessageBox.Icon.Question, parent, title, text, buttons, default
        )
