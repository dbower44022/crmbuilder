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

**Lifetime guards (PI-159 / WTK-119).** Paint and update events can be
delivered during teardown windows (pytest-qt's ``_process_events``, deferred
deletions crossing event-loop iterations) to a header whose owning table,
proxy, or paint device is mid-destruction — a SIGSEGV, not an exception.
Every path that touches a C++ object therefore probes ``shiboken6.isValid``
first and degrades to a no-op on a torn-down object. Transient-object rule:
``paintSection`` constructs no QStyle/QStyleOption objects — it delegates
stock painting to ``super()`` and draws with the supplied painter. If a
future change needs a ``QStyleOptionHeader``, construct it per-call as a
Python local (a value type, so ``deleteLater()`` does not apply), never
cached on the instance across paints.
"""

from __future__ import annotations

import shiboken6
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
        """Bind to a :class:`MultiSortProxyModel` and repaint on changes.

        Also subscribes to the proxy's ``destroyed`` signal so a destroyed
        proxy is unreachable from the paint path even before the validity
        probes in :meth:`indicator_for` / :meth:`paintSection`.
        """
        self._proxy = proxy
        proxy.sortKeysChanged.connect(self._on_sort_keys_changed)
        proxy.destroyed.connect(self._on_proxy_destroyed)
        self._on_sort_keys_changed()

    def detach_proxy(self) -> None:
        """Disconnect from the attached proxy and clear the back-reference.

        Safe to call with no proxy attached or with a proxy whose C++
        object is already gone — teardown must never raise.
        """
        proxy = self._proxy
        self._proxy = None
        if proxy is None or not shiboken6.isValid(proxy):
            return
        try:
            proxy.sortKeysChanged.disconnect(self._on_sort_keys_changed)
            proxy.destroyed.disconnect(self._on_proxy_destroyed)
        except RuntimeError:
            pass  # already disconnected

    def _on_proxy_destroyed(self) -> None:
        self._proxy = None

    def indicator_for(
        self, column: int
    ) -> tuple[int, Qt.SortOrder] | None:
        """Return ``(rank, order)`` for an active sort column, else ``None``.

        ``rank`` is the 1-based precedence; ``order`` the column's own sort
        direction. Inactive columns return ``None`` (no glyph). Exposed for
        tests and for :meth:`paintSection`, so it must be safe standalone:
        a missing or destroyed proxy reads as "no active sort".
        """
        proxy = self._proxy
        if proxy is None or not shiboken6.isValid(proxy):
            return None
        for rank, (col, order) in enumerate(proxy.sort_keys(), start=1):
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
        # The proxy's sortKeysChanged can fire while the header is dying;
        # don't touch the C++ side of a half-destructed widget.
        if not shiboken6.isValid(self):
            return
        viewport = self.viewport()
        if viewport is not None:
            viewport.update()

    def paintSection(  # noqa: N802 (Qt override)
        self, painter: QPainter, rect, logical_index: int
    ) -> None:
        if not shiboken6.isValid(self) or not painter.isActive():
            return
        super().paintSection(painter, rect, logical_index)
        indicator = self.indicator_for(logical_index)
        if indicator is None:
            return
        rank, order = indicator
        arrow = "▲" if order == Qt.SortOrder.AscendingOrder else "▼"
        glyph = f"{arrow}{rank}"
        # Last fence: PySide6 raises RuntimeError on wrapper access it can
        # detect as already-deleted; a skipped glyph beats a crash. Kept
        # narrow so programming errors still surface.
        try:
            painter.save()
            painter.drawText(
                rect.adjusted(0, 0, -_GLYPH_MARGIN, 0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                glyph,
            )
            painter.restore()
        except RuntimeError:
            return
