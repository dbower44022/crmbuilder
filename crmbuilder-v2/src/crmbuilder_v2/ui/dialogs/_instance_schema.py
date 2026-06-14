"""Field schema for the instance CRUD dialogs (PI-186 / PRJ-027).

A declarative ``FieldSchema`` list consumed by ``EntityCrudDialog``. The schema
keys are the parent-prefixed ``instance_*`` names the REST bodies expect, except
the two secret inputs whose keys are the write-only plaintext ``secret`` /
``secret_key`` the router translates into keyring references (REQ-157).

The create dialog omits ``instance_identifier`` (server-assigned); the edit
dialog includes it read-only. The secret fields use
``omit_when_empty_in_create`` so a blank create sends no secret, and — because
the record carries no ``secret`` key — a blank edit produces no diff, so an
unchanged secret is never overwritten; typing a value rotates it.
"""

from __future__ import annotations

import re
from copy import deepcopy

from crmbuilder_v2.access.vocab import (
    INSTANCE_AUTH_METHODS,
    INSTANCE_ROLES,
    INSTANCE_STATUSES,
    INSTANCE_VENDORS,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

IDENTIFIER_RE = re.compile(r"^INST-\d{3}$")


_IDENTIFIER_FIELD = FieldSchema(
    key="instance_identifier",
    label="Identifier",
    widget="line",
    read_only_on_edit=True,
)

_CONTENT_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="instance_name",
        label="Name",
        widget="line",
        required=True,
        placeholder="Connection label (e.g., CBM sandbox, CBM production)",
    ),
    FieldSchema(
        key="instance_url",
        label="URL",
        widget="line",
        required=True,
        placeholder="https://crm.example.org",
    ),
    FieldSchema(
        key="instance_vendor",
        label="CRM system",
        widget="combo",
        required=True,
        vocab=INSTANCE_VENDORS,
        default="espocrm",
        compute_options=lambda _state: sorted(INSTANCE_VENDORS),
    ),
    FieldSchema(
        key="instance_role",
        label="Role",
        widget="combo",
        required=True,
        vocab=INSTANCE_ROLES,
        default="both",
        compute_options=lambda _state: sorted(INSTANCE_ROLES),
    ),
    FieldSchema(
        key="instance_auth_method",
        label="Auth method",
        widget="combo",
        required=True,
        vocab=INSTANCE_AUTH_METHODS,
        default="api_key",
        compute_options=lambda _state: sorted(INSTANCE_AUTH_METHODS),
    ),
    FieldSchema(
        key="secret",
        label="API key / password",
        widget="line",
        omit_when_empty_in_create=True,
        placeholder="Stored in the OS keyring; leave blank to keep the current value",
    ),
    FieldSchema(
        key="secret_key",
        label="HMAC secret key",
        widget="line",
        omit_when_empty_in_create=True,
        placeholder="Only for HMAC auth; stored in the OS keyring",
    ),
    FieldSchema(
        key="instance_status",
        label="Status",
        widget="combo",
        required=True,
        vocab=INSTANCE_STATUSES,
        default="active",
        compute_options=lambda _state: sorted(INSTANCE_STATUSES),
    ),
    FieldSchema(
        key="instance_notes",
        label="Internal notes",
        widget="text",
    ),
]


def instance_fields(*, include_identifier: bool) -> list[FieldSchema]:
    """Return a fresh copy of the instance field schema.

    :param include_identifier: When True, prepend the read-only
        ``instance_identifier`` field (the edit dialog); the create dialog
        omits it because the identifier is server-assigned.
    :returns: A deep copy so per-dialog mutation never aliases the module list.
    """
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(deepcopy(_IDENTIFIER_FIELD))
    fields.extend(deepcopy(_CONTENT_FIELDS))
    return fields
