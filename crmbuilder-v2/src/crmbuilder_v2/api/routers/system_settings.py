"""System-settings endpoints — PI-406 (REQ-485 / DEC-918).

The governed-setting routes plus the per-instance value routes, delegating to
:mod:`crmbuilder_v2.access.repositories.system_settings`. Bodies use the
parent-prefixed ``system_setting_*`` names; responses use the v2
``{data, meta, errors}`` envelope. Static routes (``next-identifier``) precede
``/{identifier}`` — route order is load-bearing.

The value routes are separate from the setting routes on purpose. A setting is
the design's governed declaration and is the same for every instance; a value is
one instance's own. Folding the value into the setting body would make the two
look like one record and invite writing a value that belongs to nobody.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import system_settings
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    SystemSettingCreateIn,
    SystemSettingPatchIn,
    SystemSettingValueIn,
)

router = APIRouter(prefix="/system-settings", tags=["system-settings"])

_PREFIX = "system_setting_"


@router.get("")
def list_all(include_deleted: bool = False, status: str | None = None):
    with readonly_session() as s:
        return ok(
            system_settings.list_system_settings(
                s, include_deleted=include_deleted, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``SET-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": system_settings.next_system_setting_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = system_settings.get_system_setting(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("system_setting", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: SystemSettingCreateIn):
    with writable_session() as s:
        return ok(
            system_settings.create_system_setting(
                s,
                key=body.system_setting_key,
                name=body.system_setting_name,
                value_type=body.system_setting_value_type,
                description=body.system_setting_description,
                status=body.system_setting_status,
                notes=body.system_setting_notes,
                identifier=body.system_setting_identifier,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: SystemSettingPatchIn):
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(system_settings.patch_system_setting(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(system_settings.delete_system_setting(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(system_settings.restore_system_setting(s, identifier))


# --- per-instance declared values -------------------------------------------


@router.get("/{identifier}/values")
def list_values(identifier: str):
    """Every instance's declared value for this setting.

    An instance with no declaration simply does not appear. That absence is the
    answer — nobody has said what it should hold — and is not padded out with a
    null row, because the two are different states (REQ-485).
    """
    with readonly_session() as s:
        if system_settings.get_system_setting(s, identifier) is None:
            raise NotFoundError("system_setting", identifier)
        return ok(
            system_settings.list_values(s, system_setting_identifier=identifier)
        )


@router.get("/{identifier}/values/{instance_identifier}")
def get_value(identifier: str, instance_identifier: str):
    with readonly_session() as s:
        if system_settings.get_system_setting(s, identifier) is None:
            raise NotFoundError("system_setting", identifier)
        record = system_settings.get_value(
            s,
            system_setting_identifier=identifier,
            instance_identifier=instance_identifier,
        )
        if record is None:
            raise NotFoundError(
                "system_setting_value", f"{identifier}/{instance_identifier}"
            )
        return ok(record)


@router.put("/{identifier}/values/{instance_identifier}")
def set_value(
    identifier: str, instance_identifier: str, body: SystemSettingValueIn
):
    """Declare what one instance should hold for this setting."""
    with writable_session() as s:
        return ok(
            system_settings.set_value(
                s,
                system_setting_identifier=identifier,
                instance_identifier=instance_identifier,
                value=body.value,
            )
        )


@router.delete("/{identifier}/values/{instance_identifier}")
def clear_value(identifier: str, instance_identifier: str):
    """Withdraw a declaration, returning this instance to undeclared."""
    with writable_session() as s:
        cleared = system_settings.clear_value(
            s,
            system_setting_identifier=identifier,
            instance_identifier=instance_identifier,
        )
        if not cleared:
            raise NotFoundError(
                "system_setting_value", f"{identifier}/{instance_identifier}"
            )
        return ok({"cleared": True})
