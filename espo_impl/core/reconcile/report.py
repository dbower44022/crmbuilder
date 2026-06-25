"""Human-readable ``.log`` + machine ``.json`` report for a reconcile apply.

Mirrors the :class:`espo_impl.core.reporter.Reporter` convention (timestamped
stem, paired ``.log``/``.json`` under a ``reports/`` directory) but is
self-contained over the reconcile :class:`ReconcileResult`. Each accepted change
is recorded as ``old → new`` with the provenance that it originated as a
live-CRM (admin-UI) edit written back into the source YAML — the live CRM is
never modified.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from espo_impl.core.reconcile.reconciler import ReconcileResult

_MAX_LOG_VALUE = 80


def _item_name(diff) -> str:
    """A label for the item a difference concerns (field/link/layout/role/team)."""
    loc = diff.locator
    for attr in ("field_name", "rel_name", "layout_type", "role", "team", "option"):
        val = getattr(loc, attr, None)
        if val:
            return val
    return diff.property or "?"


def _short(value: Any) -> str:
    """Compact one-line rendering for the .log (layouts can be huge)."""
    text = " ".join(str(value).split())
    return text if len(text) <= _MAX_LOG_VALUE else text[: _MAX_LOG_VALUE - 1] + "…"


def _diff_dict(diff) -> dict[str, Any]:
    """Full, machine-readable serialization of one difference for the .json."""
    return {
        "entity": diff.entity,
        "config_type": diff.config_type.value,
        "category": diff.category.value,
        "item": _item_name(diff),
        "property": diff.property,
        "yaml_value": diff.yaml_value,   # old (what was in YAML)
        "crm_value": diff.crm_value,     # new (written back from the CRM)
    }


def _change_line(diff) -> str:
    """One .log line describing an applied/skipped change as old → new."""
    head = f"{diff.entity}.{_item_name(diff)} ({diff.config_type.value}/{diff.category.value})"
    if diff.category.value == "changed":
        return f"{head} : {_short(diff.yaml_value)} → {_short(diff.crm_value)}"
    if diff.category.value == "crm_only":
        return f"{head} : added from CRM"
    return head


def write_reconcile_report(
    result: ReconcileResult,
    reports_dir: Path,
    *,
    instance_name: str | None = None,
    source_url: str | None = None,
    timestamp: str | None = None,
) -> tuple[Path, Path]:
    """Write paired ``.log`` and ``.json`` reconcile reports.

    :param result: The apply outcome.
    :param reports_dir: Directory to write into (created if absent) — typically
        the client repo's ``reports/``.
    :param instance_name: Source instance name for the header.
    :param source_url: Source instance URL for the header.
    :param timestamp: ISO timestamp; defaults to now (seconds precision).
    :returns: ``(log_path, json_path)``.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp or datetime.now().isoformat(timespec="seconds")
    stem = f"reconcile-{ts.replace(':', '').replace('-', '').replace('T', '_')}"
    log_path = reports_dir / f"{stem}.log"
    json_path = reports_dir / f"{stem}.json"

    log_path.write_text(_render_log(result, ts, instance_name, source_url))
    json_path.write_text(
        json.dumps(
            _render_json(result, ts, instance_name, source_url),
            indent=2,
            default=str,
        )
    )
    return log_path, json_path


def _render_log(
    result: ReconcileResult,
    ts: str,
    instance_name: str | None,
    source_url: str | None,
) -> str:
    lines = [
        "===========================================",
        "CRM Builder — Reconcile Report",
        "===========================================",
        f"Timestamp     : {ts}",
        f"Instance      : {instance_name or '(unknown)'}",
        f"URL           : {source_url or '(unknown)'}",
        f"Files touched : {len(result.files)}",
        f"Applied       : {result.applied_count}",
        f"Not applied   : {result.not_applied_count}",
        "===========================================",
        "",
        "These changes originated as live-CRM (admin-UI) edits and were written",
        "back into the source YAML. The live CRM was not modified.",
        "",
    ]
    for fr in result.files:
        ver = (
            f"  content_version {fr.old_version} → {fr.new_version}"
            if fr.new_version
            else ""
        )
        lines.append(f"[{fr.path}]{ver}")
        if fr.applied:
            lines.append("  APPLIED:")
            lines.extend(f"    {_change_line(d)}" for d in fr.applied)
        if fr.not_applied:
            lines.append("  NOT APPLIED:")
            lines.extend(
                f"    {_change_line(d)} : {reason}" for d, reason in fr.not_applied
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_json(
    result: ReconcileResult,
    ts: str,
    instance_name: str | None,
    source_url: str | None,
) -> dict[str, Any]:
    return {
        "operation": "reconcile",
        "direction": "crm_to_yaml",
        "timestamp": ts,
        "instance_name": instance_name,
        "source_url": source_url,
        "applied_count": result.applied_count,
        "not_applied_count": result.not_applied_count,
        "files": [
            {
                "path": str(fr.path),
                "old_version": fr.old_version,
                "new_version": fr.new_version,
                "applied": [_diff_dict(d) for d in fr.applied],
                "not_applied": [
                    {**_diff_dict(d), "reason": reason}
                    for d, reason in fr.not_applied
                ],
            }
            for fr in result.files
        ],
    }
