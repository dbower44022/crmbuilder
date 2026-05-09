"""Entity identifier picker widget — v0.3 slice C.

Editable ``QComboBox`` + ``QCompleter`` for selecting an entity by
identifier or title. Used by the ``ReferenceCreateDialog`` (DEC-033)
for both source and target identifier fields. Items are rendered as
``"IDENTIFIER — title"`` strings; the completer matches substrings
across both identifier and title so the user can type either.

The widget is generic over entity type. Callers populate it via
:meth:`set_entries` with ``(identifier, title)`` tuples; the dialog's
cascading-filter logic decides which entity type is current and
fetches the appropriate list.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QCompleter, QWidget


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

    def _on_activated(self, index: int) -> None:
        identifier = self.itemData(index)
        if identifier:
            self.selection_changed.emit(identifier)
