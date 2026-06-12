"""Spreadsheet adapter end-to-end and edge-case validation (WTK-114).

Inputs beyond the WTK-110 golden samples and the WTK-112 seam checks:
malformed and ragged CSVs, mixed-type and sparse columns, ambiguous
enum-like value sets, files at and over the WTK-111 size limits, and
unsupported formats. The standing claim under test: the full
ingest -> profile -> emit flow rejects bad inputs cleanly with useful
errors, produces sane evidence/confidence output on messy-but-valid
sheets, and the emitted inventory stays conformant to the
normalized-inventory contract — seam checker plus the landed
``plan_deposit`` — in every case.

Defects this validation surfaced (fixed in the adapter alongside):
an uncaught ``UnicodeDecodeError`` on bytes invalid in cp1252 too
(spec §6.1 promises undecodable files become manifest ``errors``); a
duplicate-header suffix colliding with a literal header and clobbering
the per-column inference (criterion C7's silent-evidence-loss mode);
a single non-CSV file silently parsed as CSV into garbage instead of
an unsupported-format rejection; and ``_auto_number_pass`` crashing
the run on an integer column with a sub-threshold non-integer
straggler.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.adapters import source_store, spreadsheet
from crmbuilder_v2.adapters.source_store import (
    SourceRegistrationError,
    register_source,
)
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.transform import audit_deposit
from crmbuilder_v2.transform.audit_deposit import ExistingState

from tests.crmbuilder_v2.seam import assert_seam_conformant

NOW = datetime(2026, 6, 12, 9, 30, 0, tzinfo=UTC)


@pytest.fixture
def sources_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    root = tmp_path / "sources"
    monkeypatch.setenv("CRMBUILDER_V2_SOURCES_DIR", str(root))
    reset_settings_cache()
    yield root
    reset_settings_cache()


def _write_sheet(
    tmp_path: Path, content: str | bytes, name: str = "sheet.csv"
) -> Path:
    target = tmp_path / "source"
    target.mkdir(exist_ok=True)
    path = target / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return target


def _profile(source: Path) -> tuple[dict, dict]:
    return spreadsheet.profile_source(source, now=NOW)


def _assert_emits_conformant_inventory(
    manifest: dict, profile: dict
) -> audit_deposit.DepositPlan:
    """The WTK-114 standing claim: whatever the input did to the run,
    the emitted pair passes the seam contract and flows through the
    landed consumer with every create at ``candidate``."""
    assert_seam_conformant(manifest, profile)
    plan = audit_deposit.plan_deposit(manifest, profile, ExistingState())
    for item in plan.creates:
        if item.record_type == "planning_item":
            continue  # the §3.6 anomaly PI — born Draft, no evidence
        assert item.payload["status"] == "candidate"
        assert item.evidence["catalog_class"] == "custom"
    return plan


def _inference(profile: dict, espo_name: str, api_name: str) -> dict:
    return profile["entities"][espo_name]["fields"][api_name]["detail"][
        "type_inference"
    ]


# ---------------------------------------------------------------------------
# Malformed and ragged CSVs
# ---------------------------------------------------------------------------


def test_empty_file_yields_empty_entity(tmp_path):
    source = _write_sheet(tmp_path, "")
    manifest, profile = _profile(source)
    (entity,) = manifest["entities"]
    assert entity["espo_name"] == "sheet"
    assert entity["fields"] == []
    entry = profile["entities"]["sheet"]
    assert entry["record_count"] == 0
    assert entry["detail"]["empty"] is True
    assert entry["fields"] == {}
    # An empty file can't even sniff a delimiter — the fallback is
    # visible as a warning, which rides into the anomaly PI.
    assert any("sniff failed" in line for line in manifest["warnings"])
    plan = _assert_emits_conformant_inventory(manifest, profile)
    creates = {item.record_type for item in plan.creates}
    assert creates == {"entity", "planning_item"}


def test_header_only_sheet_is_all_empty_columns(tmp_path):
    source = _write_sheet(tmp_path, "Name,Email,Joined\n")
    manifest, profile = _profile(source)
    (entity,) = manifest["entities"]
    assert [f["field_type"] for f in entity["fields"]] == ["empty"] * 3
    entry = profile["entities"]["sheet"]
    assert entry["record_count"] == 0
    assert entry["detail"]["empty"] is True
    for api_name in ("Name", "Email", "Joined"):
        block = _inference(profile, "sheet", api_name)
        assert block["inferred_type"] == "empty"
        assert block["confidence"] == "none"
        assert block["non_empty_count"] == 0
        # record_count 0: population_rate is omitted, not divided by 0.
        assert "population_rate" not in entry["fields"][api_name]
    plan = _assert_emits_conformant_inventory(manifest, profile)
    assert len(plan.creates) == 4  # 1 entity + 3 fields


def test_blank_rows_only_counted_not_recorded(tmp_path):
    source = _write_sheet(tmp_path, ",,\n  ,  ,\n,,\n")
    manifest, profile = _profile(source)
    (entity,) = manifest["entities"]
    assert entity["fields"] == []
    entry = profile["entities"]["sheet"]
    assert entry["record_count"] == 0
    assert entry["detail"]["blank_row_count"] == 3
    _assert_emits_conformant_inventory(manifest, profile)


def test_long_ragged_rows_truncated_to_header_width(tmp_path):
    source = _write_sheet(
        tmp_path,
        "A,B\n1,2,EXTRA,MORE\n3,4\n5,6,SPILL\n",
    )
    manifest, profile = _profile(source)
    entry = profile["entities"]["sheet"]
    assert entry["record_count"] == 3
    assert entry["detail"]["ragged_row_count"] == 2
    # The spilled cells are gone: only the two header columns exist
    # and B holds exactly the in-width values.
    (entity,) = manifest["entities"]
    assert [f["api_name"] for f in entity["fields"]] == ["A", "B"]
    assert entry["fields"]["B"]["populated_count"] == 3
    assert any("2 ragged row(s)" in line for line in manifest["warnings"])
    assert any(
        "2 ragged row(s)" in row["note"] for row in profile["anomalies"]
    )
    _assert_emits_conformant_inventory(manifest, profile)


def test_unclosed_quote_swallows_rest_of_file(tmp_path):
    # RFC 4180 parsing consumes from the unclosed quote to EOF as one
    # cell — the rows "disappear" into it rather than crashing.
    source = _write_sheet(
        tmp_path,
        'Name,Notes\nAda,"unclosed quote\nGrace,fine\nKay,also fine\n',
    )
    manifest, profile = _profile(source)
    entry = profile["entities"]["sheet"]
    assert entry["record_count"] == 1
    notes = entry["fields"]["Notes"]
    assert notes["populated_count"] == 1
    _assert_emits_conformant_inventory(manifest, profile)


def test_undecodable_sheet_becomes_error_and_run_continues(tmp_path):
    # 0x81 is invalid in UTF-8 and unmapped in cp1252 — past the
    # fallback, so the sheet fails; the sibling sheet still profiles.
    source = _write_sheet(tmp_path, b"a,b\n\x81,2\n", name="broken.csv")
    _write_sheet(tmp_path, "Name\nAda\nGrace\n", name="good.csv")
    manifest, profile = _profile(source)
    (error,) = manifest["errors"]
    assert error.startswith("sheet broken:")
    assert "decode" in error
    assert [e["espo_name"] for e in manifest["entities"]] == ["good"]
    assert profile["entities"]["good"]["record_count"] == 2
    plan = _assert_emits_conformant_inventory(manifest, profile)
    # The failure reaches triage as an anomaly Planning Item line.
    assert any(
        line.startswith("audit error: sheet broken:")
        for line in plan.anomalies
    )


def test_oversized_cell_becomes_error_not_crash(tmp_path):
    import csv as csv_module

    huge = "x" * (csv_module.field_size_limit() + 1)
    source = _write_sheet(tmp_path, f"A,B\n1,{huge}\n", name="huge.csv")
    manifest, profile = _profile(source)
    (error,) = manifest["errors"]
    assert error.startswith("sheet huge:")
    assert manifest["entities"] == []
    _assert_emits_conformant_inventory(manifest, profile)


def test_duplicate_header_suffix_never_collides(tmp_path):
    # `Amount, Amount, Amount_2`: the renamed second column must not
    # collide with the literal third — a collision keys two columns
    # onto one inference/profile entry (C7's silent-evidence-loss
    # mode). Distinct types per column prove nothing was clobbered.
    source = _write_sheet(
        tmp_path,
        "Amount,Amount,Amount_2\n"
        "1,alpha,2024-01-05\n"
        "2,beta,2024-02-10\n"
        "3,gamma,2024-03-15\n",
    )
    manifest, profile = _profile(source)
    (entity,) = manifest["entities"]
    api_names = [f["api_name"] for f in entity["fields"]]
    assert api_names == ["Amount", "Amount_2", "Amount_2_2"]
    assert len(set(api_names)) == 3
    assert [f["yaml_name"] for f in entity["fields"]] == [
        "amount",
        "amount_2",
        "amount_2_2",
    ]
    assert _inference(profile, "sheet", "Amount")["base_type"] == "integer"
    assert _inference(profile, "sheet", "Amount_2")["base_type"] == "text"
    assert _inference(profile, "sheet", "Amount_2_2")["base_type"] == "date"
    renames = sorted(
        row["note"] for row in profile["anomalies"] if "duplicate" in row["note"]
    )
    assert renames == [
        "duplicate header 'Amount'; renamed 'Amount_2'",
        "duplicate header 'Amount_2'; renamed 'Amount_2_2'",
    ]
    _assert_emits_conformant_inventory(manifest, profile)


def test_utf16_tab_delimited_excel_unicode_export(tmp_path):
    text = "Name\tVisits\nAda\t3\nGrace\t5\n"
    source = _write_sheet(
        tmp_path, text.encode("utf-16"), name="unicode.csv"
    )
    manifest, profile = _profile(source)
    assert manifest["warnings"] == []  # BOM sniff, no fallback
    (entity,) = manifest["entities"]
    assert [f["api_name"] for f in entity["fields"]] == ["Name", "Visits"]
    assert _inference(profile, "unicode", "Visits")["base_type"] == "integer"
    _assert_emits_conformant_inventory(manifest, profile)


# ---------------------------------------------------------------------------
# Mixed-type and sparse columns
# ---------------------------------------------------------------------------


def _column_sheet(tmp_path: Path, header: str, cells: list[str]) -> Path:
    return _write_sheet(
        tmp_path, header + "\n" + "\n".join(cells) + "\n"
    )


def test_inference_threshold_boundary(tmp_path):
    # 19/20 integers is exactly tau (0.95): the type wins, and the
    # straggler must not crash the auto_number post-pass.
    cells = [str(i + 1) for i in range(19)] + ["word"]
    source = _column_sheet(tmp_path, "Mostly Numbers", cells)
    manifest, profile = _profile(source)
    block = _inference(profile, "sheet", "Mostly Numbers")
    assert block["inferred_type"] == "integer"  # no auto_number promotion
    assert block["match_rate"] == 0.95
    assert block["confidence"] == "medium"
    _assert_emits_conformant_inventory(manifest, profile)


def test_below_threshold_degrades_to_text_with_runner_up(tmp_path):
    cells = [str(i + 1) for i in range(18)] + ["w1", "w2"]
    source = _column_sheet(tmp_path, "Mixed", cells)
    _, profile = _profile(source)
    block = _inference(profile, "sheet", "Mixed")
    assert block["inferred_type"] == "text"
    assert block["match_rate"] == 1.0  # text is the universal fallback
    assert block["runner_up"] == "integer"
    assert block["runner_up_rate"] == 0.9


def test_half_dates_half_integers_is_text_with_evidence(tmp_path):
    cells = [f"2024-01-{i + 1:02d}" for i in range(5)] + [
        str(i + 1) for i in range(5)
    ]
    source = _column_sheet(tmp_path, "When Or Count", cells)
    _, profile = _profile(source)
    block = _inference(profile, "sheet", "When Or Count")
    assert block["inferred_type"] == "text"
    # Both recognizers tie at 0.5; specificity breaks the tie.
    assert block["runner_up"] == "integer"
    assert block["runner_up_rate"] == 0.5


def test_sparse_column_low_population_low_confidence(tmp_path):
    rows = ["5" if i < 2 else "" for i in range(100)]
    rows[50] = "5"  # 3 populated, repeated so auto_number can't fire
    other = ["filler"] * 100
    content = "Rare,Filler\n" + "\n".join(
        f"{a},{b}" for a, b in zip(rows, other, strict=True)
    )
    source = _write_sheet(tmp_path, content + "\n")
    manifest, profile = _profile(source)
    rare = profile["entities"]["sheet"]["fields"]["Rare"]
    assert rare["populated_count"] == 3
    assert rare["population_rate"] == 0.03
    assert rare["detail"]["low_population"] is True
    block = rare["detail"]["type_inference"]
    assert block["inferred_type"] == "integer"
    assert block["confidence"] == "low"  # won the vote, < 10 populated
    _assert_emits_conformant_inventory(manifest, profile)


def test_auto_number_density_boundary(tmp_path):
    at = [str(v) for v in (1, 2, 3, 4, 5, 6, 7, 8, 9, 15)]  # span 15/10
    over = [str(v) for v in (1, 2, 3, 4, 5, 6, 7, 8, 9, 16)]  # span 16/10
    source = _write_sheet(
        tmp_path,
        "At,Over\n" + "\n".join(f"{a},{b}" for a, b in zip(at, over, strict=True)) + "\n",
    )
    _, profile = _profile(source)
    assert _inference(profile, "sheet", "At")["inferred_type"] == "auto_number"
    assert _inference(profile, "sheet", "Over")["inferred_type"] == "integer"


# ---------------------------------------------------------------------------
# Ambiguous enum-like value sets
# ---------------------------------------------------------------------------


def test_enum_support_floor(tmp_path):
    nine = (["red", "green", "blue"] * 3)[:9]
    ten = (["red", "green", "blue"] * 4)[:10]
    source = _write_sheet(
        tmp_path,
        "Nine,Ten\n"
        + "\n".join(
            f"{a},{b}" for a, b in zip(nine + [""], ten, strict=True)
        )
        + "\n",
    )
    manifest, profile = _profile(source)
    below = _inference(profile, "sheet", "Nine")
    assert below["inferred_type"] == "text"  # 9 < enum_min_support
    assert below["confidence"] == "low"
    at_floor = _inference(profile, "sheet", "Ten")
    assert at_floor["inferred_type"] == "enum"
    assert at_floor["recognizer"] == "enum_post_pass"
    fields = {
        f["api_name"]: f for f in manifest["entities"][0]["fields"]
    }
    assert "options" not in fields["Nine"]["properties"]
    assert sorted(fields["Ten"]["properties"]["options"]) == [
        "blue",
        "green",
        "red",
    ]
    _assert_emits_conformant_inventory(manifest, profile)


def test_enum_absolute_option_cap(tmp_path):
    # 60 populated cells: the cap is min(24, ceil(0.5 * 60)) = 24.
    in_cap = [f"opt{i % 24:02d}" for i in range(60)]
    over_cap = [f"opt{i % 25:02d}" for i in range(60)]
    source = _write_sheet(
        tmp_path,
        "InCap,OverCap\n"
        + "\n".join(
            f"{a},{b}" for a, b in zip(in_cap, over_cap, strict=True)
        )
        + "\n",
    )
    manifest, profile = _profile(source)
    assert _inference(profile, "sheet", "InCap")["inferred_type"] == "enum"
    over = _inference(profile, "sheet", "OverCap")
    assert over["inferred_type"] == "text"  # 25 distinct > enum_max_options
    fields = {f["api_name"]: f for f in manifest["entities"][0]["fields"]}
    assert len(fields["InCap"]["properties"]["options"]) == 24
    _assert_emits_conformant_inventory(manifest, profile)


def test_all_unique_values_never_enum(tmp_path):
    cells = [f"name{i}" for i in range(12)]
    source = _column_sheet(tmp_path, "Names", cells)
    _, profile = _profile(source)
    block = _inference(profile, "sheet", "Names")
    assert block["inferred_type"] == "text"  # distinct == populated


def test_numeric_codes_stay_integer_never_enum_or_boolean(tmp_path):
    # {1,0} is deliberately not boolean and the enum post-pass never
    # touches numeric bases — the 2-value distribution is the signal.
    flags = (["0", "1"] * 6)[:12]
    codes = (["0", "1", "2"] * 4)[:12]
    source = _write_sheet(
        tmp_path,
        "Flag,Code\n"
        + "\n".join(f"{a},{b}" for a, b in zip(flags, codes, strict=True))
        + "\n",
    )
    manifest, profile = _profile(source)
    for api_name in ("Flag", "Code"):
        block = _inference(profile, "sheet", api_name)
        assert block["inferred_type"] == "integer", api_name
        metrics = profile["entities"]["sheet"]["fields"][api_name]
        assert "declared_option_count" not in metrics
        assert "top_values" in metrics["detail"]  # distribution as evidence
    fields = {f["api_name"]: f for f in manifest["entities"][0]["fields"]}
    assert "options" not in fields["Flag"]["properties"]


def test_comma_multi_value_token_cap(tmp_path):
    # Comma is admitted as a delimiter only under the tighter 12-token
    # cap; 13 distinct tokens reject it and the column stays text.
    toks13 = [f"t{i:02d}" for i in range(13)]
    toks10 = [f"t{i}" for i in range(10)]
    wide = [f"{toks13[i % 13]}, {toks13[(i + 1) % 13]}" for i in range(20)]
    tight = [f"{toks10[i % 10]}, {toks10[(i + 3) % 10]}" for i in range(20)]
    source = _write_sheet(
        tmp_path,
        "Wide,Tight\n"
        + "\n".join(f'"{a}","{b}"' for a, b in zip(wide, tight, strict=True))
        + "\n",
    )
    manifest, profile = _profile(source)
    assert _inference(profile, "sheet", "Wide")["inferred_type"] == "text"
    tight_block = _inference(profile, "sheet", "Tight")
    assert tight_block["inferred_type"] == "multi_enum"
    metrics = profile["entities"]["sheet"]["fields"]["Tight"]
    assert metrics["declared_option_count"] == 10
    assert metrics["used_option_count"] == 10
    # Token distribution sums past populated_count by construction.
    assert (
        sum(metrics["detail"]["value_distribution"].values())
        >= metrics["populated_count"]
    )
    _assert_emits_conformant_inventory(manifest, profile)


# ---------------------------------------------------------------------------
# Files at and over the size limit (end-to-end through the WTK-111 store)
# ---------------------------------------------------------------------------


def test_size_limit_at_and_over_end_to_end(
    sources_root, tmp_path, monkeypatch
):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    sheet = inbox / "contacts.csv"
    sheet.write_text("Name,Visits\nAda,3\nGrace,5\n", encoding="utf-8")
    size = sheet.stat().st_size

    # Exactly at the per-file limit: registration passes (the check is
    # strictly greater-than) and the snapshot profiles end to end.
    monkeypatch.setattr(source_store, "PER_FILE_LIMIT_BYTES", size)
    snapshot = register_source(
        [sheet], "CRMBUILDER", "Limit Probe", registered_by="doug", now=NOW
    )
    manifest, profile = _profile(snapshot)
    assert manifest["source_name"] == "Limit Probe"
    assert (
        profile["entities"]["contacts"]["detail"]["source_file_sha256"]
    )
    _assert_emits_conformant_inventory(manifest, profile)

    # One byte over: refused before anything is copied, with the
    # machine-readable code and the override named in the message.
    monkeypatch.setattr(source_store, "PER_FILE_LIMIT_BYTES", size - 1)
    with pytest.raises(SourceRegistrationError) as excinfo:
        register_source(
            [sheet],
            "CRMBUILDER",
            "Limit Probe",
            registered_by="doug",
            now=datetime(2026, 6, 12, 9, 45, 0, tzinfo=UTC),
        )
    assert excinfo.value.code == "source_file_too_large"
    assert "--allow-oversize" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Unsupported formats and missing inputs
# ---------------------------------------------------------------------------


def test_single_non_csv_file_rejected(tmp_path):
    workbook = tmp_path / "book.xlsx"
    workbook.write_bytes(b"PK\x03\x04 not a real workbook")
    with pytest.raises(ValueError, match="unsupported source format"):
        spreadsheet.profile_source(workbook, now=NOW)
    with pytest.raises(ValueError, match="export each sheet to CSV"):
        spreadsheet.profile_source(workbook, now=NOW)


def test_directory_without_csvs_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "book.xlsx").write_bytes(b"PK\x03\x04")
    with pytest.raises(ValueError, match="no CSV files found"):
        spreadsheet.profile_source(source, now=NOW)


def test_missing_source_rejected(tmp_path):
    with pytest.raises(ValueError, match="source not found"):
        spreadsheet.profile_source(tmp_path / "absent", now=NOW)
    with pytest.raises(ValueError, match="source not found"):
        spreadsheet.profile_source(tmp_path / "absent.csv", now=NOW)
