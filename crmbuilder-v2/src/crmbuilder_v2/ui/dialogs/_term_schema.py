"""Field schema for the term (glossary) CRUD dialogs (PI-061).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``, following
the v0.4 methodology-entity pattern. The schema keys are the plain field names
the ``/terms`` REST body expects (no parent prefix). The create dialog omits
``identifier`` (server-assigned); the edit dialog includes it read-only.

``scope`` and ``version`` are not exposed on the form: new terms default to
``system`` scope and version 1. Engagement overlays are an advanced case handled
through the API directly (DEC-404 keeps the desktop surface focused on the
glossary content).
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import TERM_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^TERM-\d{3}$")


_IDENTIFIER_FIELD = FieldSchema(
    key="identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="name",
        label="Name",
        widget="line",
        required=True,
        placeholder="The term itself, e.g. Engagement",
    ),
    FieldSchema(
        key="definition",
        label="Definition",
        widget="text",
        required=True,
        placeholder="One or two plain-English sentences.",
    ),
    FieldSchema(
        key="usage_scope",
        label="Scope (where it applies)",
        widget="text",
        placeholder="Which documents and contexts this term is used in.",
    ),
    FieldSchema(
        key="examples",
        label="Examples",
        widget="text",
        placeholder="One or two concrete uses to ground the abstraction.",
    ),
    FieldSchema(
        key="distinguishing_notes",
        label="Distinguishing notes",
        widget="text",
        placeholder="What this term is NOT to be confused with.",
    ),
    FieldSchema(
        key="related_terms",
        label="Related terms",
        widget="line",
        placeholder="Names of related terms, e.g. Client, Session",
    ),
    FieldSchema(
        key="status",
        label="Status",
        widget="combo",
        required=True,
        vocab=TERM_STATUSES,
        default="active",
    ),
]


def term_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the term field schema.

    ``include_identifier`` adds the read-only ``identifier`` field at the top —
    used by the edit dialog; the create dialog omits it (server-assigned).
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
