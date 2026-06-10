"""LinkFilterInput — debounced free-text filter box for link panels.

PI-116 / WTK-061. A small reusable ``QLineEdit`` subclass shared by the
two surfaces that render a record's relationships as link rows
(``ReferencesSection`` and ``ReferencesPanel``) so the debounce timing,
placeholder, clear affordance, and ``Esc`` behavior stay identical
across both. The widget owns only the *input* contract; the host panel
owns *what* the filter does (proxy ``setFilterFixedString`` for the
embedded grid; a cached-list re-filter for the standalone panel) and
connects it to the :data:`filterChanged` signal.

Behavior (per the WTK-059 design, §3.2 / §3.5):

- Typing emits ``filterChanged(text)`` after a **250 ms single-shot
  debounce** — a fast typist's burst of keystrokes coalesces into one
  filter pass over the loaded rows. The pending timer *restarts* on each
  keystroke; only the trailing value is emitted.
- **Clearing is immediate, not debounced**: emptying the field (the
  native ``✕`` clear button, select-all-delete, or ``Esc``) cancels any
  pending debounce and emits ``filterChanged("")`` at once so the full
  list is restored with no lag.
- ``Esc`` while the field has text clears it; ``Esc`` on an already-empty
  field is ignored (propagated to the host so it does not steal the key).

This is the first input debounce in the v2 UI; the single-shot-restart
``QTimer`` is the standard Qt idiom.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit, QWidget

#: Debounce window between the last keystroke and the filter pass. Long
#: enough to coalesce a fast typist's keystrokes into one pass, short
#: enough to feel live. Tunable in one place.
_FILTER_DEBOUNCE_MS = 250

#: Placeholder copy, shared by both call sites (sentence case + ellipsis).
_PLACEHOLDER = "Filter links…"


class LinkFilterInput(QLineEdit):
    """A debounced, clearable single-line filter input for link panels.

    Emits :data:`filterChanged` with the current text after the debounce
    settles, or immediately on clear/empty. The host connects that signal
    to its own apply path; this widget never touches the model directly.
    """

    #: Emitted after the debounce settles, or immediately on clear/empty.
    filterChanged = Signal(str)

    def __init__(
        self,
        *,
        object_name: str | None = None,
        max_width: int | None = None,
        delay_ms: int = _FILTER_DEBOUNCE_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._delay_ms = delay_ms
        self.setPlaceholderText(_PLACEHOLDER)
        self.setClearButtonEnabled(True)
        if object_name:
            self.setObjectName(object_name)
        if max_width is not None:
            self.setMaximumWidth(max_width)

        # Single-shot debounce timer: each keystroke restarts it; the
        # trailing timeout emits the current text.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_now)

        self.textChanged.connect(self._on_text_changed)

    # ------------------------------------------------------------------
    # Debounce plumbing
    # ------------------------------------------------------------------

    def _on_text_changed(self, text: str) -> None:
        """Restart the debounce on input; emit immediately when cleared."""
        if text == "":
            # Clearing bypasses the debounce so the full list is restored
            # at once (✕ button, select-all-delete, or Esc all land here).
            self._timer.stop()
            self.filterChanged.emit("")
            return
        self._timer.start(self._delay_ms)

    def _emit_now(self) -> None:
        """Emit the current text as the settled filter value."""
        self.filterChanged.emit(self.text())

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt override
        """Clear on ``Esc`` when there is text; otherwise let it propagate."""
        from PySide6.QtCore import Qt

        if event.key() == Qt.Key.Key_Escape:
            if self.text():
                self.clear()  # → textChanged("") → immediate emit
                event.accept()
                return
            # Empty field: don't steal Esc from the host panel/dialog.
            event.ignore()
            return
        super().keyPressEvent(event)
