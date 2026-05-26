"""Field schema for the field CRUD dialogs (v0.5+, PI-004 first slice).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.4 methodology-entity pattern and mirroring
``_entity_schema.py`` and ``_persona_schema.py``. The fields are in
``field.md`` §3.2 order; the schema keys are the parent-prefixed
``field_*`` names the REST bodies expect.

The create dialog omits ``field_identifier`` (server-assigned) and
includes a parent-entity picker
(``field_belongs_to_entity_identifier``) per spec §3.5.4. The edit
dialog includes ``field_identifier`` as a read-only field and does
NOT include the parent-entity picker — re-parenting requires
explicit edge management per spec §3.6.5 / PI-053 (deferred to a
follow-on slice).

``field_status`` carries a ``compute_options`` callback that
restricts the combo to the valid successors of the record's current
status per the transition map.

``field_type`` is a combo over the 11-value v0.5 vocabulary
(``FIELD_TYPES``) with no transition logic (type can change freely;
it is not a lifecycle field).

``field_required`` is modelled as a combo over ``("false", "true")``
because the EntityCrudDialog base supports only string-valued
widgets. The ``field_crud.FieldCreateDialog`` / ``FieldEditDialog``
subclasses override the request-body construction to coerce these
strings to Python booleans before submitting.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    FIELD_STATUS_TRANSITIONS,
    FIELD_STATUSES,
    FIELD_TYPES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^FLD-\d{3}$")
PARENT_ENTITY_IDENTIFIER_RE = re.compile(r"^ENT-\d{3}$")

_DESCRIPTION_PLACEHOLDER = (
    "Brief description of what this field conceptually represents"
)

_REQUIRED_CHOICES = ("false", "true")


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`FIELD_STATUS_TRANSITIONS`. ``candidate`` (the create-dialog
    starting point) yields all three values; ``confirmed`` and
    ``deferred`` yield the two-value narrowed set.
    """
    current = current or "candidate"
    if current not in FIELD_STATUSES:
        return sorted(FIELD_STATUSES)
    return sorted(
        {current} | set(FIELD_STATUS_TRANSITIONS.get(current, frozenset()))
    )


def type_choices() -> list[str]:
    """Return the sorted list of valid ``field_type`` values."""
    return sorted(FIELD_TYPES)


def _live_entity_choices(client) -> list[tuple[str, str]]:
    """Return ``(identifier, name)`` tuples for live entities.

    Used by the create dialog's parent-entity picker.
    """
    try:
        entities = client.list_entities(include_deleted=False)
    except Exception:  # noqa: BLE001 — picker is a UI affordance
        return []
    return [
        (
            e.get("entity_identifier") or "",
            e.get("entity_name") or "",
        )
        for e in entities
        if e.get("entity_identifier")
    ]


_IDENTIFIER_FIELD = FieldSchema(
    key="field_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)


_PARENT_ENTITY_FIELD = FieldSchema(
    key="field_belongs_to_entity_identifier",
    label="Parent entity",
    widget="combo",
    required=True,
    regex=PARENT_ENTITY_IDENTIFIER_RE,
    regex_hint="must be an ENT-NNN entity identifier",
)


_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="field_name", label="Name", widget="line", required=True
    ),
    FieldSchema(
        key="field_description",
        label="Description",
        widget="text",
        required=True,
        placeholder=_DESCRIPTION_PLACEHOLDER,
    ),
    FieldSchema(
        key="field_type",
        label="Type",
        widget="combo",
        required=True,
        vocab=FIELD_TYPES,
        default="text",
    ),
    FieldSchema(
        key="field_required",
        label="Required",
        widget="combo",
        required=True,
        vocab=frozenset(_REQUIRED_CHOICES),
        default="false",
    ),
    FieldSchema(
        key="field_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="field_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=FIELD_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("field_status")
        ),
    ),
]


def field_fields(
    *, include_identifier: bool, include_parent_entity: bool, client=None
) -> list[FieldSchema]:
    """Return a fresh copy of the field schema.

    ``include_identifier`` adds the read-only ``field_identifier``
    field at the top — used by the edit dialog; the create dialog
    omits it because the identifier is server-assigned.

    ``include_parent_entity`` adds the
    ``field_belongs_to_entity_identifier`` parent-entity picker —
    used by the create dialog only (per spec §3.5.4). The edit
    dialog omits it because PUT/PATCH do not accept reparenting.

    ``client`` is required when ``include_parent_entity=True`` so
    the picker can populate its choices from the live entities list.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    if include_parent_entity:
        parent_schema = deepcopy(_PARENT_ENTITY_FIELD)
        choices = _live_entity_choices(client) if client is not None else []
        # Populate via compute_options so the combo refreshes if the
        # dialog reopens against an updated entity list. The returned
        # list of plain identifiers is fed to the combo's items; we
        # render them with names appended for human readability via
        # the dialog's choice-render override below.
        parent_schema.vocab = frozenset(
            ident for ident, _name in choices
        )
        parent_schema.compute_options = (
            lambda state, c=choices: [ident for ident, _name in c]
        )
        fields.append(parent_schema)
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
