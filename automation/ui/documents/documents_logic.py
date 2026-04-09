"""Pure-Python logic for the Documents view (Section 14.7).

Inventory assembly, staleness grouping, sort order, and document status
derivation. No PySide6 imports.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from automation.docgen import WORK_ITEM_TYPE_TO_DOCUMENT_TYPE, DocumentType
from automation.docgen.generation_log import GenerationLogEntry
from automation.docgen.staleness import StaleDocument
from automation.ui.common.readable_first import format_work_item_name

# Eight document types grouped per Section 13.2
DOCUMENT_TYPE_GROUPS: list[tuple[str, list[DocumentType]]] = [
    ("Core Documents", [
        DocumentType.MASTER_PRD,
        DocumentType.ENTITY_INVENTORY,
    ]),
    ("Entity Documents", [
        DocumentType.ENTITY_PRD,
    ]),
    ("Domain Documents", [
        DocumentType.DOMAIN_OVERVIEW,
        DocumentType.PROCESS_DOCUMENT,
        DocumentType.DOMAIN_PRD,
    ]),
    ("Delivery Documents", [
        DocumentType.YAML_PROGRAM_FILES,
        DocumentType.CRM_EVALUATION_REPORT,
    ]),
]

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "master_prd": "Master PRD",
    "entity_inventory": "Entity Inventory",
    "entity_prd": "Entity PRD",
    "domain_overview": "Domain Overview",
    "process_document": "Process Document",
    "domain_prd": "Domain PRD",
    "yaml_program_files": "YAML Program Files",
    "crm_evaluation_report": "CRM Evaluation Report",
}


class DocumentStatus:
    """Constants for document status."""

    NOT_GENERATED = "not_generated"
    CURRENT = "current"
    STALE = "stale"
    DRAFT_ONLY = "draft_only"


# Sort priority: stale first, then current, draft only, not generated
_STATUS_SORT_ORDER = {
    DocumentStatus.STALE: 0,
    DocumentStatus.CURRENT: 1,
    DocumentStatus.DRAFT_ONLY: 2,
    DocumentStatus.NOT_GENERATED: 3,
}


@dataclasses.dataclass
class DocumentEntry:
    """A single document in the inventory.

    Combines work item data, generation log, and staleness info.
    """

    work_item_id: int
    item_type: str
    document_type: str
    document_name: str
    work_item_status: str
    document_status: str
    last_generated_at: str | None
    file_path: str | None
    git_commit_hash: str | None
    # Staleness detail
    change_count: int
    change_summary: str
    # Scoping
    domain_name: str | None
    entity_name: str | None
    process_name: str | None


def load_document_inventory(
    conn: sqlite3.Connection,
    stale_docs: list[StaleDocument],
    scoped_work_item_id: int | None = None,
) -> list[DocumentEntry]:
    """Build the document inventory from work items and staleness data.

    :param conn: Client database connection.
    :param stale_docs: Stale document records from docgen.get_stale_documents().
    :param scoped_work_item_id: If provided, return only the entry for this work item.
    :returns: Sorted list of DocumentEntry.
    """
    stale_map: dict[int, StaleDocument] = {s.work_item_id: s for s in stale_docs}

    # Query work items that produce documents (exclude stakeholder_review, crm_deployment, etc.)
    generatable_types = tuple(WORK_ITEM_TYPE_TO_DOCUMENT_TYPE.keys())
    placeholders = ",".join("?" for _ in generatable_types)

    if scoped_work_item_id is not None:
        query = (
            "SELECT wi.id, wi.item_type, wi.status, "
            "  wi.domain_id, wi.entity_id, wi.process_id, "
            "  d.name AS domain_name, e.name AS entity_name, p.name AS process_name "
            "FROM WorkItem wi "
            "LEFT JOIN Domain d ON wi.domain_id = d.id "
            "LEFT JOIN Entity e ON wi.entity_id = e.id "
            "LEFT JOIN Process p ON wi.process_id = p.id "
            f"WHERE wi.item_type IN ({placeholders}) AND wi.id = ?"
        )
        rows = conn.execute(query, [*generatable_types, scoped_work_item_id]).fetchall()
    else:
        query = (
            "SELECT wi.id, wi.item_type, wi.status, "
            "  wi.domain_id, wi.entity_id, wi.process_id, "
            "  d.name AS domain_name, e.name AS entity_name, p.name AS process_name "
            "FROM WorkItem wi "
            "LEFT JOIN Domain d ON wi.domain_id = d.id "
            "LEFT JOIN Entity e ON wi.entity_id = e.id "
            "LEFT JOIN Process p ON wi.process_id = p.id "
            f"WHERE wi.item_type IN ({placeholders}) "
            "ORDER BY wi.id"
        )
        rows = conn.execute(query, generatable_types).fetchall()

    entries: list[DocumentEntry] = []
    for row in rows:
        wi_id, item_type, status = row[0], row[1], row[2]
        domain_name, entity_name, process_name = row[6], row[7], row[8]

        doc_type_enum = WORK_ITEM_TYPE_TO_DOCUMENT_TYPE.get(item_type)
        if not doc_type_enum:
            continue
        doc_type = doc_type_enum.value

        # Get latest generation log
        gen_log = _get_latest_gen_log(conn, wi_id)

        # Determine document status
        stale_info = stale_map.get(wi_id)
        doc_status = _compute_status(gen_log, stale_info)

        doc_name = format_work_item_name(item_type, domain_name, entity_name, process_name)

        entries.append(DocumentEntry(
            work_item_id=wi_id,
            item_type=item_type,
            document_type=doc_type,
            document_name=doc_name,
            work_item_status=status,
            document_status=doc_status,
            last_generated_at=gen_log.generated_at if gen_log else None,
            file_path=gen_log.file_path if gen_log else None,
            git_commit_hash=gen_log.git_commit_hash if gen_log else None,
            change_count=stale_info.change_count if stale_info else 0,
            change_summary=stale_info.change_summary if stale_info else "",
            domain_name=domain_name,
            entity_name=entity_name,
            process_name=process_name,
        ))

    return sort_entries(entries)


def sort_entries(entries: list[DocumentEntry]) -> list[DocumentEntry]:
    """Sort document entries: stale first, then current, draft only, not generated.

    :param entries: Unsorted document entries.
    :returns: Sorted list.
    """
    return sorted(entries, key=lambda e: _STATUS_SORT_ORDER.get(e.document_status, 99))


def filter_stale(entries: list[DocumentEntry]) -> list[DocumentEntry]:
    """Return only stale document entries.

    :param entries: Full document entries list.
    :returns: Entries with document_status == STALE.
    """
    return [e for e in entries if e.document_status == DocumentStatus.STALE]


def _get_latest_gen_log(
    conn: sqlite3.Connection, work_item_id: int
) -> GenerationLogEntry | None:
    """Get the latest final generation log entry for a work item."""
    row = conn.execute(
        "SELECT id, work_item_id, document_type, file_path, generated_at, "
        "generation_mode, git_commit_hash "
        "FROM GenerationLog "
        "WHERE work_item_id = ? AND generation_mode = 'final' "
        "ORDER BY generated_at DESC, id DESC LIMIT 1",
        (work_item_id,),
    ).fetchone()
    if not row:
        # Check for draft-only
        row = conn.execute(
            "SELECT id, work_item_id, document_type, file_path, generated_at, "
            "generation_mode, git_commit_hash "
            "FROM GenerationLog "
            "WHERE work_item_id = ? AND generation_mode = 'draft' "
            "ORDER BY generated_at DESC, id DESC LIMIT 1",
            (work_item_id,),
        ).fetchone()
    if not row:
        return None
    return GenerationLogEntry(
        id=row[0], work_item_id=row[1], document_type=row[2],
        file_path=row[3], generated_at=row[4], generation_mode=row[5],
        git_commit_hash=row[6],
    )


def _compute_status(
    gen_log: GenerationLogEntry | None,
    stale_info: StaleDocument | None,
) -> str:
    """Determine document status from generation log and staleness info."""
    if gen_log is None:
        return DocumentStatus.NOT_GENERATED
    if stale_info is not None:
        return DocumentStatus.STALE
    if gen_log.generation_mode == "draft":
        return DocumentStatus.DRAFT_ONLY
    return DocumentStatus.CURRENT
