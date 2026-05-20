"""Multi-tenancy routing fix slice A — export-write gate tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.config import get_settings, reset_settings_cache
from crmbuilder_v2.runtime.engagement_routing import (
    UNCONFIGURED_SENTINEL,
    assert_export_dir_ready,
)
from crmbuilder_v2.runtime.exceptions import (
    EngagementExportDirMissing,
    EngagementExportDirNotConfigured,
)


def _settings_with_export_dir(value: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", value)
    reset_settings_cache()
    return get_settings()


def test_assert_ready_with_unconfigured_sentinel_raises_EngagementExportDirNotConfigured(
    monkeypatch: pytest.MonkeyPatch,
):
    s = _settings_with_export_dir(UNCONFIGURED_SENTINEL, monkeypatch)
    with pytest.raises(EngagementExportDirNotConfigured):
        assert_export_dir_ready(s)
    reset_settings_cache()


def test_assert_ready_with_nonexistent_path_raises_EngagementExportDirMissing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    missing = tmp_path / "does-not-exist"
    s = _settings_with_export_dir(str(missing), monkeypatch)
    with pytest.raises(EngagementExportDirMissing) as excinfo:
        assert_export_dir_ready(s)
    assert str(missing) in str(excinfo.value)
    reset_settings_cache()


def test_assert_ready_with_existing_directory_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    existing = tmp_path / "exports"
    existing.mkdir()
    s = _settings_with_export_dir(str(existing), monkeypatch)
    assert assert_export_dir_ready(s) is None
    reset_settings_cache()


def test_assert_ready_with_empty_string_export_dir_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
):
    """An empty ``CRMBUILDER_V2_EXPORT_DIR`` is treated as unset and falls
    back to the engine default (Settings interpretation, not the
    ``__UNCONFIGURED__`` sentinel). The default is the git-tracked engine
    ``db-export`` directory, which exists, so the gate passes.
    """
    s = _settings_with_export_dir("", monkeypatch)
    assert str(s.export_dir).endswith("PRDs/product/crmbuilder-v2/db-export")
    assert assert_export_dir_ready(s) is None
    reset_settings_cache()
