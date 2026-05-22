"""Field schema for the close_out_payload CRUD dialogs (UI v0.7)."""

from __future__ import annotations

from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS,
    CLOSE_OUT_PAYLOAD_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema


def status_choices(current: str | None) -> list[str]:
    current = current or "drafted"
    if current not in CLOSE_OUT_PAYLOAD_STATUSES:
        return sorted(CLOSE_OUT_PAYLOAD_STATUSES)
    return sorted(
        {current} | set(CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="close_out_payload_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="close_out_payload_title", label="Title", widget="line", required=True
    ),
    FieldSchema(
        key="close_out_payload_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="One- or two-sentence summary of the payload",
    ),
    FieldSchema(
        key="close_out_payload_notes", label="Internal notes", widget="text"
    ),
    FieldSchema(
        key="close_out_payload_file_path",
        label="File path",
        widget="line",
        required=True,
        placeholder="close-out-payloads/ses_NNN.json",
    ),
    FieldSchema(
        key="close_out_payload_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=CLOSE_OUT_PAYLOAD_STATUSES,
        default="drafted",
        compute_options=lambda state: status_choices(
            state.get("close_out_payload_status")
        ),
    ),
]


def close_out_payload_fields(*, include_identifier: bool) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
