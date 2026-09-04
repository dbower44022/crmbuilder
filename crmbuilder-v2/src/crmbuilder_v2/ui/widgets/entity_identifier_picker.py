"""Entity identifier picker widget — v0.3 slice C; popup redesigned for
REQ-564 / REQ-565 (PI-465, DEC-1045).

Editable ``QComboBox`` + ``QCompleter`` for selecting an entity by
identifier or title. Used by the ``ReferenceCreateDialog`` (DEC-033)
for both source and target identifier fields and by the process dialog
for its domain picker. Items are rendered as ``"IDENTIFIER — title"``
strings; the completer matches substrings across both identifier and
title so the user can type either.

The opened list is a custom popup (:class:`_PickerPopup`) rather than
the stock combo view: its rows are single-spaced, one text line high,
so a long list shows as many records as the space allows (REQ-564), and
a search box sits at its top that narrows the rows by identifier or
name as the person types, restoring the full list when cleared
(REQ-565). Picking a row selects it exactly as the stock view did —
``currentIndex`` moves, ``activated`` fires, ``selection_changed`` fires.

The widget is generic over entity type. Callers populate it via
:meth:`set_entries` with ``(identifier, title)`` tuples; the dialog's
cascading-filter logic decides which entity type is current and
fetches the appropriate list.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QLineEdit,
    QListView,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.styling import t

# Rows visible in the opened list before it scrolls (REQ-564: compact,
# so this many rows fit where the stock popup showed about half).
_VISIBLE_ROWS = 12


def _token(key: str, fallback: str) -> str:
    try:
        return t(key)
    except KeyError:
        return fallback


class _PickerPopup(QFrame):
    """The opened list: a search box over a single-spaced, filtered view."""

    def __init__(self, picker: EntityIdentifierPicker) -> None:
        super().__init__(
            picker, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self._picker = picker
        self.setObjectName("identifier_picker_popup")
        self.setStyleSheet(
            f"""
QFrame#identifier_picker_popup {{
    background: {_token("color.neutral.0", "#ffffff")};
    border: 1px solid {_token("color.neutral.300", "#d0d4d9")};
    border-radius: {_token("radius.subtle", "4px")};
}}
QFrame#identifier_picker_popup QLineEdit {{
    margin: 0;
}}
QListView#identifier_picker_list {{
    border: 0;
    background: {_token("color.neutral.0", "#ffffff")};
    outline: 0;
}}
QListView#identifier_picker_list::item {{
    min-height: 0;
    padding: 1px {_token("space.2", "8px")};
    color: {_token("color.neutral.800", "#2b3136")};
}}
QListView#identifier_picker_list::item:hover {{
    background: {_token("color.neutral.100", "#f1f3f5")};
    color: {_token("color.neutral.900", "#1b2024")};
}}
QListView#identifier_picker_list::item:selected {{
    background: {_token("color.accent.subtle", "#e3f1f2")};
    color: {_token("color.neutral.900", "#1b2024")};
}}
"""
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.search = QLineEdit()
        self.search.setObjectName("identifier_picker_search")
        self.search.setPlaceholderText("Search by identifier or name")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search_changed)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(picker.model())
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterRole(Qt.ItemDataRole.DisplayRole)

        self.view = QListView()
        self.view.setObjectName("identifier_picker_list")
        self.view.setModel(self.proxy)
        self.view.setUniformItemSizes(True)
        self.view.setSpacing(0)
        self.view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.clicked.connect(self.choose)
        self.view.installEventFilter(self)
        layout.addWidget(self.view)

    # -- filtering -------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self.proxy.setFilterFixedString(text.strip())
        if self.proxy.rowCount():
            self.view.setCurrentIndex(self.proxy.index(0, 0))

    def visible_count(self) -> int:
        return self.proxy.rowCount()

    # -- choosing --------------------------------------------------------

    def choose(self, proxy_index) -> None:
        if not proxy_index.isValid():
            return
        source_row = self.proxy.mapToSource(proxy_index).row()
        self._picker.hidePopup()
        self._picker.setCurrentIndex(source_row)
        self._picker.activated.emit(source_row)

    def choose_current_or_first(self) -> None:
        index = self.view.currentIndex()
        if not index.isValid() and self.proxy.rowCount():
            index = self.proxy.index(0, 0)
        self.choose(index)

    # -- keyboard --------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self._picker.hidePopup()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.choose_current_or_first()
                return True
            if watched is self.search and key == Qt.Key.Key_Down:
                if self.proxy.rowCount():
                    if not self.view.currentIndex().isValid():
                        self.view.setCurrentIndex(self.proxy.index(0, 0))
                    self.view.setFocus()
                return True
            if watched is self.view and key == Qt.Key.Key_Up:
                current = self.view.currentIndex()
                if not current.isValid() or current.row() == 0:
                    self.search.setFocus()
                    return True
        return super().eventFilter(watched, event)

    # -- sizing ----------------------------------------------------------

    def open_below(self, anchor: QWidget) -> None:
        self.search.clear()
        self.proxy.setFilterFixedString("")
        row_height = self.view.sizeHintForRow(0) if self.proxy.rowCount() else 20
        rows = min(max(self.proxy.rowCount(), 1), _VISIBLE_ROWS)
        list_height = row_height * rows + 2 * self.view.frameWidth()
        self.view.setFixedHeight(list_height)
        self.setFixedWidth(max(anchor.width(), 240))
        self.adjustSize()
        self.move(anchor.mapToGlobal(QPoint(0, anchor.height())))
        self.show()
        self.search.setFocus()


class EntityIdentifierPicker(QComboBox):
    """Editable combo box for selecting an entity by identifier or title.

    Signals:

    * ``selection_changed(str)`` — emitted with the selected identifier
      when the user picks a list item or the editable text resolves to
      a known entry.
    """

    selection_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        # identifier -> "IDENTIFIER — title" rendering
        self._entries: dict[str, str] = {}
        self._completer = QCompleter(self)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompleter(self._completer)
        self.activated.connect(self._on_activated)
        self._popup: _PickerPopup | None = None

    def set_entries(self, entries: list[tuple[str, str]]) -> None:
        """Populate the picker with ``(identifier, title)`` tuples.

        Clears any existing entries first. The first column of each
        rendered row is ``IDENTIFIER``; the title is appended after an
        em-dash for human readability. The picker stores the identifier
        as ``Qt.UserRole`` data on each item.
        """
        self.clear()
        self._entries.clear()
        for identifier, title in entries:
            display = f"{identifier} — {title}" if title else identifier
            self._entries[identifier] = display
            self.addItem(display, userData=identifier)
        # Re-attach the completer's model so its filter sees the new items.
        self._completer.setModel(self.model())
        if self._popup is not None:
            self._popup.proxy.setSourceModel(self.model())

    def selected_identifier(self) -> str | None:
        """Return the identifier of the current selection or ``None``.

        Resolves in this order:

        1. The current index's user-data (set when the user picks from
           the dropdown).
        2. The current text — matched verbatim against either the
           rendered display strings or the bare identifiers — for the
           case where the user typed a value the completer accepted.
        """
        index = self.currentIndex()
        if index >= 0:
            data = self.itemData(index)
            if data:
                return data
        current_text = self.currentText().strip()
        if not current_text:
            return None
        for identifier, display in self._entries.items():
            if display == current_text or identifier == current_text:
                return identifier
        return None

    def clear_selection(self) -> None:
        """Clear the current selection and edit text."""
        self.setCurrentIndex(-1)
        self.setEditText("")

    # -- popup (REQ-564 / REQ-565) -------------------------------------------

    def popup(self) -> _PickerPopup:
        """The opened-list widget, built on first use."""
        if self._popup is None:
            self._popup = _PickerPopup(self)
        return self._popup

    def showPopup(self) -> None:  # noqa: N802 — Qt naming
        self.popup().open_below(self)

    def hidePopup(self) -> None:  # noqa: N802 — Qt naming
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
        super().hidePopup()

    def _on_activated(self, index: int) -> None:
        identifier = self.itemData(index)
        if identifier:
            self.selection_changed.emit(identifier)
