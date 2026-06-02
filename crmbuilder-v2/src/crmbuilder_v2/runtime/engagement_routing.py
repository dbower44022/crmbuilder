"""Active-engagement resolution, routing, and the export-write gate.

Three public helpers (multi-tenancy routing fix, slice A):

* :func:`resolve_active_engagement` — read ``current_engagement.json``
  and return the active engagement code (or ``None``).
* :func:`route_settings_to_engagement` — point ``Settings`` at one
  engagement's per-engagement DB and export directory via env vars +
  cache resets (DEC-110).
* :func:`assert_export_dir_ready` — the gate raised at every active
  export-write site when ``engagement_export_dir`` is unconfigured
  (DEC-109) or missing on disk (DEC-114).

The CLI calls the first two at startup; the UI activation flow calls
them during engagement switching (slice B refactors the UI onto these).
"""

from __future__ import annotations

import json
import logging
import os

from ..access import db as access_db
from ..access import engagement as engagement_repo
from ..access import meta_db
from ..config import Settings, reset_settings_cache
from .exceptions import (
    EngagementExportDirMissing,
    EngagementExportDirNotConfigured,
    UnknownEngagementError,
)

_log = logging.getLogger("crmbuilder_v2.runtime.engagement_routing")

#: Reserved ``CRMBUILDER_V2_EXPORT_DIR`` value meaning "the active
#: engagement has no export_dir configured; writes must fail loud."
UNCONFIGURED_SENTINEL = "__UNCONFIGURED__"


def resolve_active_engagement() -> str | None:
    """Return the active engagement code from the marker file, or ``None``.

    Reads ``<data_dir>/current_engagement.json`` — the same canonical
    marker the v0.5 dogfood migration writes. ``data_dir()`` normalises
    away the ``engagements/`` segment, so this resolves correctly whether
    or not ``Settings`` has already been routed at an engagement DB.

    A missing file means "no active engagement". A corrupt or
    key-missing file is logged and also treated as no active engagement
    (better to fail loud at the caller than to misroute on a bad marker).
    """
    marker_path = meta_db.data_dir() / "current_engagement.json"
    if not marker_path.exists():
        return None
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _log.warning(
            "current_engagement.json unreadable/corrupt at %s; "
            "treating as no active engagement",
            marker_path,
        )
        return None
    code = payload.get("engagement_code")
    if not code:
        _log.warning(
            "current_engagement.json has no engagement_code at %s; "
            "treating as no active engagement",
            marker_path,
        )
        return None
    return code


def route_settings_to_engagement(code: str) -> None:
    """Route ``Settings`` at the engagement identified by ``code``.

    Order matters so caches reset against the final env-var state
    (slice plan §3):

    1. Look up the engagement in the meta DB (raises
       :class:`UnknownEngagementError` if absent) — done while
       ``Settings`` still point at the pre-routing state.
    2. Compute the per-engagement DB path.
    3. Set ``CRMBUILDER_V2_DB_PATH``.
    4. Set ``CRMBUILDER_V2_EXPORT_DIR`` to the engagement's
       ``engagement_export_dir`` if non-empty, else the
       :data:`UNCONFIGURED_SENTINEL`.
    5. ``reset_settings_cache()``.
    6. ``reset_engine_cache()``.
    7. ``reset_meta_engine_cache()`` only if ``data_dir()`` now resolves
       differently (moot for a fresh CLI process; relevant for in-process
       re-routing under a long-running UI).
    8. ``init_meta_db_pool()`` to re-init pools against the new state.

    Code matching is case-insensitive; the canonical stored code drives
    the per-engagement DB filename.
    """
    engagements = engagement_repo.list_engagements_in_meta()
    match = next(
        (e for e in engagements if e.engagement_code.upper() == code.upper()),
        None,
    )
    if match is None:
        raise UnknownEngagementError(
            code=code,
            available_codes=[e.engagement_code for e in engagements],
        )

    canonical_code = match.engagement_code
    prev_data_dir = meta_db.data_dir()

    # PI-123 cutover (D6): the runtime binds to the **single unified DB**, not a
    # per-engagement file. Engagement selection is now row-level — the request
    # middleware resolves the active engagement (marker / X-Engagement) and the
    # central filter/stamp scope every query. So we point at ``v2-unified.db``
    # and turn scoping on; the engagement's export dir is still per-engagement
    # (D7). (The legacy ``engagement_db_path`` per-file routing is retired.)
    db_path = meta_db.data_dir() / "v2-unified.db"
    os.environ["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    os.environ["CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED"] = "true"

    export_dir = (match.engagement_export_dir or "").strip()
    os.environ["CRMBUILDER_V2_EXPORT_DIR"] = export_dir or UNCONFIGURED_SENTINEL

    reset_settings_cache()
    access_db.reset_engine_cache()
    if meta_db.data_dir() != prev_data_dir:
        meta_db.reset_meta_engine_cache()
    meta_db.init_meta_db_pool()

    _log.info(
        "routed Settings at engagement %s on the unified DB "
        "(db_path=%s, export_dir=%s, scoping=on)",
        canonical_code,
        db_path,
        os.environ["CRMBUILDER_V2_EXPORT_DIR"],
    )


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
        raise EngagementExportDirNotConfigured(code=resolve_active_engagement())
    if not s.export_dir.is_dir():
        raise EngagementExportDirMissing(
            path=s.export_dir, code=resolve_active_engagement()
        )
