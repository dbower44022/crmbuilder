"""Documents view — main container (Section 14.7).

Registered as the "Documents" sidebar entry in RequirementsWindow.
Two entry points: sidebar (cross-cutting) and Work Item Detail header
(scoped to a single work item with "Show All Documents" toggle).
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from automation.ui.common.toast import show_toast
from automation.ui.documents.batch_controls import BatchControls
from automation.ui.documents.document_inventory import DocumentInventory
from automation.ui.documents.documents_logic import (
    DocumentEntry,
    filter_stale,
    load_document_inventory,
)
from automation.ui.documents.generation_flow import GenerationFlow

logger = logging.getLogger(__name__)

_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)


class DocumentsView(QWidget):
    """The Documents view — Section 14.7.

    :param parent: Parent widget.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._master_db_path: str | None = None
        self._project_folder: str | None = None
        self._scoped_work_item_id: int | None = None
        self._filter_stale_only: bool = False
        self._entries: list[DocumentEntry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(8, 8, 8, 4)
        self._title = QLabel("Documents")
        self._title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1F3864;")
        header.addWidget(self._title)
        header.addStretch()

        # Toggle for scoped vs all
        self._toggle_btn = QPushButton("Show All Documents")
        self._toggle_btn.setStyleSheet(_PRIMARY_STYLE)
        self._toggle_btn.setVisible(False)
        self._toggle_btn.clicked.connect(self._on_toggle_scope)
        header.addWidget(self._toggle_btn)

        layout.addLayout(header)

        # Batch controls
        self._batch_controls = BatchControls()
        self._batch_controls.regenerate_selected.connect(self._on_regenerate_selected)
        self._batch_controls.select_all_stale.connect(self._on_select_all_stale)
        layout.addWidget(self._batch_controls)

        # Inventory
        self._inventory = DocumentInventory()
        self._inventory.generate_final_requested.connect(
            lambda wi_id: self._run_generation(wi_id, "final")
        )
        self._inventory.generate_draft_requested.connect(
            lambda wi_id: self._run_generation(wi_id, "draft")
        )
        self._inventory.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self._inventory, stretch=1)

        # Generation flow (hidden by default)
        self._gen_flow: GenerationFlow | None = None

    def set_scope(
        self,
        work_item_id: int | None = None,
        stale_only: bool = False,
    ) -> None:
        """Set the view scope before refreshing.

        :param work_item_id: Scope to a single work item (from header action).
        :param stale_only: Show only stale documents (from Requirements Dashboard link).
        """
        self._scoped_work_item_id = work_item_id
        self._filter_stale_only = stale_only
        self._toggle_btn.setVisible(work_item_id is not None)
        if work_item_id:
            self._title.setText("Document — Scoped")
        elif stale_only:
            self._title.setText("Documents — Stale")
        else:
            self._title.setText("Documents")

    def set_project_folder(self, project_folder: str | None) -> None:
        """Set the project folder for document generation.

        :param project_folder: Path to the client project repository root.
        """
        self._project_folder = project_folder

    def refresh(self, conn: sqlite3.Connection, master_db_path: str | None = None) -> None:
        """Reload the inventory from the database.

        :param conn: Client database connection.
        :param master_db_path: Path to master database (for DocumentGenerator).
        """
        self._conn = conn
        self._master_db_path = master_db_path

        try:
            from automation.docgen.staleness import get_stale_documents
            stale_docs = get_stale_documents(conn)
        except Exception:
            stale_docs = []

        self._entries = load_document_inventory(
            conn, stale_docs,
            scoped_work_item_id=self._scoped_work_item_id,
        )

        if self._filter_stale_only:
            self._entries = filter_stale(self._entries)

        self._inventory.update_entries(self._entries)
        self._on_selection_changed()

    def _on_toggle_scope(self) -> None:
        """Toggle between scoped and all documents."""
        if self._scoped_work_item_id:
            self.set_scope(work_item_id=None)
        else:
            # Cannot re-scope without original work item ID
            pass
        if self._conn:
            self.refresh(self._conn, self._master_db_path)

    def _on_selection_changed(self) -> None:
        """Update batch controls when selection changes."""
        selected = self._inventory.get_selected_work_item_ids()
        self._batch_controls.update_selection_count(len(selected))

    def _on_select_all_stale(self) -> None:
        """Select all stale document rows."""
        self._inventory.select_all_stale()
        self._on_selection_changed()

    def _on_regenerate_selected(self) -> None:
        """Regenerate all selected documents in batch (final mode only)."""
        selected_ids = self._inventory.get_selected_work_item_ids()
        if not selected_ids:
            show_toast(self, "No documents selected for regeneration")
            return
        if not self._conn:
            return

        if not self._project_folder:
            show_toast(
                self,
                "No project folder configured for this client. "
                "Associate an instance in the Deployment tab.",
            )
            return

        try:
            from automation.docgen.generator import DocumentGenerator
            docgen = DocumentGenerator(self._conn, project_folder=self._project_folder)
            results = docgen.generate_batch(selected_ids, mode="final")

            success = sum(1 for r in results if not r.error)
            failures = sum(1 for r in results if r.error)
            self._batch_controls.show_summary(success, 0, failures)

            # Refresh the inventory
            self.refresh(self._conn, self._master_db_path)

        except Exception as e:
            logger.warning("Batch generation failed: %s", e)
            show_toast(self, f"Batch generation failed: {e}")

    def _run_generation(self, work_item_id: int, mode: str) -> None:
        """Run generation for a single work item.

        :param work_item_id: Work item to generate.
        :param mode: 'final' or 'draft'.
        """
        if not self._conn:
            return

        if not self._project_folder:
            show_toast(
                self,
                "No project folder configured for this client. "
                "Associate an instance in the Deployment tab.",
            )
            return

        try:
            from automation.docgen.generator import DocumentGenerator
            docgen = DocumentGenerator(self._conn, project_folder=self._project_folder)
            result = docgen.generate(work_item_id, mode=mode)

            if result.error:
                show_toast(self, f"Generation failed: {result.error}")
            else:
                path = result.file_path or (result.file_paths[0] if result.file_paths else "")
                show_toast(self, f"Generated: {path}")

            # Refresh the inventory
            self.refresh(self._conn, self._master_db_path)

        except Exception as e:
            logger.warning("Generation failed for work item %d: %s", work_item_id, e)
            show_toast(self, f"Generation failed: {e}")
