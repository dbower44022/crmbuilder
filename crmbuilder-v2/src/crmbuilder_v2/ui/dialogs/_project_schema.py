"""Field schema for the workstream CRUD dialogs (UI v0.7)."""

from __future__ import annotations

from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    PROJECT_STATUS_TRANSITIONS,
    PROJECT_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema


def status_choices(current: str | None) -> list[str]:
    current = current or "planned"
    if current not in PROJECT_STATUSES:
        return sorted(PROJECT_STATUSES)
    return sorted(
        {current} | set(PROJECT_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="project_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="project_name", label="Name", widget="line", required=True),
    FieldSchema(
        key="project_purpose",
        label="Purpose",
        widget="line",
        required=True,
        placeholder="One sentence",
    ),
    FieldSchema(
        key="project_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="Paragraph describing the workstream",
    ),
    FieldSchema(key="project_notes", label="Internal notes", widget="text"),
    FieldSchema(
        key="project_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=PROJECT_STATUSES,
        default="planned",
        compute_options=lambda state: status_choices(state.get("project_status")),
    ),
]


def workstream_fields(*, include_identifier: bool) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
