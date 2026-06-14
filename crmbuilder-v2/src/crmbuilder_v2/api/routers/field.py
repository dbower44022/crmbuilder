"""Fields endpoints — the sixth methodology entity type (v0.5+, PI-004
first slice).

The eight standard endpoints from ``field.md`` §3.5.1. Each delegates
to the :mod:`crmbuilder_v2.access.repositories.field` repository;
request/response bodies use the parent-prefixed ``field_*`` field
names. Error responses use the v2 ``{data, meta, errors}`` envelope,
except disallowed status transitions which the dedicated
``status_transition_handler`` renders with the spec's
``{"error": ..., "from": ..., "to": ...}`` shape.

Per ``field.md`` §3.5.4 POST atomicity is the one cross-spec
deviation: ``POST /fields`` REQUIRES a
``field_belongs_to_entity_identifier`` body key; the access layer
creates the field row, the ``field_belongs_to_entity`` edge, and the
change-log emit in one transaction. PUT and PATCH do NOT accept the
key — reparenting requires explicit DELETE-then-POST edge management
via ``/references`` (PI-053 tracks the convenience endpoint).

The ``?entity_identifier=ENT-NNN`` list filter (spec §3.5.5) returns
only fields whose live ``field_belongs_to_entity`` edge points to the
named entity — the most common access pattern at CBM-redo scale.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import field
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.routers.utilization_evidence import embed_inline_evidence
from crmbuilder_v2.api.schemas import (
    FieldCreateIn,
    FieldPatchIn,
    FieldReplaceIn,
)

router = APIRouter(prefix="/fields", tags=["fields"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "field_"

# PRJ-025 PI-182 — the §7 intrinsic body keys (``field_*``) and the
# unprefixed repo kwarg each forwards to on create / replace.
_INTRINSIC_BODY_TO_KWARG = {
    "field_tooltip": "tooltip",
    "field_usage_summary": "usage_summary",
    "field_default_value": "default_value",
    "field_format": "format",
    "field_numeric_scale": "numeric_scale",
    "field_max_length": "max_length",
    "field_min": "min",
    "field_max": "max",
    "field_read_only": "read_only",
    "field_unique": "unique",
    "field_externally_populated": "externally_populated",
}


def _intrinsic_kwargs(body) -> dict:
    """Pull the §7 intrinsic body fields into their repo kwargs."""
    return {
        kwarg: getattr(body, body_key)
        for body_key, kwarg in _INTRINSIC_BODY_TO_KWARG.items()
    }


def _options_arg(body) -> list | None:
    """Serialise ``field_options`` to a list of dicts, or ``None``."""
    if body.field_options is None:
        return None
    return [opt.model_dump() for opt in body.field_options]


@router.get("")
def list_all(
    entity_identifier: str | None = None,
    include_deleted: bool = False,
    include_evidence: str | None = None,
):
    with readonly_session() as s:
        records = field.list_fields(
            s,
            entity_identifier=entity_identifier,
            include_deleted=include_deleted,
        )
        return ok(
            embed_inline_evidence(
                s,
                records,
                subject_type="field",
                identifier_key="field_identifier",
                include_evidence=include_evidence,
                is_list=True,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``FLD-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": field.next_field_identifier(s)})


@router.get("/{identifier}")
def get(
    identifier: str,
    include_deleted: bool = False,
    include_evidence: str | None = None,
):
    with readonly_session() as s:
        record = field.get_field(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("field", identifier)
        embed_inline_evidence(
            s,
            [record],
            subject_type="field",
            identifier_key="field_identifier",
            include_evidence=include_evidence,
            is_list=False,
        )
        return ok(record)


@router.post("", status_code=201)
def create(body: FieldCreateIn):
    with writable_session() as s:
        return ok(
            field.create_field(
                s,
                field_belongs_to_entity_identifier=(
                    body.field_belongs_to_entity_identifier
                ),
                name=body.field_name,
                description=body.field_description,
                type=body.field_type,
                required=body.field_required,
                notes=body.field_notes,
                status=body.field_status,
                identifier=body.field_identifier,
                options=_options_arg(body),
                **_intrinsic_kwargs(body),
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FieldReplaceIn):
    with writable_session() as s:
        return ok(
            field.update_field(
                s,
                identifier,
                field_identifier=body.field_identifier,
                name=body.field_name,
                description=body.field_description,
                type=body.field_type,
                required=body.field_required,
                notes=body.field_notes,
                status=body.field_status,
                options=_options_arg(body),
                **_intrinsic_kwargs(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FieldPatchIn):
    # ``exclude_unset`` keeps an explicit ``field_notes: null`` (clear)
    # distinct from an omitted ``field_notes`` (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(field.patch_field(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(field.delete_field(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(field.restore_field(s, identifier))
