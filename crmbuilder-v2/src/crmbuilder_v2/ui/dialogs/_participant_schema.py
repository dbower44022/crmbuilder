"""Field schema for the participant CRUD dialogs (REL-069 / PI-391).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``, mirroring
``_persona_schema.py``. The keys are the parent-prefixed ``participant_*`` names
the REST bodies expect. The create dialog omits ``participant_identifier``
(server-assigned); the edit dialog includes it read-only. A participant's persona
backing (``persona_backed_by_participant``) is attached from the detail pane's
references affordance, not inlined here.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import PARTICIPANT_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^PTC-\d{3}$")

_ROLE_KIND_PLACEHOLDER = (
    "The role this participant plays, e.g. Business Subject-Matter Expert"
)


_IDENTIFIER_FIELD = FieldSchema(
    key="participant_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="participant_name", label="Name", widget="line", required=True
    ),
    FieldSchema(
        key="participant_role_kind",
        label="Role",
        widget="line",
        required=True,
        placeholder=_ROLE_KIND_PLACEHOLDER,
    ),
    FieldSchema(
        key="participant_affiliation",
        label="Affiliation",
        widget="line",
        placeholder="Organization / company",
    ),
    FieldSchema(
        key="participant_contact",
        label="Contact",
        widget="line",
        placeholder="Email or phone",
    ),
    FieldSchema(
        key="participant_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="participant_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=PARTICIPANT_STATUSES,
        default="active",
    ),
]


def participant_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the participant field schema.

    ``include_identifier`` adds the read-only ``participant_identifier`` field at
    the top — used by the edit dialog; the create dialog omits it (server-assigned).
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
