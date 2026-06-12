"""Spreadsheet profiler adapter tests (WTK-110 §7).

Three golden fixtures live beside this module as literal CSV files
(the manifest-is-the-fixture-format property, WTK-090 §2.1): G-1
typed coverage, G-2 cross-sheet reference, G-3 degradation honesty.
Expectations are hand-pinned from the spec's §7.1 tables; conformance
checks C1–C8 cover the seam contract, the landed-consumer path, the
stage-1 table, the partition rule, idempotent re-runs, determinism,
and the profile join.

One deliberate deviation from the §7.1 G-1 annotation: ``Website``
(9 populated of 12) grades ``low``, not ``medium`` — §5.2 is the
normative grade table (`medium` requires ``non_empty_count >= 10``)
and it wins over the sample's prose.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access.vocab import CATALOG_ATTRIBUTE_TYPES, FIELD_TYPES
from crmbuilder_v2.adapters import spreadsheet
from crmbuilder_v2.adapters.spreadsheet import AdapterOptions
from crmbuilder_v2.transform import audit_deposit, normalize
from crmbuilder_v2.transform.audit_deposit import ExistingRecord, ExistingState
from crmbuilder_v2.transform.normalize import DiscoveredItem

from tests.crmbuilder_v2.seam import assert_seam_conformant
from tests.crmbuilder_v2.transform.test_audit_deposit import (
    t1_manifest,
    t1_profile,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)

# G-1's pinned column -> native type expectations (spec §7.1).
G1_EXPECTED_TYPES = {
    "ID": "auto_number",
    "Name": "text",
    "Email": "email",
    "Phone": "phone",
    "Active": "boolean",
    "Joined": "date",
    "Donation Total": "currency",
    "Visits": "integer",
    "Score": "decimal",
    "Website": "url",
    "Stage": "enum",
    "Tags": "multi_enum",
    "Notes": "long_text",
    "Legacy Code": "empty",
}

# §6.3's third column, entry for entry (criterion C3).
SPREADSHEET_COMPOSED = {
    "text": "text",
    "long_text": "long_text",
    "integer": "number",
    "decimal": "number",
    "currency": "money",
    "percent": "number",
    "boolean": "boolean",
    "date": "date",
    "datetime": "datetime",
    "time": "text",
    "email": "text",
    "phone": "text",
    "url": "text",
    "enum": "enum",
    "multi_enum": "multi_enum",
    "reference": "reference",
    "auto_number": "number",
    "empty": "text",
}


@pytest.fixture(scope="module")
def g1() -> tuple[dict, dict]:
    return spreadsheet.profile_source(FIXTURES / "g1", now=NOW)


@pytest.fixture(scope="module")
def g2() -> tuple[dict, dict]:
    return spreadsheet.profile_source(FIXTURES / "g2", now=NOW)


@pytest.fixture(scope="module")
def g3() -> tuple[dict, dict]:
    return spreadsheet.profile_source(FIXTURES / "g3", now=NOW)


def _fields(manifest: dict, espo_name: str) -> dict[str, dict]:
    entity = next(
        e for e in manifest["entities"] if e["espo_name"] == espo_name
    )
    return {f["api_name"]: f for f in entity["fields"]}


def _inference(profile: dict, espo_name: str, api_name: str) -> dict:
    return profile["entities"][espo_name]["fields"][api_name]["detail"][
        "type_inference"
    ]


# ---------------------------------------------------------------------------
# G-1 — typed coverage (spec §7.1)
# ---------------------------------------------------------------------------


def test_g1_manifest_shape(g1):
    manifest, _ = g1
    assert manifest["manifest_version"] == 1
    assert manifest["source_system"] == "spreadsheet"
    assert manifest["timestamp"] == "2026-06-12T08:00:00Z"
    assert manifest["source_url"].startswith("file://")
    assert manifest["source_name"] == "g1"
    assert manifest["errors"] == []
    assert manifest["warnings"] == []
    assert manifest["relationships"] == []
    assert manifest["roles"] == []
    assert manifest["teams"] == []

    (entity,) = manifest["entities"]
    assert entity["yaml_name"] == "contacts"
    assert entity["espo_name"] == "contacts"  # the profile join key
    assert entity["label_singular"] == "contacts"  # no singularization
    assert entity["entity_type"] is None  # kind is triage's (DEC-292)
    assert entity["entity_class"] == "custom"
    assert entity["stream"] is False
    assert entity["layouts"] == []
    assert entity["filtered_tabs"] == []
    assert "label_plural" not in entity

    fields = _fields(manifest, "contacts")
    assert {n: f["field_type"] for n, f in fields.items()} == G1_EXPECTED_TYPES
    for field in fields.values():
        assert field["field_class"] == "custom"
        assert field["properties"]["required"] is False
        assert "default" not in field["properties"]
        assert field["label"] == field["api_name"]
    # Header slugs are the yaml_name form.
    assert fields["Donation Total"]["yaml_name"] == "donation_total"
    assert fields["Legacy Code"]["yaml_name"] == "legacy_code"
    # Observed options, descending count then alphabetical.
    assert fields["Stage"]["properties"]["options"] == [
        "active",
        "paused",
        "closed",
    ]
    assert fields["Tags"]["properties"]["options"] == [
        "donor",
        "mentor",
        "volunteer",
        "board",
    ]


def test_g1_profile_metrics(g1):
    _, profile = g1
    assert profile["manifest_version"] == 1
    assert profile["profiled_at"] == "2026-06-12T08:00:00Z"
    assert profile["anomalies"] == []
    assert profile["options"] == AdapterOptions().profile_options()

    entity = profile["entities"]["contacts"]
    assert entity["record_count"] == 12
    assert "last_record_created_at" not in entity  # no designation
    detail = entity["detail"]
    assert detail["source_file"] == "contacts.csv"
    assert detail["blank_row_count"] == 0
    assert detail["ragged_row_count"] == 0
    assert detail["empty"] is False

    fields = entity["fields"]
    website = fields["Website"]
    assert website["populated_count"] == 9
    assert website["population_rate"] == 0.75
    stage = fields["Stage"]
    # A spreadsheet declares nothing: declared == used by construction,
    # the ghost-option signal is structurally zero (§4.6).
    assert stage["declared_option_count"] == 3
    assert stage["used_option_count"] == 3
    assert stage["detail"]["value_distribution"] == {
        "active": 6,
        "paused": 4,
        "closed": 2,
    }
    tags = fields["Tags"]
    distribution = tags["detail"]["value_distribution"]
    assert sum(distribution.values()) >= tags["populated_count"]  # tokens
    legacy = fields["Legacy Code"]
    assert legacy["populated_count"] == 0
    assert legacy["population_rate"] == 0.0
    assert legacy["detail"]["low_population"] is True


def test_g1_type_inference_evidence(g1):
    _, profile = g1
    for api_name, expected in G1_EXPECTED_TYPES.items():
        block = _inference(profile, "contacts", api_name)
        assert block["inferred_type"] == expected, api_name
        if api_name == "Website":
            assert block["confidence"] == "low"  # 9 populated < 10 (§5.2)
        elif api_name == "Legacy Code":
            assert block["confidence"] == "none"
            assert block["match_rate"] is None
            assert block["non_empty_count"] == 0
        else:
            assert block["confidence"] == "medium", api_name
        assert block["date_order_assumed"] is False
    # PII redaction: email/phone inferences omit sample_values.
    assert "sample_values" not in _inference(profile, "contacts", "Email")
    assert "sample_values" not in _inference(profile, "contacts", "Phone")
    stage = _inference(profile, "contacts", "Stage")
    assert stage["base_type"] == "text"
    assert stage["recognizer"] == "enum_post_pass"
    assert stage["sample_values"] == ["active", "paused", "closed"]
    auto = _inference(profile, "contacts", "ID")
    assert auto["base_type"] == "integer"
    assert auto["recognizer"] == "auto_number_post_pass"


# ---------------------------------------------------------------------------
# G-2 — cross-sheet reference (spec §7.1)
# ---------------------------------------------------------------------------


def test_g2_reference_inference(g2):
    manifest, profile = g2
    assert manifest["relationships"] == []  # §6.4: never, in v1

    fields = _fields(manifest, "donations")
    assert fields["Contact ID"]["field_type"] == "reference"
    assert fields["Donation ID"]["field_type"] == "auto_number"
    assert fields["Amount"]["field_type"] == "currency"
    assert fields["Date"]["field_type"] == "date"

    contact_id = profile["entities"]["donations"]["fields"]["Contact ID"]
    assert contact_id["detail"]["reference_inference"] == {
        "target_sheet": "contacts",
        "target_column": "ID",
        "containment": 1.0,
        "matched_distinct": 10,
        "header_hint": True,
    }
    block = contact_id["detail"]["type_inference"]
    assert block["inferred_type"] == "reference"
    assert block["base_type"] == "integer"  # preserved as evidence
    assert block["recognizer"] == "reference_containment"
    assert block["confidence"] == "high"  # hint-promoted from medium

    # contacts is unchanged from G-1 — in particular its ID column is
    # not re-typed by the reverse pairing.
    g1_manifest, _ = spreadsheet.profile_source(FIXTURES / "g1", now=NOW)
    contacts_fields = _fields(manifest, "contacts")
    assert {n: f["field_type"] for n, f in contacts_fields.items()} == {
        n: f["field_type"] for n, f in _fields(g1_manifest, "contacts").items()
    }
    assert contacts_fields["ID"]["field_type"] == "auto_number"


# ---------------------------------------------------------------------------
# G-3 / C8 — degradation honesty: exact anomaly, warning, and
# inference expectations (spec §7.1/§7.2)
# ---------------------------------------------------------------------------


def test_g3_messy_sheet_expectations(g3):
    manifest, profile = g3

    (entity,) = manifest["entities"]
    assert [f["api_name"] for f in entity["fields"]] == [
        "Amount",
        "Amount_2",
        "column_3",
        "Mixed",
        "When",
        "Status",
    ]
    assert [f["yaml_name"] for f in entity["fields"]] == [
        "amount",
        "amount_2",
        "column_3",
        "mixed",
        "when",
        "status",
    ]

    profile_entity = profile["entities"]["messy"]
    assert profile_entity["record_count"] == 25
    assert profile_entity["detail"]["blank_row_count"] == 2
    assert profile_entity["detail"]["ragged_row_count"] == 1

    # The exact warning set: encoding fallback, header assumption,
    # ragged rows — no sniff fallback (the delimiter sniffs clean).
    warnings = manifest["warnings"]
    assert len(warnings) == 3
    assert any("cp1252" in line for line in warnings)
    assert any("header assumed" in line for line in warnings)
    assert any("ragged" in line for line in warnings)
    assert manifest["errors"] == []

    # The exact anomaly set, in the WTK-096 row shape.
    notes = {
        (row["field"], row["note"].split(":")[0].split(";")[0])
        for row in profile["anomalies"]
    }
    assert len(profile["anomalies"]) == 4
    assert all(row["scope"] == "entity" for row in profile["anomalies"])
    assert all(row["entity"] == "messy" for row in profile["anomalies"])
    assert notes == {
        (None, "header assumed"),
        ("column_3", "empty header in position 3"),
        ("Amount_2", "duplicate header 'Amount'"),
        (None, "1 ragged row(s) normalized to the header width of 6"),
    }

    # The 60/40 column degrades to text with the runner-up recorded.
    mixed = _inference(profile, "messy", "Mixed")
    assert mixed["inferred_type"] == "text"
    assert mixed["match_rate"] == 1.0
    assert mixed["runner_up"] == "integer"
    assert mixed["runner_up_rate"] == 0.6
    # The all-<=-12 slash-date column assumes M/D and says so.
    when = _inference(profile, "messy", "When")
    assert when["inferred_type"] == "date"
    assert when["date_order_assumed"] is True
    # Whitespace-only cells count toward empty_string_count, not
    # population.
    column_3 = profile_entity["fields"]["column_3"]
    assert column_3["populated_count"] == 23
    assert column_3["population_rate"] == 0.92
    assert column_3["detail"]["empty_string_count"] == 2
    assert column_3["detail"]["type_inference"]["inferred_type"] == "text"
    # The ragged row was padded: its Status cell is empty.
    status = profile_entity["fields"]["Status"]
    assert status["populated_count"] == 24


# ---------------------------------------------------------------------------
# C1 — seam key-contract conformance, one checker for both adapters
# ---------------------------------------------------------------------------


def test_c1_seam_conformance_both_adapters(g1, g2, g3):
    for manifest, profile in (g1, g2, g3):
        assert_seam_conformant(manifest, profile)
    # The landed EspoCRM transform fixtures pass the same checker.
    assert_seam_conformant(t1_manifest(), t1_profile())


# ---------------------------------------------------------------------------
# C2 / C5 — end-to-end through the landed plan_deposit, then the
# idempotent re-run (spec §7.2)
# ---------------------------------------------------------------------------


def test_c2_plan_deposit_end_to_end(g1):
    manifest, profile = g1
    plan = audit_deposit.plan_deposit(manifest, profile, ExistingState())

    by_type: dict[str, list] = {}
    for item in plan.creates:
        by_type.setdefault(item.record_type, []).append(item)
    assert set(by_type) == {"entity", "field"}
    assert len(by_type["entity"]) == 1
    assert len(by_type["field"]) == 14
    assert plan.anomalies == []  # zero unmapped-type anomalies
    assert plan.matches == []

    assert plan.source_label == "spreadsheet @ g1"  # delta D2
    assert plan.apply_context["source_system"] == "spreadsheet"  # delta D1

    for item in plan.creates:
        assert item.payload["status"] == "candidate"
        assert item.evidence["catalog_class"] == "custom"

    field_types = {
        item.payload["name"]: item.payload["type"] for item in by_type["field"]
    }
    composed = normalize.composed_type_map("spreadsheet")
    assert field_types == {
        name: composed[native] for name, native in G1_EXPECTED_TYPES.items()
    }

    # Evidence carries the type_inference block verbatim (§5.3).
    for item in by_type["field"]:
        api_name = item.payload["name"]
        detail = item.evidence["detail"]
        assert detail["type_inference"] == _inference(
            profile, "contacts", api_name
        )
        assert detail["wire_type"] == G1_EXPECTED_TYPES[api_name]
    stage = next(i for i in by_type["field"] if i.payload["name"] == "Stage")
    assert stage.evidence["declared_option_count"] == 3
    assert stage.evidence["used_option_count"] == 3


def test_c5_idempotent_rerun(g1):
    manifest, profile = g1
    first = audit_deposit.plan_deposit(manifest, profile, ExistingState())

    existing = ExistingState()
    existing.entities["contacts"] = ExistingRecord("ENT-001", "contacts", False)
    for index, item in enumerate(
        i for i in first.creates if i.record_type == "field"
    ):
        name = item.payload["name"]
        existing.fields[("ENT-001", name.lower())] = ExistingRecord(
            f"FLD-{index + 1:03d}", name, False
        )

    second = audit_deposit.plan_deposit(manifest, profile, existing)
    assert second.creates == []
    assert len(second.matches) == 15  # 1 entity + 14 fields
    assert all(match.evidence is not None for match in second.matches)


# ---------------------------------------------------------------------------
# C3 / C4 — stage-1 totality and the constant-custom partition
# ---------------------------------------------------------------------------


def test_c3_stage1_totality_and_composition():
    table = normalize.SYSTEM_TYPE_MAPS["spreadsheet"]
    assert set(table) == spreadsheet.INFERRED_TYPES  # total, both ways
    assert all(value in CATALOG_ATTRIBUTE_TYPES for value in table.values())
    composed = normalize.composed_type_map("spreadsheet")
    assert composed == SPREADSHEET_COMPOSED  # §6.3, entry for entry
    assert all(value in FIELD_TYPES for value in composed.values())
    # A conforming adapter build never reaches the §3.10 fallback.
    for native in spreadsheet.INFERRED_TYPES:
        field_type, anomaly = normalize.normalize_type("spreadsheet", native)
        assert anomaly is None, native
        assert field_type == SPREADSHEET_COMPOSED[native]


def test_c4_constant_custom_partition():
    items = (
        # A sheet named like a catalog standard item still partitions
        # custom — tiers 2 and 3 are never consulted.
        DiscoveredItem("entity", "Contacts"),
        DiscoveredItem("entity", "anything"),
        DiscoveredItem("attribute", "Email"),
        DiscoveredItem("attribute", "column_7"),
    )
    for item in items:
        catalog_class, anomaly = normalize.partition(
            "spreadsheet",
            item,
            catalog_lookup=lambda *a, **k: "standard",  # must be ignored
        )
        assert catalog_class == "custom", item
        assert anomaly is None


# ---------------------------------------------------------------------------
# C6 / C7 — determinism and profile-join completeness
# ---------------------------------------------------------------------------


def test_c6_determinism(g2):
    again = spreadsheet.profile_source(FIXTURES / "g2", now=NOW)
    for first, second in zip(g2, again, strict=True):
        assert json.dumps(first, indent=2, sort_keys=True) == json.dumps(
            second, indent=2, sort_keys=True
        )


def test_c7_profile_join_completeness(g1, g2, g3):
    for manifest, profile in (g1, g2, g3):
        index = {
            e["espo_name"]: {f["api_name"] for f in e["fields"]}
            for e in manifest["entities"]
        }
        assert set(profile["entities"]) == set(index)
        for espo_name, entry in profile["entities"].items():
            assert set(entry["fields"]) == index[espo_name]


# ---------------------------------------------------------------------------
# Consumer deltas D1/D2 — label rule and per-system map selection
# ---------------------------------------------------------------------------


def test_d2_file_source_label(g1):
    manifest, _ = g1
    # Netloc-less file:// URI -> the path's basename, not 'unknown'.
    assert audit_deposit.derive_source_label(manifest) == "spreadsheet @ g1"
    named = dict(manifest, source_url="file:///tmp/cbm-mentor-tracking.xlsx")
    assert (
        audit_deposit.derive_source_label(named)
        == "spreadsheet @ cbm-mentor-tracking.xlsx"
    )
    # Host-bearing URLs and the no-source_system default are unchanged.
    assert (
        audit_deposit.derive_source_label(t1_manifest())
        == "espocrm @ crm.example.org"
    )


def test_d1_unknown_source_system_rejected(g1):
    manifest, profile = g1
    bogus = copy.deepcopy(manifest)
    bogus["source_system"] = "dynamics365"
    with pytest.raises(ValueError):
        audit_deposit.plan_deposit(bogus, profile, ExistingState())


# ---------------------------------------------------------------------------
# Operator designations and the CLI
# ---------------------------------------------------------------------------


def test_no_header_designation(tmp_path):
    target = tmp_path / "raw"
    target.mkdir()
    (target / "sheet.csv").write_text("1,2\n3,4\n5,6\n", encoding="utf-8")
    options = AdapterOptions(no_header_sheets=frozenset({"sheet"}))
    manifest, profile = spreadsheet.profile_source(target, options, now=NOW)
    (entity,) = manifest["entities"]
    assert [f["api_name"] for f in entity["fields"]] == [
        "column_1",
        "column_2",
    ]
    assert profile["entities"]["sheet"]["record_count"] == 3


def test_created_column_designation(g1):
    options = AdapterOptions(created_columns={"contacts": "Joined"})
    _, profile = spreadsheet.profile_source(
        FIXTURES / "g1", options, now=NOW
    )
    entity = profile["entities"]["contacts"]
    assert entity["last_record_created_at"] == "2024-07-01T00:00:00Z"
    assert entity["detail"]["last_record_created_at_basis"] == {
        "column": "Joined"
    }
    website = entity["fields"]["Website"]
    assert website["last_populated_at"] == "2024-07-01T00:00:00Z"
    assert website["detail"]["last_populated_at_basis"] == {"column": "Joined"}
    # Without the designation neither key exists (g1 fixture).
    _, undesignated = g1
    assert "last_record_created_at" not in undesignated["entities"]["contacts"]


def test_cli_writes_manifest_pair_beside_input(tmp_path, capsys):
    source = tmp_path / "g1"
    source.mkdir()
    source.joinpath("contacts.csv").write_bytes(
        (FIXTURES / "g1" / "contacts.csv").read_bytes()
    )
    assert spreadsheet.main([str(source)]) == 0
    manifest = audit_deposit.load_manifest(source / "audit-report.json")
    profile = audit_deposit.load_profile(source / "utilization-profile.json")
    assert_seam_conformant(manifest, profile)
    out = capsys.readouterr().out
    assert "Profiled 1 sheet(s), 14 column(s)" in out
