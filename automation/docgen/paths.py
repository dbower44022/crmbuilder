"""Output path resolution for the Document Generator.

Implements L2 PRD Section 13.7.1 — computes the output file path for each
document type given the work item, database connections, and project folder root.

Path patterns:
    Master PRD:         PRDs/{client}-Master-PRD.docx
    Entity Inventory:   PRDs/{client}-Entity-Inventory.docx
    Entity PRD:         PRDs/entities/{EntityName}-Entity-PRD.docx
    Domain Overview:    PRDs/{domain_code}/{client}-Domain-Overview-{DomainName}.docx
    Process Document:   PRDs/{domain_code}/{PROCESS-CODE}.docx
    Domain PRD:         PRDs/{domain_code}/{client}-Domain-PRD-{DomainName}.docx
    YAML Program:       programs/{entity_name}.yaml
    CRM Evaluation:     PRDs/{client}-CRM-Evaluation-Report.docx

Sub-domains nest: PRDs/{parent_code}/{subdomain_code}/{PROCESS-CODE}.docx
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from automation.docgen import DocumentType


def get_client_short_name(master_conn: sqlite3.Connection | None) -> str:
    """Return the client short name (code) from the Client table.

    Falls back to lowercased client name if code is missing,
    or 'client' if no Client record exists.
    """
    if master_conn is None:
        return "client"
    row = master_conn.execute(
        "SELECT code, name FROM Client ORDER BY id LIMIT 1"
    ).fetchone()
    if not row:
        return "client"
    code, name = row
    if code:
        return code
    if name:
        return name.lower().replace(" ", "-")
    return "client"


def _get_domain_path_parts(
    conn: sqlite3.Connection, domain_id: int
) -> list[str]:
    """Return path segments for a domain, handling sub-domain nesting.

    For a top-level domain, returns [domain_code].
    For a sub-domain, returns [parent_code, subdomain_code].
    """
    row = conn.execute(
        "SELECT code, parent_domain_id FROM Domain WHERE id = ?",
        (domain_id,),
    ).fetchone()
    if not row:
        return []
    code, parent_id = row
    if parent_id is not None:
        parent_row = conn.execute(
            "SELECT code FROM Domain WHERE id = ?", (parent_id,)
        ).fetchone()
        if parent_row:
            return [parent_row[0], code]
    return [code]


def resolve_output_path(
    doc_type: DocumentType,
    conn: sqlite3.Connection,
    work_item_id: int,
    project_folder: str | Path,
    master_conn: sqlite3.Connection | None = None,
) -> Path | list[Path]:
    """Compute the output path for a document generation request.

    :param doc_type: The document type being generated.
    :param conn: Client database connection.
    :param work_item_id: The WorkItem.id driving generation.
    :param project_folder: Root of the client's project repository.
    :param master_conn: Master database connection (for client name).
    :returns: A Path for single-file types, or list[Path] for YAML (one per entity).
    """
    root = Path(project_folder)
    client = get_client_short_name(master_conn)

    wi = conn.execute(
        "SELECT item_type, domain_id, entity_id, process_id FROM WorkItem WHERE id = ?",
        (work_item_id,),
    ).fetchone()
    if not wi:
        raise ValueError(f"Work item {work_item_id} not found")

    _item_type, domain_id, entity_id, process_id = wi

    if doc_type == DocumentType.MASTER_PRD:
        return root / "PRDs" / f"{client}-Master-PRD.docx"

    if doc_type == DocumentType.ENTITY_INVENTORY:
        return root / "PRDs" / f"{client}-Entity-Inventory.docx"

    if doc_type == DocumentType.ENTITY_PRD:
        if entity_id is None:
            raise ValueError(f"Work item {work_item_id} has no entity_id for Entity PRD")
        row = conn.execute(
            "SELECT name FROM Entity WHERE id = ?", (entity_id,)
        ).fetchone()
        entity_name = row[0] if row else "Unknown"
        return root / "PRDs" / "entities" / f"{entity_name}-Entity-PRD.docx"

    if doc_type == DocumentType.DOMAIN_OVERVIEW:
        if domain_id is None:
            raise ValueError(f"Work item {work_item_id} has no domain_id for Domain Overview")
        row = conn.execute(
            "SELECT name FROM Domain WHERE id = ?", (domain_id,)
        ).fetchone()
        domain_name = row[0] if row else "Unknown"
        parts = _get_domain_path_parts(conn, domain_id)
        return root / "PRDs" / Path(*parts) / f"{client}-Domain-Overview-{domain_name}.docx"

    if doc_type == DocumentType.PROCESS_DOCUMENT:
        if process_id is None:
            raise ValueError(f"Work item {work_item_id} has no process_id for Process Document")
        row = conn.execute(
            "SELECT code, domain_id FROM Process WHERE id = ?", (process_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Process {process_id} not found")
        process_code, proc_domain_id = row
        parts = _get_domain_path_parts(conn, proc_domain_id)
        return root / "PRDs" / Path(*parts) / f"{process_code}.docx"

    if doc_type == DocumentType.DOMAIN_PRD:
        if domain_id is None:
            raise ValueError(f"Work item {work_item_id} has no domain_id for Domain PRD")
        row = conn.execute(
            "SELECT name FROM Domain WHERE id = ?", (domain_id,)
        ).fetchone()
        domain_name = row[0] if row else "Unknown"
        parts = _get_domain_path_parts(conn, domain_id)
        return root / "PRDs" / Path(*parts) / f"{client}-Domain-PRD-{domain_name}.docx"

    if doc_type == DocumentType.YAML_PROGRAM_FILES:
        if domain_id is None:
            raise ValueError(f"Work item {work_item_id} has no domain_id for YAML generation")
        # Get all entities in scope for this domain
        entity_rows = conn.execute(
            "SELECT DISTINCT e.id, e.name FROM Entity e "
            "LEFT JOIN ProcessEntity pe ON pe.entity_id = e.id "
            "LEFT JOIN Process p ON pe.process_id = p.id "
            "WHERE e.primary_domain_id = ? OR p.domain_id = ?",
            (domain_id, domain_id),
        ).fetchall()
        if not entity_rows:
            return []
        return [root / "programs" / f"{name}.yaml" for _, name in entity_rows]

    if doc_type == DocumentType.CRM_EVALUATION_REPORT:
        return root / "PRDs" / f"{client}-CRM-Evaluation-Report.docx"

    raise ValueError(f"Unknown document type: {doc_type}")
