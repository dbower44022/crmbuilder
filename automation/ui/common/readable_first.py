"""Human-readable-first formatting helpers (Section 14.10.5).

Pure Python — no PySide6 imports. All UI display code should use
these helpers rather than building display strings directly.

The canonical format is: "Human Name (IDENTIFIER)"
"""

from __future__ import annotations


def format_readable(name: str, identifier: str | None = None) -> str:
    """Format a name with optional identifier in human-readable-first style.

    Returns "Name (IDENTIFIER)" if identifier is provided, otherwise just "Name".

    :param name: The human-readable name.
    :param identifier: Optional technical identifier or code.
    :returns: Formatted display string.
    """
    if identifier:
        return f"{name} ({identifier})"
    return name


def format_work_item_name(
    item_type: str,
    domain_name: str | None = None,
    entity_name: str | None = None,
    process_name: str | None = None,
) -> str:
    """Build a human-readable name for a work item.

    Combines the item_type label with scoping context (domain, entity, process).

    :param item_type: The work item's item_type value.
    :param domain_name: Optional domain name for context.
    :param entity_name: Optional entity name for context.
    :param process_name: Optional process name for context.
    :returns: Display string like "Entity PRD: Contact" or "Master PRD".
    """
    label = ITEM_TYPE_LABELS.get(item_type, item_type.replace("_", " ").title())

    # Add scoping context
    if process_name:
        return f"{label}: {process_name}"
    if entity_name:
        return f"{label}: {entity_name}"
    if domain_name:
        return f"{label}: {domain_name}"
    return label


ITEM_TYPE_LABELS: dict[str, str] = {
    "master_prd": "Master PRD",
    "business_object_discovery": "Business Object Discovery",
    "entity_prd": "Entity PRD",
    "domain_overview": "Domain Overview",
    "process_definition": "Process Definition",
    "domain_reconciliation": "Domain Reconciliation",
    "stakeholder_review": "Stakeholder Review",
    "yaml_generation": "YAML Generation",
    "crm_selection": "CRM Selection",
    "crm_deployment": "CRM Deployment",
    "crm_configuration": "CRM Configuration",
    "verification": "Verification",
}
