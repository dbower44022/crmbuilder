"""Field-permission-rule repository — security design record (PI-051 / REQ-129).

Per the reconciliation decision DEC-698. A ``field_permission_rule``
(``FPR-NNN``) declares the unconditional access level (``read_write`` /
``read_only`` / ``no_access``) a Role has to one target field, so an adapter
can render it into the target CRM's field-permission matrix. The module-level
functions back the ``/field-permission-rules`` REST endpoints and any
access-layer caller:

* :func:`list_field_permission_rules` / :func:`get_field_permission_rule` —
  reads. ``list`` takes optional ``role`` / ``target_field`` /
  ``deployment_status`` filters.
* :func:`create_field_permission_rule` — insert with a server-assigned (or
  explicit) identifier. ``role`` (``ROL-NNN``) and ``target_field``
  (``FLD-NNN``) are each validated to exist and be live; the (role, field) pair
  is checked unique among live rows.
* :func:`update_field_permission_rule` / :func:`patch_field_permission_rule` —
  full / partial update. Subject, permission level, status, and deployment
  status changes are re-validated.
* :func:`delete_field_permission_rule` / :func:`restore_field_permission_rule`
  — soft-delete round-trip.
* :func:`next_field_permission_rule_identifier` — the ``FPR-NNN`` allocator.

Invariants (per DEC-698): role/target_field must resolve live; at most one live
rule per (role, target_field); standard four-status design lifecycle gate; and
**confirmed-before-deploy** — ``deployment_status`` may only leave ``pending``
when ``status == confirmed``.
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
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Field, FieldPermissionRule, Role
from crmbuilder_v2.access.vocab import (
    FIELD_PERMISSION_LEVELS,
    FIELD_RULE_DEPLOYMENT_STATUSES,
    FIELD_RULE_STATUS_TRANSITIONS,
    FIELD_RULE_STATUSES,
)

_ENTITY_TYPE = "field_permission_rule"
_IDENTIFIER_PREFIX = "FPR"
_IDENTIFIER_RE = re.compile(r"^FPR-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "role",
        "target_field",
        "permission_level",
        "status",
        "deployment_status",
        "description",
        "notes",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _fail(field: str, code: str, message: str) -> None:
    raise UnprocessableError([FieldError(field, code, message)])


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        _fail(
            "field_permission_rule_identifier",
            "invalid_format",
            r"must match ^FPR-\d{3}$ (e.g. FPR-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_permission_level(level: object) -> str:
    if level not in FIELD_PERMISSION_LEVELS:
        _fail(
            "field_permission_rule_permission_level",
            "invalid_value",
            f"must be one of {sorted(FIELD_PERMISSION_LEVELS)}",
        )
    return level  # type: ignore[return-value]


def _require_status(status: object) -> str:
    if status not in FIELD_RULE_STATUSES:
        _fail(
            "field_permission_rule_status",
            "invalid_value",
            f"must be one of {sorted(FIELD_RULE_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _require_deployment_status(deployment_status: object) -> str:
    if deployment_status not in FIELD_RULE_DEPLOYMENT_STATUSES:
        _fail(
            "field_permission_rule_deployment_status",
            "invalid_value",
            f"must be one of {sorted(FIELD_RULE_DEPLOYMENT_STATUSES)}",
        )
    return deployment_status  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _require_live_role(role: object, *, session: Session) -> str:
    """Resolve ``role``, requiring it to exist as a live ``ROL-NNN`` row."""
    if not isinstance(role, str) or not role.strip():
        _fail(
            "field_permission_rule_role",
            "missing_role",
            "field_permission_rule_role is required",
        )
    identifier = role.strip()  # type: ignore[union-attr]
    row = get_by_identifier(session, Role, Role.role_identifier, identifier)
    if row is None:
        _fail(
            "field_permission_rule_role",
            "invalid_role",
            f"role {identifier!r} not found",
        )
    if row.role_deleted_at is not None:
        _fail(
            "field_permission_rule_role",
            "invalid_role",
            f"role {identifier!r} is soft-deleted",
        )
    return identifier


def _require_live_field(target_field: object, *, session: Session) -> str:
    """Resolve ``target_field`` to a live ``FLD-NNN`` row."""
    if not isinstance(target_field, str) or not target_field.strip():
        _fail(
            "field_permission_rule_target_field",
            "missing_target_field",
            "field_permission_rule_target_field is required",
        )
    identifier = target_field.strip()  # type: ignore[union-attr]
    row = get_by_identifier(session, Field, Field.field_identifier, identifier)
    if row is None:
        _fail(
            "field_permission_rule_target_field",
            "invalid_target_field",
            f"field {identifier!r} not found",
        )
    if row.field_deleted_at is not None:
        _fail(
            "field_permission_rule_target_field",
            "invalid_target_field",
            f"field {identifier!r} is soft-deleted",
        )
    return identifier


def _require_unique_pair(
    role: str,
    target_field: str,
    *,
    session: Session,
    exclude_identifier: str | None = None,
) -> None:
    """Reject a second live rule for the same (role, target_field) cell."""
    stmt = select(FieldPermissionRule.field_permission_rule_identifier).where(
        FieldPermissionRule.field_permission_rule_role == role,
        FieldPermissionRule.field_permission_rule_target_field == target_field,
        FieldPermissionRule.field_permission_rule_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            FieldPermissionRule.field_permission_rule_identifier
            != exclude_identifier
        )
    if session.scalars(stmt).first() is not None:
        raise ConflictError(
            "a live field_permission_rule already exists for "
            f"(role={role!r}, target_field={target_field!r})"
        )


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in FIELD_RULE_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _require_confirmed_before_deploy(
    status: str, deployment_status: str
) -> None:
    """Only a ``confirmed`` rule may leave ``deployment_status == pending``."""
    if deployment_status != "pending" and status != "confirmed":
        _fail(
            "field_permission_rule_deployment_status",
            "deploy_before_confirmed",
            "deployment_status may only leave 'pending' once status is "
            "'confirmed'",
        )


def _get_row(session: Session, identifier: str) -> FieldPermissionRule:
    row = get_by_identifier(
        session,
        FieldPermissionRule,
        FieldPermissionRule.field_permission_rule_identifier,
        identifier,
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_field_permission_rules(
    session: Session,
    *,
    role: str | None = None,
    target_field: str | None = None,
    deployment_status: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return rules ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``role`` / ``target_field`` / ``deployment_status`` filter the columns.
    """
    stmt = select(FieldPermissionRule).order_by(
        FieldPermissionRule.field_permission_rule_identifier
    )
    if role is not None:
        stmt = stmt.where(
            FieldPermissionRule.field_permission_rule_role == role
        )
    if target_field is not None:
        stmt = stmt.where(
            FieldPermissionRule.field_permission_rule_target_field
            == target_field
        )
    if deployment_status is not None:
        stmt = stmt.where(
            FieldPermissionRule.field_permission_rule_deployment_status
            == deployment_status
        )
    if not include_deleted:
        stmt = stmt.where(
            FieldPermissionRule.field_permission_rule_deleted_at.is_(None)
        )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_field_permission_rule(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single rule by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session,
        FieldPermissionRule,
        FieldPermissionRule.field_permission_rule_identifier,
        identifier,
    )
    if row is None:
        return None
    if (
        row.field_permission_rule_deleted_at is not None
        and not include_deleted
    ):
        return None
    return to_dict(row)


def next_field_permission_rule_identifier(session: Session) -> str:
    """Return the next available ``FPR-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(FieldPermissionRule.field_permission_rule_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    role: str,
    target_field: str,
    permission_level: str,
    status: str,
    deployment_status: str,
    description: str | None,
    notes: str | None,
) -> FieldPermissionRule:
    return FieldPermissionRule(
        field_permission_rule_identifier=identifier,
        field_permission_rule_name=name,
        field_permission_rule_role=role,
        field_permission_rule_target_field=target_field,
        field_permission_rule_permission_level=permission_level,
        field_permission_rule_status=status,
        field_permission_rule_deployment_status=deployment_status,
        field_permission_rule_description=description,
        field_permission_rule_notes=notes,
    )


def _insert_with_autoassign(
    session: Session, **columns
) -> FieldPermissionRule:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_field_permission_rule_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **columns)
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
        "could not assign a unique field_permission_rule identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_field_permission_rule(
    session: Session,
    *,
    name: str,
    role: str,
    target_field: str,
    permission_level: str,
    status: str | None = None,
    deployment_status: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a field_permission_rule.

    Validation order: ``name`` non-empty; ``permission_level`` in vocab;
    ``status`` defaults to ``candidate``; ``deployment_status`` defaults to
    ``pending``; confirmed-before-deploy; ``role`` / ``target_field`` resolve
    live; the (role, field) pair is unique among live rows; then insert.
    """
    name = _require_nonempty(name, field="field_permission_rule_name")
    permission_level = _require_permission_level(permission_level)
    if status is None:
        status = "candidate"
    status = _require_status(status)
    if deployment_status is None:
        deployment_status = "pending"
    deployment_status = _require_deployment_status(deployment_status)
    _require_confirmed_before_deploy(status, deployment_status)
    description = _optional_text(
        description, field="field_permission_rule_description"
    )
    notes = _optional_text(notes, field="field_permission_rule_notes")
    role = _require_live_role(role, session=session)
    target_field = _require_live_field(target_field, session=session)
    _require_unique_pair(role, target_field, session=session)

    columns = {
        "name": name,
        "role": role,
        "target_field": target_field,
        "permission_level": permission_level,
        "status": status,
        "deployment_status": deployment_status,
        "description": description,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(
                session,
                FieldPermissionRule,
                FieldPermissionRule.field_permission_rule_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(
                f"field_permission_rule {identifier!r} already exists"
            )
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.field_permission_rule_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_field_permission_rule(
    session: Session,
    identifier: str,
    *,
    field_permission_rule_identifier: str | None = None,
    name: str,
    role: str,
    target_field: str,
    permission_level: str,
    status: str,
    deployment_status: str,
    description: str | None = None,
    notes: str | None = None,
) -> dict:
    """Full-replace update (PUT)."""
    row = _get_row(session, identifier)
    if (
        field_permission_rule_identifier is not None
        and field_permission_rule_identifier != identifier
    ):
        _fail(
            "field_permission_rule_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="field_permission_rule_name")
    permission_level = _require_permission_level(permission_level)
    description = _optional_text(
        description, field="field_permission_rule_description"
    )
    notes = _optional_text(notes, field="field_permission_rule_notes")
    role = _require_live_role(role, session=session)
    target_field = _require_live_field(target_field, session=session)
    _require_unique_pair(
        role, target_field, session=session, exclude_identifier=identifier
    )

    status_v = _require_status(status)
    if status_v != row.field_permission_rule_status:
        _check_transition(row.field_permission_rule_status, status_v)
    deployment_status_v = _require_deployment_status(deployment_status)
    _require_confirmed_before_deploy(status_v, deployment_status_v)

    row.field_permission_rule_name = name
    row.field_permission_rule_role = role
    row.field_permission_rule_target_field = target_field
    row.field_permission_rule_permission_level = permission_level
    row.field_permission_rule_status = status_v
    row.field_permission_rule_deployment_status = deployment_status_v
    row.field_permission_rule_description = description
    row.field_permission_rule_notes = notes
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


def patch_field_permission_rule(
    session: Session, identifier: str, **fields
) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched."""
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        _fail(
            "fields",
            "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}",
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    if "name" in fields:
        row.field_permission_rule_name = _require_nonempty(
            fields["name"], field="field_permission_rule_name"
        )
    if "permission_level" in fields:
        row.field_permission_rule_permission_level = _require_permission_level(
            fields["permission_level"]
        )
    if "description" in fields:
        row.field_permission_rule_description = _optional_text(
            fields["description"], field="field_permission_rule_description"
        )
    if "notes" in fields:
        row.field_permission_rule_notes = _optional_text(
            fields["notes"], field="field_permission_rule_notes"
        )

    # role / target_field are co-validated: a change to either re-resolves and
    # re-checks the (role, field) uniqueness against the (possibly new) pair.
    if "role" in fields or "target_field" in fields:
        role = _require_live_role(
            fields.get("role", row.field_permission_rule_role),
            session=session,
        )
        target_field = _require_live_field(
            fields.get(
                "target_field", row.field_permission_rule_target_field
            ),
            session=session,
        )
        _require_unique_pair(
            role,
            target_field,
            session=session,
            exclude_identifier=identifier,
        )
        row.field_permission_rule_role = role
        row.field_permission_rule_target_field = target_field

    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.field_permission_rule_status:
            _check_transition(row.field_permission_rule_status, status_v)
            row.field_permission_rule_status = status_v
    if "deployment_status" in fields:
        row.field_permission_rule_deployment_status = (
            _require_deployment_status(fields["deployment_status"])
        )
    _require_confirmed_before_deploy(
        row.field_permission_rule_status,
        row.field_permission_rule_deployment_status,
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


def delete_field_permission_rule(session: Session, identifier: str) -> dict:
    """Soft-delete the rule. Idempotent."""
    row = _get_row(session, identifier)
    if row.field_permission_rule_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.field_permission_rule_deleted_at = datetime.now(UTC)
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


def restore_field_permission_rule(session: Session, identifier: str) -> dict:
    """Clear the soft-delete. Raises 422 if the row is live or the (role,
    target_field) cell is now occupied by another live rule."""
    row = _get_row(session, identifier)
    if row.field_permission_rule_deleted_at is None:
        _fail(
            "field_permission_rule_deleted_at",
            "not_deleted",
            "field_permission_rule is not soft-deleted",
        )
    _require_unique_pair(
        row.field_permission_rule_role,
        row.field_permission_rule_target_field,
        session=session,
        exclude_identifier=identifier,
    )
    before = to_dict(row)
    row.field_permission_rule_deleted_at = None
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
