"""Field schema for the planning items CRUD dialogs.

v0.2 slice C introduces the Planning Items write surface as the third
user of the schema-driven ``EntityCrudDialog`` base. Six fields map
directly onto the access-layer PlanningItem model: identifier, title,
description, item_type, status, resolution_reference.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    EXECUTION_MODES,
    PLANNING_ITEM_STATUSES,
    PLANNING_ITEM_TYPES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^PI-\d{3,}$")
IDENTIFIER_HINT = "Identifier must be in the format PI-NNN (e.g., PI-001)."


_PLANNING_ITEM_FIELDS_TEMPLATE: list[FieldSchema] = [
    FieldSchema(
        key="identifier",
        label="Identifier",
        widget="line",
        required=True,
        placeholder="PI-NNN",
        regex=IDENTIFIER_RE,
        regex_hint=IDENTIFIER_HINT,
        read_only_on_edit=True,
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(key="description", label="Description", widget="text"),
    FieldSchema(
        key="executive_summary",
        label="Executive Summary",
        widget="text",
        # Required since PI-075 (migration 0023): the column is NOT NULL.
        required=True,
        min_length=200,
        max_length=800,
        placeholder=(
            "200-800 character audience-facing summary for non-technical "
            "reviewers."
        ),
    ),
    FieldSchema(
        key="item_type",
        label="Type",
        widget="combo",
        required=True,
        vocab=PLANNING_ITEM_TYPES,
    ),
    FieldSchema(
        key="status",
        label="Status",
        widget="combo",
        required=True,
        vocab=PLANNING_ITEM_STATUSES,
        default="Draft",
    ),
    # PI-183: the ADO execution_mode gate. A PI's own mode; its effective mode
    # is the more restrictive of this and its Project's. dispatch_approved is
    # NOT here — it is set only via the Approve Dispatch action (REQ-155).
    FieldSchema(
        key="execution_mode",
        label="Execution Mode",
        widget="combo",
        required=True,
        vocab=EXECUTION_MODES,
        default="ado",
    ),
    FieldSchema(
        key="resolution_reference",
        label="Resolution Reference",
        widget="line",
        omit_when_empty_in_create=True,
    ),
]


def planning_item_fields() -> list[FieldSchema]:
    """Return a fresh copy of the planning-item field schema."""
    return deepcopy(_PLANNING_ITEM_FIELDS_TEMPLATE)
