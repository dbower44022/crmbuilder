"""PI-123 Slice 2 — migration 0038 adds the nullable engagement_id discriminator.

Three CI-safe tests (none need the decommissioned catalog YAMLs):

- ``test_scoped_models_carry_engagement_id`` — every engagement-scoped model
  (mixin user) exposes a nullable ``engagement_id``; the ``engagements`` tenant
  table and the ``catalog_*`` system/shared tables do not.

- ``test_migration_table_list_matches_models`` — the migration's hardcoded
  ``SCOPED_TABLES`` is exactly the set of model tables carrying ``engagement_id``.
  This pins the migration to the models so the two cannot drift (a table that
  gains the mixin but is missing from the migration, or vice-versa, fails here).

- ``test_0038_adds_and_drops_engagement_id`` — exercises the real ALTER path:
  build the full schema via ``create_all``, drop ``engagement_id`` from the
  scoped tables to simulate the pre-0038 state, stamp at 0037, then
  ``upgrade head`` (runs only 0038) and assert the column is back on every
  scoped table and absent from the excluded ones. Then downgrade and assert
  it is gone again.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base, EngagementScopedMixin
from sqlalchemy import create_engine, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_0037 = "0037_pi_123_engagements_table_in_unified_db"
_MIGRATION_PATH = (
    _ALEMBIC_DIR
    / "migrations"
    / "versions"
    / "0038_pi_123_engagement_id_discriminator_nullable.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("_m0038", _MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Engagement-scoped tables introduced AFTER migration 0038 and managed by
# create_all (not back-filled into 0038's frozen ALTER list). 0038 could not
# have scoped a table that did not yet exist when it ran, so these are excluded
# from the migration↔model equality below. Their own create migration (or
# create_all on the live DB) scopes them from birth.
#   - ``findings`` — PI-134 reconciliation gate (DEC-400).
#   - ``utilization_evidence`` — PI-153 baseline-candidate evidence (WTK-088).
#   - ``migration_mappings`` — WTK-106 Phase 3 migration-mapping record
#     (created scoped-from-birth by migration 0048).
#   - ``review_signoffs`` — requirements-provenance Phase 6 review attestation
#     (created scoped-from-birth by migration 0051).
#   - ``services`` — PI-161 cross-domain service record (created
#     scoped-from-birth by migration 0052).
#   - ``field_options`` — PRJ-025 PI-182 enum option child collection
#     (created scoped-from-birth by migration 0053).
_POST_0038_SCOPED_TABLES: frozenset[str] = frozenset(
    {
        "findings",
        "utilization_evidence",
        "migration_mappings",
        "review_signoffs",
        "services",
        "field_options",
        # PRJ-025 PI-189 slice 1 composite design records.
        "associations",
        "engine_overrides",
        # PRJ-025 PI-189 slice 2 condition-carrying design records.
        "rules",
        "views",
        "automations",
        # PRJ-025 PI-189 slice 3 dedup + template design records.
        "dedup_rules",
        "message_templates",
        # PI-186 (PRJ-027) instance entity.
        "instances",
        # PI-185 (PRJ-027) per-(object, instance) membership join.
        "instance_memberships",
        # PI-193 / PI-194 (PRJ-027) net-new design families.
        "layouts",
        "roles",
        "teams",
        # PI-195 (PRJ-027) filtered-tab design family.
        "filtered_tabs",
    }
)


def _model_scoped_tables() -> set[str]:
    # Scoped tables are the EngagementScopedMixin subclasses — NOT merely any
    # table with an ``engagement_id`` column. A system/shared table may carry
    # an ``engagement_id`` FK to engagements without being a row-scoped tenant
    # table (e.g. role_assignments, PI-γ), so key on the mixin, not the column.
    return {
        mapper.class_.__tablename__
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, EngagementScopedMixin)
    }


def test_scoped_models_carry_engagement_id() -> None:
    scoped = _model_scoped_tables()
    # 30 scoped at migration 0038 + the create_all-managed tables added since.
    assert len(scoped) == 30 + len(_POST_0038_SCOPED_TABLES), (
        f"expected {30 + len(_POST_0038_SCOPED_TABLES)} scoped tables, "
        f"got {len(scoped)}"
    )
    # The tenant table and the catalog/system tables are excluded.
    assert "engagements" not in scoped
    assert not any(name.startswith("catalog_") for name in scoped)
    # PI-123 Stage 2 (the strict-schema flip): the model now carries
    # ``engagement_id`` as a NOT NULL VARCHAR(32) FK on every scoped table —
    # the cutover target reached by create_all / the consolidation. (Migration
    # 0038 still adds the column *nullable*; the strict shape is not an in-place
    # chain migration — see pi-123-slice3-enforce-plan.md.)
    for name in scoped:
        col = Base.metadata.tables[name].c["engagement_id"]
        assert col.nullable is False, name
        assert str(col.type) == "VARCHAR(32)", (name, str(col.type))


def test_migration_table_list_matches_models() -> None:
    mod = _load_migration_module()
    migration_tables = set(mod.SCOPED_TABLES)
    # Compare against the scoped models that existed at 0038 — i.e. the current
    # set minus tables added afterward by create_all (see _POST_0038_SCOPED_TABLES).
    model_tables_at_0038 = _model_scoped_tables() - _POST_0038_SCOPED_TABLES
    assert migration_tables == model_tables_at_0038, (
        "migration 0038 SCOPED_TABLES drifted from the engagement_id-bearing "
        f"models:\n  only in migration: {sorted(migration_tables - model_tables_at_0038)}"
        f"\n  only in models: {sorted(model_tables_at_0038 - migration_tables)}"
    )


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    export_dir = db_path.parent / "db-export"
    export_dir.mkdir(parents=True, exist_ok=True)
    env["CRMBUILDER_V2_EXPORT_DIR"] = str(export_dir)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


def test_0038_adds_and_drops_engagement_id(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    mod = _load_migration_module()
    scoped = list(mod.SCOPED_TABLES)

    # Build the full current schema (every table, with engagement_id), then
    # drop the column from the scoped tables to recreate the pre-0038 state.
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    try:
        with engine.begin() as c:
            for t in scoped:
                c.execute(text(f"ALTER TABLE {t} DROP COLUMN engagement_id"))
    except Exception as exc:  # pragma: no cover - environment guard
        engine.dispose()
        pytest.skip(f"SQLite lacks DROP COLUMN for setup: {exc}")
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0037], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", "head"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    insp = inspect(create_engine(f"sqlite:///{db}"))
    for t in scoped:
        cols = {c["name"] for c in insp.get_columns(t)}
        assert "engagement_id" in cols, f"{t} missing engagement_id after 0038"
    # Excluded tables untouched.
    for t in ("engagements", "catalog_entity"):
        cols = {c["name"] for c in insp.get_columns(t)}
        assert "engagement_id" not in cols, f"{t} wrongly gained engagement_id"

    down = _alembic(["downgrade", "-1"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    for t in scoped:
        cols = {c["name"] for c in insp2.get_columns(t)}
        assert "engagement_id" not in cols, f"{t} kept engagement_id after downgrade"
