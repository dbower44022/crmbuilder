"""The export-write gate.

PI-β removed per-engagement-file routing and the single-active
``current_engagement.json`` marker: the runtime binds to the single
unified DB and the active engagement is selected per request by the
``X-Engagement`` header (``api/scope_middleware``). What remains here is
the export-write gate raised at every active export-write site when the
configured ``engagement_export_dir`` is unconfigured (DEC-109) or missing
on disk (DEC-114). (The snapshot/export machinery itself is PI-β slice 4.)
"""

from __future__ import annotations

import logging

from ..config import Settings
from .exceptions import (
    EngagementExportDirMissing,
    EngagementExportDirNotConfigured,
)

_log = logging.getLogger("crmbuilder_v2.runtime.engagement_routing")

#: Reserved ``CRMBUILDER_V2_EXPORT_DIR`` value meaning "the active
#: engagement has no export_dir configured; writes must fail loud."
UNCONFIGURED_SENTINEL = "__UNCONFIGURED__"


def assert_export_dir_ready(s: Settings) -> None:
    """Raise if the active engagement's export_dir is unconfigured/missing.

    * ``__UNCONFIGURED__`` sentinel → :class:`EngagementExportDirNotConfigured`
      (DEC-109).
    * a path that is not an existing directory →
      :class:`EngagementExportDirMissing` (DEC-114).

    Otherwise returns ``None``. Subdirectories below the configured root
    are still auto-created by the writers; this gate only guards the
    operator-configured root itself.
    """
    if str(s.export_dir) == UNCONFIGURED_SENTINEL:
        raise EngagementExportDirNotConfigured(code=None)
    if not s.export_dir.is_dir():
        raise EngagementExportDirMissing(path=s.export_dir, code=None)
