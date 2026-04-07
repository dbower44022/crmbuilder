# automation.importer.mappers — Payload-to-record mapping per work item type

from __future__ import annotations

import sqlite3

from automation.importer.mappers import (
    business_object_discovery,
    crm_deployment,
    crm_selection,
    domain_overview,
    domain_reconciliation,
    entity_prd,
    master_prd,
    process_definition,
    yaml_generation,
)
from automation.importer.proposed import ProposedBatch

_MAPPER_MODULES = {
    "master_prd": master_prd,
    "business_object_discovery": business_object_discovery,
    "entity_prd": entity_prd,
    "domain_overview": domain_overview,
    "process_definition": process_definition,
    "domain_reconciliation": domain_reconciliation,
    "yaml_generation": yaml_generation,
    "crm_selection": crm_selection,
    "crm_deployment": crm_deployment,
}


def get_mapper(work_item_type: str):
    """Return the mapper module for the given work item type.

    :raises ValueError: If no mapper exists for the type.
    """
    mod = _MAPPER_MODULES.get(work_item_type)
    if mod is None:
        raise ValueError(f"No mapper for work item type '{work_item_type}'")
    return mod


def map_payload(
    conn: sqlite3.Connection,
    work_item: dict,
    payload: dict,
    session_type: str,
    ai_session_id: int,
    master_conn: sqlite3.Connection | None = None,
    envelope: dict | None = None,
) -> ProposedBatch:
    """Route to the type-specific mapper."""
    mod = get_mapper(work_item["item_type"])
    return mod.map_payload(
        conn, work_item, payload, session_type, ai_session_id,
        master_conn=master_conn, envelope=envelope,
    )
