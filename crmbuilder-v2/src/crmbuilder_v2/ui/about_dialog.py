"""About dialog — modest-showcase canary surface for v0.6 styling.

Restructured in v0.6 slice A per design pass §2.8 and DEC-094:

* Wordmark + tagline header block (replaces the prior unchromed title).
* Metadata table restructured from ``QFormLayout`` to a vertical
  two-line-per-row list, paths and URLs in JetBrains Mono.
* Single right-aligned "Close" button (Secondary category — the
  default ``QPushButton`` treatment in the project-level QSS).

Wired to ``Help → About`` in the main window. Acts as the canary
surface that exercises tokens, fonts, the modal elevation
infrastructure, and the dialog hook pattern end-to-end before any
panel work begins.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import crmbuilder_v2
from crmbuilder_v2.config import Settings, get_settings
from crmbuilder_v2.runtime.engagement_routing import UNCONFIGURED_SENTINEL
from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.modal_backdrop import attach as _backdrop_attach
from crmbuilder_v2.ui.widgets.modal_backdrop import detach as _backdrop_detach

_APP_NAME = "CRMBuilder v2"
_APP_PACKAGE = "crmbuilder-v2"
_TAGLINE = "Declarative CRM deployment and methodology authoring"

# Per design pass §2.8 — paths and URLs render in JetBrains Mono so
# absolute paths align cleanly. The set of mono-rendered labels is
# intentionally narrow.
_MONO_LABELS = frozenset(
    {"API base url", "Database path", "Snapshot directory"}
)


def _snapshot_dir_display(settings: Settings) -> str:
    """Render the Snapshot directory value across its three states.

    Multi-tenancy routing fix slice B (B3): the active engagement's
    export directory can be unconfigured (the ``__UNCONFIGURED__``
    sentinel) or configured at a path that does not exist on disk.
    Surface both to the operator instead of leaking the raw sentinel
    string or an unverified path.
    """
    if str(settings.export_dir) == UNCONFIGURED_SENTINEL:
        return "(not configured)"
    if not settings.export_dir.is_dir():
        return f"(missing — {settings.export_dir})"
    return str(settings.export_dir)


def _resolve_version() -> str:
    try:
        return version(_APP_PACKAGE)
    except PackageNotFoundError:
        return getattr(
            crmbuilder_v2, "__version__", "unknown (development install)"
        )


def _px(token_key: str) -> int:
    """Resolve a spacing token to an int pixel value for Qt layout APIs."""
    raw = t(token_key)
    if raw.endswith("px"):
        raw = raw[:-2]
    return int(raw)


def _wordmark_label() -> QLabel:
    label = QLabel(_APP_NAME)
    font = QFont(t("font.family.default"))
    font.setPixelSize(_px("font.size.heading_2"))
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    label.setStyleSheet(f"color: {t('color.neutral.900')};")
    return label


def _tagline_label() -> QLabel:
    label = QLabel(_TAGLINE)
    font = QFont(t("font.family.default"))
    font.setPixelSize(_px("font.size.small"))
    label.setFont(font)
    label.setStyleSheet(f"color: {t('color.neutral.500')};")
    return label


def _metadata_label_widget(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(t("font.family.default"))
    font.setPixelSize(_px("font.size.small"))
    font.setWeight(QFont.Weight.Medium)
    label.setFont(font)
    label.setStyleSheet(f"color: {t('color.neutral.500')};")
    return label


def _metadata_value_widget(value: str, *, mono: bool) -> QLabel:
    label = QLabel(value)
    family = t("font.family.mono") if mono else t("font.family.default")
    font = QFont(family)
    if mono:
        font.setPixelSize(_px("font.size.small"))
    else:
        font.setPixelSize(_px("font.size.body"))
    label.setFont(font)
    color = t("color.neutral.700") if mono else t("color.neutral.800")
    label.setStyleSheet(f"color: {color};")
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    label.setWordWrap(True)
    return label


class AboutDialog(QDialog):
    """Modal About dialog (canary surface for v0.6 styling)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {_APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(440)
        apply_dialog_shadow(self)

        outer = QVBoxLayout(self)
        outer_pad = _px("space.5")
        outer.setContentsMargins(outer_pad, outer_pad, outer_pad, outer_pad)
        outer.setSpacing(_px("space.3"))

        # Header block — wordmark + tagline, with space.1 between them.
        header_box = QVBoxLayout()
        header_box.setContentsMargins(0, 0, 0, 0)
        header_box.setSpacing(_px("space.1"))
        header_box.addWidget(_wordmark_label())
        header_box.addWidget(_tagline_label())
        outer.addLayout(header_box)
        # Header → metadata spacing per design pass §2.8 (space.4).
        outer.addSpacing(_px("space.4") - _px("space.3"))

        # Metadata list — two lines per row, paths in mono.
        settings = get_settings()
        rows: list[tuple[str, str]] = [
            ("Application", _APP_NAME),
            ("Version", _resolve_version()),
            ("API base url", settings.api_base_url),
            ("Database path", str(settings.db_path)),
            ("Snapshot directory", _snapshot_dir_display(settings)),
        ]
        for label_text, value_text in rows:
            row_layout = QVBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(_px("space.1"))
            row_layout.addWidget(_metadata_label_widget(label_text))
            row_layout.addWidget(
                _metadata_value_widget(
                    value_text, mono=label_text in _MONO_LABELS
                )
            )
            outer.addLayout(row_layout)

        outer.addStretch(1)

        # Action row — right-aligned Close button.
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        self._close_btn = QPushButton("Close")
        self._close_btn.setDefault(True)
        self._close_btn.clicked.connect(self.accept)
        action_row.addWidget(self._close_btn)
        outer.addLayout(action_row)

    # ------------------------------------------------------------------
    # Modal backdrop hooks (v0.6 slice A — DEC-091)
    # ------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802 — Qt naming
        super().showEvent(event)
        _backdrop_attach(self)

    def hideEvent(self, event):  # noqa: N802 — Qt naming
        _backdrop_detach(self)
        super().hideEvent(event)
