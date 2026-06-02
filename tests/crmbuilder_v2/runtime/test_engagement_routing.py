"""Multi-tenancy routing fix slice A — engagement routing helper tests."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access.engagement import create_engagement
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    data_dir,
    meta_session_scope,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_models import EngagementRow
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.runtime.engagement_routing import (
    UNCONFIGURED_SENTINEL,
    resolve_active_engagement,
    route_settings_to_engagement,
)
from crmbuilder_v2.runtime.exceptions import UnknownEngagementError


@pytest.fixture
def routing_env(v2_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A meta DB with two engagements: CRMBUILDER (null export_dir) and
    CBM (a real, existing export_dir). ``data_dir()`` resolves to
    ``tmp_path`` because ``v2_env`` points ``db_path`` at
    ``tmp_path/v2.db``.
    """
    from crmbuilder_v2.access import meta_exporter

    monkeypatch.setattr(
        meta_exporter, "meta_export_dir", lambda: tmp_path / "meta-export"
    )
    reset_meta_engine_cache()
    bootstrap_meta_db()

    cbm_export = tmp_path / "cbm-export"
    cbm_export.mkdir()
    with meta_session_scope() as s:
        create_engagement(
            s,
            engagement_code="CRMBUILDER",
            engagement_name="Dogfood",
            engagement_purpose="p",
        )
        create_engagement(
            s,
            engagement_code="CBM",
            engagement_name="Cleveland",
            engagement_purpose="p",
            engagement_export_dir=str(cbm_export),
        )
    yield cbm_export
    reset_meta_engine_cache()


def _write_marker(code: str) -> Path:
    marker = data_dir() / "current_engagement.json"
    marker.write_text(
        json.dumps({"engagement_identifier": "ENG-001", "engagement_code": code}),
        encoding="utf-8",
    )
    return marker


# --------------------------------------------------------------------------
# resolve_active_engagement
# --------------------------------------------------------------------------


def test_resolve_no_marker_returns_none(routing_env):
    assert resolve_active_engagement() is None


def test_resolve_valid_marker_returns_code(routing_env):
    _write_marker("CBM")
    assert resolve_active_engagement() == "CBM"


def test_resolve_corrupt_marker_returns_none_and_warns(routing_env, caplog):
    import logging

    marker = data_dir() / "current_engagement.json"
    marker.write_text("{not valid json", encoding="utf-8")
    # Make capture robust against cross-test logging pollution: an earlier
    # test that runs Alembic (fileConfig with disable_existing_loggers=True)
    # disables the crmbuilder_v2 loggers, and ui.app._configure_logging
    # strips root handlers. Re-enable the module logger and attach caplog's
    # handler directly so the warning is captured regardless of order.
    logger = logging.getLogger("crmbuilder_v2.runtime.engagement_routing")
    logger.disabled = False
    logger.setLevel(logging.WARNING)
    logger.addHandler(caplog.handler)
    try:
        assert resolve_active_engagement() is None
    finally:
        logger.removeHandler(caplog.handler)
    assert any("current_engagement.json" in r.message for r in caplog.records)


# --------------------------------------------------------------------------
# route_settings_to_engagement
# --------------------------------------------------------------------------


def test_route_unknown_code_raises_UnknownEngagementError(routing_env):
    with pytest.raises(UnknownEngagementError) as excinfo:
        route_settings_to_engagement("BOGUS")
    assert excinfo.value.code == "BOGUS"
    assert set(excinfo.value.available_codes) == {"CRMBUILDER", "CBM"}


def test_route_valid_code_sets_db_path_env_var(routing_env):
    # PI-123 cutover: routing binds to the single unified DB (not a
    # per-engagement file) and turns scoping on; the engagement is selected
    # row-level via the marker/header at request time.
    route_settings_to_engagement("CBM")
    assert os.environ["CRMBUILDER_V2_DB_PATH"] == str(data_dir() / "v2-unified.db")
    assert os.environ["CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED"] == "true"


def test_route_engagement_with_export_dir_sets_export_dir_env_var(routing_env):
    cbm_export = routing_env
    route_settings_to_engagement("CBM")
    assert os.environ["CRMBUILDER_V2_EXPORT_DIR"] == str(cbm_export)


def test_route_engagement_with_null_export_dir_sets_sentinel(routing_env):
    route_settings_to_engagement("CRMBUILDER")
    assert os.environ["CRMBUILDER_V2_EXPORT_DIR"] == UNCONFIGURED_SENTINEL


def test_route_engagement_with_empty_string_export_dir_treated_as_null(
    routing_env,
):
    # Insert a row with an empty-string export_dir directly (the repo's
    # create_engagement validation would reject it), to exercise the
    # helper's ``(value or "").strip()`` empty-as-null handling.
    now = datetime.now(UTC)
    with meta_session_scope() as s:
        s.add(
            EngagementRow(
                engagement_identifier="ENG-003",
                engagement_code="EMPTY",
                engagement_name="Empty Export",
                engagement_purpose="p",
                engagement_status="active",
                engagement_export_dir="",
                engagement_created_at=now,
                engagement_updated_at=now,
            )
        )
    route_settings_to_engagement("EMPTY")
    assert os.environ["CRMBUILDER_V2_EXPORT_DIR"] == UNCONFIGURED_SENTINEL


def test_route_resets_settings_cache_so_subsequent_get_settings_reflects_change(
    routing_env,
):
    cbm_export = routing_env
    route_settings_to_engagement("CBM")
    s = get_settings()
    assert s.db_path == data_dir() / "v2-unified.db"  # PI-123: unified DB
    assert s.export_dir == cbm_export


def test_route_twice_to_different_engagement_reflects_second_engagement_after_caches_reset(
    routing_env,
):
    # PI-123 cutover: both engagements route to the same unified DB; only the
    # export dir (and the row-level scope) differs between them.
    route_settings_to_engagement("CBM")
    assert get_settings().db_path == data_dir() / "v2-unified.db"

    route_settings_to_engagement("CRMBUILDER")
    s = get_settings()
    assert s.db_path == data_dir() / "v2-unified.db"
    assert str(s.export_dir) == UNCONFIGURED_SENTINEL
