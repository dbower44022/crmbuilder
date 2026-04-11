"""Document Generator for CRM Builder Automation.

Implements L2 PRD Section 13 — reads committed database records and produces
formatted deliverables (Word documents and YAML program files). The generator
runs on implementor demand and never modifies work items.

Eight document types are supported, each mapped to a work item type:

    Document Type           Work Item Type
    ─────────────────────   ──────────────────────
    master_prd              master_prd
    entity_inventory        business_object_discovery
    entity_prd              entity_prd
    domain_overview         domain_overview
    process_document        process_definition
    domain_prd              domain_reconciliation
    yaml_program_files      yaml_generation
    crm_evaluation_report   crm_selection
"""

from __future__ import annotations

import enum


class DocumentType(enum.Enum):
    """The eight document types supported by the Document Generator."""

    MASTER_PRD = "master_prd"
    ENTITY_INVENTORY = "entity_inventory"
    ENTITY_PRD = "entity_prd"
    DOMAIN_OVERVIEW = "domain_overview"
    PROCESS_DOCUMENT = "process_document"
    DOMAIN_PRD = "domain_prd"
    YAML_PROGRAM_FILES = "yaml_program_files"
    CRM_EVALUATION_REPORT = "crm_evaluation_report"


# Maps each document type to the work item type that produces it.
DOCUMENT_TYPE_TO_WORK_ITEM_TYPE: dict[DocumentType, str] = {
    DocumentType.MASTER_PRD: "master_prd",
    DocumentType.ENTITY_INVENTORY: "business_object_discovery",
    DocumentType.ENTITY_PRD: "entity_prd",
    DocumentType.DOMAIN_OVERVIEW: "domain_overview",
    DocumentType.PROCESS_DOCUMENT: "process_definition",
    DocumentType.DOMAIN_PRD: "domain_reconciliation",
    DocumentType.YAML_PROGRAM_FILES: "yaml_generation",
    DocumentType.CRM_EVALUATION_REPORT: "crm_selection",
}

# Reverse mapping: work item type → document type.
WORK_ITEM_TYPE_TO_DOCUMENT_TYPE: dict[str, DocumentType] = {
    v: k for k, v in DOCUMENT_TYPE_TO_WORK_ITEM_TYPE.items()
}
