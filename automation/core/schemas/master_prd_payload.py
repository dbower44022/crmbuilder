"""Concrete JSON schema definitions for the ``master_prd`` payload.

This module is consumed by both the Prompt Generator (rendered into the
prompt-optimized guide as the output specification the AI must follow)
and the Import Processor (validated in Section 11.2 Layer 3).

The Python TypedDicts mirror the JSON Schema in
``master_prd_payload.schema.json`` — both must stay in sync.

Field names align with the existing mapper in
``automation.importer.mappers.master_prd`` which is the source of truth
for what the database expects.  Fields present in the payload but not
consumed by the mapper (e.g. ``responsibilities``, ``crm_capabilities``,
``business_value``, ``key_capabilities``, ``cross_domain_services``,
``system_scope``, ``interview_transcript``) are retained in
``AISession.structured_output`` for reference and downstream use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# TypedDict definitions
# ---------------------------------------------------------------------------


class PersonaPayload(TypedDict):
    """A single persona entry in the master_prd payload."""

    name: str
    code: str
    description: str
    responsibilities: list[str]
    crm_capabilities: list[str]


class SubDomainPayload(TypedDict, total=False):
    """A sub-domain nested inside a domain entry.

    ``is_service`` and ``identifier`` are optional.
    """

    name: str
    code: str
    identifier: str
    description: str
    sort_order: int
    is_service: bool


class DomainPayload(TypedDict, total=False):
    """A top-level domain entry.

    ``sub_domains`` and ``identifier`` are optional.
    """

    name: str
    code: str
    identifier: str
    description: str
    sort_order: int
    sub_domains: list[SubDomainPayload]


class ProcessPayload(TypedDict):
    """A single process entry in the master_prd payload."""

    name: str
    code: str
    description: str
    sort_order: int
    tier: str  # "core" | "important" | "enhancement"
    business_value: str
    key_capabilities: list[str]
    domain_code: str


class CrossDomainServicePayload(TypedDict):
    """A cross-domain service entry."""

    name: str
    code: str
    description: str
    capabilities: list[str]
    consuming_domains: list[str]
    owned_entities: list[str]


class SystemScopePayload(TypedDict):
    """System scope boundaries."""

    in_scope: list[str]
    out_of_scope: list[str]
    integrations: list[str]


class MasterPrdPayload(TypedDict):
    """Top-level payload for the ``master_prd`` work item type."""

    organization_overview: str
    personas: list[PersonaPayload]
    domains: list[DomainPayload]
    processes: list[ProcessPayload]
    cross_domain_services: list[CrossDomainServicePayload]
    system_scope: SystemScopePayload
    interview_transcript: str


# ---------------------------------------------------------------------------
# JSON Schema loading
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).with_name("master_prd_payload.schema.json")


def load_json_schema() -> dict:
    """Load and return the master_prd payload JSON Schema as a dict."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
