"""Export-write gate tests (``runtime.engagement_routing``).

PI-β removed per-engagement-file routing and the ``current_engagement.json``
marker; the only public helper left in this module is the export-write gate
``assert_export_dir_ready`` (the snapshot/export machinery itself is PI-β
slice 4). The active engagement is now selected per request by the
``X-Engagement`` header (see ``api/test_engagement_scope_middleware``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.config import Settings
from crmbuilder_v2.runtime.engagement_routing import (
    UNCONFIGURED_SENTINEL,
    assert_export_dir_ready,
)
from crmbuilder_v2.runtime.exceptions import (
    EngagementExportDirMissing,
    EngagementExportDirNotConfigured,
)


def test_assert_export_dir_ready_passes_for_existing_dir(tmp_path: Path):
    s = Settings(export_dir=tmp_path)
    # Existing directory → no raise.
    assert assert_export_dir_ready(s) is None


def test_assert_export_dir_ready_raises_not_configured_for_sentinel():
    s = Settings(export_dir=UNCONFIGURED_SENTINEL)
    with pytest.raises(EngagementExportDirNotConfigured):
        assert_export_dir_ready(s)


def test_assert_export_dir_ready_raises_missing_for_absent_dir(tmp_path: Path):
    absent = tmp_path / "does-not-exist"
    s = Settings(export_dir=absent)
    with pytest.raises(EngagementExportDirMissing):
        assert_export_dir_ready(s)
