"""catalog seed

Revision ID: 0004_catalog_seed
Revises: 0003_catalog_schema
Create Date: 2026-05-14

Loads the 42-entry base entity catalog from the YAML directory at
``PRDs/product/crmbuilder-v2/research/base-entity-catalog/`` into the
catalog_* tables created in revision 0003. Atomic within Alembic's
transaction — a CatalogLoaderError raised by the loader rolls back
the whole migration.

This migration was authored once when catalog ingestion shipped. After
this commit the source YAMLs are removed from the working tree, so a
*fresh* install will fail this migration with a clear "catalog
directory not found" error. Productisation per PRD section 9 will add
a packaged seed dump that doesn't depend on the YAMLs being present;
until then, fresh installs recover the YAMLs from git history.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories.catalog import suppression as suppress_catalog_exports
from crmbuilder_v2.bootstrap.catalog_loader import load_catalog

revision: str = "0004_catalog_seed"
down_revision: Union[str, None] = "0003_catalog_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    yaml_dir = _resolve_catalog_yaml_dir()
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        # The loader writes through the ORM directly (not the access layer),
        # so its suppress_exports flag is currently a no-op. The
        # ``suppress_catalog_exports`` context manager protects against any
        # future loader rewrite that switches to access-layer writes.
        with suppress_catalog_exports():
            report = load_catalog(session, yaml_dir, suppress_exports=True)
            session.flush()
    finally:
        session.close()

    # Sanity checks against the PRD's expected counts (catalog v0.10).
    # Drift tolerance per PRD section 8: ±5 entities, ±50 attributes,
    # ±100 sub-rows. Any single mismatch outside that window aborts.
    _assert_within(report.entities_inserted + report.entities_updated, 42, 5, "entities")
    _assert_within(
        report.attributes_inserted + report.attributes_updated, 415, 50, "attributes"
    )
    _assert_within(report.presence_cells_inserted, 2905, 100, "attribute presence cells")


def downgrade() -> None:
    # The schema migration's downgrade drops the tables wholesale; nothing
    # to do here.
    pass


def _resolve_catalog_yaml_dir() -> Path:
    """Return the path to the base-entity-catalog YAML directory.

    The catalog lives at ``<repo>/PRDs/product/crmbuilder-v2/research/
    base-entity-catalog/`` relative to the repo root. The path is
    derived from this migration script's own location rather than from
    ``Settings.export_dir``, so an operator who has overridden
    ``CRMBUILDER_V2_EXPORT_DIR`` (e.g. tests, alternate data layouts)
    still finds the YAMLs at the source-tree location.

    Tests and atypical installs can override via the
    ``CRMBUILDER_V2_CATALOG_YAML_DIR`` environment variable.
    """
    override = os.environ.get("CRMBUILDER_V2_CATALOG_YAML_DIR")
    if override:
        return Path(override)
    # __file__ is at <repo>/crmbuilder-v2/migrations/versions/0004_catalog_seed.py
    repo_root = Path(__file__).resolve().parents[3]
    return (
        repo_root
        / "PRDs"
        / "product"
        / "crmbuilder-v2"
        / "research"
        / "base-entity-catalog"
    )


def _assert_within(actual: int, expected: int, tolerance: int, label: str) -> None:
    if abs(actual - expected) > tolerance:
        raise RuntimeError(
            f"catalog seed: {label} count {actual} outside tolerance "
            f"{expected}±{tolerance} (likely catalog YAMLs corrupted or "
            f"out of sync with this migration's expectations)"
        )
