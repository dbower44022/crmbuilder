"""MultiSortHeaderView — multi-key precedence indicator + click routing.

PI-117 / WTK-068. Qt's stock ``QHeaderView`` tracks a single
``sortIndicatorSection``, so it cannot show multi-key precedence. This
subclass paints a compact ``▲1`` / ``▼2`` glyph — arrow for direction,
number for the 1-based precedence rank — in every active sort column, and
routes header clicks into the :class:`MultiSortProxyModel` it is attached
to:

- **plain click** → ``proxy.set_primary(col)`` (single-key sort / toggle);
- **Ctrl- or Shift-click** → ``proxy.cycle_secondary(col)`` (add / cycle a
  secondary key).

It subscribes to the proxy's ``sortKeysChanged`` signal so the indicators
always reflect live precedence. Installed on both link surfaces so the
indicator rendering and modifier semantics stay identical.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHeaderView

# Right-margin (px) for the precedence glyph inside a header cell.
_GLYPH_MARGIN = 6


class MultiSortHeaderView(QHeaderView):
    """A horizontal header that renders multi-key sort precedence."""

    def __init__(
        self, orientation: Qt.Orientation, parent=None
    ) -> None:
        super().__init__(orientation, parent)
        self._proxy = None
        self._active_modifiers: Qt.KeyboardModifier = (
            Qt.KeyboardModifier.NoModifier
        )
        self.setSectionsClickable(True)
        # We paint our own multi-key indicator; suppress Qt's single
        # arrow so the two do not collide.
        self.setSortIndicatorShown(False)
        self.sectionClicked.connect(self._on_section_clicked)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def attach_proxy(self, proxy) -> None:
        """Bind to a :class:`MultiSortProxyModel` and repaint on changes."""
        self._proxy = proxy
        proxy.sortKeysChanged.connect(self._on_sort_keys_changed)
        self._on_sort_keys_changed()

    def indicator_for(
        self, column: int
    ) -> tuple[int, Qt.SortOrder] | None:
        """Return ``(rank, order)`` for an active sort column, else ``None``.

        ``rank`` is the 1-based precedence; ``order`` the column's own sort
        direction. Inactive columns return ``None`` (no glyph). Exposed for
        tests and for :meth:`paintSection`.
        """
        if self._proxy is None:
            return None
        for rank, (col, order) in enumerate(self._proxy.sort_keys(), start=1):
            if col == column:
                return (rank, order)
        return None

    # ------------------------------------------------------------------
    # Click routing
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        # Capture the modifiers active at press; sectionClicked (emitted on
        # release) reads them via _on_section_clicked.
        self._active_modifiers = event.modifiers()
        super().mousePressEvent(event)

    def _on_section_clicked(self, section: int) -> None:
        self._route_click(section, self._active_modifiers)

    def _route_click(
        self, section: int, modifiers: Qt.KeyboardModifier
    ) -> None:
        """Translate a (section, modifiers) click into a proxy mutation.

        Exposed as a method so tests can drive routing deterministically
        without synthesising real mouse events.
        """
        if self._proxy is None:
            return
        modifier_held = bool(
            modifiers
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        )
        if modifier_held:
            self._proxy.cycle_secondary(section)
        else:
            self._proxy.set_primary(section)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def _on_sort_keys_changed(self) -> None:
        viewport = self.viewport()
        if viewport is not None:
            viewport.update()

    def paintSection(  # noqa: N802 (Qt override)
        self, painter: QPainter, rect, logical_index: int
    ) -> None:
        super().paintSection(painter, rect, logical_index)
        indicator = self.indicator_for(logical_index)
        if indicator is None:
            return
        rank, order = indicator
        arrow = "▲" if order == Qt.SortOrder.AscendingOrder else "▼"
        glyph = f"{arrow}{rank}"
        painter.save()
        painter.drawText(
            rect.adjusted(0, 0, -_GLYPH_MARGIN, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            glyph,
        )
        painter.restore()
