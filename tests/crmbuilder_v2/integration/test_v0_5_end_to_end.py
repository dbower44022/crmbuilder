"""v0.5 end-to-end lifecycle integration smoke.

Per the slice E prompt, this exercises the full v0.5 user journey from
a v0.4-state ``v2.db`` through dogfood migration, CBM engagement
creation via :class:`NewEngagementDialog`, picker-driven switching back
to CRMBUILDER, and confirmation of per-engagement DB isolation.

Subprocess management uses no-op stubs per the slice E guidance — the
real activation worker is exercised, but its subprocess managers are
mock callables. The DB-isolation assertion relies on the meta DB +
per-engagement DB files actually being created and rehoused; no real
API/MCP processes spawn.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import bootstrap_database, reset_engine_cache
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    reset_meta_engine_cache,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.dogfood_v0_5 import (
    needs_migration,
    run_dogfood_migration,
)
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.activation_worker import SubprocessManagers
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.new_engagement_dialog import NewEngagementDialog
from crmbuilder_v2.ui.panels.engagements import EngagementsPanel
from fastapi.testclient import TestClient


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A clean v0.4-state workspace with a small dogfood-shaped v2.db."""
    data = tmp_path / "crmbuilder-v2" / "data"
    data.mkdir(parents=True)
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(data / "v2.db"))
    monkeypatch.setenv(
        "CRMBUILDER_V2_EXPORT_DIR", str(tmp_path / "exports")
    )

    from crmbuilder_v2.access import meta_exporter

    test_meta_export = tmp_path / "test-meta-export"
    monkeypatch.setattr(
        meta_exporter, "meta_export_dir", lambda: test_meta_export
    )

    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()

    # Seed a minimal v0.4-shape v2.db with two sessions + three decisions
    # so post-migration row counts have something to verify.
    db = data / "v2.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE sessions (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE decisions (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE planning_items (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE change_log (id INTEGER PRIMARY KEY);
            CREATE TABLE charter (id INTEGER PRIMARY KEY);
            CREATE TABLE status (id INTEGER PRIMARY KEY);
            CREATE TABLE risks (id INTEGER PRIMARY KEY);
            CREATE TABLE topics (id INTEGER PRIMARY KEY);
            CREATE TABLE refs (id INTEGER PRIMARY KEY);
            CREATE TABLE domains (domain_identifier TEXT PRIMARY KEY);
            CREATE TABLE entities (entity_identifier TEXT PRIMARY KEY);
            CREATE TABLE processes (process_identifier TEXT PRIMARY KEY);
            CREATE TABLE crm_candidates (crm_candidate_identifier TEXT PRIMARY KEY);
            INSERT INTO sessions(identifier) VALUES ('SES-001'), ('SES-002');
            INSERT INTO decisions(identifier) VALUES
                ('DEC-001'), ('DEC-002'), ('DEC-003');
            """
        )
        conn.commit()
    finally:
        conn.close()

    yield data
    reset_meta_engine_cache()
    reset_engine_cache()
    reset_settings_cache()


def _noop_managers() -> SubprocessManagers:
    return SubprocessManagers(
        kill_api=lambda: None,
        kill_mcp=lambda: None,
        launch_api=lambda _p: None,
        launch_mcp=lambda _p: None,
    )


def _client_against_meta() -> StorageClient:
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def test_v0_5_full_lifecycle(qtbot, workspace):
    """End-to-end: migrate → create CBM → switch to CRMBUILDER → switch back.

    Asserts only the DB-isolation and engagement-routing guarantees that
    matter at the methodology level. Per-panel UI assertions are
    covered by the unit suites; this integration test focuses on the
    full-lifecycle invariants.
    """
    data = workspace

    # 1. The v0.4-state DB exists; migration is needed.
    assert (data / "v2.db").exists()
    assert needs_migration() is True

    # 2. Run dogfood migration.
    result = run_dogfood_migration()
    assert result.success, result.error

    # 3. Assert: v2.db gone; backup present; meta DB present; CRMBUILDER
    #    DB present; row counts match.
    assert not (data / "v2.db").exists()
    assert (data / "v2.db.pre-v0.5-backup").exists()
    assert (data / "engagements.db").exists()
    assert engagement_db_path("CRMBUILDER").exists()
    assert result.row_count_verifications["sessions"] == (2, 2)
    assert result.row_count_verifications["decisions"] == (3, 3)

    # 4. Stamp CRMBUILDER.db at Alembic head. The dogfood migration
    #    copies the v2.db file as-is, which in real production usage
    #    already carries an ``alembic_version`` table; the test fixture
    #    seeds a bare v2.db without one. The slice-D activation worker's
    #    step-3 Alembic upgrade needs the destination DB to be stamped,
    #    otherwise it would re-apply the initial migration and fail
    #    because the tables already exist. Mirrors what
    #    ``run_engagement_migrations`` does on a fresh-bootstrapped DB.
    import os

    from alembic import command

    from crmbuilder_v2.migration.lazy_migration import (
        make_engagement_alembic_config,
    )

    prior_env = os.environ.get("CRMBUILDER_V2_DB_PATH")
    os.environ["CRMBUILDER_V2_DB_PATH"] = str(engagement_db_path("CRMBUILDER"))
    reset_settings_cache()
    reset_engine_cache()
    try:
        command.stamp(make_engagement_alembic_config("CRMBUILDER"), "head")
    finally:
        if prior_env is None:
            os.environ.pop("CRMBUILDER_V2_DB_PATH", None)
        else:
            os.environ["CRMBUILDER_V2_DB_PATH"] = prior_env
        reset_settings_cache()
        reset_engine_cache()

    # 5. Open a StorageClient against the meta DB; CRMBUILDER row present.
    client = _client_against_meta()
    engagements = client.list_engagements()
    assert len(engagements) == 1
    assert engagements[0]["engagement_code"] == "CRMBUILDER"
    assert engagements[0]["engagement_status"] == "active"

    # 6. Wire the active context to CRMBUILDER (mirrors the desktop's
    #    boot-time load_from_disk path).
    ctx = ActiveEngagementContext()
    ctx.load_from_disk()
    assert ctx.engagement_code() == "CRMBUILDER"

    # 6. Open the NewEngagementDialog and submit CBM.
    dialog = NewEngagementDialog(client, ctx, _noop_managers())
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("CBM")
    dialog._widgets["engagement_name"].setText("Cleveland Business Mentoring")
    dialog._widgets["engagement_purpose"].setPlainText(
        "CBM Phase 1 pilot per the v0.5 dogfood discipline"
    )
    with qtbot.waitSignal(dialog.accepted, timeout=15000):
        dialog._on_save_clicked()

    # 7. Assert: CBM record + DB file exist; active engagement switched.
    cbm = client.get_engagement("ENG-002")
    assert cbm["engagement_code"] == "CBM"
    assert engagement_db_path("CBM").exists()
    assert ctx.engagement_code() == "CBM"

    # 8. Per-engagement DB isolation: CBM.db has an empty sessions table
    #    (no SES-027+ dogfood content carried over). CRMBUILDER.db still
    #    has the two seeded sessions.
    cbm_conn = sqlite3.connect(str(engagement_db_path("CBM")))
    try:
        cbm_sessions = cbm_conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]
    finally:
        cbm_conn.close()
    assert cbm_sessions == 0

    crmbuilder_conn = sqlite3.connect(str(engagement_db_path("CRMBUILDER")))
    try:
        crmbuilder_sessions = crmbuilder_conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]
    finally:
        crmbuilder_conn.close()
    assert crmbuilder_sessions == 2

    # 9. Switch back to CRMBUILDER via the engagement panel's flow.
    #    Use the panel's _on_picker-equivalent path: construct a worker
    #    directly (the picker → activation_worker wiring is already
    #    covered by unit tests).
    from crmbuilder_v2.access.engagement_models import (
        Engagement,
        EngagementStatus,
    )
    from crmbuilder_v2.ui.activation_worker import ActivationWorker

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    crmbuilder_eng = Engagement(
        engagement_identifier="ENG-001",
        engagement_code="CRMBUILDER",
        engagement_name="CRMbuilder v2",
        engagement_purpose="",
        engagement_status=EngagementStatus.ACTIVE,
        engagement_last_opened_at=None,
        engagement_export_dir=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=None,
    )
    worker = ActivationWorker(
        target_engagement=crmbuilder_eng,
        previous_engagement=ctx.engagement(),
        client=client,
        active_context=ctx,
        managers=_noop_managers(),
    )
    with qtbot.waitSignal(worker.completed, timeout=15000):
        worker.run()
    assert ctx.engagement_code() == "CRMBUILDER"

    # 10. EngagementsPanel sees both engagements with CRMBUILDER active.
    panel = EngagementsPanel(client, active_context=ctx)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=5000)
    by_code = {
        panel._model.record_at(r)["engagement_code"]: panel._model.record_at(r)
        for r in range(panel._model.rowCount())
    }
    assert "CRMBUILDER" in by_code
    assert "CBM" in by_code
    # CRMBUILDER's display identifier carries the active-engagement glyph.
    from crmbuilder_v2.ui.panels.engagements import ACTIVE_GLYPH

    assert by_code["CRMBUILDER"]["_display_identifier"].startswith(ACTIVE_GLYPH)
    assert not by_code["CBM"]["_display_identifier"].startswith(ACTIVE_GLYPH)
