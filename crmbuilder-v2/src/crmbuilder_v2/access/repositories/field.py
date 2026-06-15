"""Field repository — the sixth methodology entity type (v0.5+, PI-004
first slice).

Per ``methodology-schema-specs/field.md``. The eight module-level
functions back the ``/fields`` REST endpoints and the desktop panel:

* :func:`list_fields` / :func:`get_field` — reads. ``list_fields``
  supports an ``entity_identifier=ENT-NNN`` filter per spec §3.5.5
  that joins the ``refs`` table to surface only fields whose live
  ``field_belongs_to_entity`` edge points to the supplied entity.
* :func:`create_field` — atomic insert of the field row PLUS its
  outgoing ``field_belongs_to_entity`` edge in one transaction per
  spec §3.5.4. Identifier is server-assigned by default (PI-002).
* :func:`update_field` — full replace (PUT). Does NOT re-parent — that
  requires explicit DELETE-then-POST edge management per spec §3.5.4
  (PI-053 tracks the convenience endpoint).
* :func:`patch_field` — partial update (PATCH). Same no-reparent rule.
* :func:`delete_field` / :func:`restore_field` — soft-delete round-trip
  that atomically detaches/reattaches the parent-entity edge per spec
  §3.4.6. The stash column
  ``field_previous_parent_entity_identifier`` carries the
  previously-attached entity identifier across the soft-deleted state.
* :func:`next_field_identifier` — the ``FLD-NNN`` allocator helper.

Validation posture (``field.md`` §3.5): identifier-format,
per-entity-scoped case-insensitive name-uniqueness, status-enum,
type-enum, parent-entity-exists, and PUT identifier/path mismatches
raise :class:`UnprocessableError` (HTTP 422); disallowed status
transitions raise :class:`StatusTransitionError` (HTTP 422 with the
dedicated body shape). Missing fields raise :class:`NotFoundError`
(404); an explicit-identifier collision on create raises
:class:`ConflictError` (409).

Two cross-spec deviations from the cross-spec defaults:

* **Atomic POST.** The ``create_field`` signature requires a
  ``field_belongs_to_entity_identifier`` kwarg; the row and the edge
  land in the same enclosing transaction. The decomposed alternative
  (POST row, then POST edge) was rejected to avoid a transient
  invalid state per spec §3.5.4.
* **Per-entity name uniqueness.** The same ``field_name`` value may
  appear on multiple parent entities (``Contact.status`` and
  ``Mentor.status`` are both valid). Uniqueness is enforced on the
  ``(parent_entity_identifier, lower(field_name))`` pair via a refs
  lookup at validate-time. Spec §3.2.3.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
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
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.formulas import FormulaError, validate_formula
from crmbuilder_v2.access.models import Entity, Field, FieldOption, Reference
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    DERIVED_RESULT_TYPES,
    FIELD_FORMATS,
    FIELD_NUMERIC_SCALES,
    FIELD_STATUS_TRANSITIONS,
    FIELD_STATUSES,
    FIELD_TYPES,
)

_ENTITY_TYPE = "field"
_IDENTIFIER_PREFIX = "FLD"
_IDENTIFIER_RE = re.compile(r"^FLD-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# PRJ-025 PI-182 — intrinsic engine-neutral design-intent attributes
# (§7). Each maps an unprefixed repo kwarg (the form the router forwards)
# to its ``field_*`` column. ``format`` / ``numeric_scale`` are
# enum-validated; ``max_length`` is integer-coerced; the three booleans
# are coerced via ``bool``; the rest are stored as the authored string.
_INTRINSIC_COLUMN_BY_KWARG: dict[str, str] = {
    "tooltip": "field_tooltip",
    "usage_summary": "field_usage_summary",
    "default_value": "field_default_value",
    "format": "field_format",
    "numeric_scale": "field_numeric_scale",
    "max_length": "field_max_length",
    "min": "field_min",
    "max": "field_max",
    "read_only": "field_read_only",
    "unique": "field_unique",
    "externally_populated": "field_externally_populated",
}
_INTRINSIC_BOOL_KWARGS = frozenset(
    {"read_only", "unique", "externally_populated"}
)

# PRJ-025 PI-197 (design §7/§9, DEC-438) — derived/formula kwargs. These
# carry cross-field semantics (gated on the effective ``field_type``) so
# they are handled outside the flat ``_INTRINSIC_COLUMN_BY_KWARG`` map:
# ``derived_result_type`` must be a DERIVED_RESULT_TYPES value present iff
# the field is ``derived``; ``formula`` is the neutral structured-formula
# AST, validated via ``access.formulas`` when supplied.
_DERIVED_COLUMN_BY_KWARG: dict[str, str] = {
    "derived_result_type": "field_derived_result_type",
    "formula": "field_formula",
}

# Fields accepted by :func:`patch_field`. The identifier, timestamps,
# and the parent-entity stash column are not patchable. Re-parenting
# is not allowed via PATCH (spec §3.5.4); use explicit edge management.
# ``options`` (the field_options child set) is handled out-of-band.
_PATCHABLE_FIELDS = frozenset(
    {"name", "description", "type", "required", "notes", "status"}
    | set(_INTRINSIC_COLUMN_BY_KWARG)
    | set(_DERIVED_COLUMN_BY_KWARG)
    | {"options"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "field_identifier",
                    "invalid_format",
                    r"must match ^FLD-\d{3}$ (e.g. FLD-001)",
                )
            ]
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value.strip()


def _require_status(status: object) -> str:
    if status not in FIELD_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "field_status",
                    "invalid_value",
                    f"must be one of {sorted(FIELD_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _require_type(field_type: object) -> str:
    if field_type not in FIELD_TYPES:
        raise UnprocessableError(
            [
                FieldError(
                    "field_type",
                    "invalid_value",
                    f"must be one of {sorted(FIELD_TYPES)}",
                )
            ]
        )
    return field_type  # type: ignore[return-value]


def _require_enum_or_none(
    value: object, allowed: frozenset[str], field: str
) -> str | None:
    """Return ``value`` if it is in ``allowed``; ``None`` for null/empty.

    Used for the optional ``field_format`` / ``field_numeric_scale``
    neutral tokens (PRJ-025 §7) — validated only when present.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if value not in allowed:
        raise UnprocessableError(
            [
                FieldError(
                    field,
                    "invalid_value",
                    f"must be null or one of {sorted(allowed)}",
                )
            ]
        )
    return value  # type: ignore[return-value]


def _coerce_int_or_none(value: object, field: str) -> int | None:
    """Coerce a non-null ``field_max_length`` to ``int`` or raise 422."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnprocessableError(
            [FieldError(field, "invalid_value", "must be an integer or null")]
        )
    return value


def _coerce_intrinsic(kwarg: str, value: object) -> object:
    """Validate one intrinsic kwarg, returning the storable column value."""
    if kwarg in _INTRINSIC_BOOL_KWARGS:
        return bool(value)
    if kwarg == "format":
        return _require_enum_or_none(value, FIELD_FORMATS, "field_format")
    if kwarg == "numeric_scale":
        return _require_enum_or_none(
            value, FIELD_NUMERIC_SCALES, "field_numeric_scale"
        )
    if kwarg == "max_length":
        return _coerce_int_or_none(value, "field_max_length")
    # Remaining text-valued intrinsics are stored as the authored string;
    # ``None`` clears.
    if value is not None and not isinstance(value, str):
        raise UnprocessableError(
            [
                FieldError(
                    _INTRINSIC_COLUMN_BY_KWARG[kwarg],
                    "invalid_value",
                    "must be a string or null",
                )
            ]
        )
    return value


def _validate_intrinsic_kwargs(provided: dict) -> dict:
    """Reject any kwarg that is not a recognised intrinsic, else echo it.

    Value validation happens later in :func:`_apply_intrinsics`; this is
    the guard that turns a typo'd ``**intrinsics`` key into a 422 rather
    than a silently-ignored field.
    """
    unknown = set(provided) - set(_INTRINSIC_COLUMN_BY_KWARG)
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown field attributes: {sorted(unknown)}",
                )
            ]
        )
    return provided


def _apply_intrinsics(row: Field, provided: dict) -> None:
    """Validate + assign the intrinsic kwargs present in ``provided``."""
    for kwarg, column in _INTRINSIC_COLUMN_BY_KWARG.items():
        if kwarg in provided:
            setattr(row, column, _coerce_intrinsic(kwarg, provided[kwarg]))


def _coerce_result_type_or_none(value: object) -> str | None:
    """Validate ``derived_result_type`` against DERIVED_RESULT_TYPES.

    ``None`` / empty clears the column; any other value must be one of
    the allowed result types (PRJ-025 PI-197, design §7/§9). The
    required-when-derived / forbidden-otherwise rule is checked by
    :func:`_apply_derived` against the field's effective type.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if value not in DERIVED_RESULT_TYPES:
        raise UnprocessableError(
            [
                FieldError(
                    "field_derived_result_type",
                    "invalid_value",
                    f"must be null or one of {sorted(DERIVED_RESULT_TYPES)}",
                )
            ]
        )
    return value  # type: ignore[return-value]


def _validate_formula_or_none(value: object) -> dict | None:
    """Validate the neutral structured formula AST, returning it or ``None``.

    ``None`` clears the column; a present value is validated against the
    ``access.formulas`` shape and a malformation raises a field-scoped 422.
    """
    if value is None:
        return None
    try:
        validate_formula(value)
    except FormulaError as exc:
        raise UnprocessableError(
            [FieldError("field_formula", "invalid_value", str(exc))]
        ) from exc
    return value  # type: ignore[return-value]


def _apply_derived(
    row: Field, provided: dict, *, effective_type: str
) -> None:
    """Validate + assign the PI-197 derived/formula kwargs in ``provided``.

    Enforces the cross-field rule against ``effective_type``: when the
    field is ``derived`` a ``field_derived_result_type`` value is REQUIRED
    (validated ∈ DERIVED_RESULT_TYPES); when it is any other type the
    column must be absent/NULL. ``formula`` is validated against the
    neutral AST shape whenever supplied (allowed on any type, but only a
    ``derived`` field's adapter renders it).
    """
    if "derived_result_type" in provided:
        row.field_derived_result_type = _coerce_result_type_or_none(
            provided["derived_result_type"]
        )
    if "formula" in provided:
        row.field_formula = _validate_formula_or_none(provided["formula"])

    # Cross-field invariant on the resolved (type, result_type) pair.
    if effective_type == "derived":
        if not row.field_derived_result_type:
            raise UnprocessableError(
                [
                    FieldError(
                        "field_derived_result_type",
                        "required_for_derived",
                        "a derived field requires field_derived_result_type "
                        f"(one of {sorted(DERIVED_RESULT_TYPES)})",
                    )
                ]
            )
    elif row.field_derived_result_type is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_derived_result_type",
                    "forbidden_for_non_derived",
                    "field_derived_result_type is only valid on a field of "
                    "type 'derived'",
                )
            ]
        )


def _load_options(session: Session, field_identifier: str) -> list[dict]:
    """Return a field's option set ordered by ``option_order`` then id."""
    rows = session.scalars(
        select(FieldOption)
        .where(FieldOption.field_identifier == field_identifier)
        .order_by(FieldOption.option_order, FieldOption.id)
    ).all()
    return [
        {
            "option_value": r.option_value,
            "option_label": r.option_label,
            "option_order": r.option_order,
        }
        for r in rows
    ]


def _field_to_dict(session: Session, row: Field) -> dict:
    """Serialise a field row with its embedded ordered option set.

    The ``field_options`` collection is surfaced inline so GET returns it
    and the change-log ``before`` / ``after`` payloads capture it (the
    collection is not a ``change_log`` entity type of its own).
    """
    out = to_dict(row)
    out["field_options"] = _load_options(session, row.field_identifier)
    return out


def _replace_options(
    session: Session, field_identifier: str, options: list
) -> None:
    """Replace a field's entire option set with ``options`` (ordered).

    Each option is ``{"option_value": str, "option_label": str|None,
    "option_order": int|None}``; ``option_order`` defaults to the list
    index. An empty list clears the set. Duplicate ``option_value`` (the
    DB unique key) is rejected with a 422 before touching the DB.
    """
    if not isinstance(options, list):
        raise UnprocessableError(
            [FieldError("field_options", "invalid_value", "must be a list")]
        )
    seen: set[str] = set()
    normalized: list[tuple[str, str | None, int]] = []
    for idx, opt in enumerate(options):
        if not isinstance(opt, dict):
            raise UnprocessableError(
                [
                    FieldError(
                        "field_options",
                        "invalid_item",
                        "each option must be an object",
                    )
                ]
            )
        value = opt.get("option_value")
        if not isinstance(value, str) or not value.strip():
            raise UnprocessableError(
                [
                    FieldError(
                        "field_options.option_value",
                        "missing_or_empty",
                        "each option requires a non-empty option_value",
                    )
                ]
            )
        value = value.strip()
        if value in seen:
            raise UnprocessableError(
                [
                    FieldError(
                        "field_options.option_value",
                        "duplicate",
                        f"duplicate option_value {value!r}",
                    )
                ]
            )
        seen.add(value)
        label = opt.get("option_label")
        if label is not None and not isinstance(label, str):
            raise UnprocessableError(
                [
                    FieldError(
                        "field_options.option_label",
                        "invalid_value",
                        "option_label must be a string or null",
                    )
                ]
            )
        order = opt.get("option_order")
        order = idx if order is None else int(order)
        normalized.append((value, label, order))

    session.execute(
        delete(FieldOption).where(
            FieldOption.field_identifier == field_identifier
        )
    )
    session.flush()
    for value, label, order in normalized:
        session.add(
            FieldOption(
                field_identifier=field_identifier,
                option_value=value,
                option_label=label,
                option_order=order,
            )
        )
    session.flush()


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`FIELD_STATUS_TRANSITIONS`. Per ``field.md`` §3.4.3 this
    check consults only the field's own status — never the status of
    the parent entity.
    """
    if requested == current:
        return
    if requested not in FIELD_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _require_live_entity(session: Session, entity_identifier: str) -> Entity:
    """Resolve the parent entity, surfacing the spec §3.5.4 422 shapes.

    Returns the live ``Entity`` row. Missing entity raises with reason
    ``not_found``; soft-deleted entity raises with reason
    ``soft_deleted``.
    """
    if not isinstance(entity_identifier, str) or not entity_identifier.strip():
        raise UnprocessableError(
            [
                FieldError(
                    "field_belongs_to_entity_identifier",
                    "missing_parent_entity",
                    "field_belongs_to_entity_identifier is required",
                )
            ]
        )
    parent = get_by_identifier(session, Entity, Entity.entity_identifier, entity_identifier)
    if parent is None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_belongs_to_entity_identifier",
                    "invalid_parent_entity",
                    f"parent entity {entity_identifier!r} not found",
                )
            ]
        )
    if parent.entity_deleted_at is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_belongs_to_entity_identifier",
                    "invalid_parent_entity",
                    f"parent entity {entity_identifier!r} is soft-deleted",
                )
            ]
        )
    return parent


def _resolve_parent_entity_identifier(
    session: Session, field_identifier: str
) -> str | None:
    """Return the field's live parent-entity identifier or ``None``.

    Looks up the live ``field_belongs_to_entity`` edge for the supplied
    field. Returns ``None`` if no such edge exists (the soft-deleted
    field state, where the edge has been hard-deleted and the parent
    is stashed in ``field_previous_parent_entity_identifier`` instead).
    """
    row = session.scalar(
        select(Reference).where(
            Reference.source_type == "field",
            Reference.source_id == field_identifier,
            Reference.target_type == "entity",
            Reference.relationship_kind == "field_belongs_to_entity",
        )
    )
    return row.target_id if row is not None else None


def _reject_duplicate_name_within_entity(
    session: Session,
    name: str,
    entity_identifier: str,
    *,
    exclude_identifier: str | None = None,
) -> None:
    """Reject a case-insensitive name collision *within the parent entity*.

    Per ``field.md`` §3.2.3: uniqueness is on
    ``(parent_entity_identifier, lower(field_name))``, not on
    ``field_name`` alone. The parent entity is resolved via the
    ``field_belongs_to_entity`` edge in the ``refs`` table — this
    function queries it directly rather than holding an FK column.
    """
    sibling_ids_stmt = select(Reference.source_id).where(
        Reference.source_type == "field",
        Reference.target_type == "entity",
        Reference.target_id == entity_identifier,
        Reference.relationship_kind == "field_belongs_to_entity",
    )
    stmt = select(Field).where(
        Field.field_identifier.in_(sibling_ids_stmt),
        func.lower(Field.field_name) == name.lower(),
        Field.field_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Field.field_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_name",
                    "duplicate",
                    f"a field named {name!r} already exists on "
                    f"entity {entity_identifier}",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Field:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(session, Field, Field.field_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``FLD-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_fields(
    session: Session,
    *,
    entity_identifier: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return all fields ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    When ``entity_identifier`` is supplied (per spec §3.5.5), the
    result is filtered to fields whose live
    ``field_belongs_to_entity`` edge points to the supplied entity.
    Soft-deleted fields are excluded from the entity-filter view
    regardless of ``include_deleted`` because their edge has been
    detached; callers wanting deleted rows on a per-entity basis must
    use the ``field_previous_parent_entity_identifier`` column.
    """
    stmt = select(Field).order_by(Field.field_identifier)
    if entity_identifier is not None:
        sibling_ids_stmt = select(Reference.source_id).where(
            Reference.source_type == "field",
            Reference.target_type == "entity",
            Reference.target_id == entity_identifier,
            Reference.relationship_kind == "field_belongs_to_entity",
        )
        stmt = stmt.where(Field.field_identifier.in_(sibling_ids_stmt))
        # When filtering by entity_identifier, soft-deleted fields have
        # no live edge so they're naturally excluded by the join.
        # include_deleted is ignored in this branch.
    else:
        if not include_deleted:
            stmt = stmt.where(Field.field_deleted_at.is_(None))
    return [_field_to_dict(session, r) for r in session.scalars(stmt).all()]


def get_field(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single field by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(session, Field, Field.field_identifier, identifier)
    if row is None:
        return None
    if row.field_deleted_at is not None and not include_deleted:
        return None
    return _field_to_dict(session, row)


def next_field_identifier(session: Session) -> str:
    """Return the next available ``FLD-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired
    identifier is never reused.
    """
    identifiers = session.scalars(select(Field.field_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_field_row(
    identifier: str,
    name: str,
    description: str,
    field_type: str,
    required: bool,
    notes: str | None,
    status: str,
    intrinsics: dict | None = None,
) -> Field:
    row = Field(
        field_identifier=identifier,
        field_name=name,
        field_description=description,
        field_type=field_type,
        field_required=required,
        field_notes=notes,
        field_status=status,
    )
    if intrinsics:
        _apply_intrinsics(row, intrinsics)
    return row


def _insert_with_autoassign(
    session: Session,
    name: str,
    description: str,
    field_type: str,
    required: bool,
    notes: str | None,
    status: str,
    intrinsics: dict | None = None,
) -> Field:
    """Insert a field with a server-assigned identifier, collision-safe.

    Computes the next ``FLD-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats.
    """
    candidate = next_field_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_field_row(
            candidate,
            name,
            description,
            field_type,
            required,
            notes,
            status,
            intrinsics,
        )
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
        "could not assign a unique field identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_field(
    session: Session,
    *,
    field_belongs_to_entity_identifier: str,
    name: str,
    description: str,
    type: str,
    required: bool | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
    options: list | None = None,
    **intrinsics,
) -> dict:
    """Create a field atomically with its parent-entity edge.

    Per ``field.md`` §3.5.4: the field row, the
    ``field_belongs_to_entity`` edge to the supplied parent entity,
    and the change-log emit all land in one transactional scope.

    Validation order:

    1. ``name`` / ``description`` non-empty.
    2. ``type`` in :data:`FIELD_TYPES`.
    3. ``status`` defaults to ``candidate``, validated against
       :data:`FIELD_STATUSES`.
    4. ``required`` defaults to ``False``.
    5. Parent entity must exist and be live (surfaces the spec
       ``missing_parent_entity`` / ``invalid_parent_entity`` shapes).
    6. ``name`` collision check scoped to the parent entity's siblings.
    7. Insert the field row (server-assigned id if ``identifier`` is
       ``None``).
    8. Create the ``field_belongs_to_entity`` edge via the references
       repository (re-imported locally to avoid an import cycle).

    PRJ-025 PI-182: ``**intrinsics`` accepts the §7 neutral design-intent
    kwargs (``tooltip``, ``format``, ``read_only``, …) and ``options`` an
    optional ordered enum/multi_enum option set that, when supplied,
    populates the ``field_options`` child collection in the same
    transaction.

    PRJ-025 PI-197: ``**intrinsics`` also accepts ``derived_result_type``
    (the value-type a ``derived`` field's formula yields — required when
    ``type`` is ``derived``, forbidden otherwise) and ``formula`` (the
    neutral structured-formula AST, validated against ``access.formulas``).
    """
    # Separate the PI-197 derived/formula kwargs from the flat §7 intrinsics
    # — they carry cross-field semantics validated against the field type.
    derived = {
        k: intrinsics.pop(k)
        for k in list(intrinsics)
        if k in _DERIVED_COLUMN_BY_KWARG
    }
    name = _require_nonempty(name, field="field_name")
    description = _require_nonempty(description, field="field_description")
    field_type = _require_type(type)
    if status is None:
        status = "candidate"
    status = _require_status(status)
    if required is None:
        required = False
    required = bool(required)
    intrinsics = _validate_intrinsic_kwargs(intrinsics)

    _require_live_entity(session, field_belongs_to_entity_identifier)
    _reject_duplicate_name_within_entity(
        session, name, field_belongs_to_entity_identifier
    )

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, description, field_type, required, notes, status,
            intrinsics,
        )
    else:
        _require_identifier_format(identifier)
        if get_by_identifier(session, Field, Field.field_identifier, identifier) is not None:
            raise ConflictError(f"field {identifier!r} already exists")
        row = _new_field_row(
            identifier, name, description, field_type, required, notes, status,
            intrinsics,
        )
        session.add(row)
        session.flush()

    _apply_derived(row, derived, effective_type=field_type)
    session.flush()

    if options is not None:
        _replace_options(session, row.field_identifier, options)

    # Create the mandatory parent-entity edge in the same transaction.
    # Imported locally to avoid a module-load cycle (references.py does
    # not import this module, but this module is loaded before the
    # references module during repository package wiring).
    from crmbuilder_v2.access.repositories import references

    references.create(
        session,
        source_type="field",
        source_id=row.field_identifier,
        target_type="entity",
        target_id=field_belongs_to_entity_identifier,
        relationship="field_belongs_to_entity",
    )

    after = _field_to_dict(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.field_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_field(
    session: Session,
    identifier: str,
    *,
    field_identifier: str | None = None,
    name: str,
    description: str,
    type: str,
    required: bool,
    notes: str | None = None,
    status: str,
    rejected_by_decision: str | None = None,
    options: list | None = None,
    **intrinsics,
) -> dict:
    """Full-replace update (PUT).

    ``field_identifier`` (the identifier echoed in the request body)
    must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``description`` / ``type``
    / ``required`` / ``status`` are required; ``notes`` is replaced
    wholesale (``None`` clears). A ``status`` change is
    transition-validated. The parent entity cannot be changed via PUT
    (spec §3.5.4).

    PRJ-025 PI-182: the §7 intrinsic ``**intrinsics`` are replaced
    wholesale (PUT semantics — an omitted scalar deserialises to its
    default and clears). ``options`` is the exception: ``None`` leaves
    the existing option set untouched and a list (including ``[]``)
    replaces it — a child collection is not silently wiped on an
    unrelated PUT.

    PRJ-025 PI-197: ``derived_result_type`` / ``formula`` follow PUT
    replace semantics too and are validated against the new ``type``
    (required-when-derived / forbidden-otherwise).
    """
    row = _get_row(session, identifier)
    if field_identifier is not None and field_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "field_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = _field_to_dict(session, row)
    # PUT replaces the derived/formula attributes wholesale — an omitted
    # key clears the column — so both keys are always passed.
    derived = {
        k: intrinsics.pop(k, None) for k in _DERIVED_COLUMN_BY_KWARG
    }
    intrinsics = _validate_intrinsic_kwargs(intrinsics)

    name = _require_nonempty(name, field="field_name")
    description = _require_nonempty(description, field="field_description")
    field_type = _require_type(type)
    status_v = _require_status(status)
    if status_v != row.field_status:
        _check_transition(row.field_status, status_v)
        if status_v == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
        row.field_status = status_v
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.field_status,
        )

    if name.lower() != row.field_name.lower():
        parent = _resolve_parent_entity_identifier(session, identifier)
        if parent is not None:
            _reject_duplicate_name_within_entity(
                session, name, parent, exclude_identifier=identifier
            )

    row.field_name = name
    row.field_description = description
    row.field_type = field_type
    row.field_required = bool(required)
    row.field_notes = notes
    _apply_intrinsics(row, intrinsics)
    _apply_derived(row, derived, effective_type=field_type)
    session.flush()

    if options is not None:
        _replace_options(session, identifier, options)

    after = _field_to_dict(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def patch_field(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``description``, ``type``, ``required``,
    ``notes``, ``status``, ``rejected_by_decision``, the PRJ-025 PI-182
    §7 intrinsics (``tooltip``, ``usage_summary``, ``default_value``,
    ``format``, ``numeric_scale``, ``max_length``, ``min``, ``max``,
    ``read_only``, ``unique``, ``externally_populated``), the PRJ-025
    PI-197 derived/formula keys (``derived_result_type``, ``formula``),
    and ``options`` (the enum option set — provided replaces it, omitted
    leaves it unchanged). A ``status`` change is transition-validated; a
    move to ``rejected`` requires either the ``rejected_by_decision`` key
    (atomic edge + flip, PI-153 §3.4) or a pre-existing
    ``rejected_by_decision`` edge. Parent-entity reparenting is not allowed
    via PATCH (spec §3.5.4).

    PI-197 cross-field rule: ``field_derived_result_type`` must be present
    iff the field's *resulting* type is ``derived`` — re-checked whenever
    either ``type`` or a derived key is supplied (so a PATCH that flips a
    field away from ``derived`` without clearing the result type, or that
    sets a result type on a non-derived field, is rejected).
    """
    rejected_by_decision = fields.pop("rejected_by_decision", None)
    # ``options`` only replaces the set when a list is supplied; an
    # omitted or explicit-null value leaves the existing set untouched.
    options = fields.pop("options", None)
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
    before = _field_to_dict(session, row)

    if "name" in fields:
        name = _require_nonempty(fields["name"], field="field_name")
        if name.lower() != row.field_name.lower():
            parent = _resolve_parent_entity_identifier(session, identifier)
            if parent is not None:
                _reject_duplicate_name_within_entity(
                    session, name, parent, exclude_identifier=identifier
                )
        row.field_name = name
    if "description" in fields:
        row.field_description = _require_nonempty(
            fields["description"], field="field_description"
        )
    if "type" in fields:
        row.field_type = _require_type(fields["type"])
    if "required" in fields:
        row.field_required = bool(fields["required"])
    if "notes" in fields:
        row.field_notes = fields["notes"]
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.field_status:
            _check_transition(row.field_status, status_v)
            if status_v == "rejected":
                _rejection.enforce_rejected_status(
                    session,
                    source_type=_ENTITY_TYPE,
                    source_identifier=identifier,
                    decision_identifier=rejected_by_decision,
                )
                rejected_by_decision = None
            row.field_status = status_v
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.field_status,
        )

    # Intrinsic §7 attributes — only the supplied keys are touched.
    _apply_intrinsics(
        row, {k: fields[k] for k in _INTRINSIC_COLUMN_BY_KWARG if k in fields}
    )

    # PI-197 derived/formula — apply the supplied keys, then re-check the
    # cross-field invariant whenever the type or a derived key was touched.
    derived = {k: fields[k] for k in _DERIVED_COLUMN_BY_KWARG if k in fields}
    if derived or "type" in fields:
        _apply_derived(row, derived, effective_type=row.field_type)

    session.flush()

    if isinstance(options, list):
        _replace_options(session, identifier, options)

    after = _field_to_dict(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def delete_field(session: Session, identifier: str) -> dict:
    """Soft-delete the field AND detach the parent-entity edge atomically.

    Per ``field.md`` §3.4.6 both effects must land in the same
    transaction. Implementation:

    1. Set ``field_deleted_at`` to now.
    2. Stash the parent entity's identifier in
       ``field_previous_parent_entity_identifier``.
    3. Hard-delete the ``field_belongs_to_entity`` edge via the
       references repository's ``_skip_cardinality_check=True`` path
       (the cardinality guard would otherwise reject deleting the
       only live edge of what was, until step 1, a live field).

    Idempotent — DELETE on an already-soft-deleted row is a no-op
    that returns the record unchanged.
    """
    row = _get_row(session, identifier)
    if row.field_deleted_at is not None:
        return _field_to_dict(session, row)
    before = _field_to_dict(session, row)

    parent = _resolve_parent_entity_identifier(session, identifier)
    row.field_deleted_at = datetime.now(UTC)
    row.field_previous_parent_entity_identifier = parent
    session.flush()

    if parent is not None:
        from crmbuilder_v2.access.repositories import references

        references.delete(
            session,
            source_type="field",
            source_id=identifier,
            target_type="entity",
            target_id=parent,
            relationship="field_belongs_to_entity",
            _skip_cardinality_check=True,
        )

    after = _field_to_dict(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def restore_field(session: Session, identifier: str) -> dict:
    """Clear ``field_deleted_at`` AND restore the parent-entity edge.

    Reads the stash column to find the previously-attached parent;
    validates the parent is still live (surfaces the spec
    ``parent_entity_soft_deleted`` 422 if not); recreates the edge
    atomically with clearing ``field_deleted_at`` and the stash.
    Raises :class:`UnprocessableError` if the row is not soft-deleted.
    """
    row = _get_row(session, identifier)
    if row.field_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_deleted_at",
                    "not_deleted",
                    "field is not soft-deleted",
                )
            ]
        )

    previous_parent = row.field_previous_parent_entity_identifier
    if previous_parent is not None:
        parent = get_by_identifier(session, Entity, Entity.entity_identifier, previous_parent)
        if parent is None:
            raise UnprocessableError(
                [
                    FieldError(
                        "field_belongs_to_entity_identifier",
                        "parent_entity_not_found",
                        f"previously-attached entity {previous_parent!r} no "
                        "longer exists; cannot restore",
                    )
                ]
            )
        if parent.entity_deleted_at is not None:
            raise UnprocessableError(
                [
                    FieldError(
                        "field_belongs_to_entity_identifier",
                        "parent_entity_soft_deleted",
                        f"previously-attached entity {previous_parent!r} is "
                        "soft-deleted; restore the parent entity first",
                    )
                ]
            )

    before = _field_to_dict(session, row)
    row.field_deleted_at = None
    row.field_previous_parent_entity_identifier = None
    session.flush()

    if previous_parent is not None:
        from crmbuilder_v2.access.repositories import references

        references.create(
            session,
            source_type="field",
            source_id=identifier,
            target_type="entity",
            target_id=previous_parent,
            relationship="field_belongs_to_entity",
        )

    after = _field_to_dict(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after
