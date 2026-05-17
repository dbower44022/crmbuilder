"""Meta DB JSON snapshot exporter (v0.5 slice B).

Writes ``PRDs/product/crmbuilder-v2/db-export/meta/engagements.json``
after every successful meta-DB write per the DEC-022 / DEC-008
git-trackable snapshot pattern.

Atomic write via tempfile + ``os.replace`` mirroring the per-engagement
exporter at ``access/exporter.py``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from crmbuilder_v2.access.engagement_models import Engagement


def meta_export_dir() -> Path:
    """Absolute path of the meta-DB snapshot directory.

    Computed from this file's location: hardcoded to
    ``<repo>/PRDs/product/crmbuilder-v2/db-export/meta/`` so dogfood
    and CBM-engagement snapshots both land in the engine repo (the
    meta DB is per-install, not per-engagement, so the snapshot lives
    with the engine).
    """
    return (
        Path(__file__).resolve().parents[4]
        / "PRDs"
        / "product"
        / "crmbuilder-v2"
        / "db-export"
        / "meta"
    )


def _atomic_write(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        suffix=".tmp", prefix=path.name, dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def write_engagements_snapshot(engagements: list[Engagement]) -> None:
    """Write the engagements JSON snapshot atomically.

    ``engagements`` should already be ordered by identifier ascending
    so the git-tracked file is diff-friendly. Each record renders as
    its ``Engagement.to_dict()`` shape.
    """
    snapshot_path = meta_export_dir() / "engagements.json"
    payload = [e.to_dict() for e in engagements]
    _atomic_write(snapshot_path, payload)
