"""DateField — QDateEdit wrapper configured for MM-DD-YY round-tripping.

The v2 access layer stores dates as ``MM-DD-YY`` strings (two-digit
year). DateField wraps ``QDateEdit`` with the calendar popup enabled
and mediates between Qt's ``QDate`` type and the access layer's string
format. It defaults to today on a fresh construction; callers
pre-populate from an existing record via ``set_date(text)``.

Two-digit year mapping uses 2000+yy. v2's working-date range is the
2020s, so the simple offset is correct; if the project ever needs
1900-era dates, replace with ``QLocale``-aware parsing.

Added in v2-ui-v0.2-A as part of the foundation refactor (DEC-026's
calendar-widget carve-out, DEC-028's reusable widget pattern).
"""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QDateEdit, QHBoxLayout, QWidget

_DISPLAY_FORMAT = "MM-dd-yy"


def _today_string() -> str:
    return QDate.currentDate().toString(_DISPLAY_FORMAT)


class DateField(QWidget):
    """Composite widget exposing a single ``QDateEdit`` with calendar popup.

    Public API:

    * ``date_text() -> str`` — the current MM-DD-YY string.
    * ``set_date(text: str) -> None`` — pre-populate from MM-DD-YY;
      empty string resets to today.
    * ``dateChanged(str)`` — emitted whenever the underlying ``QDateEdit``
      changes its value.
    """

    dateChanged = Signal(str)  # noqa: N815 — matches Qt signal naming

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._edit = QDateEdit()
        self._edit.setCalendarPopup(True)
        self._edit.setDisplayFormat(_DISPLAY_FORMAT)
        self._edit.setDate(QDate.currentDate())
        self._edit.dateChanged.connect(self._on_internal_changed)
        layout.addWidget(self._edit)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def date_text(self) -> str:
        return self._edit.date().toString(_DISPLAY_FORMAT)

    def set_date(self, text: str) -> None:
        if not text:
            self._edit.setDate(QDate.currentDate())
            return
        parsed = QDate.fromString(text, _DISPLAY_FORMAT)
        if not parsed.isValid():
            # Fall back to today rather than raising; the access layer
            # will reject the eventual write if the value is meaningless,
            # surfacing a clearer error than a Qt-level parse exception.
            self._edit.setDate(QDate.currentDate())
            return
        self._edit.setDate(parsed)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_internal_changed(self, _date: QDate) -> None:
        self.dateChanged.emit(self.date_text())
