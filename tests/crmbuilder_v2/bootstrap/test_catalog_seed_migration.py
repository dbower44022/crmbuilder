"""End-to-end test for the Alembic catalog seed migration.

Runs ``alembic upgrade head`` against a fresh temp database that has
the real ``PRDs/product/crmbuilder-v2/research/base-entity-catalog/``
YAMLs on disk, and verifies the resulting row counts match the PRD's
expected totals (catalog v0.10).

This complements ``test_catalog_loader.py`` which exercises the loader
in isolation against fixture YAMLs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_CATALOG_DIR = _REPO_ROOT / "PRDs" / "product" / "crmbuilder-v2" / "research" / "base-entity-catalog"


pytestmark = pytest.mark.skipif(
    not _CATALOG_DIR.exists(),
    reason="catalog YAMLs decommissioned (per PRD section 5); integration "
    "test runs only on installations that still have them",
)


def test_alembic_upgrade_head_seeds_full_catalog(tmp_path: Path):
    db = tmp_path / "v2.db"
    export = tmp_path / "db-export"
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db)
    env["CRMBUILDER_V2_EXPORT_DIR"] = str(export)

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic upgrade failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    # Open the resulting database and count rows.
    engine = create_engine(f"sqlite:///{db}")
    with Session(bind=engine) as s:
        from crmbuilder_v2.access.models import (
            CatalogAttribute,
            CatalogAttributeEnumValue,
            CatalogAttributePresence,
            CatalogAttributeSynonym,
            CatalogEntity,
            CatalogEntitySynonym,
            CatalogEntitySystem,
            CatalogRelationship,
            CatalogRelationshipPresence,
            CatalogSource,
        )

        # Hard assertions against catalog v0.10 reality.
        assert s.scalar(select(func.count()).select_from(CatalogEntity)) == 42
        assert s.scalar(select(func.count()).select_from(CatalogAttribute)) == 415
        assert (
            s.scalar(select(func.count()).select_from(CatalogAttributePresence))
            == 2905
        )
        assert (
            s.scalar(select(func.count()).select_from(CatalogEntitySystem)) == 294
        )
        assert s.scalar(select(func.count()).select_from(CatalogSource)) == 228

        # Subclass FK resolution: 8 subclasses, all with parent_entity_id set.
        subclass_count = s.scalar(
            select(func.count())
            .select_from(CatalogEntity)
            .where(CatalogEntity.entry_kind == "subclass")
        )
        assert subclass_count == 8
        orphan_subclasses = s.scalar(
            select(func.count())
            .select_from(CatalogEntity)
            .where(
                (CatalogEntity.entry_kind == "subclass")
                & (CatalogEntity.parent_entity_id.is_(None))
            )
        )
        assert orphan_subclasses == 0

        # Donation→major-gift discriminator must point at a real
        # donation.donationType attribute (catalog v0.10 fix).
        major = s.scalar(
            select(CatalogEntity).where(
                CatalogEntity.catalog_id == "donation-major-gift"
            )
        )
        assert major.discriminator_attribute == "donationType"
        donation = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "donation")
        )
        dtype = s.scalar(
            select(CatalogAttribute).where(
                (CatalogAttribute.catalog_entity_id == donation.id)
                & (CatalogAttribute.name == "donationType")
            )
        )
        assert dtype is not None

        # Relationships have both endpoints resolved.
        bad_rel = s.scalar(
            select(func.count())
            .select_from(CatalogRelationship)
            .where(
                (CatalogRelationship.source_entity_id.is_(None))
                | (CatalogRelationship.target_entity_id.is_(None))
            )
        )
        assert bad_rel == 0
        assert s.scalar(select(func.count()).select_from(CatalogRelationship)) == 106
        assert (
            s.scalar(select(func.count()).select_from(CatalogRelationshipPresence))
            == 742
        )

        # api_name population for standard cells (PRD acceptance criterion 4):
        # at least 90% of standard cells carry an api_name.
        std_total = s.scalar(
            select(func.count())
            .select_from(CatalogAttributePresence)
            .where(CatalogAttributePresence.status == "standard")
        )
        std_with_api = s.scalar(
            select(func.count())
            .select_from(CatalogAttributePresence)
            .where(
                (CatalogAttributePresence.status == "standard")
                & (CatalogAttributePresence.api_name.is_not(None))
            )
        )
        assert std_with_api / std_total >= 0.90
