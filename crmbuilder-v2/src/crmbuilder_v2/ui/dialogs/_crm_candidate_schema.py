"""Field schema for the crm_candidate CRUD dialogs (UI v0.4 slice E).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern. The fields are in
``crm_candidate.md`` section 3.2 order; the schema keys are the
parent-prefixed ``crm_candidate_*`` names the REST bodies expect.

The create dialog omits ``crm_candidate_identifier`` (server-assigned);
the edit dialog includes it as a read-only field.
``crm_candidate_status`` carries a ``compute_options`` callback that
restricts the combo to the valid successors of the record's current
status per the transition map — which, for ``active`` (the
create-dialog default), is all four values, and for the three
terminal states (``selected``, ``declined``, ``removed``) collapses to
the single current value (effectively read-only post-transition).
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    CRM_CANDIDATE_STATUS_TRANSITIONS,
    CRM_CANDIDATE_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^CRM-\d{3}$")


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`CRM_CANDIDATE_STATUS_TRANSITIONS`. ``active`` (the
    create-dialog starting point) yields all four values; the three
    terminal states (``selected``, ``declined``, ``removed``) have
    empty successor sets, so the combo shows only the current value
    (effectively read-only post-transition).
    """
    current = current or "active"
    if current not in CRM_CANDIDATE_STATUSES:
        return sorted(CRM_CANDIDATE_STATUSES)
    return sorted(
        {current} | set(CRM_CANDIDATE_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="crm_candidate_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="crm_candidate_name",
        label="Name",
        widget="line",
        required=True,
        placeholder="CRM product (e.g., EspoCRM, SuiteCRM)",
    ),
    FieldSchema(
        key="crm_candidate_fit_reason",
        label="Fit reason",
        widget="text",
        required=True,
        placeholder=(
            "What about this CRM made it worth considering for the engagement"
        ),
    ),
    FieldSchema(
        key="crm_candidate_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="crm_candidate_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=CRM_CANDIDATE_STATUSES,
        default="active",
        compute_options=lambda state: status_choices(
            state.get("crm_candidate_status")
        ),
    ),
]


def crm_candidate_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the crm_candidate field schema.

    ``include_identifier`` adds the read-only ``crm_candidate_identifier``
    field at the top — used by the edit dialog; the create dialog
    omits it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
