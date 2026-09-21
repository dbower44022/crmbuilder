"""Applying an object type's own settings (REQ-613 / PI-527).

An object type is more than its fields: what it is called, whether it has a
record stream, how its list sorts, what is searched, its icon and colour, its
board view, and whether the platform guards against two people saving at
once. All of it is part of the design, and all of it goes through one
platform action — but the platform keeps the values in two different places
when read back, and only some of them under the same names it accepts on
write. This module holds that map in one table rather than in the flow of the
code, so adding a setting is a row rather than a branch.

Only settings that actually differ are written, and the operator is told
which. Two things the design can declare cannot be written at all: whether
several people may be assigned to a record, and the registration that lets
meetings and calls be filed against an object type. The platform exposes
neither through its interface, so each is reported as manual configuration
rather than silently skipped.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from crmbuilder_v2.introspect.espo_client import format_error_detail
from crmbuilder_v2.introspect.utilization import wire_entity_name
from crmbuilder_v2.publish.entities import AuthenticationRejected
from crmbuilder_v2.publish.espo_write_client import EspoWriteClient

#: What happened to an object type's settings.
UPDATED = "updated"
SKIPPED = "skipped"
FAILED = "failed"
PREVIEWED = "previewed"
#: Something only a person can do on the server, reported rather than applied.
UNAVAILABLE = "unavailable"

#: Where the platform keeps a setting when it reports one back.
IN_ENTITY = "entity"
IN_COLLECTION = "collection"
IN_CLIENT = "client"


@dataclass(frozen=True)
class Setting:
    """One setting: where it is read from, and what it is called on write.

    :ivar source: Which of the platform's three places holds it.
    :ivar payload_key: What the update action calls it, when that differs
        from the design's name for it.
    :ivar absent_value: What the platform means by not reporting it, so that
        a declared ``False`` against an absent value is not a difference.
    """

    source: str
    payload_key: str | None = None
    absent_value: Any = None


#: Every setting this system applies, by the design's name for it.
SETTINGS: dict[str, Setting] = {
    "labelSingular": Setting(IN_ENTITY),
    "labelPlural": Setting(IN_ENTITY),
    "stream": Setting(IN_ENTITY, absent_value=False),
    "disabled": Setting(IN_ENTITY, absent_value=False),
    "optimisticConcurrencyControl": Setting(IN_ENTITY, absent_value=False),
    "orderBy": Setting(IN_COLLECTION, payload_key="sortBy"),
    "order": Setting(IN_COLLECTION, payload_key="sortDirection"),
    "textFilterFields": Setting(IN_COLLECTION),
    "fullTextSearch": Setting(IN_COLLECTION, absent_value=False),
    "fullTextSearchMinLength": Setting(IN_COLLECTION),
    "countDisabled": Setting(IN_COLLECTION, absent_value=False),
    "iconClass": Setting(IN_CLIENT),
    "color": Setting(IN_CLIENT),
    "kanbanViewMode": Setting(IN_CLIENT, absent_value=False),
    "statusField": Setting(IN_CLIENT),
}

#: The setting the platform will not let anything but a person change.
MULTIPLE_ASSIGNED_USERS = "multipleAssignedUsers"

_MULTIPLE_ASSIGNED_REASON = (
    "whether several people may be assigned to one record cannot be set "
    "through the platform's interface. Set it by hand in the administration "
    "screens for this object type."
)
_ACTIVITY_PARENT_REASON = (
    "registering an object type so meetings, calls and tasks can be filed "
    "against it is a change to the platform's own definition files, which "
    "its interface does not expose. Add it by hand on the server, then "
    "rebuild."
)


@dataclass(frozen=True)
class SettingsIntent:
    """An object type's settings, as the design declares them.

    :ivar entity: The design's name for the object type.
    :ivar values: The settings the design declares, by the design's names.
        A setting the design does not mention is absent, and is neither
        compared nor written.
    :ivar multiple_assigned_users: Whether several people may be assigned to
        one record, when the design says; ``None`` when it does not.
    """

    entity: str
    values: Mapping[str, Any] = dataclass_field(default_factory=dict)
    multiple_assigned_users: bool | None = None


@dataclass
class SettingsOutcome:
    """What happened to one object type's settings.

    :ivar entity: The design's name for the object type.
    :ivar status: One of :data:`UPDATED`, :data:`SKIPPED`, :data:`FAILED`,
        :data:`PREVIEWED`.
    :ivar changed: The settings that differed, by the design's names.
    :ivar detail: What a person needs to read about it.
    :ivar manual_config: What the platform will not do, which somebody must
        now configure by hand.
    """

    entity: str
    status: str
    changed: list[str] = dataclass_field(default_factory=list)
    detail: str = ""
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def _live_value(
    setting: Setting,
    name: str,
    entity_defs: Mapping[str, Any],
    client_defs: Mapping[str, Any],
) -> Any:
    if setting.source == IN_ENTITY:
        return entity_defs.get(name, setting.absent_value)
    if setting.source == IN_COLLECTION:
        collection = entity_defs.get("collection") or {}
        return collection.get(name, setting.absent_value)
    return client_defs.get(name, setting.absent_value)


def changed_settings(
    intent: SettingsIntent,
    entity_defs: Mapping[str, Any],
    client_defs: Mapping[str, Any] | None = None,
) -> list[str]:
    """Which declared settings differ from the instance.

    :param intent: The settings as declared.
    :param entity_defs: The object type's definition, as the instance
        reports it, including its collection block.
    :param client_defs: The object type's presentation definition.
    :returns: The design's names for the settings that differ, in the order
        this system applies them.
    """
    client_defs = client_defs or {}
    changed: list[str] = []
    for name, setting in SETTINGS.items():
        declared = intent.values.get(name)
        if declared is None:
            continue
        if _live_value(setting, name, entity_defs, client_defs) != declared:
            changed.append(name)
    return changed


def multiple_assigned_users_live(entity_defs: Mapping[str, Any]) -> bool:
    """Whether the instance lets several people be assigned to one record.

    The platform does not report this as a setting. It shows instead in the
    shape of the object type: a field for the assigned people, or a link for
    collaborators.
    """
    fields = entity_defs.get("fields") or {}
    links = entity_defs.get("links") or {}
    return "assignedUsers" in fields or "collaborators" in links


def update_payload(intent: SettingsIntent, changed: Iterable[str]) -> dict[str, Any]:
    """The update body for the settings that differ.

    Only what differs is sent. The platform routes each key to wherever it
    keeps that setting, so the caller does not have to.
    """
    payload: dict[str, Any] = {"name": wire_entity_name(intent.entity)}
    for name in changed:
        setting = SETTINGS[name]
        payload[setting.payload_key or name] = intent.values[name]
    return payload


def apply_settings(
    client: EspoWriteClient,
    intent: SettingsIntent,
    *,
    preview: bool = False,
) -> SettingsOutcome:
    """Apply one object type's declared settings.

    :param client: A write-capable client for the target instance.
    :param intent: The settings as declared.
    :param preview: When true, report what would change and write nothing.
    :returns: What happened, including anything the platform will not do.
    :raises AuthenticationRejected: If the instance rejects the credential.
    """
    wire = wire_entity_name(intent.entity)

    defs_status, entity_defs = client.get_entity_defs(wire)
    if defs_status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if defs_status != 200 or not isinstance(entity_defs, Mapping):
        return SettingsOutcome(
            intent.entity,
            FAILED,
            detail=(
                f"the instance did not report this object type's definition "
                f"({defs_status}): {format_error_detail(entity_defs)}"
            ),
        )

    client_status, client_defs = client.get_client_defs(wire)
    if client_status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if not isinstance(client_defs, Mapping):
        client_defs = {}

    manual = _manual_steps(intent, entity_defs)
    changed = changed_settings(intent, entity_defs, client_defs)

    if not changed:
        return SettingsOutcome(
            intent.entity,
            SKIPPED,
            detail="already as declared",
            manual_config=manual,
        )
    if preview:
        return SettingsOutcome(
            intent.entity,
            PREVIEWED,
            changed=changed,
            detail=f"would change: {', '.join(changed)}",
            manual_config=manual,
        )

    status, body = client.update_entity(update_payload(intent, changed))
    if status == 401:
        raise AuthenticationRejected(
            "the instance rejected the credential (401); nothing further "
            "can be applied"
        )
    if status == 200:
        return SettingsOutcome(
            intent.entity,
            UPDATED,
            changed=changed,
            detail=f"changed: {', '.join(changed)}",
            manual_config=manual,
        )
    return SettingsOutcome(
        intent.entity,
        FAILED,
        changed=changed,
        detail=(
            f"the instance refused the settings ({status}): "
            f"{format_error_detail(body)}"
        ),
        manual_config=manual,
    )


def _manual_steps(
    intent: SettingsIntent, entity_defs: Mapping[str, Any]
) -> list[str]:
    """What the design asks for that the platform will not accept."""
    manual: list[str] = []
    if intent.multiple_assigned_users is not None:
        if multiple_assigned_users_live(entity_defs) != intent.multiple_assigned_users:
            manual.append(f"{intent.entity}: {_MULTIPLE_ASSIGNED_REASON}")
    return manual


def activity_parent_registration(
    client: EspoWriteClient, entity: str, holder: str = "Meeting"
) -> list[str]:
    """Whether an object type can have meetings and calls filed against it.

    Turning the activity panels on is two things. The panels themselves are a
    layout, which the layout applier writes. Being allowed to file a meeting
    against this object type is a change to the platform's own definition
    files, which its interface does not expose — so this reads whether the
    registration is already there and, when it is not, says what must be done
    by hand.

    Read once rather than polled, deliberately. Version 1 polled here because
    version 1 *wrote* the registration and then verified it, and the platform
    can serve stale definition metadata straight after a cache rebuild. This
    writes nothing, so there is nothing to wait for: a registration absent now
    will be absent in twenty seconds.

    :param client: A client for the target instance.
    :param entity: The design's name for the object type.
    :param holder: The activity to check the registration against.
    :returns: A manual-configuration line, or nothing when already registered.
    """
    status, defs = client.get_entity_defs(holder)
    if status != 200 or not isinstance(defs, Mapping):
        return [
            f"{entity}: could not tell whether meetings and calls may be "
            f"filed against it ({status}). {_ACTIVITY_PARENT_REASON}"
        ]
    parent = ((defs.get("fields") or {}).get("parent") or {})
    registered = wire_entity_name(entity) in (parent.get("entityList") or [])
    if registered:
        return []
    return [f"{entity}: {_ACTIVITY_PARENT_REASON}"]


@dataclass
class ActivityRegistrationOutcome:
    """Whether one object type may yet receive meetings, calls and tasks.

    :ivar name: The object type, as a person would say it.
    :ivar status: :data:`SKIPPED` when it already may, :data:`UNAVAILABLE`
        when somebody must change the server first.
    :ivar detail: Which, in words.
    :ivar manual_config: What that somebody must do.
    """

    name: str
    status: str = SKIPPED
    detail: str = "meetings, calls and tasks may already be filed against it"
    manual_config: list[str] = dataclass_field(default_factory=list)

    @property
    def failed(self) -> bool:
        """Never. A change only a person can make is not a failed run."""
        return False


def check_activity_registration(
    client: EspoWriteClient, entities: Iterable[str]
) -> list[ActivityRegistrationOutcome]:
    """Report, per object type, whether it may yet receive activities.

    Called for every object type the design builds on the base kind that
    carries activities. That base kind is necessary and not sufficient:
    on the client's test instance five object types had it and only three
    were listed as permitted parents, so nobody could file a meeting against
    a contribution — and no publish had ever mentioned it (REQ-636).
    """
    outcomes: list[ActivityRegistrationOutcome] = []
    for entity in entities:
        steps = activity_parent_registration(client, entity)
        if not steps:
            outcomes.append(ActivityRegistrationOutcome(name=entity))
            continue
        outcomes.append(
            ActivityRegistrationOutcome(
                name=entity,
                status=UNAVAILABLE,
                detail=_ACTIVITY_PARENT_REASON,
                manual_config=steps,
            )
        )
    return outcomes
