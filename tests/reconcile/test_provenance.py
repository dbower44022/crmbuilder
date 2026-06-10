"""Provenance-index tests: synthetic multi-file fixtures + a real-file smoke test."""
from __future__ import annotations

from pathlib import Path

from espo_impl.core.reconcile.provenance import (
    build_field_provenance,
    discover_program_files,
)

_MN_ACCOUNT = """\
version: "1.0"
content_version: "1.0.0"
entities:
  Account:
    fields:
      - name: industrySubsector
        type: enum
        label: "Industry Subsector"
"""

_FU_ACCOUNT = """\
version: "1.0"
content_version: "1.0.0"
entities:
  Account:
    fields:
      - name: geographicServiceArea
        type: multiEnum
        label: "Geographic Service Area"
"""

_DUP = """\
version: "1.0"
content_version: "1.0.0"
entities:
  Account:
    fields:
      - name: industrySubsector
        type: enum
        label: "Dup"
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body)
    return p


def test_same_entity_across_files_maps_each_field_to_its_file(tmp_path):
    mn = _write(tmp_path, "MN-Account.yaml", _MN_ACCOUNT)
    fu = _write(tmp_path, "FU-Account.yaml", _FU_ACCOUNT)

    desired, collisions = build_field_provenance([mn, fu])

    assert collisions == []
    account = desired["Account"]
    assert account["industrySubsector"][1] == mn
    assert account["geographicServiceArea"][1] == fu
    # The FieldDefinition is carried through for the diff engine.
    assert account["industrySubsector"][0].type == "enum"


def test_duplicate_field_is_reported_not_overwritten(tmp_path):
    mn = _write(tmp_path, "MN-Account.yaml", _MN_ACCOUNT)
    dup = _write(tmp_path, "ZZ-Account.yaml", _DUP)

    desired, collisions = build_field_provenance([mn, dup])

    # First occurrence wins.
    assert desired["Account"]["industrySubsector"][1] == mn
    assert len(collisions) == 1
    c = collisions[0]
    assert (c.entity, c.field_name) == ("Account", "industrySubsector")
    assert c.first_file == mn and c.duplicate_file == dup


def test_discover_skips_test_and_archive_variants(tmp_path):
    (tmp_path / "Archive").mkdir()
    keep = _write(tmp_path, "MN-Session.yaml", _MN_ACCOUNT)
    _write(tmp_path, "MN-Session-TEST.yaml", _MN_ACCOUNT)
    _write(tmp_path / "Archive", "old.yaml", _MN_ACCOUNT)

    found = discover_program_files(tmp_path)

    assert keep in found
    assert tmp_path / "MN-Session-TEST.yaml" not in found
    assert tmp_path / "Archive" / "old.yaml" not in found


def test_real_cbm_file_smoke():
    real = Path.home() / "Dropbox/Projects/ClevelandBusinessMentors/programs/MN/MN-Session.yaml"
    if not real.exists():
        return  # client repo not present in this environment
    desired, collisions = build_field_provenance([real])
    assert desired["Session"]["sessionType"][1] == real
    assert desired["Session"]["meetingLocationType"][0].label == "Meeting Location Type"
