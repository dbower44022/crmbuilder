"""Field schema for the manual_config CRUD dialogs (PI-004 cohort, v0.5+).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``,
following the v0.3 governance-entity pattern and mirroring
``_entity_schema.py``. Fields are in ``manual_config.md`` §3.2 order;
the schema keys are the parent-prefixed ``manual_config_*`` names the
REST bodies expect.

The create dialog omits ``manual_config_identifier`` (server-assigned);
the edit dialog includes it as a read-only field. Per spec §3.6.4's
create-then-attach flow there are no reference multi-selects in either
dialog — references attach from the detail pane's
``ReferencesSection`` after the manual_config record exists.

**Mark-Completed UX (per spec §3.6.5).** The status-combo-driven
pattern ships in v0.5+ — the user changes ``manual_config_status``
to ``completed`` and the §3.5.3 cross-field invariant is enforced
server-side: a 422 with the dedicated
``completed_status_requires_completion_fields`` body surfaces inline
if either completion field is missing. The dedicated "Mark Completed"
button alternative is the spec's §3.8.1 open question, deferred to
v0.6+ on operator-workflow signal.

**Visibility of completion fields.** ``FieldSchema`` does not currently
support ``visible_when`` / ``required_when`` / ``widget="datetime"`` —
build prompt §12a chose the "always-show-but-conditionally-required"
fallback, which acceptance §3.7 item 14 explicitly accepts as inline
provision of the affordance. Both completion fields ship as ``line``
widgets carrying placeholder text explaining when they are required;
the access layer rejects with the dedicated body shape when they are
missing on transition into ``completed``.

``manual_config_status`` carries a ``compute_options`` callback that
restricts the combo to the valid successors of the record's current
status per the transition map. ``manual_config_category`` carries a
``compute_options`` callback returning the full unconstrained
seven-value vocabulary (consultant may freely re-classify).
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    MANUAL_CONFIG_CATEGORIES,
    MANUAL_CONFIG_STATUS_TRANSITIONS,
    MANUAL_CONFIG_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^MCF-\d{3}$")

_DESCRIPTION_PLACEHOLDER = (
    "Brief description of what the manual config is and why it exists"
)
_INSTRUCTIONS_PLACEHOLDER = "Step-by-step instructions for the operator"
_COMPLETED_AT_PLACEHOLDER = (
    "ISO 8601 UTC timestamp; leave blank to default to now when status "
    "is completed"
)
_COMPLETED_BY_PLACEHOLDER = (
    "Operator identifier; required when status is completed"
)


def status_choices(current: str | None) -> list[str]:
    """Return the status values selectable from ``current``.

    The current value plus its valid successors per
    :data:`MANUAL_CONFIG_STATUS_TRANSITIONS`. ``candidate`` (the create-
    dialog starting point) yields three values (NOT including
    ``completed`` — the direct ``candidate → completed`` transition is
    invalid per §3.4.1; the user must go through ``confirmed`` first).
    ``confirmed`` yields ``[confirmed, completed, deferred]``;
    ``deferred`` yields the two-value narrowed set; ``completed`` is
    terminal, yielding just itself.
    """
    current = current or "candidate"
    if current not in MANUAL_CONFIG_STATUSES:
        return sorted(MANUAL_CONFIG_STATUSES)
    return sorted(
        {current}
        | set(MANUAL_CONFIG_STATUS_TRANSITIONS.get(current, frozenset()))
    )


def category_choices() -> list[str]:
    """Return the full sorted seven-value category vocabulary.

    Per spec §3.2.3 the category vocabulary is closed in v0.5+; the
    combo offers all seven values unconditionally. Re-classification
    is permitted at any time (no transition rules on category).
    """
    return sorted(MANUAL_CONFIG_CATEGORIES)


_IDENTIFIER_FIELD = FieldSchema(
    key="manual_config_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="manual_config_name",
        label="Name",
        widget="line",
        required=True,
    ),
    FieldSchema(
        key="manual_config_category",
        label="Category",
        widget="combo",
        required=True,
        vocab=MANUAL_CONFIG_CATEGORIES,
        compute_options=lambda _state: category_choices(),
    ),
    FieldSchema(
        key="manual_config_description",
        label="Description",
        widget="text",
        required=True,
        placeholder=_DESCRIPTION_PLACEHOLDER,
    ),
    FieldSchema(
        key="manual_config_instructions",
        label="Instructions",
        widget="text",
        required=True,
        placeholder=_INSTRUCTIONS_PLACEHOLDER,
    ),
    FieldSchema(
        key="manual_config_notes",
        label="Internal notes",
        widget="text",
    ),
    FieldSchema(
        key="manual_config_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=MANUAL_CONFIG_STATUSES,
        default="candidate",
        compute_options=lambda state: status_choices(
            state.get("manual_config_status")
        ),
    ),
    # Completion fields — visibility/conditional-requirement are
    # enforced at the access layer per spec §3.5.3. The widgets are
    # always present in the form; placeholder text documents the
    # when-required rule. A status-transition into ``completed`` that
    # leaves ``manual_config_completed_by`` blank surfaces the
    # dedicated 422 error body inline.
    FieldSchema(
        key="manual_config_completed_at",
        label="Completed at",
        widget="line",
        placeholder=_COMPLETED_AT_PLACEHOLDER,
        omit_when_empty_in_create=True,
    ),
    FieldSchema(
        key="manual_config_completed_by",
        label="Completed by",
        widget="line",
        placeholder=_COMPLETED_BY_PLACEHOLDER,
        omit_when_empty_in_create=True,
    ),
]


def manual_config_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the manual_config field schema.

    ``include_identifier`` adds the read-only ``manual_config_identifier``
    field at the top — used by the edit dialog; the create dialog omits
    it because the identifier is server-assigned.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
