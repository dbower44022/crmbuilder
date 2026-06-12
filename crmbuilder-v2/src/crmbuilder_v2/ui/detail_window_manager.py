"""Standalone non-modal detail-window manager (PI-121 / WTK-079).

The related-record grids (``ReferencesSection`` and ``WorkTaskGridSection``)
carry a per-row "Open <item type>" action that emits ``open_requested`` and
bubbles it up to :class:`~crmbuilder_v2.ui.main_window.MainWindow`. This module
turns that request into a *separate, non-modal, persistent* detail window
showing the related record's full view, leaving the originating view exactly
where it was — so two records can sit side by side instead of one replacing the
other (the "Go to" / ``navigate_requested`` path).

Design (``PRDs/product/crmbuilder-v2/pi-121-open-item-detail-window-ui-design.md``
§3.3, §3.5): the window content is an *existing* :class:`ListDetailPanel` built
by the shared :func:`crmbuilder_v2.ui.main_window.build_panel` factory and
pre-selected to the target record — one generic window host, never one window
class per entity type (C4). Windows are owned/tracked by the manager's strong
reference list (no cap, C3) and ``WA_DeleteOnClose`` collects them on close
(C8). Unknown or unopenable types log and no-op (C7).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMainWindow, QWidget

from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.widgets.references_section import _pretty_entity_type

_log = logging.getLogger("crmbuilder_v2.ui.detail_window_manager")

# Cascade offset (px) so a freshly-spawned window does not land exactly on top
# of its predecessor (C3 — independently positioned). Cosmetic and tunable.
_CASCADE_DELTA = 32
# Default size of a spawned detail window. The content is a full master/detail
# panel, so it wants room. Cosmetic and tunable.
_DEFAULT_WIDTH = 900
_DEFAULT_HEIGHT = 640


class StandaloneDetailWindow(QMainWindow):
    """A non-modal top-level window hosting one entity panel (PI-121 / WTK-079).

    The central widget is a factory-built :class:`ListDetailPanel`, pre-selected
    to the target record, so the window shows the identical full detail the main
    window would — including the record's own link grids — with no per-type
    window code (C4). ``WA_DeleteOnClose`` plus the manager's strong reference
    keep it GC-safe while visible and collected on close (C8); ``closed`` fires
    on close so the manager drops its reference.
    """

    closed = Signal(object)

    def __init__(self, panel: ListDetailPanel, title: str) -> None:
        # Parent is intentionally omitted so the window is a genuine top-level
        # window; ownership is the manager's ref list, not Qt parenting.
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(title)
        self._panel = panel
        self.setCentralWidget(panel)
        self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)

    @property
    def panel(self) -> ListDetailPanel:
        """The hosted detail panel (read-only accessor for callers/tests)."""
        return self._panel

    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Emit ``closed`` so the manager drops its reference, then close.

        Qt delivers ``closeEvent`` only to this top-level window, NOT to the
        hosted panel, so the panel's own worker-draining ``closeEvent`` never
        runs on a window close. We therefore drain the panel's workers
        explicitly here — otherwise ``WA_DeleteOnClose`` deletes the panel while
        a worker QThread is still live, which aborts the process (a flaky
        teardown SIGABRT that surfaced running the full suite in one process).
        """
        self.closed.emit(self)
        self._panel.drain_workers()
        super().closeEvent(event)


class DetailWindowManager(QObject):
    """Spawns, tracks, and tears down standalone detail windows (PI-121).

    Owned by :class:`~crmbuilder_v2.ui.main_window.MainWindow`. Each
    :meth:`open` call builds a fresh panel for the target entity type via the
    shared factory, hosts it in a non-modal :class:`StandaloneDetailWindow`,
    pre-selects the record, and keeps a strong reference until the window
    closes. There is no cap on how many windows coexist (C3); the originating
    view is never touched.

    :param client: the storage client threaded into every spawned panel.
    :param panel_factory: ``(label, client) -> QWidget`` — the shared
        ``build_panel`` that maps a sidebar label to a panel widget.
    :param navigate_router: ``(entity_type, identifier) -> None`` — the main
        window's navigation router, so a standalone panel's "Go to" navigates
        the *main* window (keeping "Go to" = navigate-in-main everywhere).
    :param parent_window: the owning main window; used for cascade positioning
        and to forward a standalone panel's ``connection_lost`` to the main
        window's uniform handler.
    """

    def __init__(
        self,
        client: StorageClient,
        panel_factory: Callable[[str, StorageClient], QWidget],
        navigate_router: Callable[[str, str], None],
        parent_window: QWidget,
    ) -> None:
        super().__init__(parent_window)
        self._client = client
        self._panel_factory = panel_factory
        self._navigate_router = navigate_router
        self._parent_window = parent_window
        self._windows: list[StandaloneDetailWindow] = []

    @property
    def open_windows(self) -> list[StandaloneDetailWindow]:
        """The currently-tracked live windows (read-only view for tests)."""
        return list(self._windows)

    def open(
        self, entity_type: str, identifier: str
    ) -> StandaloneDetailWindow | None:
        """Spawn a non-modal detail window for ``(entity_type, identifier)``.

        Returns the window, or ``None`` (logging a warning, spawning nothing)
        when the type has no sidebar panel or the panel is not a
        :class:`ListDetailPanel` — e.g. Chat or a not-yet-implemented
        placeholder (C7). Mirrors how the navigation router already warns on an
        unknown ``entity_type`` rather than crashing.
        """
        # Lazy import avoids a load-time cycle (main_window imports this module).
        from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL

        label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
        if label is None:
            _log.warning(
                "Open requested for unknown entity_type=%s identifier=%s",
                entity_type,
                identifier,
            )
            return None
        panel = self._panel_factory(label, self._client)
        if not isinstance(panel, ListDetailPanel):
            _log.warning(
                "Open requested for non-openable entity_type=%s (label=%s); "
                "no detail window spawned",
                entity_type,
                label,
            )
            return None

        title = f"{_pretty_entity_type(entity_type)} {identifier}"
        window = StandaloneDetailWindow(panel, title)
        # Route the spawned panel's own signals (§3.5): connection loss to the
        # main window's uniform handler; "Go to" to the main window's router
        # (so it navigates the main window, not the standalone one); "Open" back
        # to this manager so the windows are self-similar (a sibling spawns).
        panel.connection_lost.connect(self._forward_connection_lost)
        panel.navigate_requested.connect(self._navigate_router)
        panel.open_requested.connect(self.open)

        self._position(window)
        window.closed.connect(self._on_window_closed)
        self._windows.append(window)
        window.show()
        # Load + select the record (off-thread, via the panel's own machinery)
        # after the window is shown so the detail load has a live widget.
        panel.select_record_by_identifier(identifier)
        return window

    def _position(self, window: StandaloneDetailWindow) -> None:
        """Cascade the window off the most-recent one (or the parent window)."""
        anchor = self._windows[-1] if self._windows else self._parent_window
        if anchor is None:
            return
        pos = anchor.pos()
        window.move(pos.x() + _CASCADE_DELTA, pos.y() + _CASCADE_DELTA)

    def _forward_connection_lost(self, message: str) -> None:
        """Forward a standalone panel's connection loss to the main window."""
        handler = getattr(self._parent_window, "_on_panel_connection_lost", None)
        if handler is not None:
            handler(message)

    def _on_window_closed(self, window: StandaloneDetailWindow) -> None:
        """Drop the manager's reference so a closed window is collected."""
        try:
            self._windows.remove(window)
        except ValueError:
            pass
