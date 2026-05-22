"""Field schema for the reference_book CRUD dialogs (UI v0.7)."""

from __future__ import annotations

from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    REFERENCE_BOOK_KINDS,
    REFERENCE_BOOK_STATUS_TRANSITIONS,
    REFERENCE_BOOK_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema


def status_choices(current: str | None) -> list[str]:
    current = current or "active"
    if current not in REFERENCE_BOOK_STATUSES:
        return sorted(REFERENCE_BOOK_STATUSES)
    return sorted(
        {current} | set(REFERENCE_BOOK_STATUS_TRANSITIONS.get(current, frozenset()))
    )


_IDENTIFIER_FIELD = FieldSchema(
    key="reference_book_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(key="reference_book_title", label="Title", widget="line", required=True),
    FieldSchema(
        key="reference_book_description",
        label="Description",
        widget="text",
        required=True,
        placeholder="Paragraph describing the reference book",
    ),
    FieldSchema(key="reference_book_notes", label="Internal notes", widget="text"),
    FieldSchema(
        key="reference_book_kind",
        label="Kind",
        widget="combo",
        required=True,
        vocab=REFERENCE_BOOK_KINDS,
    ),
    FieldSchema(
        key="reference_book_file_path",
        label="File path",
        widget="line",
        required=True,
        placeholder="PRDs/product/crmbuilder-v2/example.md",
    ),
    FieldSchema(
        key="reference_book_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=REFERENCE_BOOK_STATUSES,
        default="active",
        compute_options=lambda state: status_choices(state.get("reference_book_status")),
    ),
]


def reference_book_fields(*, include_identifier: bool) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
