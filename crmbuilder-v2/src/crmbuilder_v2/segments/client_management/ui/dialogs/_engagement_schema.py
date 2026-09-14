"""Field schema for the engagement CRUD dialogs (UI v0.5 slice C).

Declarative ``FieldSchema`` lists consumed by ``EntityCrudDialog``,
following the v0.4 methodology-entity pattern. Fields are in
``engagement.md`` section 3.2 order; schema keys are the parent-prefixed
``engagement_*`` names the REST bodies expect.

The Create dialog includes ``engagement_code`` (writeable, with the
regex constraint hint visible) but omits ``engagement_identifier``
(server-assigned). The Edit dialog includes both as read-only — the
identifier because it is immutable by definition, the code because
renaming requires a per-engagement DB file move and is deferred to
v0.6+ per ``engagement.md`` §3.6.3.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.engagement_models import EngagementStatus
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
IDENTIFIER_RE = re.compile(r"^ENG-\d{3}$")

_VALID_STATUSES: frozenset[str] = frozenset(s.value for s in EngagementStatus)

_IDENTIFIER_FIELD = FieldSchema(
    key="engagement_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CODE_FIELD_CREATE = FieldSchema(
    key="engagement_code",
    label="Code",
    widget="line",
    required=True,
    placeholder="2-10 characters, uppercase letters and digits, must start with a letter",
    regex=CODE_RE,
    regex_hint=(
        "Code must be 2-10 uppercase letters and digits, starting with a letter."
    ),
)

_CODE_FIELD_EDIT = FieldSchema(
    key="engagement_code",
    label="Code",
    widget="line",
    read_only=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="engagement_name",
        label="Name",
        widget="line",
        required=True,
    ),
    FieldSchema(
        key="engagement_purpose",
        label="Purpose",
        widget="text",
        required=True,
        placeholder="What this engagement covers",
    ),
    FieldSchema(
        key="engagement_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=_VALID_STATUSES,
        default="active",
    ),
]


def engagement_fields_create() -> list[FieldSchema]:
    """Return the Create-dialog schema (code is editable; no identifier)."""
    fields: list[FieldSchema] = [deepcopy(_CODE_FIELD_CREATE)]
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields


def engagement_fields_edit() -> list[FieldSchema]:
    """Return the Edit-dialog schema (identifier + code both read-only)."""
    fields: list[FieldSchema] = [
        deepcopy(_IDENTIFIER_FIELD),
        deepcopy(_CODE_FIELD_EDIT),
    ]
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
