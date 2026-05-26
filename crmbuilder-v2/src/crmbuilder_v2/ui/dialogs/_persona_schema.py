"""Field schema for the persona CRUD dialogs (v0.5+, PI-003).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.4 methodology-entity pattern and mirroring
``_entity_schema.py``. The fields are in ``persona.md`` §3.2 order;
the schema keys are the parent-prefixed ``persona_*`` names the REST
bodies expect.

The create dialog omits ``persona_identifier`` (server-assigned); the
edit dialog includes it as a read-only field. Per the v0.4 DEC-067
create-then-attach precedent (adopted unchanged by this v0.5+ build),
there is no domain-affiliation multi-select or entity-realization
single-select in either dialog — affiliations and realization attach
from the detail pane's ``ReferencesSection`` after the persona record
exists.

``persona_status`` carries a ``compute_options`` callback that
restricts the combo to the valid successors of the record's current
status per the transition map — which, for a ``candidate`` (the
create-dialog default), is all three values, and for ``confirmed`` /
``deferred`` is the narrowed set.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    PERSONA_STATUS_TRANSITIONS,
    PERSONA_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^PER-\d{3}$")

_ROLE_SUMMARY_PLACEHOLDER = (
    "Brief description of what this role does in the organization"
)


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`PERSONA_STATUS_TRANSITIONS`. ``candidate`` (the create-dialog
    starting point) yields all three values; ``confirmed`` and
    ``deferred`` yield the two-value narrowed set.
    """
    current = current or "candidate"
    if current not in PERSONA_STATUSES:
        return sorted(PERSONA_STATUSES)
    return sorted(
        {current} | set(PERSONA_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="persona_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="persona_name", label="Name", widget="line", required=True
    ),
    FieldSchema(
        key="persona_role_summary",
        label="Role summary",
        widget="text",
        required=True,
        placeholder=_ROLE_SUMMARY_PLACEHOLDER,
    ),
    FieldSchema(
        key="persona_responsibilities",
        label="Responsibilities",
        widget="text",
    ),
    FieldSchema(
        key="persona_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="persona_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=PERSONA_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("persona_status")
        ),
    ),
]


def persona_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the persona field schema.

    ``include_identifier`` adds the read-only ``persona_identifier``
    field at the top — used by the edit dialog; the create dialog
    omits it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
