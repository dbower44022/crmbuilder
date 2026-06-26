"""Field schemas for the Agent Profile Registry CRUD dialogs (PI-330 / REQ-367).

Declarative ``FieldSchema`` lists consumed by ``EntityCrudDialog``, one builder
per registry entity (agent_profile / skill / governance_rule / learning). The
schema keys are the plain REST body field names (no parent prefix); create
bodies accept ``scope`` ("system" or an engagement identifier) which the access
layer maps onto the nullable ``engagement_id`` column.

The JSON columns (``capability_description``, ``io_contract``, ``predicate``)
are NOT on these forms — they are edited through the dedicated ``JsonFieldDialog``
launched from the panel detail, which parses and validates the JSON properly.
Likewise the system-managed ``version`` / ``confidence`` counters are omitted.

The ``scope`` combo is built per call from the live engagement list so an
operator can author a system default or an engagement overlay. Scope is
read-only on edit (re-scoping an existing row is a structural change handled via
the API directly).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crmbuilder_v2.access.vocab import (
    AGENT_PROFILE_TIERS,
    LEARNING_CATEGORIES,
    LEARNING_STATUSES,
    LEARNING_TIERS,
    REGISTRY_STATUSES,
    RULE_ENFORCEMENT_MODES,
    SKILL_KINDS,
    SYSTEM_AREAS,
)
from crmbuilder_v2.ui.base.crud_dialog import FieldSchema

if TYPE_CHECKING:
    from crmbuilder_v2.ui.client import StorageClient

_SYSTEM_SCOPE = "system"

_AREA_HINT = "A system area (e.g. storage, access, api, ui) or an engagement area."


def _identifier_field() -> FieldSchema:
    return FieldSchema(
        key="identifier",
        label="Identifier",
        widget="line",
        read_only_on_edit=True,
    )


def _scope_field(client: StorageClient) -> FieldSchema:
    """A scope combo: ``system`` plus every engagement identifier.

    Built per call so engagement overlays target live engagements. A failure
    to reach the engagement list degrades gracefully to system-only scope.
    """
    values = {_SYSTEM_SCOPE}
    try:
        for eng in client.list_engagements():
            ident = eng.get("engagement_identifier") or eng.get("identifier")
            if ident:
                values.add(str(ident))
    except Exception:  # noqa: BLE001 — scope still works with system-only.
        pass
    return FieldSchema(
        key="scope",
        label="Scope",
        widget="combo",
        required=True,
        vocab=frozenset(values),
        default=_SYSTEM_SCOPE,
        read_only_on_edit=True,
    )


def agent_profile_fields(
    client: StorageClient, *, include_identifier: bool
) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(_identifier_field())
    fields.extend(
        [
            FieldSchema(
                key="area",
                label="Area",
                widget="line",
                required=True,
                placeholder=_AREA_HINT,
            ),
            FieldSchema(
                key="tier",
                label="Tier",
                widget="combo",
                required=True,
                vocab=AGENT_PROFILE_TIERS,
            ),
            FieldSchema(
                key="description",
                label="System prompt",
                widget="text",
                required=True,
                placeholder="The agent's system prompt / role definition.",
            ),
            FieldSchema(
                key="status",
                label="Status",
                widget="combo",
                required=True,
                vocab=REGISTRY_STATUSES,
                default="active",
            ),
            _scope_field(client),
        ]
    )
    return fields


def skill_fields(
    client: StorageClient, *, include_identifier: bool
) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(_identifier_field())
    fields.extend(
        [
            FieldSchema(key="name", label="Name", widget="line", required=True),
            FieldSchema(
                key="kind",
                label="Kind",
                widget="combo",
                required=True,
                vocab=SKILL_KINDS,
                default="instruction",
            ),
            FieldSchema(
                key="description",
                label="Description",
                widget="text",
                required=True,
                placeholder="What the skill does.",
            ),
            FieldSchema(
                key="backing_callable",
                label="Backing callable",
                widget="line",
                placeholder="For tool skills, e.g. GET /workstreams/{id}/prior-phase-outputs",
            ),
            FieldSchema(
                key="status",
                label="Status",
                widget="combo",
                required=True,
                vocab=REGISTRY_STATUSES,
                default="active",
            ),
            _scope_field(client),
        ]
    )
    return fields


def governance_rule_fields(
    client: StorageClient, *, include_identifier: bool
) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(_identifier_field())
    fields.extend(
        [
            FieldSchema(
                key="body",
                label="Rule body",
                widget="text",
                required=True,
                placeholder="The rule, in plain declarative language.",
            ),
            FieldSchema(
                key="enforcement",
                label="Enforcement",
                widget="combo",
                required=True,
                vocab=RULE_ENFORCEMENT_MODES,
                default="advisory",
            ),
            FieldSchema(
                key="rule_type",
                label="Rule type",
                widget="line",
                placeholder="Optional key, e.g. no_force_push, or disable:GVR-007 for an overlay.",
            ),
            FieldSchema(
                key="severity",
                label="Severity",
                widget="line",
                placeholder="Optional, e.g. error / warning.",
            ),
            FieldSchema(
                key="status",
                label="Status",
                widget="combo",
                required=True,
                vocab=REGISTRY_STATUSES,
                default="active",
            ),
            _scope_field(client),
        ]
    )
    return fields


def learning_fields(
    client: StorageClient, *, include_identifier: bool
) -> list[FieldSchema]:
    fields: list[FieldSchema] = []
    if include_identifier:
        fields.append(_identifier_field())
    fields.extend(
        [
            FieldSchema(
                key="area",
                label="Area",
                widget="line",
                required=True,
                placeholder=_AREA_HINT,
            ),
            FieldSchema(
                key="tier",
                label="Tier",
                widget="combo",
                required=True,
                vocab=LEARNING_TIERS,
                default="developer",
            ),
            FieldSchema(
                key="category",
                label="Category",
                widget="combo",
                required=True,
                vocab=LEARNING_CATEGORIES,
                default="pattern",
            ),
            FieldSchema(
                key="content",
                label="Content",
                widget="text",
                required=True,
                placeholder="The learning, stated plainly.",
            ),
            FieldSchema(
                key="status",
                label="Status",
                widget="combo",
                required=True,
                vocab=LEARNING_STATUSES,
                default="active",
            ),
            _scope_field(client),
        ]
    )
    return fields


__all__ = [
    "SYSTEM_AREAS",
    "agent_profile_fields",
    "skill_fields",
    "governance_rule_fields",
    "learning_fields",
]
