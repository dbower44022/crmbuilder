"""Migration-mapping endpoints (WTK-107, per ``migration-mapping-api.md``).

The eight standard methodology routes plus two derived gate reads. Each
delegates to :mod:`crmbuilder_v2.access.repositories.migration_mapping`;
bodies use the parent-prefixed ``migration_mapping_*`` field names. Error
responses use the v2 ``{data, meta, errors}`` envelope, except disallowed
status transitions (the ``status_transition_handler`` flat shape) and the
invariant-I3 refusal (the dedicated ``duplicate_mapping_for_candidate``
flat shape).

Two design points from the spec:

* **Embedded links.** Every record carries a read-only
  ``migration_mapping_links`` block resolving the two mandatory edges —
  the record has no name column, so the source → target pair is its label
  (spec §4.1). Assembly is batched, never per-row.
* **Two gates.** ``GET /migration-mappings/triage-completeness`` is the
  Master PRD v0.2 §8 completeness rule ("a keep/transform without a
  recorded mapping is incomplete triage") as a callable check — the Phase
  3 close gate. ``GET /migration-mappings/compile-preflight`` is the
  merge-coherence + entity-context gate the compiler runs before emitting
  batches. Both are reads; the completeness rule is deliberately never
  enforced at write time (mappings and dispositions are recorded in
  either order within a triage session).

POST atomicity per spec §4.7: the body REQUIRES both edge keys; the
access layer creates the row, the ``migrates_from_record`` edge, the
``migrates_to_record`` edge(s), and the change-log emit in one
transaction. PUT and PATCH do NOT accept the edge keys — re-pointing is
explicit reference management (normally soft-delete and re-create).

Static routes (``next-identifier``, ``triage-completeness``,
``compile-preflight``) are declared before ``/{identifier}`` — route
order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import migration_mapping
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    MigrationMappingCreateIn,
    MigrationMappingPatchIn,
    MigrationMappingReplaceIn,
)

router = APIRouter(prefix="/migration-mappings", tags=["migration-mappings"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. ``rejected_by_decision`` is
# deliberately unprefixed (the shared ``_rejection`` contract) and passes
# through the strip untouched.
_PREFIX = "migration_mapping_"


@router.get("")
def list_all(
    level: str | None = None,
    source_identifier: str | None = None,
    target_identifier: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            migration_mapping.list_migration_mappings(
                s,
                level=level,
                source_identifier=source_identifier,
                target_identifier=target_identifier,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``MIG-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok(
            {"next": migration_mapping.next_migration_mapping_identifier(s)}
        )


@router.get("/triage-completeness")
def triage_completeness(level: str | None = None):
    """The PRD §8 completion gate: keeps/transforms with no live mapping."""
    with readonly_session() as s:
        return ok(migration_mapping.triage_completeness(s, level=level))


@router.get("/compile-preflight")
def compile_preflight():
    """The compile gate: merge-group coherence + entity-level context."""
    with readonly_session() as s:
        return ok(migration_mapping.compile_preflight(s))


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = migration_mapping.get_migration_mapping(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("migration_mapping", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: MigrationMappingCreateIn):
    with writable_session() as s:
        return ok(
            migration_mapping.create_migration_mapping(
                s,
                level=body.migration_mapping_level,
                disposition=body.migration_mapping_disposition,
                source_system_label=body.migration_mapping_source_system_label,
                source_entity_name=body.migration_mapping_source_entity_name,
                migrates_from_identifier=(
                    body.migration_mapping_migrates_from_identifier
                ),
                migrates_to_identifiers=(
                    body.migration_mapping_migrates_to_identifiers
                ),
                source_attribute_name=(
                    body.migration_mapping_source_attribute_name
                ),
                transform_rules=body.migration_mapping_transform_rules,
                notes=body.migration_mapping_notes,
                status=body.migration_mapping_status,
                identifier=body.migration_mapping_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: MigrationMappingReplaceIn):
    with writable_session() as s:
        return ok(
            migration_mapping.update_migration_mapping(
                s,
                identifier,
                migration_mapping_identifier=body.migration_mapping_identifier,
                level=body.migration_mapping_level,
                disposition=body.migration_mapping_disposition,
                source_system_label=body.migration_mapping_source_system_label,
                source_entity_name=body.migration_mapping_source_entity_name,
                source_attribute_name=(
                    body.migration_mapping_source_attribute_name
                ),
                transform_rules=body.migration_mapping_transform_rules,
                notes=body.migration_mapping_notes,
                status=body.migration_mapping_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: MigrationMappingPatchIn):
    # ``exclude_unset`` keeps an explicit ``migration_mapping_notes: null``
    # (clear) distinct from an omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            migration_mapping.patch_migration_mapping(s, identifier, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(migration_mapping.delete_migration_mapping(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(migration_mapping.restore_migration_mapping(s, identifier))
