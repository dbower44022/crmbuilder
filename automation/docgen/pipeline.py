"""Seven-step rendering pipeline for the Document Generator.

Implements L2 PRD Section 13.5:
  Step 1 Select — validate work item is in generatable state
  Step 2 Query  — invoke the data query layer
  Step 3 Validate — check data dictionary for completeness
  Step 4 Render — invoke the template module
  Step 5 Write  — file written by template; git commit for final
  Step 6 Record — write GenerationLog for final
  Step 7 Present — return result object

The pipeline is synchronous — no threads, no async.
"""

from __future__ import annotations

import dataclasses
import logging
import sqlite3
from pathlib import Path

from automation.docgen import (
    WORK_ITEM_TYPE_TO_DOCUMENT_TYPE,
    DocumentType,
    git_ops,
)
from automation.docgen.generation_log import record as record_generation
from automation.docgen.paths import resolve_output_path
from automation.docgen.queries import (
    crm_evaluation as q_crm_evaluation,
)
from automation.docgen.queries import (
    domain_overview as q_domain_overview,
)
from automation.docgen.queries import (
    domain_prd as q_domain_prd,
)
from automation.docgen.queries import (
    entity_inventory as q_entity_inventory,
)
from automation.docgen.queries import (
    entity_prd as q_entity_prd,
)

# Query modules
from automation.docgen.queries import (
    master_prd as q_master_prd,
)
from automation.docgen.queries import (
    process_document as q_process_document,
)
from automation.docgen.queries import (
    user_process_guide as q_user_process_guide,
)
from automation.docgen.queries import (
    yaml_program as q_yaml_program,
)
from automation.docgen.templates import (
    crm_evaluation_template as t_crm_evaluation,
)
from automation.docgen.templates import (
    domain_overview_template as t_domain_overview,
)
from automation.docgen.templates import (
    domain_prd_template as t_domain_prd,
)
from automation.docgen.templates import (
    entity_inventory_template as t_entity_inventory,
)
from automation.docgen.templates import (
    entity_prd_template as t_entity_prd,
)

# Template modules
from automation.docgen.templates import (
    master_prd_template as t_master_prd,
)
from automation.docgen.templates import (
    process_document_template as t_process_document,
)
from automation.docgen.templates import (
    user_process_guide_template as t_user_process_guide,
)
from automation.docgen.templates import (
    yaml_program_template as t_yaml_program,
)
from automation.docgen.validation import ValidationWarning, validate
from automation.docgen.workflow_diagram import get_diagram_path

logger = logging.getLogger(__name__)

# Maps document type to (query_module, template_module)
_TYPE_MODULES = {
    DocumentType.MASTER_PRD: (q_master_prd, t_master_prd),
    DocumentType.ENTITY_INVENTORY: (q_entity_inventory, t_entity_inventory),
    DocumentType.ENTITY_PRD: (q_entity_prd, t_entity_prd),
    DocumentType.DOMAIN_OVERVIEW: (q_domain_overview, t_domain_overview),
    DocumentType.PROCESS_DOCUMENT: (q_process_document, t_process_document),
    DocumentType.DOMAIN_PRD: (q_domain_prd, t_domain_prd),
    DocumentType.YAML_PROGRAM_FILES: (q_yaml_program, t_yaml_program),
    DocumentType.CRM_EVALUATION_REPORT: (q_crm_evaluation, t_crm_evaluation),
    DocumentType.USER_PROCESS_GUIDE: (q_user_process_guide, t_user_process_guide),
}


@dataclasses.dataclass
class GenerationResult:
    """Result of a single document generation."""

    work_item_id: int
    document_type: DocumentType
    mode: str
    file_path: str | None = None
    file_paths: list[str] | None = None  # For YAML (multiple files)
    warnings: list[ValidationWarning] = dataclasses.field(default_factory=list)
    git_commit_hash: str | None = None
    error: str | None = None
    generation_log_id: int | None = None


def run_pipeline(
    conn: sqlite3.Connection,
    work_item_id: int,
    mode: str = "final",
    project_folder: str | Path | None = None,
    master_conn: sqlite3.Connection | None = None,
) -> GenerationResult:
    """Execute the seven-step rendering pipeline.

    :param conn: Client database connection.
    :param work_item_id: The WorkItem.id to generate.
    :param mode: 'final' or 'draft'.
    :param project_folder: Root of the client's project repository.
    :param master_conn: Master database connection.
    :returns: GenerationResult describing what happened.
    :raises ValueError: If mode is invalid or work item is not generatable.
    """
    if mode not in ("final", "draft"):
        raise ValueError(f"Invalid generation mode: {mode!r}. Must be 'final' or 'draft'.")

    # ── Step 1: Select ──────────────────────────────────────────────
    wi = conn.execute(
        "SELECT item_type, status FROM WorkItem WHERE id = ?",
        (work_item_id,),
    ).fetchone()
    if not wi:
        raise ValueError(f"Work item {work_item_id} not found")

    item_type, status = wi

    # Validate generatable state
    if mode == "final" and status != "complete":
        raise ValueError(
            f"Work item {work_item_id} has status '{status}'; "
            f"final generation requires 'complete' status."
        )
    if mode == "draft" and status != "in_progress":
        raise ValueError(
            f"Work item {work_item_id} has status '{status}'; "
            f"draft generation requires 'in_progress' status."
        )

    # Determine document type from work item type
    doc_type = WORK_ITEM_TYPE_TO_DOCUMENT_TYPE.get(item_type)
    if not doc_type:
        raise ValueError(
            f"Work item type '{item_type}' does not produce a generated document."
        )

    result = GenerationResult(
        work_item_id=work_item_id,
        document_type=doc_type,
        mode=mode,
    )

    try:
        # ── Step 2: Query ───────────────────────────────────────────
        query_mod, template_mod = _TYPE_MODULES[doc_type]
        if doc_type == DocumentType.USER_PROCESS_GUIDE:
            # User Process Guide query also needs the project folder so it
            # can merge YAML program data with DB process records.
            data_dict = query_mod.query(
                conn, work_item_id, master_conn,
                project_folder=project_folder,
            )
        else:
            data_dict = query_mod.query(conn, work_item_id, master_conn)

        # For process documents, inject the diagram path
        if doc_type == DocumentType.PROCESS_DOCUMENT and project_folder:
            process_id = conn.execute(
                "SELECT process_id FROM WorkItem WHERE id = ?",
                (work_item_id,),
            ).fetchone()
            if process_id and process_id[0]:
                diagram = get_diagram_path(conn, process_id[0], project_folder)
                data_dict["diagram_path"] = str(diagram) if diagram else None

        # ── Step 3: Validate ────────────────────────────────────────
        is_draft = mode == "draft"
        warnings = validate(doc_type, data_dict, is_draft=is_draft)
        result.warnings = warnings

        # ── Step 4 & 5: Render + Write ──────────────────────────────
        if project_folder:
            output = resolve_output_path(
                doc_type, conn, work_item_id, project_folder, master_conn
            )

            if doc_type == DocumentType.YAML_PROGRAM_FILES:
                # YAML generates multiple files
                if isinstance(output, list):
                    template_mod.generate_multi(data_dict, output)
                    file_paths = [str(p) for p in output]
                    result.file_paths = file_paths
                    result.file_path = file_paths[0] if file_paths else None
                else:
                    template_mod.generate(data_dict, output, is_draft=is_draft)
                    result.file_path = str(output)
                    result.file_paths = [str(output)]
            else:
                template_mod.generate(data_dict, output, is_draft=is_draft)
                result.file_path = str(output)

            # Git commit for final mode
            if mode == "final" and result.file_path:
                commit_files = result.file_paths or [result.file_path]
                # Build commit message
                doc_name = _get_document_name(conn, doc_type, work_item_id)
                commit_msg = f"Generated {doc_type.value}: {doc_name}"
                commit_hash = git_ops.commit(
                    project_folder, commit_files, commit_msg
                )
                result.git_commit_hash = commit_hash

        # ── Step 6: Record ──────────────────────────────────────────
        if mode == "final" and result.file_path:
            rel_path = result.file_path
            if project_folder:
                try:
                    rel_path = str(
                        Path(result.file_path).relative_to(project_folder)
                    )
                except ValueError:
                    pass

            log_id = record_generation(
                conn,
                work_item_id,
                doc_type.value,
                rel_path,
                mode,
                result.git_commit_hash,
            )
            result.generation_log_id = log_id

    except Exception as e:
        logger.exception("Pipeline error for work item %d", work_item_id)
        result.error = str(e)

    # ── Step 7: Present ─────────────────────────────────────────────
    return result


def _get_document_name(
    conn: sqlite3.Connection, doc_type: DocumentType, work_item_id: int
) -> str:
    """Build a human-readable document name for commit messages."""
    wi = conn.execute(
        "SELECT entity_id, domain_id, process_id FROM WorkItem WHERE id = ?",
        (work_item_id,),
    ).fetchone()
    if not wi:
        return str(work_item_id)

    entity_id, domain_id, process_id = wi

    if doc_type == DocumentType.ENTITY_PRD and entity_id:
        row = conn.execute("SELECT name FROM Entity WHERE id = ?", (entity_id,)).fetchone()
        return row[0] if row else str(entity_id)

    if doc_type in (DocumentType.DOMAIN_OVERVIEW, DocumentType.DOMAIN_PRD,
                    DocumentType.YAML_PROGRAM_FILES) and domain_id:
        row = conn.execute("SELECT name FROM Domain WHERE id = ?", (domain_id,)).fetchone()
        return row[0] if row else str(domain_id)

    if doc_type in (
        DocumentType.PROCESS_DOCUMENT, DocumentType.USER_PROCESS_GUIDE,
    ) and process_id:
        row = conn.execute(
            "SELECT name, code FROM Process WHERE id = ?", (process_id,)
        ).fetchone()
        if row:
            return f"{row[0]} ({row[1]})"
        return str(process_id)

    return doc_type.value
