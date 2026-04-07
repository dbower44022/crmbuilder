"""Phase mapping for CRM Builder Automation work items.

Maps each work item's item_type (and, for three service-aware types, the
related Domain's is_service flag) to a phase number. Phase is never stored
on a WorkItem row — it is always calculated at query time.

Phase mapping defined in L2 PRD Section 14.2.3.
"""

# Static mapping for item_types whose phase does not depend on is_service.
ITEM_TYPE_TO_PHASE: dict[str, int] = {
    "master_prd": 1,
    "business_object_discovery": 2,
    "entity_prd": 2,
    "stakeholder_review": 7,
    "yaml_generation": 8,
    "crm_selection": 9,
    "crm_deployment": 10,
    "crm_configuration": 11,
    "verification": 12,
}

# Item types whose phase depends on the related Domain's is_service flag.
# When is_service is True, all three map to Phase 4 (Cross-Domain Service
# Definition). When False, they map to Phases 3, 5, 6 respectively.
SERVICE_AWARE_ITEM_TYPES: set[str] = {
    "domain_overview",
    "process_definition",
    "domain_reconciliation",
}

_SERVICE_AWARE_NON_SERVICE_PHASE: dict[str, int] = {
    "domain_overview": 3,
    "process_definition": 5,
    "domain_reconciliation": 6,
}

PHASE_NAMES: dict[int, str] = {
    1: "Master PRD",
    2: "Entity Definition",
    3: "Domain Overview",
    4: "Cross-Domain Service Definition",
    5: "Process Definition",
    6: "Domain Reconciliation",
    7: "Stakeholder Review",
    8: "YAML Generation",
    9: "CRM Selection",
    10: "CRM Deployment",
    11: "CRM Configuration",
    12: "Verification",
}


def get_phase(item_type: str, is_service: bool = False) -> int:
    """Return the phase number for a work item.

    For domain_overview, process_definition, and domain_reconciliation,
    the is_service flag determines the phase: True maps to Phase 4,
    False maps to Phases 3, 5, 6 respectively.

    For all other item_types, is_service is ignored.

    :param item_type: The work item's item_type value.
    :param is_service: Whether the related Domain has is_service = True.
    :returns: The phase number (1–12).
    :raises ValueError: If item_type is not recognized.
    """
    if item_type in SERVICE_AWARE_ITEM_TYPES:
        if is_service:
            return 4
        return _SERVICE_AWARE_NON_SERVICE_PHASE[item_type]
    if item_type in ITEM_TYPE_TO_PHASE:
        return ITEM_TYPE_TO_PHASE[item_type]
    raise ValueError(f"Unknown item_type: {item_type}")


def get_phase_name(phase_number: int) -> str:
    """Return the human-readable name for a phase number.

    :param phase_number: The phase number (1–12).
    :returns: The phase name string.
    :raises ValueError: If phase_number is not recognized.
    """
    if phase_number not in PHASE_NAMES:
        raise ValueError(f"Unknown phase number: {phase_number}")
    return PHASE_NAMES[phase_number]
