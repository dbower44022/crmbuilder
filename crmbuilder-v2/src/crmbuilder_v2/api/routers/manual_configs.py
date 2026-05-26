"""Manual Configs endpoints — PI-004 cohort methodology entity (v0.5+).

The eight standard endpoints from ``manual_config.md`` §3.5.1. Each
delegates to the :mod:`crmbuilder_v2.access.repositories.manual_config`
repository; request/response bodies use the parent-prefixed
``manual_config_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope. Two dedicated body shapes diverge
from the envelope: disallowed status transitions render via
``status_transition_handler`` (the ``{"error": ..., "from": ..., "to":
...}`` shape from ``domain.md`` §3.5.3) and the §3.5.3 completed-field-
population error renders via
``completed_status_requires_completion_fields_handler`` (envelope-
preserving but adds the ``missing`` field per
``manual_config.md`` §3.5.3).

Per ``manual_config.md`` §3.5.4 reference handling is decomposed: no
``/manual-configs/{id}/scopes`` shortcut endpoints; no inline-
affiliation fields in create/update bodies. All four outbound
reference kinds (``manual_config_scopes_to_domain``,
``manual_config_touches_entity``, ``manual_config_touches_field``,
``manual_config_realizes_requirement``) attach via the existing
``POST /references`` route.

URL plural is hyphenated per §3.5.1; storage entity-type name keeps
the underscore.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import manual_config
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ManualConfigCreateIn,
    ManualConfigPatchIn,
    ManualConfigReplaceIn,
)

router = APIRouter(prefix="/manual-configs", tags=["manual-configs"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "manual_config_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            manual_config.list_manual_configs(
                s, include_deleted=include_deleted
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``MCF-NNN`` identifier."""
    with readonly_session() as s:
        return ok(
            {"next": manual_config.next_manual_config_identifier(s)}
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = manual_config.get_manual_config(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("manual_config", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: ManualConfigCreateIn):
    with writable_session() as s:
        return ok(
            manual_config.create_manual_config(
                s,
                name=body.manual_config_name,
                category=body.manual_config_category,
                description=body.manual_config_description,
                instructions=body.manual_config_instructions,
                notes=body.manual_config_notes,
                status=body.manual_config_status,
                completed_at=body.manual_config_completed_at,
                completed_by=body.manual_config_completed_by,
                identifier=body.manual_config_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ManualConfigReplaceIn):
    with writable_session() as s:
        return ok(
            manual_config.update_manual_config(
                s,
                identifier,
                manual_config_identifier=body.manual_config_identifier,
                name=body.manual_config_name,
                category=body.manual_config_category,
                description=body.manual_config_description,
                instructions=body.manual_config_instructions,
                notes=body.manual_config_notes,
                status=body.manual_config_status,
                completed_at=body.manual_config_completed_at,
                completed_by=body.manual_config_completed_by,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ManualConfigPatchIn):
    # ``exclude_unset`` keeps an explicit ``manual_config_notes: null``
    # (clear) distinct from an omitted ``manual_config_notes`` (leave
    # unchanged) — same for the completion fields.
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(manual_config.patch_manual_config(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(manual_config.delete_manual_config(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(manual_config.restore_manual_config(s, identifier))
