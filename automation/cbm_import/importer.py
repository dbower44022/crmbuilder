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

from automation.cbm_import.parsers import (
    domain_prd,
    entity_inventory,
    entity_prd,
    process_document,
)
from automation.cbm_import.parsers import master_prd as master_prd_parser
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
            master_wi_id = engine.create_project()
            r = self.import_master_prd(master_wi_id)
            report.merge(r)
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
                                r = self.import_process(proc_file.stem, proc_file)
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
        """Import the Master PRD document."""
        report = ImportReport()
        path = self._prds / "CBM-Master-PRD.docx"
        if not path.exists():
            report.add_error(f"Master PRD not found: {path}")
            return report

        try:
            data, parse_report = master_prd_parser.parse(path)
            report.merge(parse_report)
            if self._conn is None:
                return report

            session_id = self._create_session(work_item_id or 1, "Master PRD bootstrap import")

            for persona in data.get("personas", []):
                self._insert_ignore(
                    "Persona", "name, code, description, created_by_session_id",
                    (persona["name"], persona["code"], persona.get("description", ""), session_id),
                )
                report.record_imported("Persona")

            for i, domain in enumerate(data.get("domains", []), 1):
                self._insert_ignore(
                    "Domain", "name, code, description, sort_order, is_service",
                    (domain["name"], domain["code"], domain.get("description", ""), i, False),
                )
                report.record_imported("Domain")

            for proc in data.get("processes", []):
                domain_id = self._resolve("Domain", "code", proc.get("domain_code", ""))
                if domain_id:
                    self._insert_ignore(
                        "Process", "domain_id, name, code, sort_order",
                        (domain_id, proc["name"], proc["code"], proc.get("sort_order", 1)),
                    )
                    report.record_imported("Process")

            if self._master_conn and data.get("organization_overview"):
                self._master_conn.execute(
                    "UPDATE Client SET organization_overview = ? WHERE code = 'CBM'",
                    (data["organization_overview"],),
                )
                self._master_conn.commit()

        except Exception as e:
            report.add_error(f"Master PRD import failed: {e}")
            logger.exception("Master PRD import failed")
        return report

    def import_entity_inventory(self, work_item_id: int | None = None) -> ImportReport:
        """Import the Entity Inventory document."""
        report = ImportReport()
        path = self._prds / "CBM-Entity-Inventory.docx"
        if not path.exists():
            report.add_error(f"Entity Inventory not found: {path}")
            return report

        try:
            data, parse_report = entity_inventory.parse(path)
            report.merge(parse_report)
            if self._conn is None:
                return report

            session_id = self._create_session(work_item_id or 1, "Entity Inventory bootstrap")

            for entity in data.get("entities", []):
                self._insert_ignore(
                    "Entity", "name, code, entity_type, is_native, created_by_session_id",
                    (entity["name"], entity["code"], entity.get("entity_type", "Base"),
                     entity.get("is_native", False), session_id),
                )
                report.record_imported("Entity")

            for bo in data.get("business_objects", []):
                entity_id = self._resolve("Entity", "name", bo.get("entity_name", ""))
                self._insert_ignore(
                    "BusinessObject", "name, status, resolution, resolved_to_entity_id, created_by_session_id",
                    (bo["name"], bo.get("status", "unclassified"), bo.get("resolution"),
                     entity_id, session_id),
                )
                report.record_imported("BusinessObject")

        except Exception as e:
            report.add_error(f"Entity Inventory import failed: {e}")
        return report

    def import_entity_prd(self, entity_name: str, path: Path | None = None) -> ImportReport:
        """Import a single Entity PRD document."""
        report = ImportReport()
        if path is None:
            path = self._prds / "entities" / f"{entity_name}-Entity-PRD.docx"
        if not path.exists():
            report.add_warning(f"Entity PRD not found: {path}")
            return report

        try:
            data, parse_report = entity_prd.parse(path)
            report.merge(parse_report)
            if self._conn is None:
                return report

            entity_info = data.get("entity", {})
            e_name = entity_info.get("name", entity_name)
            wi_id = self._find_work_item("entity_prd") or 1
            session_id = self._create_session(wi_id, f"Entity PRD import: {e_name}")

            entity_id = self._resolve("Entity", "name", e_name)
            if not entity_id:
                self._conn.execute(
                    "INSERT INTO Entity (name, code, entity_type, is_native, "
                    "singular_label, plural_label, description, created_by_session_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (e_name, e_name.upper(), entity_info.get("entity_type", "Base"),
                     entity_info.get("is_native", False),
                     entity_info.get("singular_label", e_name),
                     entity_info.get("plural_label", ""), entity_info.get("description", ""),
                     session_id),
                )
                self._conn.commit()
                entity_id = self._resolve("Entity", "name", e_name)

            for field in data.get("fields", []):
                try:
                    cursor = self._conn.execute(
                        "INSERT INTO Field (entity_id, name, label, field_type, is_required, "
                        "default_value, description, created_by_session_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (entity_id, field["name"], field.get("label", field["name"]),
                         field.get("field_type", "varchar"), field.get("is_required", False),
                         field.get("default_value"), field.get("description", ""), session_id),
                    )
                    self._conn.commit()
                    field_id = cursor.lastrowid
                    report.record_imported("Field")

                    for opt in data.get("field_options", []):
                        if opt["field_name"] == field["name"]:
                            self._conn.execute(
                                "INSERT INTO FieldOption (field_id, value, label, sort_order, "
                                "created_by_session_id) VALUES (?, ?, ?, ?, ?)",
                                (field_id, opt["value"], opt["label"],
                                 opt.get("sort_order", 0), session_id),
                            )
                            self._conn.commit()
                            report.record_imported("FieldOption")
                except sqlite3.IntegrityError:
                    self._conn.rollback()
                    report.record_skipped(path.name, "Field", field["name"], "Duplicate field")

        except Exception as e:
            report.add_error(f"Entity PRD import failed for {entity_name}: {e}")
        return report

    def import_process(self, process_code: str, path: Path | None = None) -> ImportReport:
        """Import a single Process Document."""
        report = ImportReport()
        if path is None or not path.exists():
            report.add_warning(f"Process document not found for {process_code}")
            return report

        try:
            data, parse_report = process_document.parse(path)
            report.merge(parse_report)
            if self._conn is None:
                return report

            proc_data = data.get("process", {})
            code = proc_data.get("code", process_code)
            wi_id = self._find_work_item("process_definition") or 1
            session_id = self._create_session(wi_id, f"Process import: {code}")

            process_id = self._resolve("Process", "code", code)
            if not process_id:
                domain_id = self._resolve("Domain", "code", proc_data.get("domain_code", ""))
                if domain_id:
                    self._conn.execute(
                        "INSERT INTO Process (domain_id, name, code, description, triggers, "
                        "completion_criteria, sort_order, created_by_session_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (domain_id, proc_data.get("name", code), code,
                         proc_data.get("description", ""), proc_data.get("triggers", ""),
                         proc_data.get("completion_criteria", ""), 1, session_id),
                    )
                    self._conn.commit()
                    process_id = self._resolve("Process", "code", code)
                    report.record_imported("Process")
                else:
                    report.record_skipped(path.name, "Process", code, "Could not resolve domain")
                    return report
            else:
                self._conn.execute(
                    "UPDATE Process SET description = ?, triggers = ?, completion_criteria = ? WHERE id = ?",
                    (proc_data.get("description", ""), proc_data.get("triggers", ""),
                     proc_data.get("completion_criteria", ""), process_id),
                )
                self._conn.commit()

            for step in data.get("steps", []):
                self._conn.execute(
                    "INSERT INTO ProcessStep (process_id, name, description, step_type, "
                    "sort_order, created_by_session_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (process_id, step["name"][:200], step.get("description", ""),
                     step.get("step_type", "action"), step.get("sort_order", 0), session_id),
                )
                self._conn.commit()
                report.record_imported("ProcessStep")

            for req in data.get("requirements", []):
                try:
                    self._conn.execute(
                        "INSERT INTO Requirement (identifier, process_id, description, "
                        "priority, status, created_by_session_id) VALUES (?, ?, ?, ?, 'proposed', ?)",
                        (req["identifier"], process_id, req.get("description", ""),
                         req.get("priority", "must"), session_id),
                    )
                    self._conn.commit()
                    report.record_imported("Requirement")
                except sqlite3.IntegrityError:
                    self._conn.rollback()
                    report.record_skipped(path.name, "Requirement", req["identifier"], "Duplicate")

            for persona_ref in data.get("personas", []):
                persona_id = self._resolve("Persona", "code", persona_ref.get("code", ""))
                if persona_id:
                    try:
                        self._conn.execute(
                            "INSERT INTO ProcessPersona (process_id, persona_id, role) VALUES (?, ?, ?)",
                            (process_id, persona_id, persona_ref.get("role", "performer")),
                        )
                        self._conn.commit()
                        report.record_imported("ProcessPersona")
                    except sqlite3.IntegrityError:
                        self._conn.rollback()

        except Exception as e:
            report.add_error(f"Process import failed for {process_code}: {e}")
        return report

    def import_domain_prd(self, domain_code: str, path: Path | None = None) -> ImportReport:
        """Import a single Domain PRD document."""
        report = ImportReport()
        if path is None or not path.exists():
            report.add_warning(f"Domain PRD not found: {path}")
            return report

        try:
            data, parse_report = domain_prd.parse(path)
            report.merge(parse_report)
            if self._conn is None:
                return report

            code = data.get("domain_code", domain_code)
            wi_id = self._find_work_item("domain_reconciliation") or 1
            session_id = self._create_session(wi_id, f"Domain PRD import: {code}")

            domain_id = self._resolve("Domain", "code", code)
            if domain_id:
                self._conn.execute(
                    "UPDATE Domain SET domain_overview_text = ?, domain_reconciliation_text = ? WHERE id = ?",
                    (data.get("domain_overview_text", ""),
                     data.get("domain_reconciliation_text", ""), domain_id),
                )
                self._conn.commit()

            for dec in data.get("decisions", []):
                try:
                    self._conn.execute(
                        "INSERT INTO Decision (identifier, title, description, status, "
                        "domain_id, created_by_session_id) VALUES (?, ?, ?, ?, ?, ?)",
                        (dec["identifier"], dec["title"], dec.get("description", ""),
                         dec.get("status", "locked"), domain_id, session_id),
                    )
                    self._conn.commit()
                    report.record_imported("Decision")
                except sqlite3.IntegrityError:
                    self._conn.rollback()
                    report.record_skipped(path.name, "Decision", dec["identifier"], "Duplicate")

        except Exception as e:
            report.add_error(f"Domain PRD import failed for {domain_code}: {e}")
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

    def _parse_dry_run(self) -> ImportReport:
        report = ImportReport()
        for path, parser in [
            (self._prds / "CBM-Master-PRD.docx", master_prd_parser),
            (self._prds / "CBM-Entity-Inventory.docx", entity_inventory),
        ]:
            if path.exists():
                _, r = parser.parse(path)
                report.merge(r)

        for f in sorted(self._prds.glob("entities/*-Entity-PRD*.docx")):
            if not f.name.startswith("~"):
                _, r = entity_prd.parse(f)
                report.merge(r)

        for d in sorted(self._prds.iterdir()):
            if d.is_dir() and d.name not in ("entities", "Archive", "WorkflowDiagrams", "services", "Graphics"):
                for f in sorted(d.rglob("*.docx")):
                    if not f.name.startswith("~") and not any(
                        kw in f.name for kw in ("Domain-PRD", "Domain-Overview", "SubDomain")
                    ):
                        _, r = process_document.parse(f)
                        report.merge(r)
                for f in sorted(d.glob("*Domain-PRD*.docx")):
                    if not f.name.startswith("~"):
                        _, r = domain_prd.parse(f)
                        report.merge(r)
        return report


def _now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
