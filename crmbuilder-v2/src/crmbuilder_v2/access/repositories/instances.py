"""Instance repository — PI-186 entity (PRJ-027).

An instance (``INST-NNN``) is one engagement-scoped connection to a live CRM
system. The standard eight CRUD functions back the ``/instances`` REST
endpoints, plus the ``INST-NNN`` allocator. ``instance_vendor`` /
``instance_role`` / ``instance_auth_method`` / ``instance_status`` are
controlled vocabularies. ``instance_status`` is a free ``active`` ⇄ ``disabled``
toggle (no transition gate).

This layer is secret-agnostic: it stores only the opaque keyring **references**
(``instance_secret_ref`` / ``instance_secret_key_ref``) it is handed. The
plaintext-to-reference translation lives at the API boundary
(:mod:`crmbuilder_v2.api.routers.instances` via :mod:`crmbuilder_v2.secrets`) so
no plaintext secret ever reaches the data layer (REQ-157).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Instance
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    INSTANCE_AUTH_METHODS,
    INSTANCE_ROLES,
    INSTANCE_STATUSES,
    INSTANCE_VENDORS,
)

_ENTITY_TYPE = "instance"
_IDENTIFIER_PREFIX = "INST"
_IDENTIFIER_RE = re.compile(r"^INST-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "vendor",
        "url",
        "role",
        "auth_method",
        "secret_ref",
        "secret_key_ref",
        "status",
        "notes",
    }
)


def _require_vendor(value: object) -> str:
    return gov.require_in(value, INSTANCE_VENDORS, field="instance_vendor")


def _require_role(value: object) -> str:
    return gov.require_in(value, INSTANCE_ROLES, field="instance_role")


def _require_auth_method(value: object) -> str:
    return gov.require_in(value, INSTANCE_AUTH_METHODS, field="instance_auth_method")


def _require_status(value: object) -> str:
    return gov.require_in(value, INSTANCE_STATUSES, field="instance_status")


def _get_row(session: Session, identifier: str) -> Instance:
    row = get_by_identifier(
        session, Instance, Instance.instance_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# --- reads ------------------------------------------------------------------


def list_instances(
    session: Session,
    *,
    include_deleted: bool = False,
    status: str | None = None,
    role: str | None = None,
) -> list[dict]:
    stmt = select(Instance).order_by(Instance.instance_identifier)
    if not include_deleted:
        stmt = stmt.where(Instance.instance_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Instance.instance_status == status)
    if role is not None:
        stmt = stmt.where(Instance.instance_role == role)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_instance(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(
        session, Instance, Instance.instance_identifier, identifier
    )
    if row is None:
        return None
    if row.instance_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_instance_identifier(session: Session) -> str:
    identifiers = session.scalars(select(Instance.instance_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# --- writes -----------------------------------------------------------------


def _new_row(
    identifier,
    name,
    vendor,
    url,
    role,
    auth_method,
    secret_ref,
    secret_key_ref,
    status,
    notes,
) -> Instance:
    return Instance(
        instance_identifier=identifier,
        instance_name=name,
        instance_vendor=vendor,
        instance_url=url,
        instance_role=role,
        instance_auth_method=auth_method,
        instance_secret_ref=secret_ref,
        instance_secret_key_ref=secret_key_ref,
        instance_status=status,
        instance_notes=notes,
    )


def _insert_with_autoassign(session, **kw) -> Instance:
    candidate = next_instance_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **kw)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique instance identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_instance(
    session: Session,
    *,
    name: str,
    url: str,
    vendor: str = "espocrm",
    role: str = "both",
    auth_method: str = "api_key",
    secret_ref: str | None = None,
    secret_key_ref: str | None = None,
    status: str = "active",
    notes: str | None = None,
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    """Create a CRM-connection instance.

    Secrets are passed as opaque keyring references, never plaintext (REQ-157).
    """
    name = gov.require_nonempty(name, field="instance_name")
    url = gov.require_nonempty(url, field="instance_url")
    vendor = _require_vendor(vendor or "espocrm")
    role = _require_role(role or "both")
    auth_method = _require_auth_method(auth_method or "api_key")
    status = _require_status(status or "active")

    kw = {
        "name": name,
        "vendor": vendor,
        "url": url,
        "role": role,
        "auth_method": auth_method,
        "secret_ref": secret_ref,
        "secret_key_ref": secret_key_ref,
        "status": status,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="instance_identifier",
            example="INST-001",
        )
        if (
            get_by_identifier(
                session, Instance, Instance.instance_identifier, identifier
            )
            is not None
        ):
            raise ConflictError(f"instance {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()

    gov.apply_timestamps(row, timestamps)
    session.flush()

    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.instance_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_instance(
    session: Session,
    identifier: str,
    *,
    instance_identifier: str | None = None,
    name: str,
    url: str,
    vendor: str = "espocrm",
    role: str = "both",
    auth_method: str = "api_key",
    secret_ref: str | None = None,
    secret_key_ref: str | None = None,
    status: str = "active",
    notes: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if instance_identifier is not None and instance_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "instance_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    row.instance_name = gov.require_nonempty(name, field="instance_name")
    row.instance_url = gov.require_nonempty(url, field="instance_url")
    row.instance_vendor = _require_vendor(vendor or "espocrm")
    row.instance_role = _require_role(role or "both")
    row.instance_auth_method = _require_auth_method(auth_method or "api_key")
    row.instance_status = _require_status(status or "active")
    row.instance_secret_ref = secret_ref
    row.instance_secret_key_ref = secret_key_ref
    row.instance_notes = notes

    gov.apply_reference_list(session, references)
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


def patch_instance(
    session: Session,
    identifier: str,
    *,
    references: list[dict] | None = None,
    **fields,
) -> dict:
    unknown = set(fields) - _PATCHABLE_FIELDS
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

    gov.apply_reference_list(session, references)

    if "name" in fields:
        row.instance_name = gov.require_nonempty(
            fields["name"], field="instance_name"
        )
    if "url" in fields:
        row.instance_url = gov.require_nonempty(fields["url"], field="instance_url")
    if "vendor" in fields:
        row.instance_vendor = _require_vendor(fields["vendor"])
    if "role" in fields:
        row.instance_role = _require_role(fields["role"])
    if "auth_method" in fields:
        row.instance_auth_method = _require_auth_method(fields["auth_method"])
    if "status" in fields:
        row.instance_status = _require_status(fields["status"])
    if "secret_ref" in fields:
        row.instance_secret_ref = fields["secret_ref"]
    if "secret_key_ref" in fields:
        row.instance_secret_key_ref = fields["secret_key_ref"]
    if "notes" in fields:
        row.instance_notes = fields["notes"]

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


def delete_instance(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.instance_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.instance_deleted_at = datetime.now(UTC)
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


def restore_instance(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.instance_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "instance_deleted_at",
                    "not_deleted",
                    "instance is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.instance_deleted_at = None
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
