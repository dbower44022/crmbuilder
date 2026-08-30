"""Quick open (Ctrl+K) — reach any record or panel by typing (REQ-526 / PI-432).

Hiding thirty-odd panels behind the phase checklist is only safe if nothing
becomes hard to reach. Quick open answers that: type a panel name fragment
("dep" → Deploy History, Deposit Events), an identifier prefix ("REQ-52" →
the matching requirements), or a word that appears in a record's list
columns for the panel the prefix names. Enter opens the highlighted row in
the current tab.

Records are found through the *panel* the identifier prefix maps to — its
``fetch_records()`` run off-thread — so quick open needs no search endpoint
and matches exactly what the panel's own list would show.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.navigation import (
    IDENTIFIER_PREFIX_TO_ENTITY_TYPE,
    split_identifier_prefix,
)
from crmbuilder_v2.ui.panel_registry import ALL_PANEL_LABELS
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.quick_open")

_DEBOUNCE_MS = 150
_MAX_RESULTS = 25
_KIND_ROLE = Qt.ItemDataRole.UserRole + 1  # "panel" | "record"
_LABEL_ROLE = Qt.ItemDataRole.UserRole + 2
_IDENT_ROLE = Qt.ItemDataRole.UserRole + 3


class QuickOpenDialog(QDialog):
    """Frameless-ish finder: a line edit, a result list, Enter to open."""

    #: (panel label, record identifier or None)
    open_requested = Signal(str, object)

    def __init__(
        self,
        *,
        entity_type_to_label: dict[str, str],
        panel_provider: Callable[[str], ListDetailPanel | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick open")
        self.setObjectName("quick_open_dialog")
        self.setModal(True)
        self.resize(560, 380)
        self._entity_type_to_label = entity_type_to_label
        self._panel_provider = panel_provider
        self._query_token = 0

        self._input = QLineEdit()
        self._input.setObjectName("quick_open_input")
        self._input.setPlaceholderText(
            "Identifier (REQ-52), panel name, or a word from a record…"
        )
        self._results = QListWidget()
        self._results.setObjectName("quick_open_results")
        self._hint = QLabel("")
        self._hint.setStyleSheet(f"color: {t('color.neutral.500')};")

        layout = QVBoxLayout(self)
        layout.addWidget(self._input)
        layout.addWidget(self._results, stretch=1)
        layout.addWidget(self._hint)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_query)
        self._input.textChanged.connect(lambda _t: self._debounce.start())
        self._input.returnPressed.connect(self._open_current)
        self._results.itemActivated.connect(lambda _i: self._open_current())
        self._input.installEventFilter(self)
        self._run_query()

    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):  # noqa: N802 (Qt naming)
        # Up/Down in the input move the result highlight.
        from PySide6.QtCore import QEvent

        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self._results.currentRow()
                count = self._results.count()
                if count:
                    delta = 1 if key == Qt.Key.Key_Down else -1
                    self._results.setCurrentRow(max(0, min(count - 1, row + delta)))
                return True
        return super().eventFilter(obj, event)

    def query_text(self) -> str:
        return self._input.text()

    def set_query(self, text: str) -> None:
        self._input.setText(text)

    def results(self) -> list[tuple[str, str, str | None]]:
        """``[(kind, label, identifier), …]`` for tests."""
        out = []
        for row in range(self._results.count()):
            item = self._results.item(row)
            out.append(
                (item.data(_KIND_ROLE), item.data(_LABEL_ROLE), item.data(_IDENT_ROLE))
            )
        return out

    # ------------------------------------------------------------------

    def _run_query(self) -> None:
        text = self._input.text().strip()
        self._query_token += 1
        token = self._query_token
        self._results.clear()
        self._hint.setText("")

        query = text.lower()
        for label in ALL_PANEL_LABELS:
            if not query or query in label.lower():
                self._add_result("panel", label, None, f"{label}  —  panel")

        split = split_identifier_prefix(text)
        if split is None:
            if text:
                self._hint.setText(
                    "Type an identifier prefix such as REQ- to search records."
                )
            self._select_first()
            return
        prefix, needle = split
        entity_type = IDENTIFIER_PREFIX_TO_ENTITY_TYPE.get(prefix)
        label = self._entity_type_to_label.get(entity_type or "")
        if label is None:
            self._hint.setText(f"No panel is known for the {prefix}- prefix.")
            self._select_first()
            return
        panel = self._panel_provider(label)
        if panel is None:
            self._select_first()
            return
        self._hint.setText(f"Searching {label}…")

        def _fetch():
            return panel.fetch_records()

        def _ok(records: Any, tok=token, lbl=label, ndl=needle):
            if tok != self._query_token:
                return
            self._show_records(lbl, ndl, list(records) if isinstance(records, list) else [])

        def _err(exc: Exception, tok=token):
            if tok != self._query_token:
                return
            self._hint.setText(f"Could not search: {exc}")

        run_in_thread(_fetch, on_success=_ok, on_error=_err, parent=self)

    def _show_records(self, label: str, needle: str, records: list[dict]) -> None:
        shown = 0
        for record in records:
            ident = str(record.get("identifier") or "")
            if not ident.upper().startswith(needle):
                continue
            title = _record_title(record)
            self._add_result("record", label, ident, f"{ident}  {title}".rstrip())
            shown += 1
            if shown >= _MAX_RESULTS:
                break
        self._hint.setText(
            f"{shown} match{'es' if shown != 1 else ''} in {label}"
            if shown
            else f"No {label} record starts with {needle}"
        )
        self._select_first()

    def _add_result(self, kind: str, label: str, ident: str | None, text: str) -> None:
        item = QListWidgetItem(text)
        item.setData(_KIND_ROLE, kind)
        item.setData(_LABEL_ROLE, label)
        item.setData(_IDENT_ROLE, ident)
        self._results.addItem(item)

    def _select_first(self) -> None:
        if self._results.count() and self._results.currentRow() < 0:
            self._results.setCurrentRow(0)

    def _open_current(self) -> None:
        item = self._results.currentItem()
        if item is None:
            return
        self.open_requested.emit(item.data(_LABEL_ROLE), item.data(_IDENT_ROLE))
        self.accept()


def _record_title(record: dict) -> str:
    for key in ("title", "name", "requirement_name", "session_title", "label"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
    for key, value in record.items():
        if key.endswith(("_name", "_title")) and isinstance(value, str) and value.strip():
            return value.strip()[:80]
    return ""
