"""Source-store intake tests (WTK-111 §8, criteria S1–S4 and S7's
intake half) plus the WTK-111 §4.2/§4.3 adapter touchpoints: the
registered-snapshot source-identity rule behind the label-stability
invariant, and the ``source_file_sha256`` evidence-detail enrichment.

The store-side criteria that need a live DB deposit (S5's evidence
rows, S6, S8) belong to the transform/integration suites; here the
label half of S5 is pinned via ``derive_source_label`` directly.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.adapters import source_store, spreadsheet
from crmbuilder_v2.adapters.source_store import (
    SOURCE_MANIFEST_FILENAME,
    SourceRegistrationError,
    register_source,
)
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.transform.audit_deposit import derive_source_label

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 6, 12, 8, 15, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 1, 14, 0, 0, tzinfo=UTC)

MENTORS_CSV = "Name,Email\nAda Lovelace,ada@example.org\n"
DONATIONS_CSV = "Donor,Amount\nAda Lovelace,$100.00\n"


@pytest.fixture
def sources_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    root = tmp_path / "sources"
    monkeypatch.setenv("CRMBUILDER_V2_SOURCES_DIR", str(root))
    reset_settings_cache()
    yield root
    reset_settings_cache()


@pytest.fixture
def intake_files(tmp_path: Path) -> list[Path]:
    """One ``.xlsx`` original plus two per-sheet CSVs, the S1 shape."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    original = inbox / "cbm-mentor-tracking.xlsx"
    original.write_bytes(b"PK\x03\x04 not a real workbook")
    mentors = inbox / "mentors.csv"
    mentors.write_text(MENTORS_CSV, encoding="utf-8")
    donations = inbox / "donations.csv"
    donations.write_text(DONATIONS_CSV, encoding="utf-8")
    return [original, mentors, donations]


def _register(files: list[Path], now: datetime = NOW) -> Path:
    return register_source(
        files,
        "CRMBUILDER",
        "CBM Mentor Tracking",
        sheet_names={"mentors.csv": "Mentors"},
        registered_by="doug",
        now=now,
    )


def _read_manifest(snapshot: Path) -> dict:
    return json.loads(
        (snapshot / SOURCE_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# S1 — registration round-trip
# ---------------------------------------------------------------------------


def test_registration_round_trip(
    sources_root: Path, intake_files: list[Path]
) -> None:
    snapshot = _register(intake_files)

    assert snapshot == (
        sources_root / "CRMBUILDER" / "cbm-mentor-tracking" / "20260612T081500Z"
    )
    assert (snapshot / "mentors.csv").read_text(encoding="utf-8") == MENTORS_CSV
    assert (snapshot / "donations.csv").is_file()
    assert (snapshot / "originals" / "cbm-mentor-tracking.xlsx").read_bytes() == (
        intake_files[0].read_bytes()
    )

    manifest = _read_manifest(snapshot)
    assert manifest["source_manifest_version"] == 1
    assert manifest["engagement"] == "CRMBUILDER"
    assert manifest["source_name"] == "CBM Mentor Tracking"
    assert manifest["source_slug"] == "cbm-mentor-tracking"
    assert manifest["registered_at"] == "2026-06-12T08:15:00Z"
    assert manifest["registered_by"] == "doug"
    assert manifest["oversize_allowed"] is False
    assert manifest["notes"] is None

    (original_entry,) = manifest["originals"]
    assert original_entry["name"] == "cbm-mentor-tracking.xlsx"
    by_file = {entry["file"]: entry for entry in manifest["sheets"]}
    assert set(by_file) == {"mentors.csv", "donations.csv"}
    assert by_file["mentors.csv"]["sheet_name"] == "Mentors"
    assert by_file["donations.csv"]["sheet_name"] is None
    # Sole original => filename-derived attribution for every sheet.
    assert by_file["mentors.csv"]["original"] == "cbm-mentor-tracking.xlsx"

    # Byte counts and hashes independently recomputed from the held files.
    for entry in [original_entry, *manifest["sheets"]]:
        held = (
            snapshot / "originals" / entry["name"]
            if "name" in entry
            else snapshot / entry["file"]
        )
        data = held.read_bytes()
        assert entry["bytes"] == len(data)
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# S2 — snapshot immutability
# ---------------------------------------------------------------------------


def test_reupload_is_a_sibling_snapshot(
    sources_root: Path, intake_files: list[Path]
) -> None:
    first = _register(intake_files)
    before = {
        path.relative_to(first): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }

    second = _register(intake_files, now=LATER)
    assert second == first.parent / "20260701T140000Z"
    after = {
        path.relative_to(first): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_existing_snapshot_is_never_written_into(
    sources_root: Path, intake_files: list[Path]
) -> None:
    _register(intake_files)
    with pytest.raises(SourceRegistrationError) as excinfo:
        _register(intake_files)
    assert excinfo.value.code == "snapshot_exists"


# ---------------------------------------------------------------------------
# S3 — size limits (enforced-with-override)
# ---------------------------------------------------------------------------


def test_per_file_limit(
    sources_root: Path,
    intake_files: list[Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(source_store, "PER_FILE_LIMIT_BYTES", 10)
    with pytest.raises(SourceRegistrationError) as excinfo:
        _register(intake_files)
    assert excinfo.value.code == "source_file_too_large"
    # The message names the file and both numbers (§3.4); the original
    # is the first input checked and the first over the limit.
    message = str(excinfo.value)
    assert "cbm-mentor-tracking.xlsx" in message
    assert str(intake_files[0].stat().st_size) in message
    assert "10" in message
    # A refusal leaves no residue under the store root.
    assert not sources_root.exists()


def test_snapshot_limit_and_override(
    sources_root: Path,
    intake_files: list[Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    total = sum(path.stat().st_size for path in intake_files)
    monkeypatch.setattr(source_store, "SNAPSHOT_LIMIT_BYTES", total - 1)
    with pytest.raises(SourceRegistrationError) as excinfo:
        _register(intake_files)
    assert excinfo.value.code == "snapshot_too_large"

    snapshot = register_source(
        intake_files,
        "CRMBUILDER",
        "CBM Mentor Tracking",
        allow_oversize=True,
        now=NOW,
    )
    assert _read_manifest(snapshot)["oversize_allowed"] is True


# ---------------------------------------------------------------------------
# S4 — gitignore coverage of the store root
# ---------------------------------------------------------------------------


def test_store_root_is_gitignored() -> None:
    result = subprocess.run(
        [
            "git",
            "check-ignore",
            "-q",
            "crmbuilder-v2/data/sources/CRMBUILDER/x/20260612T081500Z/y.csv",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Intake validation
# ---------------------------------------------------------------------------


def test_intake_refusals(
    sources_root: Path, intake_files: list[Path], tmp_path: Path
) -> None:
    with pytest.raises(SourceRegistrationError) as excinfo:
        register_source(intake_files, "  ", "CBM Mentor Tracking", now=NOW)
    assert excinfo.value.code == "engagement_required"

    with pytest.raises(SourceRegistrationError) as excinfo:
        register_source(intake_files, "CRMBUILDER", "***", now=NOW)
    assert excinfo.value.code == "source_name_required"

    with pytest.raises(SourceRegistrationError) as excinfo:
        register_source(
            [tmp_path / "absent.csv"], "CRMBUILDER", "X1", now=NOW
        )
    assert excinfo.value.code == "source_file_missing"

    other = tmp_path / "other"
    other.mkdir()
    twin = other / "mentors.csv"
    twin.write_text("A\n1\n", encoding="utf-8")
    with pytest.raises(SourceRegistrationError) as excinfo:
        register_source(
            [*intake_files, twin], "CRMBUILDER", "X2", now=NOW
        )
    assert excinfo.value.code == "duplicate_file_name"


# ---------------------------------------------------------------------------
# CLI — directory expansion, sheet names, S7's intake half
# ---------------------------------------------------------------------------


def test_cli_round_trip_logs_no_cell_values(
    sources_root: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "SENTINEL-PII-555-0100"
    inbox = tmp_path / "cli-inbox"
    inbox.mkdir()
    (inbox / "mentors.csv").write_text(
        f"Name,Phone\nAda Lovelace,{sentinel}\n", encoding="utf-8"
    )
    (inbox / "workbook.xlsx").write_bytes(b"PK\x03\x04")

    rc = source_store.main(
        [
            str(inbox),
            "--engagement",
            "CRMBUILDER",
            "--source-name",
            "CLI Source",
            "--sheet-name",
            "mentors.csv=Mentors",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    snapshot = Path(captured.out.split("Snapshot: ")[1].strip())
    assert (snapshot / "mentors.csv").is_file()
    manifest = _read_manifest(snapshot)
    assert manifest["sheets"][0]["sheet_name"] == "Mentors"

    # §3.5 rule 2: names, byte counts, hashes — never content.
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert sentinel not in (
        snapshot / SOURCE_MANIFEST_FILENAME
    ).read_text(encoding="utf-8")


def test_cli_refusal_exit_code(
    sources_root: Path,
    intake_files: list[Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(source_store, "PER_FILE_LIMIT_BYTES", 10)
    rc = source_store.main(
        [
            *(str(path) for path in intake_files),
            "--engagement",
            "CRMBUILDER",
            "--source-name",
            "CBM Mentor Tracking",
        ]
    )
    assert rc == 1
    assert "source_file_too_large" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# WTK-111 §4.2/§4.3 — adapter touchpoints over a registered snapshot
# ---------------------------------------------------------------------------


def test_registered_snapshot_source_identity(
    sources_root: Path, intake_files: list[Path]
) -> None:
    snapshot = _register(intake_files)
    manifest, profile = spreadsheet.profile_source(snapshot, now=NOW)

    # §4.3: source_url is the SOURCE directory (the snapshot's parent),
    # source_name defaults from the registered name.
    assert manifest["source_url"] == snapshot.parent.resolve().as_uri()
    assert manifest["source_name"] == "CBM Mentor Tracking"
    assert derive_source_label(manifest) == (
        "spreadsheet @ cbm-mentor-tracking"
    )

    # An explicit source_name still wins over the registered default.
    override, _ = spreadsheet.profile_source(
        snapshot, source_name="Renamed", now=NOW
    )
    assert override["source_name"] == "Renamed"

    # §4.2: each entity's detail carries its sheet's registered hash.
    registered = _read_manifest(snapshot)
    hashes = {
        entry["file"]: entry["sha256"] for entry in registered["sheets"]
    }
    assert len(profile["entities"]) == 2
    for entity in profile["entities"].values():
        detail = entity["detail"]
        assert detail["source_file_sha256"] == hashes[detail["source_file"]]


def test_source_label_stable_across_snapshots(
    sources_root: Path, intake_files: list[Path]
) -> None:
    first = _register(intake_files)
    second = _register(intake_files, now=LATER)

    manifest_one, _ = spreadsheet.profile_source(first, now=NOW)
    manifest_two, _ = spreadsheet.profile_source(second, now=LATER)
    # The §4.3 invariant: one source, one label, across every snapshot —
    # while each run still carries its own snapshot instant.
    assert derive_source_label(manifest_one) == derive_source_label(
        manifest_two
    )
    assert manifest_one["timestamp"] != manifest_two["timestamp"]


def test_unregistered_directory_keeps_literal_behavior(
    tmp_path: Path,
) -> None:
    adhoc = tmp_path / "adhoc-export"
    adhoc.mkdir()
    (adhoc / "mentors.csv").write_text(MENTORS_CSV, encoding="utf-8")

    manifest, profile = spreadsheet.profile_source(adhoc, now=NOW)
    assert manifest["source_url"] == adhoc.resolve().as_uri()
    assert manifest["source_name"] == "adhoc-export"
    (entity,) = profile["entities"].values()
    assert "source_file_sha256" not in entity["detail"]


def test_unreadable_source_manifest_degrades_with_warning(
    tmp_path: Path,
) -> None:
    adhoc = tmp_path / "broken-snapshot"
    adhoc.mkdir()
    (adhoc / "mentors.csv").write_text(MENTORS_CSV, encoding="utf-8")
    (adhoc / SOURCE_MANIFEST_FILENAME).write_text(
        "{not json", encoding="utf-8"
    )

    manifest, _ = spreadsheet.profile_source(adhoc, now=NOW)
    assert manifest["source_url"] == adhoc.resolve().as_uri()
    assert any(
        SOURCE_MANIFEST_FILENAME in warning
        for warning in manifest["warnings"]
    )
