"""Reconcile report-writer tests (offline)."""
from __future__ import annotations

import json
from pathlib import Path

from espo_impl.core.reconcile.locators import FieldLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference
from espo_impl.core.reconcile.reconciler import FileReconcileResult, ReconcileResult
from espo_impl.core.reconcile.report import write_reconcile_report


def _changed():
    return Difference(
        config_type=ConfigType.FIELD,
        category=DiffCategory.CHANGED,
        entity="Contact",
        locator=FieldLocator("Contact", "title", "label"),
        property="label",
        yaml_value="Title",
        crm_value="Account Title",
        source_file=Path("MN-Contact.yaml"),
    )


def _yaml_only():
    return Difference(
        config_type=ConfigType.FIELD,
        category=DiffCategory.YAML_ONLY,
        entity="Contact",
        locator=FieldLocator("Contact", "legacy", None),
        source_file=Path("MN-Contact.yaml"),
    )


def _result():
    fr = FileReconcileResult(
        path=Path("MN-Contact.yaml"),
        applied=[_changed()],
        not_applied=[(_yaml_only(), "report-only (not auto-applied in v1)")],
        old_version="1.0.0",
        new_version="1.1.0",
    )
    return ReconcileResult(files=[fr])


def test_writes_paired_log_and_json(tmp_path):
    log_path, json_path = write_reconcile_report(
        _result(), tmp_path / "reports",
        instance_name="CBM Test", source_url="https://crm.example",
        timestamp="2026-06-09T12:00:00",
    )

    assert log_path.exists() and json_path.exists()
    assert log_path.suffix == ".log" and json_path.suffix == ".json"
    assert log_path.stem == json_path.stem  # paired stem

    log = log_path.read_text()
    assert "CRM Builder — Reconcile Report" in log
    assert "CBM Test" in log
    assert "live CRM was not modified" in log            # provenance note
    assert "content_version 1.0.0 → 1.1.0" in log
    assert "Title → Account Title" in log                 # old → new
    assert "report-only" in log                           # not-applied reason


def test_json_is_machine_readable(tmp_path):
    _, json_path = write_reconcile_report(
        _result(), tmp_path / "reports", timestamp="2026-06-09T12:00:00",
    )
    data = json.loads(json_path.read_text())

    assert data["operation"] == "reconcile"
    assert data["direction"] == "crm_to_yaml"
    assert data["applied_count"] == 1
    assert data["not_applied_count"] == 1
    f = data["files"][0]
    assert f["new_version"] == "1.1.0"
    assert f["applied"][0]["yaml_value"] == "Title"
    assert f["applied"][0]["crm_value"] == "Account Title"
    assert f["not_applied"][0]["reason"].startswith("report-only")


def test_creates_reports_dir(tmp_path):
    target = tmp_path / "client" / "reports"
    assert not target.exists()
    write_reconcile_report(_result(), target, timestamp="2026-06-09T12:00:00")
    assert target.is_dir()
