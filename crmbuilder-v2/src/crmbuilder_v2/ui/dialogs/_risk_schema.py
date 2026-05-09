"""Field schema for the risks CRUD dialogs.

v0.2 slice B introduces the Risks write surface as the first user of
the schema-driven ``EntityCrudDialog`` base. The seven fields map
directly onto the access-layer Risk model: identifier, title,
description, probability, impact, response_plan, status.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    RISK_IMPACTS,
    RISK_PROBABILITIES,
    RISK_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^RSK-\d{3,}$")
IDENTIFIER_HINT = "Identifier must be in the format RSK-NNN (e.g., RSK-001)."


_RISK_FIELDS_TEMPLATE: list[FieldSchema] = [
    FieldSchema(
        key="identifier",
        label="Identifier",
        widget="line",
        required=True,
        placeholder="RSK-NNN",
        regex=IDENTIFIER_RE,
        regex_hint=IDENTIFIER_HINT,
        read_only_on_edit=True,
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(key="description", label="Description", widget="text"),
    FieldSchema(
        key="probability",
        label="Probability",
        widget="combo",
        required=True,
        vocab=RISK_PROBABILITIES,
    ),
    FieldSchema(
        key="impact",
        label="Impact",
        widget="combo",
        required=True,
        vocab=RISK_IMPACTS,
    ),
    FieldSchema(
        key="status",
        label="Status",
        widget="combo",
        required=True,
        vocab=RISK_STATUSES,
        default="Open",
    ),
    FieldSchema(key="response_plan", label="Response Plan", widget="text"),
]


def risk_fields() -> list[FieldSchema]:
    """Return a fresh copy of the risk field schema."""
    return deepcopy(_RISK_FIELDS_TEMPLATE)
