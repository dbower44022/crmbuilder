"""Field schema for the Session CRUD dialogs (PI-073 / DEC-314 redesign).

Sessions are the medium-agnostic communication container — one Claude.ai
chat / email / phone call / Zoom meeting / in-person meeting / Slack
thread = one session. The schema mirrors ``session-v2.md`` §3.2.

Identifier prefix ``SES-NNN``. Six-status lifecycle (planned, in_flight,
complete, cancelled, not_started, superseded). Editable throughout (the
DEC-013 append-only rule is superseded by DEC-314).
"""

from __future__ import annotations

from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    SESSION_MEDIUMS,
    SESSION_STATUS_TRANSITIONS,
    SESSION_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema


def status_choices(current: str | None) -> list[str]:
    current = current or "planned"
    if current not in SESSION_STATUSES:
        return sorted(SESSION_STATUSES)
    return sorted(
        {current} | set(SESSION_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="session_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="session_title",
        label="Title",
        widget="line",
        required=True,
    ),
    FieldSchema(
        key="session_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="Paragraph describing the session — what communication is happening, who is involved, what defines its close.",
    ),
    FieldSchema(
        key="session_medium",
        label="Medium",
        widget="combo",
        required=True,
        vocab=SESSION_MEDIUMS,
        default="chat",
    ),
    FieldSchema(
        key="session_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=SESSION_STATUSES,
        default="planned",
        compute_options=lambda state: status_choices(state.get("session_status")),
    ),
    FieldSchema(
        key="session_notes",
        label="Internal notes",
        widget="text",
    ),
]


def session_fields(*, include_identifier: bool) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
