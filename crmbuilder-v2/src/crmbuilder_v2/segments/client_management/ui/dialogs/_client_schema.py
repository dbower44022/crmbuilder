"""Field schema for the client dialogs (PI-512 / REQ-589).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``. The keys
are the parent-prefixed ``client_*`` names the REST bodies expect. The create
dialog omits ``client_identifier`` (server-assigned); the edit dialog includes
it read-only. The engagements a client holds are assigned from the Clients
panel's detail pane, not inlined here.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.segments.client_management.vocab import CLIENT_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^CLI-\d{3,}$")

_IDENTIFIER_FIELD = FieldSchema(
    key="client_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="client_name", label="Name", widget="line", required=True),
    FieldSchema(key="client_notes", label="Notes", widget="text"),
    FieldSchema(
        key="client_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=CLIENT_STATUSES,
        default="active",
    ),
]


def client_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the client field schema."""
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
