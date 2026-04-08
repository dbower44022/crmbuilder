"""Requirements mode container (Section 14.1).

Sidebar navigation, client selector, drill-down stack, and breadcrumbs.
The sidebar has four entries: Dashboard, Data Browser, Documents, Impact Review.
Dashboard and Impact Review are functional. Data Browser and Documents are Step 15c.

Drill-down views: Work Item Detail, Session Orchestration, Import Review.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.ui.client_context import ClientContext, ClientInfo, load_clients
from automation.ui.common.client_indicator import ClientIndicator
from automation.ui.common.confirmation import confirm_action
from automation.ui.common.readable_first import format_work_item_name
from automation.ui.common.toast import show_toast
from automation.ui.dashboard.dashboard_view import DashboardView
from automation.ui.impact.impact_view import ImpactView
from automation.ui.navigation import NavEntry, NavigationStack
from automation.ui.work_item.detail_view import WorkItemDetailView

logger = logging.getLogger(__name__)

# Default master database location — under automation/data/
_DEFAULT_MASTER_DB = Path(__file__).resolve().parent.parent / "data" / "master.db"

# Content stack indices
_IDX_DASHBOARD = 0
_IDX_DETAIL = 1
_IDX_DATA_BROWSER = 2
_IDX_DOCUMENTS = 3
_IDX_IMPACT_REVIEW = 4
_IDX_SESSION = 5
_IDX_IMPORT = 6


class PlaceholderView(QWidget):
    """Placeholder for sidebar entries not yet implemented."""

    def __init__(self, title: str, step: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(f"{title}\n\nComing in {step}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #757575;")
        layout.addWidget(label)


class RequirementsWindow(QWidget):
    """The Requirements mode container — sidebar + content area.

    :param master_db_path: Path to the master database. Defaults to automation/data/master.db.
    :param parent: Parent widget.
    """

    def __init__(self, master_db_path: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._master_db_path = str(master_db_path or _DEFAULT_MASTER_DB)
        self._client_context = ClientContext()
        self._client_conn: sqlite3.Connection | None = None
        self._nav_stack = NavigationStack(NavEntry("Dashboard", "dashboard"))

        self._build_ui()
        self._wire_header_actions()
        self._load_clients()
        self._client_context.on_change(self._on_client_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top bar: client selector + indicator
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(8, 8, 8, 4)

        top_bar.addWidget(QLabel("Client:"))
        self._client_combo = QComboBox()
        self._client_combo.setMinimumWidth(200)
        self._client_combo.currentIndexChanged.connect(self._on_client_combo_changed)
        top_bar.addWidget(self._client_combo)

        self._client_indicator = ClientIndicator()
        top_bar.addWidget(self._client_indicator, stretch=1)

        layout.addLayout(top_bar)

        # Breadcrumb bar (hidden when at root)
        self._breadcrumb_bar = QWidget()
        breadcrumb_layout = QHBoxLayout(self._breadcrumb_bar)
        breadcrumb_layout.setContentsMargins(8, 0, 8, 0)
        self._breadcrumb_container = QHBoxLayout()
        breadcrumb_layout.addLayout(self._breadcrumb_container)
        breadcrumb_layout.addStretch()
        self._breadcrumb_bar.setVisible(False)
        layout.addWidget(self._breadcrumb_bar)

        # Main area: sidebar + content
        main_area = QHBoxLayout()

        # Sidebar
        self._sidebar = QListWidget()
        self._sidebar.setMaximumWidth(180)
        self._sidebar.setStyleSheet(
            "QListWidget { font-size: 13px; } "
            "QListWidget::item { padding: 8px; } "
            "QListWidget::item:selected { "
            "   background-color: #E3F2FD; color: #1565C0; font-weight: bold; }"
        )
        for label in ("Dashboard", "Data Browser", "Documents", "Impact Review"):
            self._sidebar.addItem(label)
        self._sidebar.setCurrentRow(0)
        self._sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        main_area.addWidget(self._sidebar)

        # Content stack
        self._content_stack = QStackedWidget()

        # Index 0: Dashboard
        self._dashboard = DashboardView(self._client_context)
        self._dashboard.work_item_selected.connect(self._on_work_item_selected)
        self._content_stack.addWidget(self._dashboard)

        # Index 1: Work Item Detail — pushed onto stack, not a sidebar entry
        self._detail_view = WorkItemDetailView()
        self._detail_view.navigate_to_item.connect(self._on_work_item_selected)
        self._detail_view.item_changed.connect(self._on_item_changed)
        self._content_stack.addWidget(self._detail_view)

        # Index 2: Data Browser placeholder
        self._content_stack.addWidget(PlaceholderView("Data Browser", "Step 15c"))

        # Index 3: Documents placeholder
        self._content_stack.addWidget(PlaceholderView("Documents", "Step 15c"))

        # Index 4: Impact Review (real view)
        self._impact_view = ImpactView()
        self._impact_view.item_changed.connect(self._on_item_changed)
        self._content_stack.addWidget(self._impact_view)

        # Index 5: Session View placeholder (created dynamically)
        self._session_placeholder = QWidget()
        self._content_stack.addWidget(self._session_placeholder)

        # Index 6: Import View placeholder (created dynamically)
        self._import_placeholder = QWidget()
        self._content_stack.addWidget(self._import_placeholder)

        main_area.addWidget(self._content_stack, stretch=1)
        layout.addLayout(main_area, stretch=1)

    def _wire_header_actions(self) -> None:
        """Connect header action signals for drill-down navigation."""
        actions = self._detail_view._actions
        actions.navigate_to_session.connect(self._on_navigate_to_session)
        actions.navigate_to_import.connect(self._on_navigate_to_import)
        self._detail_view._session_tab.navigate_to_session.connect(
            lambda wid: self._on_navigate_to_session(wid, "clarification")
        )

        # Pass database connection to the impacts tab for review actions
        # (done in _on_work_item_selected when conn is available)

    def _load_clients(self) -> None:
        """Load clients from the master database into the combo box."""
        # Ensure master database exists
        Path(self._master_db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = run_master_migrations(self._master_db_path)
            conn.close()
        except Exception:
            logger.warning("Could not initialize master database at %s", self._master_db_path)

        self._client_combo.blockSignals(True)
        self._client_combo.clear()
        self._client_combo.addItem("-- Select Client --", None)

        try:
            clients = load_clients(self._master_db_path)
            for client in clients:
                self._client_combo.addItem(client.name, client)
        except Exception:
            logger.warning("Could not load clients from master database")

        self._client_combo.blockSignals(False)

    def _on_client_combo_changed(self, index: int) -> None:
        """Handle client selection from the combo box."""
        client = self._client_combo.currentData()
        if client is None:
            self._client_context.clear()
            return

        # Confirmation if changing client (placeholder for in-progress state)
        if self._client_context.is_selected:
            if not confirm_action(
                self, "Change Client",
                "Changing the client will reset all Requirements mode state. Continue?"
            ):
                # Revert combo to previous selection
                self._client_combo.blockSignals(True)
                for i in range(self._client_combo.count()):
                    if self._client_combo.itemData(i) == self._client_context.client:
                        self._client_combo.setCurrentIndex(i)
                        break
                self._client_combo.blockSignals(False)
                return

        self._client_context.select(client)

    def _on_client_changed(self, client: ClientInfo | None) -> None:
        """Handle client context change — refresh all views."""
        if self._client_conn:
            self._client_conn.close()
            self._client_conn = None

        self._client_indicator.set_client_name(client.name if client else "")

        # Reset navigation
        self._nav_stack.reset()
        self._update_breadcrumbs()
        self._sidebar.setCurrentRow(0)
        self._content_stack.setCurrentIndex(_IDX_DASHBOARD)

        if client:
            # Open client database
            try:
                db_path = client.database_path
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                self._client_conn = run_client_migrations(db_path)
                self._dashboard.refresh(self._client_conn)
            except Exception as e:
                logger.error("Failed to open client database: %s", e)
                show_toast(self, f"Failed to open client database: {e}")

    def _on_sidebar_changed(self, index: int) -> None:
        """Handle sidebar selection change."""
        # Reset drill-down when switching sidebar entries
        self._nav_stack.reset()
        self._update_breadcrumbs()

        if index == 0:
            # Dashboard
            self._content_stack.setCurrentIndex(_IDX_DASHBOARD)
            if self._client_conn:
                self._dashboard.refresh(self._client_conn)
        elif index == 1:
            # Data Browser placeholder
            self._content_stack.setCurrentIndex(_IDX_DATA_BROWSER)
        elif index == 2:
            # Documents placeholder
            self._content_stack.setCurrentIndex(_IDX_DOCUMENTS)
        elif index == 3:
            # Impact Review
            self._content_stack.setCurrentIndex(_IDX_IMPACT_REVIEW)
            if self._client_conn:
                self._impact_view.refresh(self._client_conn)

    def _on_work_item_selected(self, work_item_id: int) -> None:
        """Handle work item click — push detail view onto drill-down stack."""
        if not self._client_conn:
            return

        # Build a label for the breadcrumb
        from automation.ui.work_item.work_item_logic import load_work_item
        item = load_work_item(self._client_conn, work_item_id)
        if not item:
            return

        label = format_work_item_name(
            item.item_type, item.domain_name, item.entity_name, item.process_name
        )
        self._nav_stack.push(NavEntry(label, "work_item", {"id": work_item_id}))
        self._update_breadcrumbs()

        # Pass connection to the impacts tab for review actions
        self._detail_view._impact_tab.set_connection(self._client_conn)

        self._detail_view.load_item(work_item_id, self._client_conn)
        self._content_stack.setCurrentIndex(_IDX_DETAIL)

    def _on_navigate_to_session(self, work_item_id: int, session_type: str = "initial") -> None:
        """Handle Generate Prompt — push session view onto drill-down stack."""
        if not self._client_conn:
            return

        from automation.ui.session.session_view import SessionView

        self._nav_stack.push(NavEntry("Generate Prompt", "session", {"id": work_item_id}))
        self._update_breadcrumbs()

        # Replace the session placeholder with a real SessionView
        old = self._content_stack.widget(_IDX_SESSION)
        session_view = SessionView(
            work_item_id, session_type, self._client_conn,
            return_callback=self._pop_drill_down,
        )
        self._content_stack.removeWidget(old)
        old.deleteLater()
        self._content_stack.insertWidget(_IDX_SESSION, session_view)
        self._content_stack.setCurrentIndex(_IDX_SESSION)

    def _on_navigate_to_import(self, work_item_id: int) -> None:
        """Handle Import Results — push import view onto drill-down stack."""
        if not self._client_conn:
            return

        from automation.ui.importer.import_view import ImportView

        self._nav_stack.push(NavEntry("Import Review", "import", {"id": work_item_id}))
        self._update_breadcrumbs()

        # Replace the import placeholder with a real ImportView
        old = self._content_stack.widget(_IDX_IMPORT)
        import_view = ImportView(
            work_item_id, self._client_conn,
            return_callback=self._pop_drill_down,
        )
        self._content_stack.removeWidget(old)
        old.deleteLater()
        self._content_stack.insertWidget(_IDX_IMPORT, import_view)
        self._content_stack.setCurrentIndex(_IDX_IMPORT)

    def _pop_drill_down(self) -> None:
        """Pop the drill-down stack and return to the previous view."""
        self._nav_stack.pop()
        self._update_breadcrumbs()

        current = self._nav_stack.current
        if current.view_type == "dashboard":
            self._content_stack.setCurrentIndex(_IDX_DASHBOARD)
            if self._client_conn:
                self._dashboard.refresh(self._client_conn)
        elif current.view_type == "work_item" and current.view_data:
            self._detail_view.load_item(current.view_data["id"], self._client_conn)
            self._content_stack.setCurrentIndex(_IDX_DETAIL)

    def _on_item_changed(self) -> None:
        """Handle work item state change — refresh dashboard data."""
        if self._client_conn:
            self._dashboard.refresh(self._client_conn)

    def _update_breadcrumbs(self) -> None:
        """Rebuild the breadcrumb bar from the navigation stack."""
        # Clear existing breadcrumbs
        while self._breadcrumb_container.count():
            child = self._breadcrumb_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._breadcrumb_bar.setVisible(self._nav_stack.show_breadcrumbs)

        if not self._nav_stack.show_breadcrumbs:
            return

        for i, entry in enumerate(self._nav_stack.breadcrumbs):
            if i > 0:
                sep = QLabel(" > ")
                sep.setStyleSheet("color: #9E9E9E; font-size: 12px;")
                self._breadcrumb_container.addWidget(sep)

            level = i + 1
            btn = QPushButton(entry.label)
            btn.setStyleSheet(
                "font-size: 12px; border: none; color: #1565C0; "
                "text-decoration: underline; padding: 2px 4px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked, lev=level: self._navigate_to_level(lev)
            )
            self._breadcrumb_container.addWidget(btn)

    def _navigate_to_level(self, level: int) -> None:
        """Pop the navigation stack to the given level."""
        self._nav_stack.pop_to_level(level)
        self._update_breadcrumbs()

        current = self._nav_stack.current
        if current.view_type == "dashboard":
            self._content_stack.setCurrentIndex(_IDX_DASHBOARD)
            if self._client_conn:
                self._dashboard.refresh(self._client_conn)
        elif current.view_type == "work_item" and current.view_data:
            self._detail_view.load_item(current.view_data["id"], self._client_conn)
            self._content_stack.setCurrentIndex(_IDX_DETAIL)

    def cleanup(self) -> None:
        """Close database connections on shutdown."""
        if self._client_conn:
            self._client_conn.close()
            self._client_conn = None
