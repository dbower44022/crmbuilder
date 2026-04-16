"""CBMImporter — public API for the CBM PRD bootstrap import.

Orchestrates parsing of all CBM Word documents and populating a client
database. Calls WorkflowEngine to construct the work item graph after
each phase of the import.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from automation.cbm_import.reporter import ImportReport
from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class CBMImporter:
    """Public API for the CBM PRD bootstrap import."""

    def __init__(
        self,
        client_db_path: Path | str,
        master_db_path: Path | str,
        cbm_repo_path: Path | str,
    ) -> None:
        self._client_db_path = str(client_db_path)
        self._master_db_path = str(master_db_path)
        self._cbm_repo = Path(cbm_repo_path)
        self._prds = self._cbm_repo / "PRDs"
        self._conn: sqlite3.Connection | None = None
        self._master_conn: sqlite3.Connection | None = None

    def import_all(self, *, dry_run: bool = False) -> ImportReport:
        """Import all CBM PRDs into the client database."""
        report = ImportReport()
        self._master_conn = run_master_migrations(self._master_db_path)
        self._conn = run_client_migrations(self._client_db_path)

        try:
            self._ensure_client_record()

            if dry_run:
                report.merge(self._parse_dry_run())
                return report

            engine = WorkflowEngine(self._conn)

            # Phase 1: Create project + import Master PRD data
            # Master PRD import has migrated to Path B. The work item
            # graph is still needed so the remaining phases can proceed.
            master_wi_id = engine.create_project()
            try:
                r = self.import_master_prd(master_wi_id)
                report.merge(r)
            except NotImplementedError:
                report.add_warning(
                    "Master PRD import skipped — migrated to Path B. "
                    "Use ImportProcessor for master PRD imports."
                )
            engine.start(master_wi_id)
            engine.complete(master_wi_id)
            engine.after_master_prd_import()

            # Phase 2: Import Entity Inventory
            bod_wi = self._find_work_item("business_object_discovery")
            r = self.import_entity_inventory(bod_wi)
            report.merge(r)
            if bod_wi:
                engine.start(bod_wi)
                engine.complete(bod_wi)
            engine.after_business_object_discovery_import()

            # Phase 3: Import Entity PRDs
            for entity_file in sorted(self._prds.glob("entities/*-Entity-PRD*.docx")):
                if entity_file.name.startswith("~"):
                    continue
                entity_name = entity_file.stem.split("-Entity-PRD")[0]
                r = self.import_entity_prd(entity_name, entity_file)
                report.merge(r)
            self._mark_type_complete("entity_prd")

            # Phase 4: Import Process Documents
            for domain_dir in sorted(self._prds.iterdir()):
                if not domain_dir.is_dir() or domain_dir.name in (
                    "entities", "Archive", "WorkflowDiagrams", "services", "Graphics"
                ):
                    continue
                for proc_file in sorted(domain_dir.rglob("*.docx")):
                    if proc_file.name.startswith("~"):
                        continue
                    if any(kw in proc_file.name for kw in ("Domain-PRD", "Domain-Overview", "SubDomain")):
                        continue
                    r = self.import_process(proc_file.stem, proc_file)
                    report.merge(r)

            # Services
            services_dir = self._prds / "services"
            if services_dir.exists():
                for svc_dir in sorted(services_dir.iterdir()):
                    if svc_dir.is_dir():
                        for proc_file in sorted(svc_dir.glob("*.docx")):
                            if not proc_file.name.startswith("~"):
                                r = self.import_process(proc_file.stem, proc_file, is_service=True)
                                report.merge(r)
            self._mark_type_complete("process_definition")

            # Phase 5: Import Domain PRDs
            for domain_dir in sorted(self._prds.iterdir()):
                if not domain_dir.is_dir() or domain_dir.name in (
                    "entities", "Archive", "WorkflowDiagrams", "services"
                ):
                    continue
                for prd_file in sorted(domain_dir.glob("*Domain-PRD*.docx")):
                    if not prd_file.name.startswith("~"):
                        r = self.import_domain_prd(domain_dir.name, prd_file)
                        report.merge(r)
            self._mark_type_complete("domain_reconciliation")

        except Exception as e:
            report.add_error(f"Fatal error during import: {e}")
            logger.exception("CBM import failed")
        finally:
            if self._conn:
                self._conn.close()
            if self._master_conn:
                self._master_conn.close()

        return report

    def import_master_prd(self, work_item_id: int | None = None) -> ImportReport:
        """Import the Master PRD document.

        .. deprecated::
            Master PRD imports must go through Path B:
            automation.importer.parsers.master_prd_docx + ImportProcessor.
        """
        raise NotImplementedError(
            "Master PRD imports must go through Path B: "
            "automation.importer.parsers.master_prd_docx + ImportProcessor."
        )

    def import_entity_inventory(self, work_item_id: int | None = None) -> ImportReport:
        """Import the Entity Inventory document.

        .. deprecated::
            Entity Inventory imports must go through Path B:
            automation.importer.parsers.entity_inventory_docx + ImportProcessor.
        """
        report = ImportReport()
        report.add_warning(
            "Entity Inventory import skipped — migrated to Path B. "
            "Use ImportProcessor for entity inventory imports."
        )
        return report

    def import_entity_prd(self, entity_name: str, path: Path | None = None) -> ImportReport:
        """Import a single Entity PRD document.

        .. deprecated::
            Entity PRD imports must go through Path B:
            automation.importer.parsers.entity_prd_docx + ImportProcessor.
        """
        report = ImportReport()
        report.add_warning(
            f"Entity PRD import skipped for {entity_name} — migrated "
            "to Path B. Use ImportProcessor for entity PRD imports."
        )
        return report

    def import_process(
        self,
        process_code: str,
        path: Path | None = None,
        *,
        is_service: bool = False,
    ) -> ImportReport:
        """Import a single Process Document.

        .. deprecated::
            Process imports must go through Path B:
            automation.importer.parsers.process_doc_docx + ImportProcessor.
        """
        report = ImportReport()
        report.add_warning(
            f"Process import skipped for {process_code} — migrated to Path B. "
            "Use ImportProcessor for process document imports."
        )
        return report

    def import_domain_prd(self, domain_code: str, path: Path | None = None) -> ImportReport:
        """Import a single Domain PRD document.

        .. deprecated::
            Domain PRD imports must go through Path B:
            automation.importer.parsers.domain_prd_docx + ImportProcessor.
        """
        report = ImportReport()
        report.add_warning(
            f"Domain PRD import skipped for {domain_code} — migrated to Path B. "
            "Use ImportProcessor for domain PRD imports."
        )
        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_client_record(self) -> None:
        if self._master_conn is None:
            return
        row = self._master_conn.execute("SELECT id FROM Client WHERE code = 'CBM'").fetchone()
        if not row:
            db_path = str(Path(self._client_db_path).resolve())
            self._master_conn.execute(
                "INSERT INTO Client (name, code, database_path) VALUES (?, ?, ?)",
                ("Cleveland Business Mentors", "CBM", db_path),
            )
            self._master_conn.commit()

    def _create_session(self, work_item_id: int, notes: str) -> int:
        if self._conn is None:
            return 0
        now = _now()
        cursor = self._conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, notes, started_at, completed_at) "
            "VALUES (?, 'initial', '[CBM bootstrap import]', 'imported', ?, ?, ?)",
            (work_item_id, notes, now, now),
        )
        self._conn.commit()
        return cursor.lastrowid

    def _find_work_item(self, item_type: str) -> int | None:
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = ? LIMIT 1", (item_type,)
        ).fetchone()
        return row[0] if row else None

    def _mark_type_complete(self, item_type: str) -> None:
        if self._conn is None:
            return
        now = _now()
        rows = self._conn.execute(
            "SELECT id, status FROM WorkItem WHERE item_type = ?", (item_type,)
        ).fetchall()
        engine = WorkflowEngine(self._conn)
        for wi_id, status in rows:
            try:
                if status in ("not_started", "ready"):
                    # Force to ready first
                    self._conn.execute(
                        "UPDATE WorkItem SET status = 'ready' WHERE id = ?", (wi_id,)
                    )
                    self._conn.commit()
                    engine.start(wi_id)
                if engine.get_status(wi_id) == "in_progress":
                    engine.complete(wi_id)
            except Exception:
                # Force complete for bootstrap
                self._conn.execute(
                    "UPDATE WorkItem SET status = 'complete', completed_at = ? WHERE id = ?",
                    (now, wi_id),
                )
                self._conn.commit()

    def _resolve(self, table: str, col: str, value: str) -> int | None:
        if not value or self._conn is None:
            return None
        row = self._conn.execute(
            f"SELECT id FROM {table} WHERE {col} = ?", (value,)  # noqa: S608
        ).fetchone()
        return row[0] if row else None

    def _insert_ignore(self, table: str, columns: str, values: tuple) -> None:
        if self._conn is None:
            return
        placeholders = ", ".join("?" for _ in values)
        try:
            self._conn.execute(
                f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})",  # noqa: S608
                values,
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            self._conn.rollback()

    def _ensure_services_domain(self, session_id: int) -> int:
        """Get the ID of the Services domain, creating it if needed.

        Service documents (e.g. NOTES-MANAGE) are structurally parallel to
        domain processes but live under a synthetic 'Services' domain row
        with is_service=TRUE.

        :param session_id: AISession ID for created_by_session_id.
        :returns: The Services domain ID.
        """
        if self._conn is None:
            return 0
        existing = self._resolve("Domain", "code", "SVC")
        if existing:
            return existing
        self._conn.execute(
            "INSERT INTO Domain (name, code, description, sort_order, is_service) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Services", "SVC", "Cross-domain services", 99, True),
        )
        self._conn.commit()
        return self._resolve("Domain", "code", "SVC") or 0

    def _parse_dry_run(self) -> ImportReport:
        report = ImportReport()
        report.add_warning(
            "All parsers have migrated to Path B. "
            "Use ImportProcessor for dry run parsing."
        )
        return report


def _now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
