"""Inline linked-record preview for the link panels (PI-118 / WTK-071).

A floating, read-only **preview card** that inspects a linked record's key
fields — *what is ``PI-048``, what's its status, when was it touched* —
without navigating away from the parent record. Reachable from within both
link surfaces:

- the embedded :class:`~crmbuilder_v2.ui.widgets.references_section.ReferencesSection`
  (row-targeted), and
- the standalone :class:`~crmbuilder_v2.ui.panels.references.ReferencesPanel`
  (endpoint-cell-targeted).

The design is specified in
``PRDs/product/crmbuilder-v2/pi-118-link-panel-inline-preview-ui-design.md``
(WTK-070). The card is **additive** over the PI-116 debounced filter and the
PI-117 ``MultiSortProxyModel`` / ``GroupingTreeModel`` rebuild: it is a
floating sibling fed by each surface's *already-shipped* index→record
resolver (``ReferencesSection._row_at`` / ``ReferencesPanel._record_at_index``),
so it composes with any sort / grouping / filter state and **never** mutates a
model (§3.7–§3.8 of the design).

Two reusable classes:

- :class:`LinkedRecordPreviewCard` — the floating inspector widget. Renders a
  header + always-available fields instantly, then has its type-specific grid
  filled by an optional background enrichment read.
- :class:`PreviewController` — wires hover dwell + keyboard activation,
  anchoring, dismiss-on-reorder/regroup/refilter, and the enrichment read into
  a host view, reusing the host's injected resolver + field extractor. One
  controller serves both the flat table and the grouped tree of a surface.

Enrichment uses only the **existing** per-type read
``StorageClient.get_<type>(identifier)`` on a background ``Worker`` — no new
storage / API / access work (the reference rows already carry
``target_type`` / ``target_id``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
    QTimer,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.exceptions import NotFoundError
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.references_section import _fmt_dt
from crmbuilder_v2.ui.workers import run_in_thread

_DASH = "—"

# Fixed comfortable card width; height sizes to content (§3.3).
_CARD_WIDTH = 360

# Per-type key-field map (§4.1). ``entity_type`` → ordered ``(label,
# record_key)`` pairs naming up to three *type-specific* fields to surface in
# the card's grid after the enrichment read resolves. Presentation config
# only — adding a type extends this dict, no storage change. The
# always-available Status / Created / Updated and the relationship context are
# rendered separately from the row data the card already holds. Types absent
# here (or whose fields are all empty) fall through to the "No additional
# details." empty state.
_PREVIEW_FIELDS: dict[str, list[tuple[str, str]]] = {
    "planning_item": [("Item type", "item_type"), ("Status", "status")],
    "decision": [("Status", "status")],
    "session": [("Medium", "session_medium"), ("Status", "session_status")],
    "risk": [("Probability", "probability"), ("Impact", "impact"), ("Status", "status")],
    "topic": [("Name", "name")],
    "domain": [("Status", "status")],
    "entity": [("Status", "status")],
    "requirement": [("Status", "status")],
}

_State = Literal["loading", "loaded", "empty", "error", "not_found"]

# Body text per non-loaded state (§3.5).
_STATE_TEXT: dict[str, str] = {
    "loading": "Loading…",
    "loaded": "",
    "empty": "No additional details.",
    "error": "Couldn't load details.",
    "not_found": "Record not found (it may have been deleted).",
}


def _pretty_type(entity_type: str) -> str:
    """Render an ``entity_type`` slug as a title-cased label (``planning_item``
    → ``Planning Item``), mirroring the grid's type column."""
    return entity_type.replace("_", " ").title()


def extract_preview_fields(
    entity_type: str, record: dict[str, Any]
) -> list[tuple[str, str]]:
    """Select the type-specific ``(label, value)`` rows for a resolved record.

    Reads :data:`_PREVIEW_FIELDS` for ``entity_type`` and pulls each named key
    from ``record``, dropping empties. Returns ``[]`` when the type has no map
    entry or the record exposes none of its fields — the caller renders the
    *"No additional details."* empty state in that case.
    """
    out: list[tuple[str, str]] = []
    for label, key in _PREVIEW_FIELDS.get(entity_type, []):
        value = record.get(key)
        if value not in (None, ""):
            out.append((label, str(value)))
    return out


class LinkedRecordPreviewCard(QWidget):
    """A floating, read-only inspector for one linked record.

    Constructed as a top-level ``ToolTip`` (hover, non-focus-stealing) or
    ``Popup`` (keyboard-pinned, focusable so Esc/Tab and screen readers work);
    the controller picks the flag per activation via ``focusable``. Chrome
    reuses the ``EngagementPicker`` popup precedent (1 px ``neutral.200``
    border, white fill) and the ``t(...)`` styling tokens — no new tokens.

    The card renders its header + always-available fields immediately from the
    row data the caller already holds (:meth:`show_for`), then has its
    type-specific grid rows filled once the optional enrichment read resolves
    (:meth:`set_enriched`); :meth:`set_state` drives the loading / empty /
    error / not-found body text.
    """

    def __init__(
        self, *, focusable: bool = False, parent: QWidget | None = None
    ) -> None:
        flag = (
            Qt.WindowType.Popup if focusable else Qt.WindowType.ToolTip
        )
        super().__init__(parent, flag)
        self.setObjectName("linked_record_preview_card")
        self.setFixedWidth(_CARD_WIDTH)
        self.setStyleSheet(
            f"#linked_record_preview_card {{"
            f"  background-color: #FFFFFF;"
            f"  border: 1px solid {t('color.neutral.200')};"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(int(t("space.2").rstrip("px")))

        # Header line: "<Type label> · <Identifier>".
        self._header_label = QLabel(self)
        self._header_label.setObjectName("linked_record_preview_header")
        self._header_label.setStyleSheet(
            f"font-size: {t('font.size.body')};"
            f" font-weight: {t('font.weight.semibold')};"
            f" color: {t('color.neutral.800')};"
        )
        layout.addWidget(self._header_label)

        # Title: the linked record's title/name, one line, elided on overflow.
        self._title_label = QLabel(self)
        self._title_label.setObjectName("linked_record_preview_title")
        self._title_label.setWordWrap(False)
        self._title_label.setStyleSheet(
            f"color: {t('color.neutral.800')};"
        )
        layout.addWidget(self._title_label)

        # Key-field grid (2-column label/value).
        self._grid_container = QWidget(self)
        self._grid = QGridLayout(self._grid_container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(int(t("space.3").rstrip("px")))
        self._grid.setVerticalSpacing(int(t("space.1").rstrip("px")))
        self._grid.setColumnStretch(1, 1)
        layout.addWidget(self._grid_container)

        # State / body line (loading / empty / error / not-found).
        self._state_label = QLabel(self)
        self._state_label.setObjectName("linked_record_preview_state")
        self._state_label.setStyleSheet(
            f"color: {t('color.neutral.500')};"
        )
        self._state_label.setVisible(False)
        layout.addWidget(self._state_label)

        # Footer hint matching the existing navigation gesture (§3.3).
        self._footer_label = QLabel("Double-click / Enter to open", self)
        self._footer_label.setObjectName("linked_record_preview_footer")
        self._footer_label.setStyleSheet(
            f"font-size: {t('font.size.small')};"
            f" color: {t('color.neutral.500')};"
        )
        layout.addWidget(self._footer_label)

        # Always-available rows rendered from the row data (kept so
        # set_enriched can append type-specific rows beneath them).
        self._base_rows: list[tuple[str, str]] = []
        self._entity_type = ""
        self._identifier = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_for(
        self,
        record: dict[str, Any],
        *,
        entity_type: str,
        identifier: str,
        relationship: str | None,
        anchor_global: QPoint,
        focusable: bool = False,
    ) -> None:
        """Render the header + always-available fields and position the card.

        ``record`` carries whatever the host row already holds — for the
        embedded section that is identifier, type, title, status, created,
        updated (a complete card with no read); for the standalone panel only
        the endpoint tuple, so the body opens as *"Loading…"*. ``relationship``
        is the row's kind label (e.g. *"Blocked by"*), rendered as relationship
        context (embedded section only). The card is positioned near
        ``anchor_global``, flipping above / left when it would clip the screen.
        """
        # The window flag is fixed at construction; reassert it here only when
        # the card has not been shown yet (the controller builds a fresh card
        # per open, so this is a no-op safety net).
        if not self.isVisible():
            self.setWindowFlag(
                Qt.WindowType.Popup if focusable else Qt.WindowType.ToolTip,
                True,
            )

        self._entity_type = entity_type
        self._identifier = identifier
        self._header_label.setText(f"{_pretty_type(entity_type)} · {identifier}")
        self._title_label.setText(str(record.get("title") or _DASH))

        rows: list[tuple[str, str]] = []
        if relationship:
            rows.append(("Relationship", relationship))
        status = record.get("status")
        if status not in (None, ""):
            rows.append(("Status", str(status)))
        created = record.get("created") or record.get("created_at")
        if created not in (None, ""):
            rows.append(("Created", _fmt_dt(created)))
        updated = record.get("updated") or record.get("updated_at")
        if updated not in (None, ""):
            rows.append(("Updated", _fmt_dt(updated)))
        self._base_rows = rows
        self._render_grid(rows)
        self.set_state("loaded" if rows else "loading")
        self._update_accessibility(rows)

        self.adjustSize()
        self._move_to(anchor_global)
        self.show()

    def set_enriched(self, fields: list[tuple[str, str]]) -> None:
        """Append the type-specific rows once the enrichment read resolves.

        Replaces the type-specific placeholder area (the rows beneath the
        always-available base rows) with ``fields``; the header, title, and
        base rows are untouched.
        """
        combined = self._base_rows + list(fields)
        self._render_grid(combined)
        self._update_accessibility(combined)
        self.adjustSize()

    def set_state(self, state: _State) -> None:
        """Drive the §3.5 body text (loading / empty / error / not-found).

        ``loaded`` hides the body line entirely; every other state shows its
        dim documented sentence.
        """
        text = _STATE_TEXT.get(state, "")
        self._state_label.setText(text)
        self._state_label.setVisible(bool(text))

    def dismiss(self) -> None:
        """Hide and schedule deletion (per the v2 transient-widget GC rule).

        A card that outlives its host while an enrichment worker is pending
        must be torn down deterministically, so it is hidden and
        ``deleteLater``-d rather than merely hidden.
        """
        self.hide()
        self.deleteLater()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _render_grid(self, rows: list[tuple[str, str]]) -> None:
        """Clear and repopulate the 2-column label/value grid."""
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for r, (label, value) in enumerate(rows):
            label_widget = QLabel(label, self._grid_container)
            label_widget.setStyleSheet(
                f"font-size: {t('font.size.small')};"
                f" color: {t('color.neutral.500')};"
            )
            value_widget = QLabel(value or _DASH, self._grid_container)
            value_widget.setStyleSheet(
                f"font-size: {t('font.size.small')};"
                f" color: {t('color.neutral.800')};"
            )
            value_widget.setWordWrap(False)
            self._grid.addWidget(label_widget, r, 0, Qt.AlignmentFlag.AlignTop)
            self._grid.addWidget(value_widget, r, 1, Qt.AlignmentFlag.AlignTop)

    def _update_accessibility(self, rows: list[tuple[str, str]]) -> None:
        """Set accessibleName/Description so a screen reader announces the card."""
        self.setAccessibleName(
            f"{_pretty_type(self._entity_type)} {self._identifier}"
        )
        description = "; ".join(f"{label}: {value}" for label, value in rows)
        self.setAccessibleDescription(description)

    def _move_to(self, anchor_global: QPoint) -> None:
        """Position the card at ``anchor_global``, flipping at screen edges."""
        x, y = anchor_global.x(), anchor_global.y()
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            size = self.sizeHint()
            if x + size.width() > avail.right():
                x = max(avail.left(), x - size.width())
            if y + size.height() > avail.bottom():
                y = max(avail.top(), y - size.height())
        self.move(x, y)


class PreviewController(QObject):
    """Wires hover + keyboard activation, anchoring, dismissal, and enrichment.

    Installed on a host surface (the embedded section or the standalone panel)
    and shared across that surface's flat table and grouped tree via
    :meth:`attach_view`. Only *which index resolves to which record* differs
    between surfaces, and that is injected:

    - ``resolver`` — ``Callable[[QModelIndex], dict | None]`` mapping an index
      on any live view back to the underlying edge dict (``_row_at`` /
      ``_record_at_index``). A group-node index resolves to ``None`` → no card.
    - ``extractor`` — ``Callable[[dict, int], tuple | None]`` returning
      ``(entity_type, identifier, title, relationship)`` for the resolved
      record and the hovered *column*, or ``None`` when that column has no
      previewable endpoint (the standalone panel's Relationship column).

    Enrichment calls the existing ``client.get_<type>(identifier)`` on a
    background worker; a monotonic token drops a stale read that resolves after
    the card has re-targeted or closed (§3.4). The controller holds **no**
    model and never mutates one (§3.8).
    """

    #: Hover dwell before a card opens — deliberately longer than PI-116's
    #: 250 ms filter debounce so a preview does not flicker during ordinary
    #: mouse travel across a long link list (§3.2).
    DWELL_MS = 400
    #: Grace period after the pointer leaves the row/cell before the card
    #: dismisses, so the user can move onto the card without it vanishing.
    GRACE_MS = 200

    def __init__(
        self,
        host: QWidget,
        resolver: Callable[[QModelIndex], dict[str, Any] | None],
        client: Any,
        extractor: Callable[
            [dict[str, Any], int], tuple[str, str, str | None, str | None] | None
        ],
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or host)
        self._host = host
        self._resolver = resolver
        self._client = client
        self._extractor = extractor

        self._views: list[QAbstractItemView] = []
        self._card: LinkedRecordPreviewCard | None = None
        self._pinned = False  # current card was keyboard-pinned

        # Stale-read guard: every open stamps a new token; a read whose token
        # is no longer current is dropped.
        self._token = 0
        self._enrich_tokens: dict[int, int] = {}
        self._enrich_types: dict[int, str] = {}
        self._in_flight: list[Any] = []

        # Hover bookkeeping.
        self._hover_view: QAbstractItemView | None = None
        self._hover_index = QModelIndex()
        self._dwell_timer = QTimer(self)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.setInterval(self.DWELL_MS)
        self._dwell_timer.timeout.connect(self._on_dwell_elapsed)
        self._grace_timer = QTimer(self)
        self._grace_timer.setSingleShot(True)
        self._grace_timer.setInterval(self.GRACE_MS)
        self._grace_timer.timeout.connect(self.dismiss)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def attach_view(self, view: QAbstractItemView) -> None:
        """Install hover + keyboard handling on ``view`` (and its viewport).

        Mouse events arrive on the viewport; key events on the view itself, so
        the event filter is installed on both. Re-targeting a keyboard-pinned
        card on arrow-key selection is wired through the view's selection
        model when one is present.
        """
        self._views.append(view)
        # Mouse tracking MUST be enabled on the viewport or Qt only delivers
        # MouseMove while a button is held — so hover-dwell would never fire and
        # the card could only be opened via the Space key (PI-118 follow-up fix:
        # the original WTK-071 build installed the filter but not tracking, so
        # the hover trigger was dead in the real app; unit tests missed it by
        # posting MouseMove straight to eventFilter).
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)
        view.installEventFilter(self)
        sel_model = view.selectionModel()
        if sel_model is not None:
            sel_model.currentChanged.connect(self._on_current_changed)

    def shutdown(self) -> None:
        """Dismiss any card and wait for in-flight enrichment workers.

        Mirrors ``ListDetailPanel.closeEvent`` so worker threads do not
        outlive the host widget. Surfaces call this from their ``closeEvent``.
        """
        self.dismiss()
        for worker in list(self._in_flight):
            try:
                worker.wait(2000)
            except Exception:  # noqa: BLE001 — best-effort teardown
                pass

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def eventFilter(  # noqa: N802 (Qt naming)
        self, obj: QObject, event: QEvent
    ) -> bool:
        et = event.type()
        if et == QEvent.Type.MouseMove:
            view = self._view_for_viewport(obj)
            if view is not None and isinstance(event, QMouseEvent):
                self._on_mouse_move(view, event.position().toPoint())
        elif et == QEvent.Type.Leave:
            if self._view_for_viewport(obj) is not None:
                self._dwell_timer.stop()
                self._start_grace()
        elif et == QEvent.Type.KeyPress and obj in self._views:
            if isinstance(event, QKeyEvent):
                if self._on_key_press(obj, event):  # type: ignore[arg-type]
                    return True
        return super().eventFilter(obj, event)

    def _view_for_viewport(self, obj: QObject) -> QAbstractItemView | None:
        for view in self._views:
            if view.viewport() is obj:
                return view
        return None

    def _on_mouse_move(self, view: QAbstractItemView, pos: QPoint) -> None:
        # Moving back over the surface cancels a pending dismiss.
        self._grace_timer.stop()
        index = view.indexAt(pos)
        if not index.isValid():
            self._dwell_timer.stop()
            self._hover_view = None
            self._hover_index = QModelIndex()
            return
        # Same cell → leave the running dwell / open card alone.
        if (
            view is self._hover_view
            and index.row() == self._hover_index.row()
            and index.column() == self._hover_index.column()
            and index.internalId() == self._hover_index.internalId()
        ):
            return
        self._hover_view = view
        self._hover_index = QModelIndex(index)
        self._dwell_timer.start()

    def _on_dwell_elapsed(self) -> None:
        if self._hover_view is not None and self._hover_index.isValid():
            self._open(self._hover_view, self._hover_index, focusable=False)

    def _on_key_press(self, view: QAbstractItemView, event: QKeyEvent) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._open_for_selection(view)
            return True
        if key == Qt.Key.Key_Escape and self._card is not None:
            self.dismiss()
            return True
        return False

    def _open_for_selection(self, view: QAbstractItemView) -> None:
        index = view.currentIndex()
        if not index.isValid():
            return
        self._open(view, index, focusable=True)

    def _on_current_changed(
        self, current: QModelIndex, _previous: QModelIndex
    ) -> None:
        # Arrow-key selection moves a keyboard-pinned card to the new row.
        if self._card is None or not self._pinned:
            return
        view = self._hover_view or (self._views[0] if self._views else None)
        if view is not None and current.isValid():
            self._open(view, current, focusable=True)

    # ------------------------------------------------------------------
    # Open + enrich
    # ------------------------------------------------------------------

    def _open(
        self, view: QAbstractItemView, index: QModelIndex, *, focusable: bool
    ) -> None:
        record = self._resolver(index)
        if record is None:  # group node / invalid → no card
            self.dismiss()
            return
        target = self._extractor(record, index.column())
        if target is None:  # non-previewable column (panel Relationship)
            self.dismiss()
            return
        entity_type, identifier, title, relationship = target
        if not entity_type or not identifier:
            self.dismiss()
            return

        self._token += 1
        token = self._token
        self._pinned = focusable

        # Tear down any prior card before showing the new one.
        self._dismiss_card_only()
        card = LinkedRecordPreviewCard(focusable=focusable, parent=self._host)
        self._card = card
        anchor = view.viewport().mapToGlobal(
            view.visualRect(index).bottomLeft()
        )
        render = {**record, "title": title}
        card.show_for(
            render,
            entity_type=entity_type,
            identifier=identifier,
            relationship=relationship,
            anchor_global=anchor,
            focusable=focusable,
        )
        self._start_enrichment(entity_type, identifier, token)

    def _start_enrichment(
        self, entity_type: str, identifier: str, token: int
    ) -> None:
        getter = getattr(self._client, f"get_{entity_type}", None)
        if getter is None:
            # No per-type read for this entity (e.g. version-keyed singletons);
            # the always-available fields are all the card can show.
            if self._card is not None:
                self._card.set_state(
                    "loaded" if self._card._base_rows else "empty"
                )
            return
        if self._card is not None:
            self._card.set_state("loading")
        worker = run_in_thread(
            lambda: getter(identifier),
            on_success=self._on_enriched_success,
            on_error=self._on_enriched_error,
            parent=self._host,
        )
        self._enrich_tokens[id(worker)] = token
        self._enrich_types[id(worker)] = entity_type
        self._in_flight.append(worker)
        worker.finished.connect(self._on_worker_finished)

    def _on_enriched_success(self, record: Any) -> None:
        worker = self.sender()
        token = self._enrich_tokens.get(id(worker), self._token) if worker else self._token
        entity_type = (
            self._enrich_types.get(id(worker), "") if worker else ""
        )
        if isinstance(record, dict):
            self._apply_enrichment(record, entity_type, token)

    def _on_enriched_error(self, exc: Any) -> None:
        worker = self.sender()
        token = self._enrich_tokens.get(id(worker), self._token) if worker else self._token
        self._apply_enrich_error(exc, token)

    def _apply_enrichment(
        self, record: dict[str, Any], entity_type: str, token: int
    ) -> None:
        """Fill the card's type-specific rows, dropping a stale-token read."""
        if token != self._token or self._card is None:
            return
        fields = extract_preview_fields(entity_type, record)
        if fields:
            self._card.set_enriched(fields)
            self._card.set_state("loaded")
        else:
            self._card.set_state("empty")

    def _apply_enrich_error(self, exc: Exception, token: int) -> None:
        """Map a read failure to the not-found / error body, dropping stale."""
        if token != self._token or self._card is None:
            return
        if isinstance(exc, NotFoundError):
            self._card.set_state("not_found")
        else:
            self._card.set_state("error")

    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if worker is None:
            return
        self._enrich_tokens.pop(id(worker), None)
        self._enrich_types.pop(id(worker), None)
        try:
            self._in_flight.remove(worker)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Dismiss
    # ------------------------------------------------------------------

    def dismiss(self) -> None:
        """Dismiss any open card and invalidate in-flight reads.

        Connected by each surface to its reorder / regroup / refilter signals
        (§3.7): any change that can move or remove the anchored row closes the
        card; the user re-points to reopen. Bumping the token here drops a
        read that resolves after the dismiss.
        """
        self._dwell_timer.stop()
        self._grace_timer.stop()
        self._token += 1
        self._pinned = False
        self._dismiss_card_only()

    def _dismiss_card_only(self) -> None:
        if self._card is not None:
            self._card.dismiss()
            self._card = None

    def _start_grace(self) -> None:
        if self._card is not None:
            self._grace_timer.start()
