"""System-settings repository — PI-406 (REQ-485 / REQ-488, DEC-918).

A system setting (``SET-NNN``) is the one design construct whose value is per
instance. Every other record describes something every instance must hold
identically; this one describes something every instance must *have*, while what
it holds is that instance's own — an outbound email address differing between
chapters is not drift, it is that chapter's.

The split matters and is the whole reason for two tables. ``system_settings``
governs *which* settings exist and what shape their values take;
:func:`set_value` records what a named instance is *declared* to hold. Declared
is not observed: an audit's reading is compared against the declaration, and
keeping them apart is what lets reconcile distinguish "holds the wrong value"
from "nobody has said what this instance should hold". The second is REQ-485's
third outcome and must never read as conformant, which is why the absence of a
value row is meaningful and is never stood in for by an empty one.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import (
    Field,
    FieldOption,
    SystemSetting,
    SystemSettingValue,
)
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import FIELD_TYPES, SYSTEM_SETTING_STATUSES

_ENTITY_TYPE = "system_setting"
_PREFIX = "SET"
_IDENTIFIER_RE = re.compile(r"^SET-\d{3}$")
_FIELD_IDENTIFIER_RE = re.compile(r"^FLD-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE = frozenset(
    {
        "key",
        "name",
        "value_type",
        "description",
        "status",
        "notes",
        "active_subset_field",
    }
)


def _require_status(v: object) -> str:
    return gov.require_in(v, SYSTEM_SETTING_STATUSES, field="system_setting_status")


def _require_value_type(v: object) -> str:
    """The value's shape, from the field vocabulary rather than a parallel one.

    PI-414 made that vocabulary able to describe any value a CRM can hold, and a
    setting's value is such a value; a second vocabulary would be a second thing
    to keep correct.
    """
    return gov.require_in(v, FIELD_TYPES, field="system_setting_value_type")


def _complete_option_values(session: Session, field_identifier: str) -> list[str]:
    """The field's complete option list, in business order (REQ-486)."""
    rows = session.scalars(
        select(FieldOption)
        .where(FieldOption.field_identifier == field_identifier)
        .order_by(FieldOption.option_order, FieldOption.id)
    ).all()
    return [r.option_value for r in rows]


def _require_active_subset_field(
    session: Session, value: object
) -> str | None:
    """Validate the field a setting would narrow (PI-407 / REQ-486, REQ-487).

    ``None`` is an ordinary setting. Otherwise the field must exist and be
    live, must be an ``enum`` (the only kind that carries a complete option
    list to draw a subset from), and must be classified data-bearing. The
    last is the whole safety property: a field anything branches on is
    permanently ineligible, and the answer is a refusal that names the field
    and the reason — never a warning, because a warning is read once by the
    person declaring and never again by the person who later adds the branch.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not _FIELD_IDENTIFIER_RE.match(value):
        raise UnprocessableError(
            [
                FieldError(
                    "system_setting_active_subset_field",
                    "invalid_format",
                    "must look like FLD-001",
                )
            ]
        )
    row = get_by_identifier(session, Field, Field.field_identifier, value)
    if row is None or row.field_deleted_at is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "system_setting_active_subset_field",
                    "field_not_found",
                    f"field {value!r} does not exist or is deleted",
                )
            ]
        )
    if row.field_type != "enum":
        raise UnprocessableError(
            [
                FieldError(
                    "system_setting_active_subset_field",
                    "not_an_option_field",
                    f"field {value!r} ({row.field_name}) is of type "
                    f"{row.field_type!r}; only an enum field carries a complete "
                    "option list an active subset can be drawn from",
                )
            ]
        )
    if not row.field_data_bearing:
        raise UnprocessableError(
            [
                FieldError(
                    "system_setting_active_subset_field",
                    "not_data_bearing",
                    f"field {value!r} ({row.field_name}) is not classified "
                    "data-bearing; only a data-bearing field may carry a "
                    "variable active subset (REQ-487)",
                )
            ]
        )
    return value


def _require_subset_value(
    session: Session, setting: SystemSetting, value: Any
) -> list[str]:
    """Validate an active-subset declaration against the complete list.

    The value is the list of option values active on one instance. Every
    entry must be one of the field's complete option values — the subset
    names *which* of the deployed values are active and can never introduce a
    value the deployed list does not hold (REQ-486). Order and duplicates are
    normalised away: the subset is a set, the complete list carries the order.
    """
    field_identifier = setting.system_setting_active_subset_field
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise UnprocessableError(
            [
                FieldError(
                    "value",
                    "invalid_value",
                    f"{setting.system_setting_identifier} names the active "
                    f"subset of field {field_identifier!r}; its value must be a "
                    "list of that field's option values",
                )
            ]
        )
    complete = _complete_option_values(session, field_identifier)
    unknown = sorted({v for v in value if v not in complete})
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "value",
                    "not_in_complete_option_list",
                    f"{unknown!r} not in the complete option list of field "
                    f"{field_identifier!r} ({complete!r}); an active subset "
                    "may only name values every instance already holds "
                    "(REQ-486)",
                )
            ]
        )
    wanted = set(value)
    return [v for v in complete if v in wanted]


def _get_row(session: Session, identifier: str) -> SystemSetting:
    row = get_by_identifier(
        session, SystemSetting, SystemSetting.system_setting_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment(identifier: str) -> str:
    return f"{_PREFIX}-{int(identifier.split('-', 1)[1]) + 1:03d}"


def list_system_settings(
    session: Session,
    *,
    include_deleted: bool = False,
    status: str | None = None,
    active_subset_field: str | None = None,
) -> list[dict]:
    """Governed settings; ``active_subset_field`` narrows to the settings that
    name one field's active subset (PI-407)."""
    stmt = select(SystemSetting).order_by(SystemSetting.system_setting_identifier)
    if not include_deleted:
        stmt = stmt.where(SystemSetting.system_setting_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(SystemSetting.system_setting_status == status)
    if active_subset_field is not None:
        stmt = stmt.where(
            SystemSetting.system_setting_active_subset_field == active_subset_field
        )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def active_subsets_for_field(session: Session, field_identifier: str) -> dict:
    """One field's classification alongside every active subset declared on it.

    REQ-487's third acceptance clause: whenever the design is asked about a
    field carrying a variable active subset, its data-bearing classification
    comes back with it. The complete option list is returned too, so a reader
    can see what each instance's subset is a subset *of*.
    """
    row = get_by_identifier(session, Field, Field.field_identifier, field_identifier)
    if row is None or row.field_deleted_at is not None:
        raise NotFoundError("field", field_identifier)
    subsets = []
    for setting in list_system_settings(
        session, active_subset_field=field_identifier
    ):
        subsets.append(
            {
                **setting,
                "values": list_values(
                    session,
                    system_setting_identifier=setting["system_setting_identifier"],
                ),
            }
        )
    return {
        "field_identifier": row.field_identifier,
        "field_name": row.field_name,
        "field_data_bearing": bool(row.field_data_bearing),
        "complete_option_list": _complete_option_values(session, field_identifier),
        "active_subsets": subsets,
    }


def get_system_setting(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(
        session, SystemSetting, SystemSetting.system_setting_identifier, identifier
    )
    if row is None or (
        row.system_setting_deleted_at is not None and not include_deleted
    ):
        return None
    return to_dict(row)


def next_system_setting_identifier(session: Session) -> str:
    return next_prefixed_identifier(
        session.scalars(select(SystemSetting.system_setting_identifier)).all(),
        _PREFIX,
    )


def _new_row(
    identifier,
    key,
    name,
    value_type,
    description,
    status,
    notes,
    active_subset_field=None,
):
    return SystemSetting(
        system_setting_identifier=identifier,
        system_setting_key=key,
        system_setting_name=name,
        system_setting_value_type=value_type,
        system_setting_description=description,
        system_setting_status=status,
        system_setting_notes=notes,
        system_setting_active_subset_field=active_subset_field,
    )


def _insert_with_autoassign(session, **kw) -> SystemSetting:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent Postgres
    # writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _PREFIX)
    candidate = next_system_setting_identifier(session)
    last: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        sp = session.begin_nested()
        row = _new_row(candidate, **kw)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last = exc
            sp.rollback()
            candidate = _increment(candidate)
            continue
        sp.commit()
        return row
    raise ConflictError(
        "could not assign a unique system_setting identifier"
    ) from last


def create_system_setting(
    session: Session,
    *,
    key: str,
    name: str,
    value_type: str,
    description: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    identifier: str | None = None,
    active_subset_field: str | None = None,
) -> dict:
    """Declare one governed system setting.

    ``active_subset_field`` makes it the setting that names one enum field's
    per-instance active subset (PI-407); refused unless that field is
    classified data-bearing (REQ-487).
    """
    key = gov.require_nonempty(key, field="system_setting_key")
    name = gov.require_nonempty(name, field="system_setting_name")
    value_type = _require_value_type(value_type)
    status = _require_status(status if status is not None else "candidate")
    active_subset_field = _require_active_subset_field(session, active_subset_field)

    # Check the key before entering the identifier allocator. The allocator
    # retries on IntegrityError because it expects an identifier collision, and
    # a duplicate key is a different constraint entirely — left to it, one
    # governed key being declared twice burns fifty attempts and surfaces as an
    # allocator failure rather than as what it is.
    existing = session.scalars(
        select(SystemSetting).where(
            SystemSetting.system_setting_key == key,
            SystemSetting.system_setting_deleted_at.is_(None),
        )
    ).first()
    if existing is not None:
        raise ConflictError(
            f"system setting {existing.system_setting_identifier} already governs "
            f"key {key!r}"
        )

    columns = {
        "key": key,
        "name": name,
        "value_type": value_type,
        "description": description,
        "status": status,
        "notes": notes,
        "active_subset_field": active_subset_field,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        if not _IDENTIFIER_RE.match(identifier):
            raise UnprocessableError(
                [
                    FieldError(
                        "system_setting_identifier",
                        "invalid_format",
                        "identifier must look like SET-001",
                    )
                ]
            )
        if (
            get_by_identifier(
                session,
                SystemSetting,
                SystemSetting.system_setting_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"system_setting {identifier!r} already exists")
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.system_setting_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def patch_system_setting(session: Session, identifier: str, **fields) -> dict:
    unknown = set(fields) - _PATCHABLE
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown patchable fields: {sorted(unknown)}",
                )
            ]
        )
    row = _get_row(session, identifier)
    before = to_dict(row)
    if "key" in fields:
        row.system_setting_key = gov.require_nonempty(
            fields["key"], field="system_setting_key"
        )
    if "name" in fields:
        row.system_setting_name = gov.require_nonempty(
            fields["name"], field="system_setting_name"
        )
    if "value_type" in fields:
        row.system_setting_value_type = _require_value_type(fields["value_type"])
    if "description" in fields:
        row.system_setting_description = fields["description"]
    if "notes" in fields:
        row.system_setting_notes = fields["notes"]
    if "status" in fields:
        row.system_setting_status = _require_status(fields["status"])
    if "active_subset_field" in fields:
        row.system_setting_active_subset_field = _require_active_subset_field(
            session, fields["active_subset_field"]
        )
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


# ---------------------------------------------------------------------------
# Per-instance declared values
# ---------------------------------------------------------------------------


def list_values(
    session: Session,
    *,
    system_setting_identifier: str | None = None,
    instance_identifier: str | None = None,
) -> list[dict]:
    """Declared values, optionally narrowed to one setting or one instance."""
    stmt = select(SystemSettingValue).order_by(SystemSettingValue.id)
    if system_setting_identifier is not None:
        stmt = stmt.where(
            SystemSettingValue.system_setting_identifier
            == system_setting_identifier
        )
    if instance_identifier is not None:
        stmt = stmt.where(
            SystemSettingValue.instance_identifier == instance_identifier
        )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_value(
    session: Session, *, system_setting_identifier: str, instance_identifier: str
) -> dict | None:
    """The value this instance is declared to hold, or ``None`` if undeclared.

    ``None`` is a real answer and the normal starting state — nobody has said
    what this instance should hold. It must stay distinguishable from a declared
    value that happens to be empty, which is why no placeholder row is written.
    """
    rows = list_values(
        session,
        system_setting_identifier=system_setting_identifier,
        instance_identifier=instance_identifier,
    )
    return rows[0] if rows else None


def set_value(
    session: Session,
    *,
    system_setting_identifier: str,
    instance_identifier: str,
    value: Any,
) -> dict:
    """Declare what one instance should hold for one governed setting.

    For a setting that names a field's active subset the value is the list of
    option values active on that instance, checked against the field's
    complete option list (REQ-486).
    """
    setting = _get_row(session, system_setting_identifier)  # 404 if unknown
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    if setting.system_setting_active_subset_field is not None:
        value = _require_subset_value(session, setting, value)
    stmt = select(SystemSettingValue).where(
        SystemSettingValue.system_setting_identifier == system_setting_identifier,
        SystemSettingValue.instance_identifier == instance_identifier,
    )
    row = session.scalars(stmt).first()
    now = datetime.now(UTC)
    if row is None:
        row = SystemSettingValue(
            system_setting_identifier=system_setting_identifier,
            instance_identifier=instance_identifier,
            value=value,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.value = value
        row.updated_at = now
    session.flush()
    return to_dict(row)


def clear_value(
    session: Session, *, system_setting_identifier: str, instance_identifier: str
) -> bool:
    """Withdraw a declaration, returning it to undeclared.

    Deleting the row rather than nulling its value is deliberate: a row holding
    NULL would be a declaration that the instance should hold nothing, which is
    a different statement from nobody having decided.
    """
    stmt = select(SystemSettingValue).where(
        SystemSettingValue.system_setting_identifier == system_setting_identifier,
        SystemSettingValue.instance_identifier == instance_identifier,
    )
    row = session.scalars(stmt).first()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def delete_system_setting(session: Session, identifier: str) -> dict:
    """Soft-delete a governed setting; idempotent.

    The declared values are deliberately left in place. A setting withdrawn from
    governance and later restored should come back with what each instance was
    said to hold, and discarding those on the way out would make an undo lossy
    for no gain — nothing reads a deleted setting's values.
    """
    row = _get_row(session, identifier)
    if row.system_setting_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.system_setting_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def restore_system_setting(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.system_setting_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "system_setting_deleted_at",
                    "not_deleted",
                    "system_setting is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.system_setting_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after
