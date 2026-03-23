"""Tests for report generation."""

import json

from espo_impl.core.models import (
    FieldResult,
    FieldStatus,
    RunReport,
    RunSummary,
)
from espo_impl.core.reporter import Reporter


def make_report(content_version: str = "1.0.0") -> RunReport:
    return RunReport(
        timestamp="2026-03-21T14:30:22+00:00",
        instance_name="CBM Production",
        espocrm_url="https://cbm.espocloud.com",
        program_file="cbm_contact_fields.yaml",
        content_version=content_version,
        operation="run",
        summary=RunSummary(total=3, created=1, updated=1, skipped=1),
        results=[
            FieldResult(
                entity="Contact",
                field="contactType",
                status=FieldStatus.UPDATED,
                verified=True,
                changes=["label", "options"],
            ),
            FieldResult(
                entity="Contact",
                field="isMentor",
                status=FieldStatus.CREATED,
                verified=True,
            ),
            FieldResult(
                entity="Contact",
                field="mentorStatus",
                status=FieldStatus.SKIPPED,
            ),
        ],
    )


def test_write_report_creates_files(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report()
    log_path, json_path = reporter.write_report(report)

    assert log_path.exists()
    assert json_path.exists()
    assert log_path.suffix == ".log"
    assert json_path.suffix == ".json"


def test_report_filename_format(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report()
    log_path, _ = reporter.write_report(report)

    assert "cbm_production" in log_path.stem
    assert "run" in log_path.stem
    assert "20260321" in log_path.stem


def test_log_contains_metadata(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report()
    log_path, _ = reporter.write_report(report)
    content = log_path.read_text()

    assert "CBM Production" in content
    assert "cbm_contact_fields.yaml" in content
    assert "run" in content.lower()


def test_log_contains_results(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report()
    log_path, _ = reporter.write_report(report)
    content = log_path.read_text()

    assert "Contact.contactType" in content
    assert "UPDATED" in content
    assert "Contact.isMentor" in content
    assert "CREATED" in content
    assert "SKIPPED" in content


def test_log_contains_summary(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report()
    log_path, _ = reporter.write_report(report)
    content = log_path.read_text()

    assert "Total fields processed : 3" in content
    assert "Created              : 1" in content


def test_json_structure(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report()
    _, json_path = reporter.write_report(report)
    data = json.loads(json_path.read_text())

    assert "run_metadata" in data
    assert data["run_metadata"]["instance"] == "CBM Production"
    assert data["run_metadata"]["operation"] == "run"

    assert "summary" in data
    assert data["summary"]["total"] == 3
    assert data["summary"]["created"] == 1

    assert "results" in data
    assert len(data["results"]) == 3
    assert data["results"][0]["field"] == "contactType"
    assert data["results"][0]["status"] == "updated"
    assert data["results"][0]["verified"] is True
    assert data["results"][0]["changes"] == ["label", "options"]


def test_creates_reports_dir_if_missing(tmp_path):
    reports_dir = tmp_path / "nested" / "reports"
    reporter = Reporter(reports_dir)
    report = make_report()
    log_path, json_path = reporter.write_report(report)

    assert log_path.exists()
    assert json_path.exists()


# --- Content version tests ---


def test_log_contains_content_version(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report(content_version="2.1.0")
    log_path, _ = reporter.write_report(report)
    content = log_path.read_text()

    assert "Version      : 2.1.0" in content


def test_json_contains_content_version(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report(content_version="2.1.0")
    _, json_path = reporter.write_report(report)
    data = json.loads(json_path.read_text())

    assert data["run_metadata"]["content_version"] == "2.1.0"


def test_report_filename_includes_version_suffix(tmp_path):
    reporter = Reporter(tmp_path)
    report = make_report(content_version="2.1.0")
    log_path, _ = reporter.write_report(report)

    assert "v2_1_0" in log_path.stem
