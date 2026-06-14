"""Engine-override endpoints (PRJ-025 PI-189 slice 1).

The eight standard methodology routes for the sparse per-engine override
layer (``engine-neutral-design-model-and-adapters.md`` §9). Each delegates to
:mod:`crmbuilder_v2.access.repositories.engine_override`; bodies use the
parent-prefixed ``override_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope. There is no status lifecycle.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import engine_override
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    EngineOverrideCreateIn,
    EngineOverridePatchIn,
    EngineOverrideReplaceIn,
)

router = APIRouter(prefix="/engine-overrides", tags=["engine-overrides"])

_PREFIX = "override_"


@router.get("")
def list_all(
    target_engine: str | None = None,
    subject_type: str | None = None,
    subject_identifier: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            engine_override.list_engine_overrides(
                s,
                target_engine=target_engine,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``OVR-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok(
            {"next": engine_override.next_engine_override_identifier(s)}
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = engine_override.get_engine_override(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("engine_override", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: EngineOverrideCreateIn):
    with writable_session() as s:
        return ok(
            engine_override.create_engine_override(
                s,
                target_engine=body.override_target_engine,
                subject_type=body.override_subject_type,
                subject_identifier=body.override_subject_identifier,
                attribute=body.override_attribute,
                value=body.override_value,
                notes=body.override_notes,
                identifier=body.override_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: EngineOverrideReplaceIn):
    with writable_session() as s:
        return ok(
            engine_override.update_engine_override(
                s,
                identifier,
                override_identifier=body.override_identifier,
                target_engine=body.override_target_engine,
                subject_type=body.override_subject_type,
                subject_identifier=body.override_subject_identifier,
                attribute=body.override_attribute,
                value=body.override_value,
                notes=body.override_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: EngineOverridePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            engine_override.patch_engine_override(s, identifier, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(engine_override.delete_engine_override(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(engine_override.restore_engine_override(s, identifier))
