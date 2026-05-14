"""Field schema for the domain CRUD dialogs (UI v0.4 slice B).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern. The fields are in
``domain.md`` section 3.2 order; the schema keys are the parent-prefixed
``domain_*`` names the REST bodies expect.

The create dialog omits ``domain_identifier`` (server-assigned); the
edit dialog includes it as a read-only field. ``domain_status`` carries
a ``compute_options`` callback that restricts the combo to the valid
successors of the record's current status per the transition map —
which, for a ``candidate`` (the create-dialog default), is all three
values, and for ``confirmed`` / ``deferred`` is the narrowed set.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    DOMAIN_STATUS_TRANSITIONS,
    DOMAIN_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^DOM-\d{3}$")


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`DOMAIN_STATUS_TRANSITIONS`. ``candidate`` (the create-dialog
    starting point) yields all three values; ``confirmed`` and
    ``deferred`` yield the two-value narrowed set.
    """
    current = current or "candidate"
    if current not in DOMAIN_STATUSES:
        return sorted(DOMAIN_STATUSES)
    return sorted(
        {current} | set(DOMAIN_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="domain_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="domain_name", label="Name", widget="line", required=True
    ),
    FieldSchema(
        key="domain_purpose",
        label="Purpose",
        widget="line",
        required=True,
        placeholder="One sentence",
    ),
    FieldSchema(
        key="domain_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="Brief paragraph",
    ),
    FieldSchema(
        key="domain_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="domain_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=DOMAIN_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("domain_status")
        ),
    ),
]


def domain_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the domain field schema.

    ``include_identifier`` adds the read-only ``domain_identifier``
    field at the top — used by the edit dialog; the create dialog omits
    it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
