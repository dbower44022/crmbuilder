"""Record-data export — PI-234 (REQ-130 / PRJ-027, DEC-693).

The export (audit-out) half of record-data transfer: read **selected seed /
reference** records from a source instance into an import-ready artifact, the
companion to the existing import side (the four-step Import wizard / V1
``import_manager``). Per DEC-693 this is seed/reference data only — a bounded
per-entity fetch (``max_size``), not a full operational-data clone (that would be
its own requirement). The artifact is a flat per-entity record map the import
step can consume; links between exported records ride along in the records'
own ``*Id`` / ``*Ids`` fields.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

#: The export artifact format tag, so an importer can validate what it reads.
ARTIFACT_FORMAT = "espocrm-records-v1"

_DEFAULT_MAX_SIZE = 200

ProgressFn = Callable[[str, str], None]


class _RecordsClient(Protocol):
    """The slice of the introspection client the export needs."""

    def get_records(
        self, entity: str, *, max_size: int = ..., offset: int = ...
    ) -> tuple[int, dict[str, Any] | None]: ...


def _note(progress: ProgressFn | None, message: str, level: str = "info") -> None:
    if progress is not None:
        progress(message, level)


def export_records(
    client: _RecordsClient,
    *,
    entity_names: list[str],
    max_size: int = _DEFAULT_MAX_SIZE,
    progress: ProgressFn | None = None,
) -> dict:
    """Export the selected entities' seed/reference records into an artifact.

    For each requested entity, bulk-fetches up to ``max_size`` records. A read
    failure for one entity is recorded on that entity (``error``) and surfaced via
    ``progress`` rather than aborting the whole export. ``truncated`` flags an
    entity whose total exceeds what was fetched (the operator should narrow the
    selection or raise ``max_size``).

    :returns: ``{"format", "max_size", "entities": {name: {records, count,
        truncated[, error]}}, "summary": {entity_count, record_count, truncated}}``.
    """
    entities: dict[str, dict[str, Any]] = {}
    total_records = 0
    any_truncated = False

    for name in entity_names:
        status, body = client.get_records(name, max_size=max_size)
        if status != 200 or not isinstance(body, dict):
            _note(
                progress,
                f"{name}: could not read records (HTTP {status}) — skipped",
                "warning",
            )
            entities[name] = {
                "records": [], "count": 0, "truncated": False,
                "error": f"HTTP {status}",
            }
            continue
        records = [r for r in body.get("list", []) if isinstance(r, dict)]
        total = body.get("total")
        truncated = isinstance(total, int) and total > len(records)
        if truncated:
            any_truncated = True
            _note(
                progress,
                f"{name}: exported {len(records)} of {total} records "
                f"(truncated at max_size={max_size})",
                "warning",
            )
        entities[name] = {
            "records": records,
            "count": len(records),
            "truncated": truncated,
        }
        total_records += len(records)

    return {
        "format": ARTIFACT_FORMAT,
        "max_size": max_size,
        "entities": entities,
        "summary": {
            "entity_count": len(entities),
            "record_count": total_records,
            "truncated": any_truncated,
        },
    }
