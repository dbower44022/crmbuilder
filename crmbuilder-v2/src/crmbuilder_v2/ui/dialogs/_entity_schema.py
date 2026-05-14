"""Field schema for the entity CRUD dialogs (UI v0.4 slice C).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern and mirroring
``_domain_schema.py``. The fields are in ``entity.md`` section 3.2
order; the schema keys are the parent-prefixed ``entity_*`` names the
REST bodies expect.

The create dialog omits ``entity_identifier`` (server-assigned); the
edit dialog includes it as a read-only field. Per DEC-067's
create-then-attach flow there is no domain-affiliation multi-select in
either dialog — affiliations attach from the detail pane's
``ReferencesSection`` after the entity record exists.

``entity_status`` carries a ``compute_options`` callback that restricts
the combo to the valid successors of the record's current status per
the transition map — which, for a ``candidate`` (the create-dialog
default), is all three values, and for ``confirmed`` / ``deferred`` is
the narrowed set.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    ENTITY_STATUS_TRANSITIONS,
    ENTITY_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^ENT-\d{3}$")

_DESCRIPTION_PLACEHOLDER = (
    "Brief description of what kind of thing this entity represents"
)


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`ENTITY_STATUS_TRANSITIONS`. ``candidate`` (the create-dialog
    starting point) yields all three values; ``confirmed`` and
    ``deferred`` yield the two-value narrowed set.
    """
    current = current or "candidate"
    if current not in ENTITY_STATUSES:
        return sorted(ENTITY_STATUSES)
    return sorted(
        {current} | set(ENTITY_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="entity_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="entity_name", label="Name", widget="line", required=True
    ),
    FieldSchema(
        key="entity_description",
        label="Description",
        widget="text",
        required=True,
        placeholder=_DESCRIPTION_PLACEHOLDER,
    ),
    FieldSchema(
        key="entity_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="entity_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=ENTITY_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("entity_status")
        ),
    ),
]


def entity_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the entity field schema.

    ``include_identifier`` adds the read-only ``entity_identifier``
    field at the top — used by the edit dialog; the create dialog omits
    it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
