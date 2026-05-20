"""Connection Info dialog — shows which engagement database the live API
process is actually bound to.

Distinct from the About dialog: that reads the *UI* process's
``get_settings()`` (only routed at startup), whereas this queries the API
via ``GET /admin/connection`` so it reflects the engagement the server is
serving *right now*, including after an in-process switch. This is the
operator's verification surface for "am I looking at the right database?".
"""

from __future__ import annotations

from typing import Any

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

from crmbuilder_v2.ui.elevation import apply_dialog_shadow
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.modal_backdrop import attach as _backdrop_attach
from crmbuilder_v2.ui.widgets.modal_backdrop import detach as _backdrop_detach

_MONO_LABELS = frozenset({"API base URL", "Database path", "Export directory"})


def _px(token_key: str) -> int:
    raw = t(token_key)
    if raw.endswith("px"):
        raw = raw[:-2]
    return int(raw)


def _human_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "—"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _label_widget(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont(t("font.family.default"))
    font.setPixelSize(_px("font.size.small"))
    font.setWeight(QFont.Weight.Medium)
    label.setFont(font)
    label.setStyleSheet(f"color: {t('color.neutral.500')};")
    return label


def _value_widget(*, mono: bool) -> QLabel:
    label = QLabel("")
    family = t("font.family.mono") if mono else t("font.family.default")
    font = QFont(family)
    font.setPixelSize(_px("font.size.small" if mono else "font.size.body"))
    label.setFont(font)
    color = t("color.neutral.700") if mono else t("color.neutral.800")
    label.setStyleSheet(f"color: {color};")
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    label.setWordWrap(True)
    return label


class ConnectionInfoDialog(QDialog):
    """Modal dialog reporting the live API's active engagement + database."""

    # Row labels in display order; mono labels are listed in _MONO_LABELS.
    _ROWS: tuple[str, ...] = (
        "Active engagement",
        "API base URL",
        "API reachable",
        "API version",
        "Database path",
        "Database exists",
        "Database size",
        "Engagement DB schema",
        "Meta DB schema",
        "Export directory",
    )

    def __init__(
        self,
        client,
        active_context=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._active_context = active_context
        self.setWindowTitle("Connection Info")
        self.setModal(True)
        self.setMinimumWidth(460)
        apply_dialog_shadow(self)

        outer = QVBoxLayout(self)
        pad = _px("space.5")
        outer.setContentsMargins(pad, pad, pad, pad)
        outer.setSpacing(_px("space.3"))

        header = QLabel("Connection Info")
        hfont = QFont(t("font.family.default"))
        hfont.setPixelSize(_px("font.size.heading_2"))
        hfont.setWeight(QFont.Weight.DemiBold)
        header.setFont(hfont)
        header.setStyleSheet(f"color: {t('color.neutral.900')};")
        outer.addWidget(header)
        outer.addSpacing(_px("space.2"))

        self._value_labels: dict[str, QLabel] = {}
        for label_text in self._ROWS:
            row = QVBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(_px("space.1"))
            row.addWidget(_label_widget(label_text))
            value = _value_widget(mono=label_text in _MONO_LABELS)
            self._value_labels[label_text] = value
            row.addWidget(value)
            outer.addLayout(row)

        outer.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._populate)
        action_row.addWidget(self._refresh_btn)
        action_row.addStretch(1)
        self._close_btn = QPushButton("Close")
        self._close_btn.setDefault(True)
        self._close_btn.clicked.connect(self.accept)
        action_row.addWidget(self._close_btn)
        outer.addLayout(action_row)

        self._populate()

    def _populate(self) -> None:
        """Query the API and (re)fill the value labels."""
        info: dict[str, Any] | None = None
        versions: dict[str, Any] | None = None
        reachable = False
        error_text = ""
        try:
            info = self._client.connection_info()
            versions = self._client.version_info()
            reachable = True
        except StorageConnectionError as exc:
            error_text = f"unreachable — {exc}"
        except StorageClientError as exc:
            error_text = f"error — {exc}"

        self._set("Active engagement", self._engagement_display(info))
        self._set(
            "API base URL",
            (info or {}).get("api_base_url") or "—",
        )
        self._set("API reachable", "Yes" if reachable else f"No ({error_text})")
        self._set("API version", (versions or {}).get("api_version") or "—")
        self._set(
            "Engagement DB schema",
            self._schema_display((versions or {}).get("engagement_schema")),
        )
        self._set(
            "Meta DB schema",
            self._schema_display((versions or {}).get("meta_schema")),
        )

        if info is None:
            for key in ("Database path", "Database size", "Export directory"):
                self._set(key, "—")
            self._set("Database exists", "—")
            return

        self._set("Database path", info.get("db_path") or "—")
        self._set(
            "Database exists", "Yes" if info.get("db_exists") else "No"
        )
        self._set("Database size", _human_size(info.get("db_size_bytes")))
        self._set("Export directory", self._export_display(info))

    def _set(self, label: str, value: str) -> None:
        widget = self._value_labels.get(label)
        if widget is not None:
            widget.setText(value)

    def _engagement_display(self, info: dict[str, Any] | None) -> str:
        code = (info or {}).get("engagement_code")
        name = None
        identifier = None
        if self._active_context is not None:
            eng = self._active_context.engagement()
            if eng is not None:
                name = eng.engagement_name
                identifier = eng.engagement_identifier
                if code is None:
                    code = eng.engagement_code
        if code is None:
            return "(none active)"
        parts = [code]
        if name:
            parts.append(f"— {name}")
        if identifier:
            parts.append(f"({identifier})")
        return " ".join(parts)

    @staticmethod
    def _schema_display(block: dict[str, Any] | None) -> str:
        if not block:
            return "—"
        current = block.get("current") or "(unstamped)"
        if block.get("up_to_date"):
            return f"{current} (up to date)"
        head = block.get("head") or "?"
        return f"{current} → head {head} (migration pending)"

    @staticmethod
    def _export_display(info: dict[str, Any]) -> str:
        if not info.get("export_dir_configured"):
            return "(not configured)"
        path = info.get("export_dir") or ""
        if not info.get("export_dir_exists"):
            return f"(missing — {path})"
        return path

    # Modal backdrop hooks (consistent with AboutDialog).
    def showEvent(self, event):  # noqa: N802 — Qt naming
        super().showEvent(event)
        _backdrop_attach(self)

    def hideEvent(self, event):  # noqa: N802 — Qt naming
        _backdrop_detach(self)
        super().hideEvent(event)
