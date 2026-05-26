"""Main window — sidebar + stacked content area, with crash banner.

Per DEC-021 the main window structure is a sidebar (left, fixed-width)
plus a ``QStackedWidget`` (right, swapping per selection). Slice B added
the lifecycle ownership and crash banner. Slice C threads the
``StorageClient`` through the constructor, replaces the Decisions
placeholder with a live ``DecisionsPanel``, and wires panel-level
``connection_lost`` to the same crash banner the lifecycle uses. Slice
D added Sessions and Risks. Slice E completes the round-2 read-only
panels: Charter, Status, Topics, Planning Items, References — every
sidebar entry now routes to a real panel. Slice F constructs and owns
a ``RefreshService`` so external storage writes (e.g., MCP, REST) are
mirrored into the UI without the user clicking Refresh, per DEC-022.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.ui.about_dialog import AboutDialog
from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.crash_banner import CrashBanner
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.close_out_payloads import CloseOutPayloadsPanel
from crmbuilder_v2.ui.panels.conversations import ConversationsPanel
from crmbuilder_v2.ui.panels.crm_candidates import CrmCandidatesPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.deposit_events import DepositEventsPanel
from crmbuilder_v2.ui.panels.domains import DomainsPanel
from crmbuilder_v2.ui.panels.engagements import EngagementsPanel
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.panels.persona import PersonasPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.processes import ProcessesPanel
from crmbuilder_v2.ui.panels.reference_books import ReferenceBooksPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.panels.work_tickets import WorkTicketsPanel
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel
from crmbuilder_v2.ui.refresh import RefreshService
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES, Sidebar

_log = logging.getLogger("crmbuilder_v2.ui.main_window")
_DEFAULT_ENTRY = "Decisions"

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
    # v0.5 slice C: meta-DB engagement registry.
    "engagement": "Engagements",
    # v0.7 governance entities.
    "workstream": "Workstreams",
    "conversation": "Conversations",
    "reference_book": "Reference Books",
    "work_ticket": "Work Tickets",
    "close_out_payload": "Close-Out Payloads",
    "deposit_event": "Deposit Events",
}


class MainWindow(QMainWindow):
    """Top-level window containing the crash banner, sidebar, and content stack."""

    def __init__(
        self,
        lifecycle: ServerLifecycle,
        client: StorageClient,
        snapshot_dir: Path | None = None,
        active_context=None,
        managers=None,
    ):
        super().__init__()
        self.setWindowTitle("CRMBuilder v2")
        self.resize(1200, 800)

        self._lifecycle = lifecycle
        self._client = client
        self._active_context = active_context
        self._managers = managers
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

        for entry in SIDEBAR_ENTRIES:
            if entry == "Charter":
                page: QWidget = CharterPanel(self._client)
            elif entry == "Status":
                page = StatusPanel(self._client)
            elif entry == "Decisions":
                page = DecisionsPanel(self._client)
            elif entry == "Sessions":
                page = SessionsPanel(self._client)
            elif entry == "Risks":
                page = RisksPanel(self._client)
            elif entry == "Planning Items":
                page = PlanningItemsPanel(self._client)
            elif entry == "Topics":
                page = TopicsPanel(self._client)
            elif entry == "References":
                page = ReferencesPanel(self._client)
            elif entry == "Domains":
                page = DomainsPanel(self._client)
            elif entry == "Entities":
                page = EntitiesPanel(self._client)
            elif entry == "Processes":
                page = ProcessesPanel(self._client)
            elif entry == "CRM Candidates":
                page = CrmCandidatesPanel(self._client)
            elif entry == "Personas":
                page = PersonasPanel(self._client)
            elif entry == "Fields":
                page = FieldsPanel(self._client)
            elif entry == "Engagements":
                page = EngagementsPanel(
                    self._client,
                    active_context=self._active_context,
                    managers=self._managers,
                )
            # v0.7 governance entities — six new panels appended to the
            # Governance group in workstream order.
            elif entry == "Workstreams":
                page = WorkstreamsPanel(self._client)
            elif entry == "Conversations":
                page = ConversationsPanel(self._client)
            elif entry == "Reference Books":
                page = ReferenceBooksPanel(self._client)
            elif entry == "Work Tickets":
                page = WorkTicketsPanel(self._client)
            elif entry == "Close-Out Payloads":
                page = CloseOutPayloadsPanel(self._client)
            elif entry == "Deposit Events":
                page = DepositEventsPanel(self._client)
            else:
                placeholder = QLabel(
                    f"Panel for {entry} — not yet implemented."
                )
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setObjectName(
                    f"placeholder_{entry.lower().replace(' ', '_')}"
                )
                page = placeholder
            if isinstance(page, ListDetailPanel):
                page.connection_lost.connect(self._on_panel_connection_lost)
                page.navigate_requested.connect(self._on_navigate_requested)
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

        watched_dir = snapshot_dir if snapshot_dir is not None else get_settings().export_dir
        self._refresh_service = RefreshService(watched_dir, self)
        self._refresh_service.data_changed.connect(self._on_data_changed)
        self._refresh_service.watch_failed.connect(self._on_watch_failed)
        self._refresh_service.start()

    def handle_crash(self, stderr_text: str) -> None:
        """Slot for ``ServerLifecycle.crashed``: show banner, disable content."""
        if stderr_text:
            _log.warning(
                "Storage server stopped; captured output:\n%s", stderr_text
            )
        else:
            _log.warning("Storage server stopped (no captured output)")
        self._lifecycle_ready = False
        self._crash_banner.show_with_message("Storage server stopped.")
        self._set_content_enabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        try:
            self._refresh_service.stop()
        except Exception:
            _log.exception("RefreshService stop failed during closeEvent")
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
        _log.info("Reconnect requested; restarting lifecycle")
        self._lifecycle.start()

    def _on_lifecycle_ready(self) -> None:
        # Fires on initial readiness AND on successful reconnect.
        self._lifecycle_ready = True
        if self._crash_banner.isVisible():
            self._crash_banner.hide()
        self._set_content_enabled(True)
        self._refresh_current_panel()

    def _on_panel_connection_lost(self, message: str) -> None:
        _log.warning("Panel reported connection lost: %s", message)
        self._lifecycle_ready = False
        self._crash_banner.show_with_message("Storage server unreachable.")
        self._set_content_enabled(False)

    def _on_data_changed(self, entity_type: str) -> None:
        """Route a file-watch event to either a silent refresh or a stale dot."""
        label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
        if label is None or label not in self._pages_by_entry:
            return
        index = self._pages_by_entry[label]
        if label == self._sidebar.current_text():
            page = self._stack.widget(index)
            if isinstance(page, ListDetailPanel):
                page.refresh()
        else:
            self._stale_entries.add(label)
            self._sidebar.set_stale(label, True)

    def _on_watch_failed(self, message: str) -> None:
        """Watcher couldn't be installed; manual Refresh remains the fallback."""
        _log.warning("File-watch refresh disabled: %s", message)

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
        """Picker row clicked: kick off the activation worker."""
        if self._active_context is None or self._managers is None:
            _log.warning(
                "Picker requested activation but no managers wired; ignoring"
            )
            return
        try:
            payload = self._client.get_engagement(identifier)
        except Exception:
            _log.exception("Failed to fetch engagement %s for activation", identifier)
            return
        from crmbuilder_v2.access.engagement_models import (
            Engagement,
            EngagementStatus,
        )
        from datetime import UTC, datetime

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
            engagement_export_dir=payload.get("engagement_export_dir"),
            engagement_created_at=_maybe_dt(payload.get("engagement_created_at"))
            or datetime.now(UTC),
            engagement_updated_at=_maybe_dt(payload.get("engagement_updated_at"))
            or datetime.now(UTC),
            engagement_deleted_at=_maybe_dt(payload.get("engagement_deleted_at")),
        )
        previous = self._active_context.engagement()
        from crmbuilder_v2.ui.activation_worker import (
            ActivationWorker,
            run_activation_in_thread,
        )
        from crmbuilder_v2.ui.widgets.activation_overlay import ActivationOverlay

        worker = ActivationWorker(
            target_engagement=target,
            previous_engagement=previous,
            client=self._client,
            active_context=self._active_context,
            managers=self._managers,
        )
        overlay = ActivationOverlay(target, previous, worker, parent=self)
        overlay.setFixedSize(self.size())
        overlay.move(0, 0)
        overlay.retry_requested.connect(
            lambda i=identifier: self._on_picker_activation_requested(i)
        )
        overlay.stay_requested.connect(overlay.close)
        overlay.show()
        worker.completed.connect(self._on_activation_completed)
        self._activation_overlay = overlay
        self._activation_thread = run_activation_in_thread(worker, parent=self)
        self._activation_worker = worker

    def _on_activation_completed(self, _engagement) -> None:
        """Engagement switch finished: the live API is now bound to the new
        engagement's DB. Refresh the visible panel and mark the rest stale
        so they re-fetch from the new DB when next navigated to."""
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
