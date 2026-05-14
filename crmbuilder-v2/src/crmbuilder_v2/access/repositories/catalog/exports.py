"""Catalog JSON export hook (catalog-ingestion-PRD-v0.1.md section 7, DEC-008).

Per-entity JSON files at ``{export_dir}/catalog/entities/{catalog_id}.json``.
The shape mirrors the REST GET response (full nested entity payload,
sorted keys, 2-space indent, no internal database IDs).

Each catalog-entity-level write fires :func:`export_entity` for the
affected entity. Attribute writes fire it for the parent entity (the
JSON contains nested attributes). The data migration suppresses
exports via :func:`suppression`; after the migration commit, a single
:func:`regenerate_all_catalog_exports` call materialises every JSON
file. Ongoing writes through the access layer maintain the files
in step with the database.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import CatalogEntity
from crmbuilder_v2.access.repositories.catalog.read import _entity_full
from crmbuilder_v2.config import Settings, get_settings

_suppressed: ContextVar[bool] = ContextVar(
    "crmbuilder_v2_catalog_export_suppressed", default=False
)


@contextmanager
def suppression() -> Iterator[None]:
    """Context manager that disables the catalog export hook.

    Used by the data migration's loader callsite. Nested invocations
    stack correctly: each context manager resets to the previous value
    on exit.
    """
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


def is_suppressed() -> bool:
    return _suppressed.get()


def catalog_export_dir(settings: Settings | None = None) -> Path:
    """Return ``{settings.export_dir}/catalog/entities``."""
    s = settings or get_settings()
    return s.export_dir / "catalog" / "entities"


def export_entity(
    session: Session,
    catalog_id: str,
    *,
    settings: Settings | None = None,
) -> Path | None:
    """Write one entity's JSON file. No-op if export is suppressed.

    Returns the written path, or ``None`` if suppressed. If the entity
    has been soft-deleted, the JSON file is removed from disk (the
    catalog export reflects the "live" entity set, not the historical
    set).
    """
    if is_suppressed():
        return None
    s = settings or get_settings()
    entities_dir = catalog_export_dir(s)
    entities_dir.mkdir(parents=True, exist_ok=True)
    target = entities_dir / f"{catalog_id}.json"

    row = session.scalar(
        select(CatalogEntity).where(CatalogEntity.catalog_id == catalog_id)
    )
    if row is None or row.is_deleted:
        # Soft-deleted entities don't appear in the live export tree.
        if target.exists():
            target.unlink()
        return None
    payload = _entity_full(session, row)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(_serialise(payload) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def regenerate_all_catalog_exports(
    session: Session, *, settings: Settings | None = None
) -> dict:
    """Rewrite every catalog entity's JSON file. Used after the seed
    migration to materialise the initial export tree, and as a recovery
    hook if the directory drifts out of sync with the database.

    Returns a summary: ``{written: N, removed: M, dir: <path>}``.
    """
    s = settings or get_settings()
    entities_dir = catalog_export_dir(s)
    entities_dir.mkdir(parents=True, exist_ok=True)

    live_rows = session.scalars(
        select(CatalogEntity).where(CatalogEntity.is_deleted.is_(False))
    ).all()
    live_ids = {row.catalog_id for row in live_rows}
    written = 0
    for row in live_rows:
        payload = _entity_full(session, row)
        target = entities_dir / f"{row.catalog_id}.json"
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(_serialise(payload) + "\n", encoding="utf-8")
        os.replace(tmp, target)
        written += 1

    # Sweep stale files (entity deleted, file remains).
    removed = 0
    for existing in entities_dir.glob("*.json"):
        if existing.stem not in live_ids:
            existing.unlink()
            removed += 1

    return {"written": written, "removed": removed, "dir": str(entities_dir)}


def _serialise(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
