"""JSON export hook.

On every successful access-layer write, the database state is rewritten
to a tree of JSON files under :attr:`Settings.export_dir`. Files are
human-readable (sorted keys, 2-space indent) and updated atomically via
sibling-tempfile + ``os.replace``.

Atomicity contract with :func:`crmbuilder_v2.access.db.session_scope`:

1. Repository code modifies the session and ``flush()`` is called.
2. :func:`build_snapshot` reads the post-flush state.
3. :func:`write_staging` writes ``<table>.json.tmp`` files.
4. The session commits.
5. :func:`promote_staging` renames each ``.tmp`` over its final name.

A failure in steps 1–3 rolls back the database transaction. A failure
in step 4 leaves orphan tempfiles, which :func:`cleanup_staging`
removes. A failure in step 5 (extremely unlikely with same-filesystem
``os.replace``) leaves the export stale; the next successful write
self-heals.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.models import (
    ChangeLog,
    Charter,
    CrmCandidate,
    Decision,
    Domain,
    Entity,
    PlanningItem,
    Process,
    Reference,
    Risk,
    Status,
    Topic,
)
from crmbuilder_v2.access.models import (
    Session as SessionModel,
)

# Map: filename (no .json) → SQLAlchemy model. Order is the export order.
_EXPORT_TABLES: list[tuple[str, type]] = [
    ("charter", Charter),
    ("status", Status),
    ("decisions", Decision),
    ("sessions", SessionModel),
    ("risks", Risk),
    ("planning_items", PlanningItem),
    ("topics", Topic),
    ("domains", Domain),
    ("entities", Entity),
    ("processes", Process),
    ("crm_candidates", CrmCandidate),
    ("references", Reference),
    ("change_log", ChangeLog),
]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"unserialisable: {type(obj).__name__}")


def _row_to_dict(row) -> dict:
    out = {}
    for col in row.__table__.columns:
        out[col.name] = getattr(row, col.name)
    return out


def build_snapshot(session: Session) -> dict[str, list[dict]]:
    """Read the current (post-flush) state of every exported table."""
    snapshot: dict[str, list[dict]] = {}
    for filename, model in _EXPORT_TABLES:
        # Stable ordering: by ``identifier`` for governance entity tables
        # (tie-broken by ``id``); by ``version`` for the versioned
        # singletons. Methodology entity tables (UI v0.4) use a
        # prefixed-string primary key named ``{type}_identifier`` and
        # carry no integer ``id`` column — order by their primary key.
        if hasattr(model, "identifier"):
            order_cols = [model.identifier, model.id]
        elif hasattr(model, "version"):
            order_cols = [model.version, model.id]
        else:
            order_cols = list(inspect(model).primary_key)
        rows = session.scalars(select(model).order_by(*order_cols)).all()
        snapshot[filename] = [_row_to_dict(r) for r in rows]
    return snapshot


def _serialise(rows: list[dict]) -> str:
    return json.dumps(
        rows,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        default=_json_default,
    )


def write_staging(snapshot: dict[str, list[dict]], export_dir: Path) -> list[Path]:
    """Write each table's JSON to a sibling ``.tmp`` file. Returns the tempfiles."""
    export_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        for name, rows in snapshot.items():
            tmp = export_dir / f"{name}.json.tmp"
            tmp.write_text(_serialise(rows) + "\n", encoding="utf-8")
            written.append(tmp)
    except Exception:
        for tmp in written:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
        raise
    return written


def promote_staging(staging: list[Path]) -> None:
    """Rename every ``.tmp`` file to its final name (drop the ``.tmp`` suffix)."""
    for tmp in staging:
        final = tmp.with_suffix("")  # drops .tmp
        os.replace(tmp, final)


def cleanup_staging(export_dir: Path) -> None:
    """Remove any leftover ``.json.tmp`` files in the export directory."""
    if not export_dir.exists():
        return
    for tmp in export_dir.glob("*.json.tmp"):
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
