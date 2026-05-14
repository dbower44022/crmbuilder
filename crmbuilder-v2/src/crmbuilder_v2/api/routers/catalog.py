"""Catalog REST endpoints (catalog-ingestion-PRD-v0.1.md section 6).

Read endpoints live here at v0.1; write endpoints are added in commit
F. All routes are mounted under ``/catalog/``.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access.repositories import catalog
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import CatalogGapCheckIn

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ---------- list ----------


@router.get("/entities")
def list_entities(
    tier: int | None = None,
    entry_kind: str | None = None,
    parent_entity: str | None = None,
    system: str | None = None,
    data_model_role: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            catalog.list_entities(
                s,
                tier=tier,
                entry_kind=entry_kind,
                parent_catalog_id=parent_entity,
                system=system,
                data_model_role=data_model_role,
                include_deleted=include_deleted,
            )
        )


# ---------- detail ----------


@router.get("/entities/{catalog_id}")
def get_entity(catalog_id: str):
    with readonly_session() as s:
        return ok(catalog.get_entity(s, catalog_id))


@router.get("/entities/{catalog_id}/attributes/{name}")
def get_attribute(catalog_id: str, name: str):
    with readonly_session() as s:
        return ok(catalog.get_attribute(s, catalog_id, name))


# ---------- search ----------


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    include_attributes: bool = True,
    include_synonyms: bool = True,
):
    with readonly_session() as s:
        return ok(
            catalog.search(
                s,
                q,
                limit=limit,
                include_attributes=include_attributes,
                include_synonyms=include_synonyms,
            )
        )


# ---------- cross-system map ----------


@router.get("/cross-system-map/{catalog_id}")
def cross_system_map(
    catalog_id: str,
    system: str | None = None,
):
    with readonly_session() as s:
        return ok(catalog.cross_system_map(s, catalog_id, system=system))


# ---------- gap check ----------


@router.post("/gap-check")
def gap_check(body: CatalogGapCheckIn):
    with readonly_session() as s:
        return ok(
            catalog.gap_check(
                s,
                based_on_catalog_id=body.based_on_catalog_id,
                draft_attribute_names=body.draft_attribute_names,
                min_systems=body.min_systems,
            )
        )
