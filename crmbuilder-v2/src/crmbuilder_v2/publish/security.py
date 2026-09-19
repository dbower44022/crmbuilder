"""Applying declared access — teams, roles and field permissions
(REQ-614 / PI-528).

Access is part of the design, and it is the part where being careless is
expensive: a role written too broadly shows people records they should not
see, and one written too narrowly stops them working. Three rules follow
from that, and they are why this module is not a thin wrapper over the
client.

**Only what the design names is touched.** A role on the instance carries
permissions this system does not model, and a person may have set them. A
role is patched with the parts the design declares and nothing else.

**A role that names an object type the instance does not have is refused
before anything is written.** The platform would accept it and produce a
role granting access to nothing, which reads as a working role in the
interface and is not one.

**A field permission is proved, not assumed.** After writing, the role is
read back and the cells checked, because a permission the platform silently
dropped is indistinguishable from one it applied — until somebody sees a
field they should not.

A team is created and its description kept current. It is never renamed and
never removed: the design refers to a team by name, so a rename would
detach it from the design, and a removal would take its members with it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.introspect.utilization import wire_entity_name
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened.
CREATED = "created"
UPDATED = "updated"
SKIPPED = "skipped"
REFUSED = "refused"
FAILED = "failed"
PREVIEWED = "previewed"

#: The five permissions the design models, and their names on the platform.
SYSTEM_PERMISSIONS: dict[str, str] = {
    "assignment": "assignmentPermission",
    "user": "userPermission",
    "export": "exportPermission",
    "mass_update": "massUpdatePermission",
    "portal": "portalPermission",
}

#: The per-object-type permissions, in the order the platform lists them.
SCOPE_ACTIONS: tuple[str, ...] = ("create", "read", "edit", "delete", "stream")

#: What a field permission may say.
FIELD_LEVELS = frozenset({"yes", "read", "no"})


@dataclass(frozen=True)
class TeamIntent:
    """A team, as the design declares it."""

    name: str
    description: str | None = None


@dataclass(frozen=True)
class FieldPermission:
    """One field restricted for one role.

    :ivar entity: The design's name for the object type.
    :ivar field: The field's name on the platform.
    :ivar level: ``yes`` to leave it alone, ``read`` for read-only, ``no``
        to hide it.
    """

    entity: str
    field: str
    level: str


@dataclass(frozen=True)
class RoleIntent:
    """A role, as the design declares it.

    :ivar name: The role's name, which is how the design refers to it.
    :ivar scope_access: Per object type, what may be done — by the design's
        names for the object types. An object type the design omits is
        omitted from the role, which denies it.
    :ivar system_permissions: The five permissions the design models, by
        their names here; anything omitted is left as the instance has it.
    :ivar field_permissions: Fields restricted for this role.
    """

    name: str
    scope_access: Mapping[str, Mapping[str, Any]] = dataclass_field(
        default_factory=dict
    )
    system_permissions: Mapping[str, str] = dataclass_field(default_factory=dict)
    field_permissions: Sequence[FieldPermission] = ()


@dataclass
class AccessOutcome:
    """What happened to one team or role.

    :ivar kind: ``team`` or ``role``.
    :ivar name: Its name.
    :ivar status: One of :data:`CREATED`, :data:`UPDATED`, :data:`SKIPPED`,
        :data:`REFUSED`, :data:`FAILED`, :data:`PREVIEWED`.
    :ivar detail: What a person needs to read about it.
    :ivar verified: Whether what was written was read back and confirmed.
    """

    kind: str
    name: str
    status: str
    detail: str = ""
    verified: bool = False

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _raise_if_unauthenticated(status: int) -> None:
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )


def _records_by_name(body: Any) -> dict[str, dict[str, Any]]:
    rows = body.get("list") if isinstance(body, Mapping) else body
    found: dict[str, dict[str, Any]] = {}
    if isinstance(rows, Sequence):
        for row in rows:
            if isinstance(row, Mapping) and row.get("name"):
                found[str(row["name"])] = dict(row)
    return found


# --- teams ------------------------------------------------------------------


def apply_teams(
    client: EspoWriteClient,
    intents: Iterable[TeamIntent],
    *,
    preview: bool = False,
) -> list[AccessOutcome]:
    """Create each declared team and keep its description current.

    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    status, body = client.get_teams()
    _raise_if_unauthenticated(status)
    live = _records_by_name(body) if status == 200 else {}
    if status != 200:
        return [
            AccessOutcome(
                "team",
                intent.name,
                FAILED,
                f"the instance did not report its teams ({status})",
            )
            for intent in intents
        ]

    outcomes: list[AccessOutcome] = []
    for intent in intents:
        existing = live.get(intent.name)
        if existing is None:
            if preview:
                outcomes.append(
                    AccessOutcome("team", intent.name, PREVIEWED, "would be created")
                )
                continue
            create_status, create_body = client.create_team(
                intent.name, intent.description
            )
            _raise_if_unauthenticated(create_status)
            outcomes.append(
                AccessOutcome("team", intent.name, CREATED)
                if create_status == 200
                else AccessOutcome(
                    "team",
                    intent.name,
                    FAILED,
                    f"the instance refused the team ({create_status}): "
                    f"{format_error_detail(create_body)}",
                )
            )
            continue

        if intent.description is None or (existing.get("description") or "") == (
            intent.description or ""
        ):
            outcomes.append(
                AccessOutcome("team", intent.name, SKIPPED, "already as declared")
            )
            continue
        if preview:
            outcomes.append(
                AccessOutcome(
                    "team", intent.name, PREVIEWED, "description would change"
                )
            )
            continue
        patch_status, patch_body = client.update_team(
            str(existing.get("id")), intent.description
        )
        _raise_if_unauthenticated(patch_status)
        outcomes.append(
            AccessOutcome("team", intent.name, UPDATED, "description changed")
            if patch_status == 200
            else AccessOutcome(
                "team",
                intent.name,
                FAILED,
                f"the instance refused the change ({patch_status}): "
                f"{format_error_detail(patch_body)}",
            )
        )
    return outcomes


# --- roles ------------------------------------------------------------------


def scope_data(scope_access: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    """The per-object-type permissions, in the platform's own shape.

    Object types are named the platform's way, and whether a person may
    create a record is a yes-or-no where the others are a scope.
    """
    data: dict[str, dict[str, str]] = {}
    for entity, scope in scope_access.items():
        cell: dict[str, str] = {}
        for action in SCOPE_ACTIONS:
            value = scope.get(action)
            if value is None:
                continue
            if action == "create" and isinstance(value, bool):
                cell[action] = "yes" if value else "no"
            else:
                cell[action] = str(value)
        data[wire_entity_name(entity)] = cell
    return data


def role_payload(intent: RoleIntent, *, include_name: bool) -> dict[str, Any]:
    """The role body, carrying only what the design declares."""
    payload: dict[str, Any] = {"data": scope_data(intent.scope_access)}
    if include_name:
        payload["name"] = intent.name
    for name, platform_name in SYSTEM_PERMISSIONS.items():
        if name in intent.system_permissions:
            payload[platform_name] = intent.system_permissions[name]
    return payload


def merged_field_data(
    current: Mapping[str, Any], permissions: Iterable[FieldPermission]
) -> dict[str, Any]:
    """The role's field permissions with the declared cells merged in.

    Only the named cells change. Everything else the role carries is left
    exactly as it was, because a person may have set it.
    """
    merged: dict[str, Any] = {
        entity: dict(cells) if isinstance(cells, Mapping) else cells
        for entity, cells in current.items()
    }
    for permission in permissions:
        wire = wire_entity_name(permission.entity)
        cells = merged.setdefault(wire, {})
        if isinstance(cells, dict):
            cells[permission.field] = permission.level
    return merged


def _missing_object_types(
    client: EspoWriteClient, intent: RoleIntent
) -> list[str]:
    """Object types the role names that the instance does not have."""
    if not intent.scope_access:
        return []
    status, scopes = client.get_all_scopes()
    _raise_if_unauthenticated(status)
    if status != 200 or not isinstance(scopes, Mapping):
        return []
    return [
        entity
        for entity in intent.scope_access
        if wire_entity_name(entity) not in scopes
    ]


def apply_role(
    client: EspoWriteClient, intent: RoleIntent, *, preview: bool = False
) -> AccessOutcome:
    """Apply one declared role, and prove its field permissions landed.

    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    missing = _missing_object_types(client, intent)
    if missing:
        return AccessOutcome(
            "role",
            intent.name,
            REFUSED,
            f"the role grants access to {', '.join(sorted(missing))}, which "
            f"the instance does not have. Writing it would produce a role "
            f"that grants nothing while looking as though it does.",
        )

    status, body = client.get_roles()
    _raise_if_unauthenticated(status)
    if status != 200:
        return AccessOutcome(
            "role",
            intent.name,
            FAILED,
            f"the instance did not report its roles ({status})",
        )
    live = _records_by_name(body).get(intent.name)

    if preview:
        return AccessOutcome(
            "role",
            intent.name,
            PREVIEWED,
            "would be created" if live is None else "would be updated",
        )

    if live is None:
        payload = role_payload(intent, include_name=True)
        if intent.field_permissions:
            payload["fieldData"] = merged_field_data({}, intent.field_permissions)
        create_status, create_body = client.create_role(payload)
        _raise_if_unauthenticated(create_status)
        if create_status != 200:
            return AccessOutcome(
                "role",
                intent.name,
                FAILED,
                f"the instance refused the role ({create_status}): "
                f"{format_error_detail(create_body)}",
            )
        return _verify_field_permissions(client, intent, CREATED)

    role_id = live.get("id")
    if not role_id:
        return AccessOutcome(
            "role",
            intent.name,
            FAILED,
            "the instance reported this role without an identifier, so it "
            "cannot be updated",
        )
    payload = role_payload(intent, include_name=False)
    if intent.field_permissions:
        payload["fieldData"] = merged_field_data(
            live.get("fieldData") or {}, intent.field_permissions
        )
    patch_status, patch_body = client.update_role(str(role_id), payload)
    _raise_if_unauthenticated(patch_status)
    if patch_status != 200:
        return AccessOutcome(
            "role",
            intent.name,
            FAILED,
            f"the instance refused the role ({patch_status}): "
            f"{format_error_detail(patch_body)}",
        )
    return _verify_field_permissions(client, intent, UPDATED)


def _verify_field_permissions(
    client: EspoWriteClient, intent: RoleIntent, status_when_confirmed: str
) -> AccessOutcome:
    """Read the role back and check each declared field permission landed."""
    if not intent.field_permissions:
        return AccessOutcome("role", intent.name, status_when_confirmed, verified=True)

    status, body = client.get_roles()
    _raise_if_unauthenticated(status)
    written = _records_by_name(body).get(intent.name) if status == 200 else None
    if written is None:
        return AccessOutcome(
            "role",
            intent.name,
            status_when_confirmed,
            "the role could not be read back, so its field permissions are "
            "unconfirmed",
        )
    field_data = written.get("fieldData") or {}
    unconfirmed = [
        f"{permission.entity}.{permission.field}"
        for permission in intent.field_permissions
        if (field_data.get(wire_entity_name(permission.entity)) or {}).get(
            permission.field
        )
        != permission.level
    ]
    if unconfirmed:
        return AccessOutcome(
            "role",
            intent.name,
            FAILED,
            "the instance accepted the role but does not report these field "
            "permissions: " + ", ".join(unconfirmed),
        )
    return AccessOutcome("role", intent.name, status_when_confirmed, verified=True)


def apply_roles(
    client: EspoWriteClient,
    intents: Iterable[RoleIntent],
    *,
    preview: bool = False,
) -> list[AccessOutcome]:
    """Apply every declared role, in the order given."""
    return [apply_role(client, intent, preview=preview) for intent in intents]
