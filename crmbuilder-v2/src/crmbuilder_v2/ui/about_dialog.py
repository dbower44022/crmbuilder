"""About dialog.

Shows the application name, resolved version, API base URL, database
path, and snapshot directory. Wired to ``Help → About`` in the main
window. Per the slice H polish prompt and the v0.1 PRD §11 Q1.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.config import get_settings

_APP_NAME = "CRMBuilder v2"
_APP_PACKAGE = "crmbuilder-v2"


def _resolve_version() -> str:
    try:
        return version(_APP_PACKAGE)
    except PackageNotFoundError:
        return "unknown (development install)"


class AboutDialog(QDialog):
    """Modal About dialog. Read-only labels with selectable text so the
    user can copy paths."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {_APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        settings = get_settings()
        rows: list[tuple[str, str]] = [
            ("Application", _APP_NAME),
            ("Version", _resolve_version()),
            ("API base URL", settings.api_base_url),
            ("Database path", str(settings.db_path)),
            ("Snapshot directory", str(settings.export_dir)),
        ]

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        for label_text, value_text in rows:
            label = QLabel(f"<b>{label_text}</b>")
            value = QLabel(value_text)
            value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            value.setWordWrap(True)
            form.addRow(label, value)
        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        # Close button counts as Reject by default; rewire to accept too.
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        outer.addWidget(buttons)
