"""Field schema for the conversation CRUD dialogs (UI v0.7)."""

from __future__ import annotations

from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    CONVERSATION_STATUS_TRANSITIONS,
    CONVERSATION_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema


def status_choices(current: str | None) -> list[str]:
    current = current or "planned"
    if current not in CONVERSATION_STATUSES:
        return sorted(CONVERSATION_STATUSES)
    return sorted(
        {current} | set(CONVERSATION_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="conversation_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="conversation_title", label="Title", widget="line", required=True),
    FieldSchema(
        key="conversation_purpose",
        label="Purpose",
        widget="line",
        required=True,
        placeholder="One sentence",
    ),
    FieldSchema(
        key="conversation_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="Paragraph describing the conversation",
    ),
    FieldSchema(key="conversation_notes", label="Internal notes", widget="text"),
    FieldSchema(
        key="conversation_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=CONVERSATION_STATUSES,
        default="planned",
        compute_options=lambda state: status_choices(state.get("conversation_status")),
    ),
]


def conversation_fields(*, include_identifier: bool) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
