"""Data dictionary completeness validation for the Document Generator.

Implements L2 PRD Section 13.5 Step 3 — checks data dictionaries for
completeness and produces warnings (not errors). The validator never blocks
generation; it returns warnings that the implementor can review.
"""

from __future__ import annotations

import dataclasses

from automation.docgen import DocumentType


@dataclasses.dataclass
class ValidationWarning:
    """A non-blocking warning about missing or incomplete data."""

    document_type: DocumentType
    field: str
    message: str


def validate(
    doc_type: DocumentType,
    data_dict: dict,
    is_draft: bool = False,
) -> list[ValidationWarning]:
    """Check a data dictionary for completeness.

    :param doc_type: The document type being generated.
    :param data_dict: The assembled data dictionary from the query layer.
    :param is_draft: If True, produce informational notes instead of warnings.
    :returns: List of ValidationWarning objects (may be empty).
    """
    warnings: list[ValidationWarning] = []

    validator = _VALIDATORS.get(doc_type)
    if validator:
        warnings = validator(doc_type, data_dict)

    if is_draft:
        # Soften message prefix for drafts
        for w in warnings:
            w.message = f"[Draft note] {w.message}"

    return warnings


def _validate_master_prd(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("organization_overview"):
        warnings.append(ValidationWarning(
            doc_type, "organization_overview",
            "No organization overview text found in Client record.",
        ))
    if not data.get("personas"):
        warnings.append(ValidationWarning(
            doc_type, "personas", "No personas defined.",
        ))
    if not data.get("domains"):
        warnings.append(ValidationWarning(
            doc_type, "domains", "No domains defined.",
        ))
    return warnings


def _validate_entity_inventory(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("entities"):
        warnings.append(ValidationWarning(
            doc_type, "entities", "No entities defined.",
        ))
    return warnings


def _validate_entity_prd(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("entity"):
        warnings.append(ValidationWarning(
            doc_type, "entity", "Entity record not found.",
        ))
        return warnings
    if not data.get("fields"):
        warnings.append(ValidationWarning(
            doc_type, "fields", "No fields defined for this entity.",
        ))
    return warnings


def _validate_domain_overview(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("domain"):
        warnings.append(ValidationWarning(
            doc_type, "domain", "Domain record not found.",
        ))
        return warnings
    if not data.get("domain_overview_text"):
        warnings.append(ValidationWarning(
            doc_type, "domain_overview_text",
            "No domain overview text found.",
        ))
    if not data.get("processes"):
        warnings.append(ValidationWarning(
            doc_type, "processes", "No processes defined in this domain.",
        ))
    return warnings


def _validate_process_document(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("process"):
        warnings.append(ValidationWarning(
            doc_type, "process", "Process record not found.",
        ))
        return warnings
    if not data.get("steps"):
        warnings.append(ValidationWarning(
            doc_type, "steps", "No process steps defined.",
        ))
    if not data.get("requirements"):
        warnings.append(ValidationWarning(
            doc_type, "requirements", "No requirements defined.",
        ))
    return warnings


def _validate_domain_prd(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("domain"):
        warnings.append(ValidationWarning(
            doc_type, "domain", "Domain record not found.",
        ))
        return warnings
    if not data.get("reconciliation_text"):
        warnings.append(ValidationWarning(
            doc_type, "reconciliation_text",
            "No domain reconciliation text found.",
        ))
    if not data.get("processes"):
        warnings.append(ValidationWarning(
            doc_type, "processes",
            "No processes defined in this domain for reconciliation.",
        ))
    return warnings


def _validate_yaml_program(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("entities"):
        warnings.append(ValidationWarning(
            doc_type, "entities",
            "No entities found in scope for YAML generation.",
        ))
    return warnings


def _validate_crm_evaluation(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("crm_platform"):
        warnings.append(ValidationWarning(
            doc_type, "crm_platform",
            "No CRM platform specified in Client record.",
        ))
    return warnings


def _validate_user_process_guide(
    doc_type: DocumentType, data: dict
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not data.get("process"):
        warnings.append(ValidationWarning(
            doc_type, "process", "Process record not found.",
        ))
        return warnings
    if not data.get("steps"):
        warnings.append(ValidationWarning(
            doc_type, "steps", "No process steps defined.",
        ))
    if not data.get("yaml_by_entity"):
        warnings.append(ValidationWarning(
            doc_type, "yaml_by_entity",
            "No YAML program data merged in. Guide will lack CRM-specific "
            "labels — confirm the project folder is configured and the "
            "programs/ directory has YAML files.",
        ))
    for err in data.get("yaml_load_errors") or []:
        warnings.append(ValidationWarning(
            doc_type, "yaml_load_errors", err,
        ))
    return warnings


_VALIDATORS = {
    DocumentType.MASTER_PRD: _validate_master_prd,
    DocumentType.ENTITY_INVENTORY: _validate_entity_inventory,
    DocumentType.ENTITY_PRD: _validate_entity_prd,
    DocumentType.DOMAIN_OVERVIEW: _validate_domain_overview,
    DocumentType.PROCESS_DOCUMENT: _validate_process_document,
    DocumentType.DOMAIN_PRD: _validate_domain_prd,
    DocumentType.YAML_PROGRAM_FILES: _validate_yaml_program,
    DocumentType.CRM_EVALUATION_REPORT: _validate_crm_evaluation,
    DocumentType.USER_PROCESS_GUIDE: _validate_user_process_guide,
}
