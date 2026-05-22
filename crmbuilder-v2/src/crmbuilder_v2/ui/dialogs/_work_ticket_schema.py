"""Field schema for the work_ticket CRUD dialogs (UI v0.7)."""

from __future__ import annotations

from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    WORK_TICKET_KINDS,
    WORK_TICKET_STATUS_TRANSITIONS,
    WORK_TICKET_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema


def status_choices(current: str | None) -> list[str]:
    current = current or "drafted"
    if current not in WORK_TICKET_STATUSES:
        return sorted(WORK_TICKET_STATUSES)
    return sorted(
        {current} | set(WORK_TICKET_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="work_ticket_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="work_ticket_title", label="Title", widget="line", required=True),
    FieldSchema(
        key="work_ticket_description",
        label="Description",
        widget="text",
        required=True,
    ),
    FieldSchema(key="work_ticket_notes", label="Internal notes", widget="text"),
    FieldSchema(
        key="work_ticket_kind",
        label="Kind",
        widget="combo",
        required=True,
        vocab=WORK_TICKET_KINDS,
    ),
    FieldSchema(
        key="work_ticket_file_path",
        label="File path",
        widget="line",
        required=True,
        placeholder="PRDs/product/crmbuilder-v2/kickoff.md",
    ),
    FieldSchema(
        key="work_ticket_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=WORK_TICKET_STATUSES,
        default="drafted",
        compute_options=lambda state: status_choices(state.get("work_ticket_status")),
    ),
]


def work_ticket_fields(*, include_identifier: bool) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
