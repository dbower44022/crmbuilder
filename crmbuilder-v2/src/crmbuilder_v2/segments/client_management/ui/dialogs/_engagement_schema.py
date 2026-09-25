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
from crmbuilder_v2.segments.client_management.vocab import (
    DEFAULT_ENGAGEMENT_VISIBILITY,
    ENGAGEMENT_VISIBILITIES,
)
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
        placeholder="What this application covers",
    ),
    # PI-580 (REQ-653): who may deploy the application.
    FieldSchema(
        key="engagement_visibility",
        label="Visibility",
        widget="combo",
        required=True,
        vocab=ENGAGEMENT_VISIBILITIES,
        default=DEFAULT_ENGAGEMENT_VISIBILITY,
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


DEFINING_CLIENT_KEY = "engagement_defining_client"


def client_choice_label(client: dict) -> str:
    """How a client appears in the defining-client combo."""
    return f"{client.get('client_identifier')} — {client.get('client_name') or '(unnamed)'}"


def _defining_client_field(clients: list[dict]) -> FieldSchema:
    """PI-580 (REQ-653): the client that defines the application, chosen
    from the live client list; the dialog maps the label back to CLI-NNN."""
    choices = frozenset(client_choice_label(c) for c in clients if c.get("client_identifier"))
    return FieldSchema(
        key=DEFINING_CLIENT_KEY,
        label="Defined by",
        widget="combo",
        required=True,
        vocab=choices,
    )


def engagement_fields_create(clients: list[dict] | None = None) -> list[FieldSchema]:
    """Return the Create-dialog schema (code is editable; no identifier).
    With ``clients`` the defining client is asked for as well."""
    fields: list[FieldSchema] = [deepcopy(_CODE_FIELD_CREATE)]
    fields.extend(deepcopy(_CONTENT_FIELDS))
    if clients is not None:
        fields.insert(2, _defining_client_field(clients))
    return fields


def engagement_fields_edit(clients: list[dict] | None = None) -> list[FieldSchema]:
    """Return the Edit-dialog schema (identifier + code both read-only).
    With ``clients`` the defining client may be changed."""
    fields: list[FieldSchema] = [
        deepcopy(_IDENTIFIER_FIELD),
        deepcopy(_CODE_FIELD_EDIT),
    ]
    fields.extend(deepcopy(_CONTENT_FIELDS))
    if clients is not None:
        fields.insert(3, _defining_client_field(clients))
    return fields
