"""Tests for automation.core.deployment.record_generator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document

from automation.core.deployment.record_generator import (
    DeploymentRecordValues,
    generate_deployment_record,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "deployment_record_values_cbmtest.json"
)


def _make_fixture_values(**overrides) -> DeploymentRecordValues:
    """Build a DeploymentRecordValues from the CBM Test fixture.

    :param overrides: Optional keyword overrides for any field.
    :returns: A populated DeploymentRecordValues, with overrides applied.
    """
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    data.update(overrides)
    return DeploymentRecordValues(**data)


# ── Validation ───────────────────────────────────────────────────────


def test_values_validates_required_fields_non_empty():
    """Empty required string fields trigger ValueError listing the field."""
    with pytest.raises(ValueError) as excinfo:
        _make_fixture_values(instance_code="")
    assert "instance_code" in str(excinfo.value)


def test_values_accepts_optional_none():
    """Optional fields (typed `T | None`) may be None."""
    values = _make_fixture_values(
        droplet_id=None,
        droplet_detail_url=None,
        droplet_console_url=None,
    )
    assert values.droplet_id is None
    assert values.droplet_detail_url is None
    assert values.droplet_console_url is None


# ── Generation ───────────────────────────────────────────────────────


def test_generate_writes_file(tmp_path):
    """Generator writes a .docx file of substantive size."""
    values = _make_fixture_values()
    out = tmp_path / "out.docx"
    result = generate_deployment_record(values, out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 10_000


def test_generated_docx_opens_in_python_docx(tmp_path):
    """The generated .docx round-trips through python-docx cleanly."""
    values = _make_fixture_values()
    out = tmp_path / "out.docx"
    generate_deployment_record(values, out)
    document = Document(str(out))
    assert len(document.paragraphs) >= 100


def _all_text(document: Document) -> str:
    """Concatenate every paragraph and table-cell string in the document."""
    chunks: list[str] = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                chunks.append(cell.text)
    return "\n".join(chunks)


def test_generated_docx_contains_expected_strings(tmp_path):
    """Key fixture values appear in the rendered document."""
    values = _make_fixture_values()
    out = tmp_path / "out.docx"
    generate_deployment_record(values, out)
    text = _all_text(Document(str(out)))

    expected_substrings = [
        values.instance_code,
        values.application_url,
        values.proton_pass_admin_entry,
        values.proton_pass_db_root_entry,
        values.proton_pass_hosting_entry,
        values.espocrm_version,
        values.mariadb_version,
        values.nginx_version,
        values.tls_sha256_fingerprint,
        values.docker_version,
        values.docker_compose_version,
        # Deploy date appears as a YYYY-MM-DD prefix in the summary
        values.instance_created_at_utc[:10],
    ]
    missing = [s for s in expected_substrings if s not in text]
    assert not missing, f"Missing substrings: {missing}"


def test_generated_docx_section_structure(tmp_path):
    """All eleven numbered sections plus Revision History / Change Log."""
    values = _make_fixture_values()
    out = tmp_path / "out.docx"
    generate_deployment_record(values, out)
    text = _all_text(Document(str(out)))

    headings = [
        "Revision History",
        "1. Document Purpose and Scope",
        "2. Deployment Summary",
        "3. DigitalOcean Droplet",
        "4. Domain and DNS",
        "5. TLS Certificate",
        "6. EspoCRM Application",
        "7. SSH Access",
        "8. Credentials Inventory",
        "9. Deployment History",
        "10. Operational Notes",
        "11. Open Items",
        "Change Log",
    ]
    missing = [h for h in headings if h not in text]
    assert not missing, f"Missing section headings: {missing}"


def test_generated_docx_validates_with_office_validator_when_available(
    tmp_path,
):
    """Run the Anthropic office validator if available; otherwise skip."""
    validator = Path("/mnt/skills/public/docx/scripts/office/validate.py")
    if not validator.exists():
        pytest.skip("Office validator not available in this environment")

    values = _make_fixture_values()
    out = tmp_path / "out.docx"
    generate_deployment_record(values, out)
    result = subprocess.run(
        [sys.executable, str(validator), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Office validator failed: {result.stdout}\n{result.stderr}"
    )


# ── CLI ──────────────────────────────────────────────────────────────


def test_cli_round_trip(tmp_path):
    """Running the module via -m produces a .docx from the fixture."""
    out = tmp_path / "cli.docx"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "automation.core.deployment.record_generator",
            "--values",
            str(FIXTURE_PATH),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, (
        f"CLI exited {result.returncode}: {result.stdout}\n{result.stderr}"
    )
    assert out.exists()
    assert out.stat().st_size > 10_000
