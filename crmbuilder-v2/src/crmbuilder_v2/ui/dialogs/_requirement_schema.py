"""Field schema for the requirement CRUD dialogs (PI-004 cohort, v0.5+).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern and mirroring
``_entity_schema.py``. The fields are in ``requirement.md`` §3.2 order;
the schema keys are the parent-prefixed ``requirement_*`` names the
REST bodies expect.

The create dialog omits ``requirement_identifier`` (server-assigned);
the edit dialog includes it as a read-only field. Per spec §3.6.4's
create-then-attach flow there are no reference multi-selects in either
dialog — references attach from the detail pane's
``ReferencesSection`` after the requirement record exists.

``requirement_status`` carries a ``compute_options`` callback that
restricts the combo to the valid successors of the record's current
status per the transition map.

``requirement_priority`` carries a ``compute_options`` callback that
returns the full MoSCoW vocabulary unconstrained — per spec §3.2.3
priority transitions are any-to-any with no rules.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    REQUIREMENT_PRIORITIES,
    REQUIREMENT_STATUS_TRANSITIONS,
    REQUIREMENT_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^REQ-\d{3}$")

_DESCRIPTION_PLACEHOLDER = "Plain-text description of the capability"
_ACCEPTANCE_PLACEHOLDER = (
    "What 'this is satisfied' looks like at a methodology level"
)


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`REQUIREMENT_STATUS_TRANSITIONS` — **except** ``confirmed``, which is
    never offered as a target (PI-228). A requirement is confirmed only by
    recording an approving decision (the ``requirement_approved_by_decision``
    edge → ``activate_by_decision``), which enforces the readability +
    provenance + topic gates; editing the status field straight to
    ``confirmed`` was the bypass we closed, so the dialog must not offer it.
    ``confirmed`` still appears when it is already the current value, so an
    already-confirmed requirement renders correctly.
    """
    current = current or "candidate"
    if current not in REQUIREMENT_STATUSES:
        choices = set(REQUIREMENT_STATUSES)
    else:
        choices = {current} | set(
            REQUIREMENT_STATUS_TRANSITIONS.get(current, frozenset())
        )
    if current != "confirmed":
        choices.discard("confirmed")
    return sorted(choices)


def priority_choices(current: str | None) -> list[str]:
    """Return the priority values selectable from ``current``.

    Per ``requirement.md`` §3.2.3 priority transitions are
    unconstrained — any value may freely follow any other. This helper
    always returns the full sorted MoSCoW vocabulary regardless of
    ``current``. The ``current`` parameter is accepted for signature
    consistency with :func:`status_choices`.
    """
    return sorted(REQUIREMENT_PRIORITIES)


_IDENTIFIER_FIELD = FieldSchema(
    key="requirement_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="requirement_name",
        label="Name",
        widget="line",
        required=True,
    ),
    FieldSchema(
        key="requirement_description",
        label="Description",
        widget="text",
        required=True,
        placeholder=_DESCRIPTION_PLACEHOLDER,
    ),
    FieldSchema(
        key="requirement_acceptance_summary",
        label="Acceptance summary",
        widget="text",
        required=True,
        placeholder=_ACCEPTANCE_PLACEHOLDER,
    ),
    FieldSchema(
        key="requirement_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="requirement_priority",
        label="Priority",
        widget="combo",
        required=True,
        vocab=REQUIREMENT_PRIORITIES,
        default="should",
        compute_options=lambda state: priority_choices(
            state.get("requirement_priority")
        ),
    ),
    FieldSchema(
        key="requirement_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=REQUIREMENT_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("requirement_status")
        ),
    ),
]


def requirement_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the requirement field schema.

    ``include_identifier`` adds the read-only ``requirement_identifier``
    field at the top — used by the edit dialog; the create dialog omits
    it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
