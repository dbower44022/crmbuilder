"""Main window — phase tabs over a crash banner (REQ-526 / PI-432, DEC-953).

The window is organised by the **phase** the user is working in. A
``QTabWidget`` holds one pinned Chat tab (DEC-258 — one shared chat
surface, never one per tab) plus one :class:`PhasePage` per open phase.
Each phase page owns its own phase-scoped sidebar (Every session · Phase N
steps · All panels) and its own lazily-built panel stack, so switching
tabs and back restores the selected step, record and scroll position.

Phases open on demand from the "+" control at the end of the tab strip
(the PRD §4 phase list plus Operate CRMBuilder); open tabs persist per
engagement in a small JSON file. Quick open (Ctrl+K) reaches any record by
identifier prefix or any panel by name, so nothing behind the collapsed
All-panels index is more than a keystroke away.

Lifecycle ownership, the crash banner, bounded auto-reconnect, the
flap guard (REQ-297) and the health heartbeat (PI-111) are unchanged from
the single-sidebar window this replaced.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPushButton,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.config import api_log_path, get_settings
from crmbuilder_v2.ui.about_dialog import AboutDialog
from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.crash_banner import CrashBanner
from crmbuilder_v2.ui.detail_window_manager import DetailWindowManager
from crmbuilder_v2.ui.exceptions import StorageConnectionError
from crmbuilder_v2.ui.navigation import (
    DEFAULT_PHASE_KEY,
    OPERATE_KEY,
    PHASES,
    PHASES_BY_KEY,
    PhaseMap,
    load_phase_map,
)
from crmbuilder_v2.ui.panel_registry import (  # noqa: F401 — re-exported
    ALL_PANEL_LABELS,
    build_panel,
)
from crmbuilder_v2.ui.phase_page import CHAT_LABEL, PhasePage
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.main_window")

# Bounded auto-reconnect: on connection loss or an owned-subprocess
# crash, the window drives ``ServerLifecycle.start()`` (probe-then-spawn)
# up to this many times before falling back to the manual-Reconnect
# banner. Each attempt itself probes (1s) then polls a fresh spawn for up
# to 10s, so this is a hard ceiling on automatic recovery effort.
_MAX_RECONNECT_ATTEMPTS = 3

# Flap guard (REQ-297). A reconnect "succeeds" the moment ``GET /health``
# responds — but /health touches no data, so if the real fault is slow/failing
# *data* requests (e.g. a contended DB) the panel re-reports connection loss
# right after recovery and the reconnect/refresh cycle repeats forever, the
# bounded-retry counter resetting on each false recovery. Treat a connection
# loss that lands within ``_FLAP_WINDOW_S`` of the last successful recovery as
# a "flap"; after ``_MAX_FLAPS`` consecutive flaps, stop auto-reconnecting and
# surface the manual-Reconnect banner instead of looping.
_MAX_FLAPS = 3
_FLAP_WINDOW_S = 30.0

# Heartbeat: how often the window probes ``GET /health`` while ready, so
# an API that died between user actions (PI-111) — especially an external
# one the lifecycle doesn't crash-monitor — is detected proactively and
# auto-restarted before the next request fails. Probe runs off the GUI
# thread; only a connection failure triggers recovery.
_HEARTBEAT_INTERVAL_MS = 15000

# Where the per-engagement set of open phase tabs is remembered. Tests point
# this at a temporary directory.
_TAB_STATE_FILENAME = "phase-tabs.json"


def _default_tab_state_path() -> Path:
    return Path.home() / ".crmbuilder-v2" / _TAB_STATE_FILENAME


# Maps reference ``entity_type`` values (as stored in the database) to
# panel labels so the navigation router (cross-panel link clicks), the
# detail-window manager and quick open can resolve a record type to a panel.
ENTITY_TYPE_TO_SIDEBAR_LABEL: dict[str, str] = {
    "charter": "Charter",
    "status": "Status",
    "decision": "Decisions",
    "session": "Sessions",
    "risk": "Risks",
    "planning_item": "Planning Items",
    "topic": "Topics",
    "reference": "References",
    # Methodology entities (UI v0.4). Domains lands in slice B,
    # Entities in slice C, Processes in slice D, CRM Candidates in
    # slice E; the file-watch router uses this map to refresh the
    # panel on external snapshot rewrites.
    "domain": "Domains",
    "entity": "Entities",
    "process": "Processes",
    "crm_candidate": "CRM Candidates",
    "persona": "Personas",
    # REL-069 / PI-391: engagement participants that back personas.
    "participant": "Participants",
    "field": "Fields",
    # PI-004 methodology cohort (v0.5+).
    "requirement": "Requirements",
    "manual_config": "Manual Configs",
    # PI-004 cohort closer (v0.5+, resolves PI-004).
    "test_spec": "Test Specs",
    # v0.5 slice C: meta-DB engagement registry.
    "engagement": "Engagements",
    # v0.7 governance entities.
    "project": "Projects",
    "conversation": "Conversations",
    "reference_book": "Reference Books",
    "work_ticket": "Work Tickets",
    "close_out_payload": "Close-Out Payloads",
    "deposit_event": "Deposit Events",
    # PI-031: code change lifecycle.
    "commit": "Commits",
    # WTK-004: ADO delivery-model entities.
    "workstream": "Workstreams",
    "work_task": "Work Tasks",
    # PI-061: glossary term entity.
    "term": "Glossary",
    # PI-186 (PRJ-027): CRM-connection instance.
    "instance": "Instances",
    # PI-224: the release-pipeline staged-delivery container.
    "release": "Releases",
    # PI-330 (REL-026): Agent Profile Registry entities.
    "agent_profile": "Agent Profiles",
    "skill": "Skills",
    "governance_rule": "Governance Rules",
    "learning": "Learnings",
    # REL-016 / PI-067: cross-engagement reference libraries.
    "reference_entry": "Reference Entries",
}



def _is_refreshable(page: object) -> bool:
    """Whether a panel exposes a ``refresh()`` the window should drive.

    Every ``ListDetailPanel`` has one. A few panels are bare ``QWidget``s outside
    that base (e.g. the reconcile grid); those that nonetheless expose a
    ``refresh()`` are refreshed on navigation and engagement switch too (REQ-431).
    """
    return callable(getattr(page, "refresh", None))


class PhaseTabStore:
    """Remembers which phase tabs each engagement has open (best-effort JSON)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self, engagement_key: str) -> tuple[list[str], str | None]:
        """``(open phase keys in order, current phase key)`` or ``([], None)``."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            entry = data.get(engagement_key) or {}
            keys = [k for k in entry.get("open", []) if k in PHASES_BY_KEY]
            current = entry.get("current")
            return keys, current if current in keys else None
        except (OSError, ValueError, AttributeError):
            return [], None

    def save(self, engagement_key: str, open_keys: list[str], current: str | None) -> None:
        try:
            data = {}
            if self._path.exists():
                try:
                    data = json.loads(self._path.read_text(encoding="utf-8")) or {}
                except ValueError:
                    data = {}
            data[engagement_key] = {"open": list(open_keys), "current": current}
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except OSError:
            _log.debug("could not persist phase tabs to %s", self._path, exc_info=True)


class MainWindow(QMainWindow):
    """Top-level window: crash banner, engagement strip, phase tabs."""

    def __init__(
        self,
        lifecycle: ServerLifecycle,
        client: StorageClient,
        snapshot_dir: Path | None = None,
        active_context=None,
        tab_state_path: Path | None = None,
        phase_map: PhaseMap | None = None,
    ):
        super().__init__()
        self.setWindowTitle("CRMBuilder v2")
        self.resize(1200, 800)

        self._lifecycle = lifecycle
        self._client = client
        self._active_context = active_context
        self._top_strip = None
        self._picker = None
        self._crash_banner = CrashBanner()
        self._phase_map = phase_map if phase_map is not None else load_phase_map(client)
        self._tab_store = PhaseTabStore(tab_state_path or _default_tab_state_path())
        # Stale-marked (page, label) pairs: panels whose data changed while
        # the user was elsewhere (engagement switch). Refreshed on next select.
        self._stale: set[tuple[int, str]] = set()
        self._retired_pages: list[PhasePage] = []
        self._reap_timer = QTimer(self)
        self._reap_timer.setSingleShot(True)
        self._reap_timer.setInterval(500)
        self._reap_timer.timeout.connect(self._reap_retired_pages)
        # REQ-138 (PI-179): cross-record navigation history. Following a
        # reference pushes the originating (entry, identifier) onto the back
        # stack so the user can step back to where they came from.
        self._nav_back: list[tuple[str, str | None]] = []
        self._nav_forward: list[tuple[str, str | None]] = []
        # Tracks whether the storage API is currently reachable — gates the
        # on-select refresh so the default selection during ``__init__`` does
        # not fire an HTTP request before the lifecycle's probe completes.
        self._lifecycle_ready = False

        # Auto-reconnect state. ``_had_first_ready`` lets app.py route a
        # *runtime* spawn failure to the in-window banner instead of the
        # fatal startup dialog. ``_auto_reconnecting`` dedupes overlapping
        # triggers; ``_reconnect_attempts`` bounds the retry loop.
        self._had_first_ready = False
        self._auto_reconnecting = False
        self._reconnect_attempts = 0
        # Flap detection (REQ-297).
        self._last_ready_at: float | None = None
        self._flap_count = 0
        self._base_url = get_settings().api_base_url
        self._log_path = api_log_path()

        # Heartbeat (PI-111).
        self._heartbeat_in_flight = False
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(_HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat_tick)

        # PI-121 / WTK-079: standalone non-modal detail windows, built through
        # the same registry the phase pages use.
        self._detail_window_manager = DetailWindowManager(
            client=self._client,
            panel_factory=build_panel,
            navigate_router=self._on_navigate_requested,
            parent_window=self,
        )

        # --- Tabs ---------------------------------------------------------
        self._tabs = QTabWidget()
        self._tabs.setObjectName("phase_tabs")
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(False)
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Pinned Chat tab (index 0). One shared surface (DEC-258).
        self._chat_panel = build_panel(CHAT_LABEL, self._client, active_context=self._active_context)
        self._tabs.addTab(self._chat_panel, CHAT_LABEL)
        bar = self._tabs.tabBar()
        bar.setTabButton(0, bar.ButtonPosition.RightSide, None)
        bar.setTabButton(0, bar.ButtonPosition.LeftSide, None)

        # "+" — open another phase.
        self._add_phase_button = QToolButton()
        self._add_phase_button.setObjectName("add_phase_button")
        self._add_phase_button.setText("+")
        self._add_phase_button.setToolTip("Open a phase as a tab")
        self._add_phase_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._add_phase_menu = QMenu(self._add_phase_button)
        self._add_phase_menu.aboutToShow.connect(self._rebuild_add_phase_menu)
        self._add_phase_button.setMenu(self._add_phase_menu)
        self._tabs.setCornerWidget(self._add_phase_button, Qt.Corner.TopRightCorner)

        # --- Header: engagement strip + quick open -----------------------
        header = QWidget()
        header.setObjectName("window_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 8, 0)
        header_layout.setSpacing(8)
        if self._active_context is not None:
            from crmbuilder_v2.ui.widgets.engagement_top_strip import (
                EngagementTopStrip,
            )

            self._top_strip = EngagementTopStrip(self._active_context)
            self._top_strip.clicked.connect(self._on_top_strip_clicked)
            header_layout.addWidget(self._top_strip)
        header_layout.addStretch(1)
        self._quick_open_button = QPushButton("Quick open   Ctrl+K")
        self._quick_open_button.setObjectName("quick_open_button")
        self._quick_open_button.setFlat(True)
        self._quick_open_button.setStyleSheet(
            f"QPushButton {{ color: {t('color.neutral.500')}; border: 1px solid "
            f"{t('color.neutral.200')}; border-radius: {t('radius.default')}; "
            f"padding: 2px 10px; }}"
        )
        self._quick_open_button.clicked.connect(self.open_quick_open)
        header_layout.addWidget(self._quick_open_button)

        container = QWidget()
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self._crash_banner)
        outer_layout.addWidget(header)
        outer_layout.addWidget(self._tabs, stretch=1)
        self.setCentralWidget(container)

        self._crash_banner.reconnect_requested.connect(self._on_reconnect_requested)
        self._lifecycle.ready.connect(self._on_lifecycle_ready)

        self._build_menu_bar()

        # Open the remembered tabs for the engagement (or the default phase).
        self._restore_tabs_for_engagement()

    # ------------------------------------------------------------------
    # Compatibility accessors — the "current phase page" view of the window
    # ------------------------------------------------------------------

    @property
    def _sidebar(self):
        return self._current_phase_page().sidebar

    @property
    def _stack(self):
        return self._current_phase_page().stack

    @property
    def _pages_by_entry(self) -> dict[str, int]:
        return self._current_phase_page().pages_by_entry

    # ------------------------------------------------------------------
    # Phase tabs
    # ------------------------------------------------------------------

    def phase_pages(self) -> list[PhasePage]:
        return [
            w for i in range(self._tabs.count())
            if isinstance((w := self._tabs.widget(i)), PhasePage)
        ]

    def open_phase_keys(self) -> list[str]:
        return [p.phase.key for p in self.phase_pages()]

    def current_phase_key(self) -> str | None:
        page = self._tabs.currentWidget()
        return page.phase.key if isinstance(page, PhasePage) else None

    def page_for_phase(self, key: str) -> PhasePage | None:
        for page in self.phase_pages():
            if page.phase.key == key:
                return page
        return None

    def _current_phase_page(self) -> PhasePage:
        """The current phase page, or the last one visited when Chat is current."""
        current = self._tabs.currentWidget()
        if isinstance(current, PhasePage):
            return current
        last = getattr(self, "_last_phase_page", None)
        if isinstance(last, PhasePage) and last in self.phase_pages():
            return last
        pages = self.phase_pages()
        if not pages:
            self.open_phase(DEFAULT_PHASE_KEY, make_current=False)
            pages = self.phase_pages()
        return pages[0]

    def open_phase(self, key: str, *, make_current: bool = True) -> PhasePage:
        """Open ``key``'s tab (in PRD order) and optionally switch to it."""
        if key not in PHASES_BY_KEY:
            raise KeyError(key)
        page = self.page_for_phase(key)
        if page is None:
            phase = PHASES_BY_KEY[key]
            page = PhasePage(phase, self._phase_map, self._build_wired_panel)
            page.entry_selected.connect(
                lambda label, pg=page: self._on_entry_selected(pg, label)
            )
            page.chat_requested.connect(self.show_chat)
            order = [p.key for p in PHASES]
            insert_at = 1  # after the pinned Chat tab
            for existing in self.phase_pages():
                if order.index(existing.phase.key) < order.index(key):
                    insert_at = self._tabs.indexOf(existing) + 1
            self._tabs.insertTab(insert_at, page, phase.tab_label)
            if phase.provisional:
                self._tabs.setTabToolTip(
                    insert_at,
                    "Step sequence is provisional until this phase's PRD section is drafted.",
                )
            first = page.first_step()
            if first is not None:
                page.show_entry(first)
        if make_current:
            self._tabs.setCurrentWidget(page)
        self._persist_tabs()
        return page

    def close_phase(self, key: str) -> bool:
        """Close ``key``'s tab; the last open phase tab cannot be closed."""
        page = self.page_for_phase(key)
        if page is None:
            return False
        if len(self.phase_pages()) <= 1:
            return False
        self._retire_page(page)
        self._persist_tabs()
        return True

    def _retire_page(self, page: PhasePage) -> None:
        """Remove a page from the strip and delete it once its workers finish.

        A panel's fetch worker is a QThread parented to the panel; deleting
        the panel while the thread runs aborts the process. Retired pages are
        parked hidden and reclaimed by ``_reap_retired_pages`` when every
        worker has finished.
        """
        index = self._tabs.indexOf(page)
        if index >= 0:
            self._tabs.removeTab(index)
        page.hide()
        page.setParent(self)
        if getattr(self, "_last_phase_page", None) is page:
            self._last_phase_page = None
        self._retired_pages.append(page)
        self._reap_timer.start()

    def _reap_retired_pages(self) -> None:
        still: list[PhasePage] = []
        for page in self._retired_pages:
            busy = False
            for _label, panel in page.built_panels():
                workers = getattr(panel, "_in_flight_workers", [])
                for worker in list(workers):
                    try:
                        if worker.isRunning():
                            busy = True
                            break
                    except RuntimeError:  # already deleted after finishing
                        continue
                if busy:
                    break
            if busy:
                still.append(page)
            else:
                page.deleteLater()
        self._retired_pages = still
        if still:
            self._reap_timer.start()

    def show_chat(self) -> None:
        self._tabs.setCurrentIndex(0)

    def _on_tab_close_requested(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if isinstance(widget, PhasePage):
            self.close_phase(widget.phase.key)

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if not isinstance(widget, PhasePage):
            return
        self._last_phase_page = widget
        self._persist_tabs()
        if not self._lifecycle_ready:
            return
        # Load the step panels' counts for the markers (only those not yet
        # loaded), and refresh what the tab is showing so it is current.
        self._load_step_counts(widget)
        panel = widget.current_panel()
        if _is_refreshable(panel):
            panel.refresh()

    def _load_step_counts(self, page: PhasePage) -> None:
        known = page.record_counts()
        for label, panel in page.step_panels():
            if label in known:
                continue
            if isinstance(panel, ListDetailPanel):
                # A refresh makes the panel current, so it is no longer stale.
                self._stale.discard((id(page), label))
                page.sidebar.set_stale(label, False)
                panel.refresh()

    def _rebuild_add_phase_menu(self) -> None:
        self._add_phase_menu.clear()
        open_keys = set(self.open_phase_keys())
        for phase in PHASES:
            if phase.key == OPERATE_KEY:
                self._add_phase_menu.addSeparator()
            text = phase.tab_label
            if phase.key in open_keys:
                text += "   (open)"
            action = self._add_phase_menu.addAction(text)
            if phase.provisional:
                action.setToolTip("Provisional step sequence")
            action.triggered.connect(lambda _c=False, k=phase.key: self.open_phase(k))

    def _engagement_key(self) -> str:
        if self._active_context is not None:
            ident = self._active_context.engagement_identifier()
            if ident:
                return ident
        return "_no_engagement"

    def _persist_tabs(self) -> None:
        if getattr(self, "_restoring_tabs", False):
            return
        self._tab_store.save(
            self._engagement_key(), self.open_phase_keys(), self.current_phase_key()
        )

    def _restore_tabs_for_engagement(self) -> None:
        """Reconcile the open phase tabs with the engagement's remembered set.

        Pages already open for a remembered phase are kept (their panels are
        marked stale by the caller); extras are retired; missing ones opened.
        """
        self._restoring_tabs = True
        try:
            keys, current = self._tab_store.load(self._engagement_key())
            if not keys:
                keys, current = [DEFAULT_PHASE_KEY], DEFAULT_PHASE_KEY
            for page in self.phase_pages():
                if page.phase.key not in keys:
                    self._retire_page(page)
            for key in keys:
                self.open_phase(key, make_current=False)
            self._tabs.setCurrentWidget(self.page_for_phase(current or keys[0]))
        finally:
            self._restoring_tabs = False
        self._persist_tabs()

    # ------------------------------------------------------------------
    # Panel construction + wiring
    # ------------------------------------------------------------------

    def _build_wired_panel(self, label: str) -> QWidget:
        page = build_panel(label, self._client, active_context=self._active_context)
        if isinstance(page, ListDetailPanel):
            page.connection_lost.connect(self._on_panel_connection_lost)
            page.navigate_requested.connect(self._on_navigate_requested)
            page.open_requested.connect(self._on_open_requested)
        return page

    def _on_entry_selected(self, page: PhasePage, label: str) -> None:
        key = (id(page), label)
        was_stale = key in self._stale
        if was_stale:
            self._stale.discard(key)
            page.sidebar.set_stale(label, False)
        panel = page.panel_for(label)
        if not _is_refreshable(panel):
            return
        # Refresh on every selection so the panel shows current data; the
        # initial selection during construction is gated on readiness.
        if was_stale or self._lifecycle_ready:
            panel.refresh()

    # ------------------------------------------------------------------
    # Quick open (Ctrl+K)
    # ------------------------------------------------------------------

    def open_quick_open(self) -> None:
        from crmbuilder_v2.ui.quick_open import QuickOpenDialog

        page = self._current_phase_page()

        def _provider(label: str):
            panel = page.ensure_panel(label)
            return panel if isinstance(panel, ListDetailPanel) else None

        dialog = QuickOpenDialog(
            entity_type_to_label=ENTITY_TYPE_TO_SIDEBAR_LABEL,
            panel_provider=_provider,
            parent=self,
        )
        dialog.open_requested.connect(self._on_quick_open_requested)
        self._quick_open_dialog = dialog
        dialog.exec()

    def _on_quick_open_requested(self, label: str, identifier) -> None:
        origin = self._current_location()
        if origin is not None:
            self._nav_back.append(origin)
            self._nav_forward.clear()
            self._update_nav_actions()
        self._go_to(label, identifier if isinstance(identifier, str) else None)

    def had_first_ready(self) -> bool:
        """True once the API has been reachable at least once this session.

        Read by ``app.py``'s ``on_spawn_failed`` to decide whether a spawn
        failure is a fatal *startup* failure (exit the app) or a runtime
        reconnect failure (fall back to the in-window banner).
        """
        return self._had_first_ready

    def handle_crash(self, stderr_text: str) -> None:
        """Slot for ``ServerLifecycle.crashed``: log, then auto-reconnect."""
        if stderr_text:
            _log.warning(
                "Storage server stopped; captured output:\n%s", stderr_text
            )
        else:
            _log.warning("Storage server stopped (no captured output)")
        self._begin_auto_reconnect("storage server stopped")

    def _begin_auto_reconnect(self, reason: str) -> None:
        """Disable content and kick off a bounded probe-then-spawn recovery.

        Idempotent while a cycle is in flight: overlapping triggers (a
        crash plus several panels each reporting connection loss) collapse
        into one retry loop. Recovery reuses the existing
        ``ServerLifecycle`` machinery, which spawns a fresh owned API even
        when the dead instance was external (manually launched) — so this
        self-heals the 05-30 "external API died, UI only noticed on click"
        case without operator action.
        """
        self._lifecycle_ready = False
        self._set_content_enabled(False)
        # Pause the heartbeat while recovering; ``_on_lifecycle_ready``
        # restarts it. ``_on_heartbeat_tick`` also guards on these flags,
        # so an in-flight probe completing mid-reconnect is a no-op.
        self._heartbeat_timer.stop()
        if self._auto_reconnecting:
            return
        self._auto_reconnecting = True
        self._reconnect_attempts = 0
        _log.info("Auto-reconnect starting (%s)", reason)
        self._crash_banner.show_with_message(
            f"Storage API at {self._base_url} stopped responding "
            "— restarting…"
        )
        self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        self._reconnect_attempts += 1
        _log.info(
            "Auto-reconnect attempt %d of %d",
            self._reconnect_attempts,
            _MAX_RECONNECT_ATTEMPTS,
        )
        if self._reconnect_attempts > 1:
            self._crash_banner.show_with_message(
                f"Restarting storage API… "
                f"(attempt {self._reconnect_attempts} of "
                f"{_MAX_RECONNECT_ATTEMPTS})"
            )
        self._lifecycle.start()

    def handle_reconnect_failed(self, stderr_text: str) -> None:
        """Route a *runtime* spawn failure from app.py into the retry loop.

        Retries up to ``_MAX_RECONNECT_ATTEMPTS``; on exhaustion shows an
        actionable banner pointing at the manual Reconnect button, the
        standalone launch command, and the rotating log file.
        """
        if stderr_text:
            _log.warning("Reconnect attempt failed:\n%s", stderr_text)
        if (
            self._auto_reconnecting
            and self._reconnect_attempts < _MAX_RECONNECT_ATTEMPTS
        ):
            self._attempt_reconnect()
            return
        self._auto_reconnecting = False
        self._crash_banner.show_with_message(
            f"Couldn't restart the storage API after "
            f"{self._reconnect_attempts} attempt(s). Click Reconnect to "
            f"retry, or run 'uv run crmbuilder-v2-api' in a terminal. "
            f"Logs: {self._log_path}"
        )

    def _on_heartbeat_tick(self) -> None:
        """Probe ``/health`` off-thread; trigger recovery on a connection miss.

        Skips while not ready, while a reconnect is already in flight, or
        while a prior probe is still outstanding — so it never stacks
        probes or fights the auto-reconnect loop.
        """
        if (
            not self._lifecycle_ready
            or self._auto_reconnecting
            or self._heartbeat_in_flight
        ):
            return
        self._heartbeat_in_flight = True
        run_in_thread(
            self._client.health,
            on_success=self._on_heartbeat_ok,
            on_error=self._on_heartbeat_failed,
            parent=self,
        )

    def _on_heartbeat_ok(self, _result) -> None:
        self._heartbeat_in_flight = False

    def _on_heartbeat_failed(self, exc: Exception) -> None:
        self._heartbeat_in_flight = False
        # Only a connection failure means the API is gone; a transient
        # domain/5xx error is not a death signal and is left to normal
        # request paths. Re-check the guards — state may have changed
        # while the probe was in flight.
        if not isinstance(exc, StorageConnectionError):
            return
        if not self._lifecycle_ready or self._auto_reconnecting:
            return
        _log.warning("Heartbeat: API unreachable (%s); auto-restarting", exc)
        self._begin_auto_reconnect("health heartbeat: API unreachable")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        try:
            self._heartbeat_timer.stop()
        except Exception:
            _log.exception("Heartbeat timer stop failed during closeEvent")
        # Panels inside tabs never receive closeEvent themselves; drain their
        # workers here so no QThread outlives its panel.
        for page in self.phase_pages() + self._retired_pages:
            for _label, panel in page.built_panels():
                if isinstance(panel, ListDetailPanel):
                    panel.drain_workers()
        try:
            pass
        except Exception:
            _log.exception("Heartbeat timer stop failed during closeEvent")
        try:
            self._lifecycle.terminate()
        except Exception:
            _log.exception("Lifecycle terminate failed during closeEvent")
        try:
            self._client.close()
        except Exception:
            _log.exception("StorageClient close failed during closeEvent")
        super().closeEvent(event)

    def _on_reconnect_requested(self) -> None:
        # Manual Reconnect button. Reset any exhausted auto-reconnect
        # cycle so the click gets a fresh bounded round of attempts.
        _log.info("Manual reconnect requested")
        self._auto_reconnecting = False
        self._flap_count = 0
        self._begin_auto_reconnect("manual reconnect")

    def _on_lifecycle_ready(self) -> None:
        # Fires on initial readiness AND on successful reconnect.
        self._lifecycle_ready = True
        self._had_first_ready = True
        self._auto_reconnecting = False
        self._reconnect_attempts = 0
        self._last_ready_at = time.monotonic()
        self._heartbeat_in_flight = False
        # Unconditional hide: a no-op when already hidden, and avoids
        # depending on isVisible() (which is False for an unshown parent).
        self._crash_banner.hide()
        self._set_content_enabled(True)
        # Begin (or resume) proactive health polling now the API is up.
        if not self._heartbeat_timer.isActive():
            self._heartbeat_timer.start()
        self._refresh_current_panel()

    def _on_panel_connection_lost(self, message: str) -> None:
        _log.warning("Panel reported connection lost: %s", message)
        if self._auto_reconnecting:
            # Already recovering; overlapping reports collapse into one cycle.
            return
        # A connection loss that lands right after a successful recovery means
        # the recovery did not stick — /health is fine but data requests keep
        # failing. Count these flaps; once they exceed the bound, stop the
        # reconnect/refresh loop and hand off to the manual Reconnect banner
        # rather than spinning forever (REQ-297).
        now = time.monotonic()
        if (
            self._last_ready_at is not None
            and (now - self._last_ready_at) < _FLAP_WINDOW_S
        ):
            self._flap_count += 1
        else:
            self._flap_count = 1
        if self._flap_count > _MAX_FLAPS:
            _log.warning(
                "Connection flapping (%d losses just after recovery); "
                "backing off auto-reconnect",
                self._flap_count,
            )
            self._lifecycle_ready = False
            self._set_content_enabled(False)
            self._heartbeat_timer.stop()
            self._crash_banner.show_with_message(
                f"The storage API at {self._base_url} keeps dropping requests "
                f"while reporting healthy. Click Reconnect to retry, or run "
                f"'uv run crmbuilder-v2-api' in a terminal. "
                f"Logs: {self._log_path}"
            )
            return
        self._begin_auto_reconnect("panel connection lost")

    def _on_navigate_requested(self, entity_type: str, identifier: str) -> None:
        """Route a panel-emitted link click to the appropriate panel."""
        label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
        if label is None or label not in SIDEBAR_ENTRIES:
            _log.warning(
                "Navigation requested for unknown entity_type=%s identifier=%s",
                entity_type,
                identifier,
            )
            return
        # REQ-138 (PI-179): record where we are so Back can return here, and
        # a new jump invalidates the forward stack.
        origin = self._current_location()
        if origin is not None:
            self._nav_back.append(origin)
            self._nav_forward.clear()
            self._update_nav_actions()
        self._go_to(label, identifier)

    def _current_location(self) -> tuple[str, str | None] | None:
        """The current (panel label, selected record identifier), if any."""
        page = self._current_phase_page()
        entry = page.current_entry()
        if not entry or entry == CHAT_LABEL:
            return None
        panel = page.panel_for(entry)
        identifier: str | None = None
        if isinstance(panel, ListDetailPanel):
            identifier = panel._currently_selected_identifier()
        return (entry, identifier)

    def _go_to(self, label: str, identifier: str | None) -> None:
        """Show ``label`` in the current phase tab and select ``identifier``."""
        if label == CHAT_LABEL:
            self.show_chat()
            return
        page = self._current_phase_page()
        if self._tabs.currentWidget() is not page:
            self._tabs.setCurrentWidget(page)
        target = page.show_entry(label)
        if identifier and isinstance(target, ListDetailPanel):
            target.select_record_by_identifier(identifier)

    def navigate_back(self) -> None:
        if not self._nav_back:
            return
        here = self._current_location()
        target = self._nav_back.pop()
        if here is not None:
            self._nav_forward.append(here)
        self._go_to(target[0], target[1])
        self._update_nav_actions()

    def navigate_forward(self) -> None:
        if not self._nav_forward:
            return
        here = self._current_location()
        target = self._nav_forward.pop()
        if here is not None:
            self._nav_back.append(here)
        self._go_to(target[0], target[1])
        self._update_nav_actions()

    def _update_nav_actions(self) -> None:
        back = getattr(self, "_back_action", None)
        if back is not None:
            back.setEnabled(bool(self._nav_back))
        fwd = getattr(self, "_forward_action", None)
        if fwd is not None:
            fwd.setEnabled(bool(self._nav_forward))

    def _on_open_requested(self, entity_type: str, identifier: str) -> None:
        """Spawn a standalone non-modal detail window for a related record
        (PI-121 / WTK-079); the originating view is left intact."""
        self._detail_window_manager.open(entity_type, identifier)

    def _refresh_current_panel(self) -> None:
        current = self._tabs.currentWidget()
        if isinstance(current, PhasePage):
            self._load_step_counts(current)
            widget = current.current_panel()
            if _is_refreshable(widget):
                widget.refresh()

    def _set_content_enabled(self, enabled: bool) -> None:
        self._tabs.setEnabled(enabled)
        for page in self.phase_pages():
            page.set_content_enabled(enabled)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        go_menu = menu_bar.addMenu("&Go")
        quick_open_action = QAction("&Quick open…", self)
        quick_open_action.setShortcut("Ctrl+K")
        quick_open_action.triggered.connect(self.open_quick_open)
        go_menu.addAction(quick_open_action)
        self._quick_open_action = quick_open_action
        go_menu.addSeparator()
        # REQ-138 (PI-179): Back/Forward through the cross-record navigation
        # trail (also Alt+Left / Alt+Right).
        back_action = QAction("&Back", self)
        back_action.setShortcut("Alt+Left")
        back_action.triggered.connect(self.navigate_back)
        back_action.setEnabled(False)
        go_menu.addAction(back_action)
        self._back_action = back_action
        forward_action = QAction("&Forward", self)
        forward_action.setShortcut("Alt+Right")
        forward_action.triggered.connect(self.navigate_forward)
        forward_action.setEnabled(False)
        go_menu.addAction(forward_action)
        self._forward_action = forward_action
        go_menu.addSeparator()
        chat_action = QAction("&Chat", self)
        chat_action.triggered.connect(self.show_chat)
        go_menu.addAction(chat_action)

        help_menu = menu_bar.addMenu("&Help")
        connection_action = QAction("&Connection Info…", self)
        connection_action.triggered.connect(self._on_connection_info_triggered)
        help_menu.addAction(connection_action)
        self._connection_info_action = connection_action
        help_menu.addSeparator()
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about_triggered)
        help_menu.addAction(about_action)
        self._about_action = about_action

    def _on_about_triggered(self) -> None:
        AboutDialog(parent=self).exec()

    def _on_connection_info_triggered(self) -> None:
        from crmbuilder_v2.ui.connection_info_dialog import ConnectionInfoDialog

        ConnectionInfoDialog(
            self._client, self._active_context, parent=self
        ).exec()

    # ------------------------------------------------------------------
    # v0.5 slice D — engagement picker + activation orchestration
    # ------------------------------------------------------------------

    def _on_top_strip_clicked(self) -> None:
        """Open the engagement picker below the top-strip."""
        from crmbuilder_v2.ui.widgets.engagement_picker import EngagementPicker

        try:
            engagements = self._client.list_engagements()
        except Exception:
            _log.exception("Failed to list engagements for picker")
            engagements = []
        active_id = (
            self._active_context.engagement_identifier()
            if self._active_context is not None
            else None
        )
        picker = EngagementPicker(engagements, active_id, parent=self)
        picker.activation_requested.connect(self._on_picker_activation_requested)
        picker.manage_requested.connect(self._on_picker_manage_requested)
        if self._top_strip is not None:
            picker.show_below(self._top_strip)
        else:
            picker.show()
        self._picker = picker

    def _on_picker_activation_requested(self, identifier: str) -> None:
        """Picker row clicked: switch the active engagement (client-side).

        PI-β: switching is a context change, not a subprocess swap. We set
        the active engagement on the context (which mirrors onto the
        ``StorageClient``'s ``X-Engagement`` header) and refresh the panels;
        every subsequent request is scoped to the new engagement.
        """
        self.switch_engagement(identifier)

    def switch_engagement(self, identifier: str) -> bool:
        """Make ``identifier`` the active engagement and refresh the panels.

        Returns ``True`` on success. Best-effort: a fetch failure is logged
        and leaves the previous engagement active.
        """
        if self._active_context is None:
            _log.warning("switch_engagement called with no active_context; ignoring")
            return False
        try:
            payload = self._client.get_engagement(identifier)
        except Exception:
            _log.exception("Failed to fetch engagement %s for switch", identifier)
            return False
        from datetime import UTC, datetime

        from crmbuilder_v2.access.engagement_models import (
            Engagement,
            EngagementStatus,
        )

        def _maybe_dt(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                return v
            try:
                dt = datetime.fromisoformat(str(v))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                return None

        target = Engagement(
            engagement_identifier=payload["engagement_identifier"],
            engagement_code=payload["engagement_code"],
            engagement_name=payload.get("engagement_name") or "",
            engagement_purpose=payload.get("engagement_purpose") or "",
            engagement_status=EngagementStatus(
                payload.get("engagement_status") or "active"
            ),
            engagement_last_opened_at=_maybe_dt(
                payload.get("engagement_last_opened_at")
            ),
            engagement_created_at=_maybe_dt(payload.get("engagement_created_at"))
            or datetime.now(UTC),
            engagement_updated_at=_maybe_dt(payload.get("engagement_updated_at"))
            or datetime.now(UTC),
            engagement_deleted_at=_maybe_dt(payload.get("engagement_deleted_at")),
        )
        # Mirror onto the client header directly (belt-and-braces: app.py also
        # wires active_engagement_changed → client.set_active_engagement).
        self._client.set_active_engagement(target.engagement_identifier)
        self._active_context.set_engagement(target)
        self._refresh_after_engagement_switch()
        return True

    def _refresh_after_engagement_switch(self) -> None:
        """Swap to the engagement's remembered tabs; mark built panels stale."""
        self._stale.clear()
        self._restore_tabs_for_engagement()
        current = self._tabs.currentWidget()
        for page in self.phase_pages():
            page.reset_record_counts()
            for label, panel in page.built_panels():
                if not _is_refreshable(panel):
                    continue
                if page is current and label == page.current_entry():
                    panel.refresh()
                else:
                    self._stale.add((id(page), label))
                    page.sidebar.set_stale(label, True)
        if isinstance(current, PhasePage) and self._lifecycle_ready:
            self._load_step_counts(current)

    def _on_picker_manage_requested(self) -> None:
        """Picker footer clicked: show the Engagements panel."""
        self._go_to("Engagements", None)
