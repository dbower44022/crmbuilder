"""Main window — sidebar + stacked content area, with crash banner.

Per DEC-021 the main window structure is a sidebar (left, fixed-width)
plus a ``QStackedWidget`` (right, swapping per selection). Slice B added
the lifecycle ownership and crash banner. Slice C threads the
``StorageClient`` through the constructor, replaces the Decisions
placeholder with a live ``DecisionsPanel``, and wires panel-level
``connection_lost`` to the same crash banner the lifecycle uses. Slice
D added Sessions and Risks. Slice E completes the round-2 read-only
panels: Charter, Status, Topics, Planning Items, References — every
sidebar entry now routes to a real panel. (PI-β slice 4 removed the
JSON-snapshot file-watch RefreshService along with the snapshot
machinery; panels refresh on selection, on lifecycle-ready, and via the
manual Refresh button.)
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
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
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.chat import ChatPanel
from crmbuilder_v2.ui.panels.close_out_payloads import CloseOutPayloadsPanel
from crmbuilder_v2.ui.panels.commits import CommitsPanel
from crmbuilder_v2.ui.panels.conversations import ConversationsPanel
from crmbuilder_v2.ui.panels.crm_candidates import CrmCandidatesPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.deposit_events import DepositEventsPanel
from crmbuilder_v2.ui.panels.domains import DomainsPanel
from crmbuilder_v2.ui.panels.engagements import EngagementsPanel
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.panels.glossary import GlossaryPanel
from crmbuilder_v2.ui.panels.manual_config import ManualConfigPanel
from crmbuilder_v2.ui.panels.persona import PersonasPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.processes import ProcessesPanel
from crmbuilder_v2.ui.panels.projects import ProjectsPanel
from crmbuilder_v2.ui.panels.reference_books import ReferenceBooksPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.requirements import RequirementsPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.test_spec import TestSpecsPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.panels.work_tasks import WorkTasksPanel
from crmbuilder_v2.ui.panels.work_tickets import WorkTicketsPanel
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES, Sidebar
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.main_window")
_DEFAULT_ENTRY = "Decisions"

# Bounded auto-reconnect: on connection loss or an owned-subprocess
# crash, the window drives ``ServerLifecycle.start()`` (probe-then-spawn)
# up to this many times before falling back to the manual-Reconnect
# banner. Each attempt itself probes (1s) then polls a fresh spawn for up
# to 10s, so this is a hard ceiling on automatic recovery effort.
_MAX_RECONNECT_ATTEMPTS = 3

# Heartbeat: how often the window probes ``GET /health`` while ready, so
# an API that died between user actions (PI-111) — especially an external
# one the lifecycle doesn't crash-monitor — is detected proactively and
# auto-restarted before the next request fails. Probe runs off the GUI
# thread; only a connection failure triggers recovery.
_HEARTBEAT_INTERVAL_MS = 15000

# Maps reference ``entity_type`` values (as stored in the database) to
# sidebar entry labels so the navigation router (cross-panel link
# clicks) and the file-watch refresh router (slice F) can resolve a
# data event to a panel. ``reference`` maps to the References panel
# even though no current detail-pane link targets it — the file watcher
# still needs the mapping so writes to ``references.json`` refresh the
# panel.
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
}


def build_panel(
    label: str,
    client: StorageClient,
    *,
    active_context=None,
) -> QWidget:
    """Construct the page widget for a sidebar label (PI-121 / WTK-079).

    One label→class table, two callers: ``MainWindow.__init__`` builds every
    sidebar page through it, and ``DetailWindowManager`` builds a standalone
    detail window's content through it — so a new entity panel is registered
    once. Entity panels are ``ListDetailPanel`` subclasses taking only the
    client; Chat takes the API base URL (DEC-253), Engagements additionally
    takes the active context, and an unmapped label falls through to a
    placeholder ``QLabel`` (which the detail-window manager treats as
    non-openable, C7).
    """
    if label == "Chat":
        # PI-052 Slice B: the chat tab consumes the FastAPI surface directly
        # (DEC-253/§2.8), so it takes the API base URL, not the StorageClient.
        return ChatPanel(get_settings().api_base_url)
    if label == "Charter":
        return CharterPanel(client)
    if label == "Status":
        return StatusPanel(client)
    if label == "Decisions":
        return DecisionsPanel(client)
    if label == "Sessions":
        return SessionsPanel(client)
    if label == "Risks":
        return RisksPanel(client)
    if label == "Planning Items":
        return PlanningItemsPanel(client)
    if label == "Topics":
        return TopicsPanel(client)
    if label == "References":
        return ReferencesPanel(client)
    if label == "Domains":
        return DomainsPanel(client)
    if label == "Entities":
        return EntitiesPanel(client)
    if label == "Processes":
        return ProcessesPanel(client)
    if label == "Requirements":
        return RequirementsPanel(client)
    if label == "Test Specs":
        return TestSpecsPanel(client)
    if label == "CRM Candidates":
        return CrmCandidatesPanel(client)
    if label == "Personas":
        return PersonasPanel(client)
    if label == "Fields":
        return FieldsPanel(client)
    if label == "Manual Configs":
        return ManualConfigPanel(client)
    if label == "Glossary":
        return GlossaryPanel(client)
    if label == "Engagements":
        return EngagementsPanel(client, active_context=active_context)
    # v0.7 governance entities.
    if label == "Projects":
        return ProjectsPanel(client)
    if label == "Conversations":
        return ConversationsPanel(client)
    if label == "Reference Books":
        return ReferenceBooksPanel(client)
    if label == "Work Tickets":
        return WorkTicketsPanel(client)
    if label == "Close-Out Payloads":
        return CloseOutPayloadsPanel(client)
    if label == "Deposit Events":
        return DepositEventsPanel(client)
    if label == "Commits":
        return CommitsPanel(client)
    # WTK-004: ADO delivery-model monitoring panels.
    if label == "Workstreams":
        return WorkstreamsPanel(client)
    if label == "Work Tasks":
        return WorkTasksPanel(client)
    placeholder = QLabel(f"Panel for {label} — not yet implemented.")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder.setObjectName(f"placeholder_{label.lower().replace(' ', '_')}")
    return placeholder


class MainWindow(QMainWindow):
    """Top-level window containing the crash banner, sidebar, and content stack."""

    def __init__(
        self,
        lifecycle: ServerLifecycle,
        client: StorageClient,
        snapshot_dir: Path | None = None,
        active_context=None,
    ):
        super().__init__()
        self.setWindowTitle("CRMBuilder v2")
        self.resize(1200, 800)

        self._lifecycle = lifecycle
        self._client = client
        self._active_context = active_context
        self._sidebar = Sidebar()
        self._top_strip = None
        self._picker = None
        self._stack = QStackedWidget()
        self._crash_banner = CrashBanner()
        self._pages_by_entry: dict[str, int] = {}
        self._stale_entries: set[str] = set()
        # Tracks whether the storage API is currently reachable. Used by
        # ``_on_sidebar_selected`` to gate the on-select refresh so that
        # the synchronous ``setCurrentRow`` during ``__init__`` does not
        # fire an HTTP request before the lifecycle's probe completes.
        # ``_on_lifecycle_ready`` flips this to True; ``handle_crash``
        # and ``_on_panel_connection_lost`` flip it back to False.
        self._lifecycle_ready = False

        # Auto-reconnect state. ``_had_first_ready`` lets app.py route a
        # *runtime* spawn failure to the in-window banner instead of the
        # fatal startup dialog. ``_auto_reconnecting`` dedupes overlapping
        # triggers (e.g. several panels reporting connection loss at once);
        # ``_reconnect_attempts`` bounds the retry loop.
        self._had_first_ready = False
        self._auto_reconnecting = False
        self._reconnect_attempts = 0
        self._base_url = get_settings().api_base_url
        self._log_path = api_log_path()

        # Heartbeat (PI-111). Started once the API is first ready, paused
        # during a reconnect cycle, restarted on the next ready. A single
        # probe is in flight at a time (``_heartbeat_in_flight``).
        self._heartbeat_in_flight = False
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(_HEARTBEAT_INTERVAL_MS)
        self._heartbeat_timer.timeout.connect(self._on_heartbeat_tick)

        # (PI-β slice 4 removed the JSON-snapshot file-watch RefreshService
        # along with the snapshot machinery it watched; ``snapshot_dir`` is now
        # an accepted-but-ignored constructor argument. Panels refresh on
        # selection, on lifecycle-ready, and via the manual Refresh button.)

        # PI-121 / WTK-079: spawns standalone non-modal detail windows on a
        # grid's "Open <item type>" action. Built through the same
        # ``build_panel`` factory the sidebar uses, so it covers every entity
        # type with no per-type window code. Constructed before the panel loop
        # so the loop can wire each panel's ``open_requested`` to it.
        self._detail_window_manager = DetailWindowManager(
            client=self._client,
            panel_factory=build_panel,
            navigate_router=self._on_navigate_requested,
            parent_window=self,
        )

        for entry in SIDEBAR_ENTRIES:
            # ``build_panel`` is the single label→class table (PI-121 / WTK-079);
            # Chat and the not-yet-implemented placeholders are not
            # ``ListDetailPanel``s, so they are excluded from the
            # connection_lost / navigate / open wiring and the on-select refresh.
            page = build_panel(
                entry, self._client, active_context=self._active_context
            )
            if isinstance(page, ListDetailPanel):
                page.connection_lost.connect(self._on_panel_connection_lost)
                page.navigate_requested.connect(self._on_navigate_requested)
                page.open_requested.connect(self._on_open_requested)
            index = self._stack.addWidget(page)
            self._pages_by_entry[entry] = index

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        # v0.5 slice D: the top-strip is the first child of the sidebar
        # column when an active_context is provided; the sidebar list
        # follows below it.
        if self._active_context is not None:
            from crmbuilder_v2.ui.widgets.engagement_top_strip import (
                EngagementTopStrip,
            )

            sidebar_col = QWidget()
            sidebar_layout = QVBoxLayout(sidebar_col)
            sidebar_layout.setContentsMargins(0, 0, 0, 0)
            sidebar_layout.setSpacing(0)
            self._top_strip = EngagementTopStrip(self._active_context)
            self._top_strip.clicked.connect(self._on_top_strip_clicked)
            sidebar_layout.addWidget(self._top_strip)
            sidebar_layout.addWidget(self._sidebar, stretch=1)
            sidebar_col.setFixedWidth(self._sidebar.width())
            content_layout.addWidget(sidebar_col)
        else:
            content_layout.addWidget(self._sidebar)
        content_layout.addWidget(self._stack, stretch=1)
        self._content_widget = content_widget

        container = QWidget()
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self._crash_banner)
        outer_layout.addWidget(content_widget, stretch=1)
        self.setCentralWidget(container)

        self._sidebar.selection_changed.connect(self._on_sidebar_selected)
        self._crash_banner.reconnect_requested.connect(self._on_reconnect_requested)
        self._lifecycle.ready.connect(self._on_lifecycle_ready)

        self._build_menu_bar()

        self._sidebar.select_entry(_DEFAULT_ENTRY)

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
        try:
            self._lifecycle.terminate()
        except Exception:
            _log.exception("Lifecycle terminate failed during closeEvent")
        try:
            self._client.close()
        except Exception:
            _log.exception("StorageClient close failed during closeEvent")
        super().closeEvent(event)

    def _on_sidebar_selected(self, entry: str) -> None:
        index = self._pages_by_entry.get(entry)
        if index is not None:
            self._stack.setCurrentIndex(index)
        was_stale = entry in self._stale_entries
        if was_stale:
            self._stale_entries.discard(entry)
            self._sidebar.set_stale(entry, False)
        if index is None:
            return
        page = self._stack.widget(index)
        if not isinstance(page, ListDetailPanel):
            return
        # Refresh the panel on every selection so it shows current data.
        # Stale-path refreshes always fire, matching prior behavior;
        # non-stale refreshes are gated on ``_lifecycle_ready`` so the
        # default-row ``setCurrentRow`` during ``__init__`` does not fire
        # an HTTP request before the lifecycle's probe completes.
        # ``_on_lifecycle_ready`` performs the initial refresh of the
        # current panel itself once the API is up.
        if was_stale or self._lifecycle_ready:
            page.refresh()

    def _on_reconnect_requested(self) -> None:
        # Manual Reconnect button. Reset any exhausted auto-reconnect
        # cycle so the click gets a fresh bounded round of attempts.
        _log.info("Manual reconnect requested")
        self._auto_reconnecting = False
        self._begin_auto_reconnect("manual reconnect")

    def _on_lifecycle_ready(self) -> None:
        # Fires on initial readiness AND on successful reconnect.
        self._lifecycle_ready = True
        self._had_first_ready = True
        self._auto_reconnecting = False
        self._reconnect_attempts = 0
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
        self._begin_auto_reconnect("panel connection lost")

    def _on_navigate_requested(self, entity_type: str, identifier: str) -> None:
        """Route a panel-emitted link click to the appropriate sidebar entry."""
        label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
        if label is None or label not in self._pages_by_entry:
            _log.warning(
                "Navigation requested for unknown entity_type=%s identifier=%s",
                entity_type,
                identifier,
            )
            return
        index = self._pages_by_entry[label]
        target = self._stack.widget(index)
        # Switch the sidebar selection so it visually matches the swap;
        # this also routes through ``_on_sidebar_selected`` which sets
        # the stack page.
        if label not in SIDEBAR_ENTRIES:
            _log.warning("Sidebar entry %s missing from SIDEBAR_ENTRIES", label)
            return
        self._sidebar.select_entry(label)
        if isinstance(target, ListDetailPanel):
            target.select_record_by_identifier(identifier)

    def _on_open_requested(self, entity_type: str, identifier: str) -> None:
        """Spawn a standalone non-modal detail window for a related record.

        The "Open <item type>" counterpart to ``_on_navigate_requested``: where
        "Go to" replaces the main window's current panel, "Open" pulls the
        record up beside it in its own window, leaving this view intact
        (PI-121 / WTK-079). Delegates to the detail-window manager, which
        no-ops gracefully on an unknown/unopenable type.
        """
        self._detail_window_manager.open(entity_type, identifier)

    def _refresh_current_panel(self) -> None:
        widget = self._stack.currentWidget()
        if isinstance(widget, ListDetailPanel):
            widget.refresh()

    def _set_content_enabled(self, enabled: bool) -> None:
        self._sidebar.setEnabled(enabled)
        self._stack.setEnabled(enabled)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

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
        """Refresh the visible panel and mark the rest stale after a switch."""
        current = self._sidebar.current_text()
        for entry, index in self._pages_by_entry.items():
            page = self._stack.widget(index)
            if not isinstance(page, ListDetailPanel):
                continue
            if entry == current:
                page.refresh()
            else:
                self._stale_entries.add(entry)
                self._sidebar.set_stale(entry, True)

    def _on_picker_manage_requested(self) -> None:
        """Picker footer clicked: navigate to the Engagements panel."""
        self._sidebar.select_entry("Engagements")
