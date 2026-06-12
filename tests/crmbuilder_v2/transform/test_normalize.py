"""Catalog normalizer tests (WTK-102 spec §6, criteria N1–N9).

Mapping- and partition-level checks run offline against the tables and
pure functions; plan-level checks (post-plan totality, fallback
safety, the engine-agnostic invariants) feed a literal
``audit-report.json`` manifest to ``plan_deposit`` per the WTK-090
fixture format. N4's seven per-system spot-check fixtures cover every
stage-1 table key programmatically plus hand-pinned composed values,
one unknown native type, and one standard and one custom item of each
of entity and attribute per that system's §4.3 markers.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import (
    CATALOG_ATTRIBUTE_TYPES,
    CATALOG_SYSTEMS,
    FIELD_TYPES,
)
from crmbuilder_v2.transform import audit_deposit, normalize
from crmbuilder_v2.transform.normalize import DiscoveredItem

# ---------------------------------------------------------------------------
# N1 — stage-1 totality per system
# ---------------------------------------------------------------------------


def test_n1_stage1_tables_cover_all_seven_systems():
    # The spreadsheet table is the eighth, adapter-only entry (WTK-110
    # delta D3): CATALOG_SYSTEMS deliberately does not grow — a
    # spreadsheet is not a catalog-surveyed product.
    assert set(normalize.SYSTEM_TYPE_MAPS) == CATALOG_SYSTEMS | {
        normalize.SPREADSHEET_SYSTEM
    }


def test_n1_stage1_totality_per_system():
    for system, table in normalize.SYSTEM_TYPE_MAPS.items():
        for key, catalog_type in table.items():
            assert catalog_type in CATALOG_ATTRIBUTE_TYPES, (system, key)
            native, subtype = key if isinstance(key, tuple) else (key, None)
            field_type, anomaly = normalize.normalize_type(
                system, native, subtype=subtype
            )
            assert anomaly is None, (system, key)
            assert field_type in FIELD_TYPES, (system, key)


def test_n1_unknown_native_type_falls_back_with_anomaly():
    for system in sorted(CATALOG_SYSTEMS):
        field_type, anomaly = normalize.normalize_type(
            system, "definitely-not-a-type"
        )
        assert field_type == "text"
        assert anomaly is not None
        assert anomaly.kind == "unmapped_type"
        assert anomaly.system == system
        assert "definitely-not-a-type" in anomaly.message


def test_n1_unknown_pair_falls_back_to_bare_type_row_anomaly_free():
    # §3.10 rule 2: a new HubSpot fieldType under a known type is
    # anomaly-free — the value-shape is still known.
    field_type, anomaly = normalize.normalize_type(
        "hubspot", "string", subtype="brand-new-fieldtype"
    )
    assert (field_type, anomaly) == ("text", None)


def test_n1_unknown_pair_without_bare_row_takes_rule_one():
    # §3.6/§3.10: (json, any) has no row and no bare fallback.
    field_type, anomaly = normalize.normalize_type(
        "hubspot", "json", subtype="text"
    )
    assert field_type == "text"
    assert anomaly is not None and anomaly.kind == "unmapped_type"


def test_n1_unknown_system_is_a_programming_error():
    with pytest.raises(ValueError):
        normalize.normalize_type("dynamics365", "Text")
    with pytest.raises(ValueError):
        normalize.partition("dynamics365", DiscoveredItem("entity", "Account"))


# ---------------------------------------------------------------------------
# N2 — stage-2 totality
# ---------------------------------------------------------------------------


def test_n2_stage2_projection_is_total_over_catalog_types():
    assert set(normalize.CATALOG_TO_FIELD_TYPE) == CATALOG_ATTRIBUTE_TYPES
    assert set(normalize.CATALOG_TO_FIELD_TYPE.values()) <= FIELD_TYPES


# ---------------------------------------------------------------------------
# N3 — composition identity for espocrm
# ---------------------------------------------------------------------------

# The landed WIRE_TYPE_MAP, pinned literally as it stood before the
# WTK-103 refactor routed audit_deposit through the composed table —
# the two-stage design is a refactoring, not a behavior change. The
# §3.3 named extensions (file/image/attachmentMultiple/barcode) are
# not adopted, so they are absent here and take the fallback chain.
_LANDED_WIRE_TYPE_MAP = {
    "varchar": "text",
    "email": "text",
    "phone": "text",
    "url": "text",
    "personName": "text",
    "address": "text",
    "text": "long_text",
    "wysiwyg": "long_text",
    "enum": "enum",
    "multiEnum": "multi_enum",
    "checklist": "multi_enum",
    "array": "multi_enum",
    "date": "date",
    "datetime": "datetime",
    "datetimeOptional": "datetime",
    "currency": "money",
    "currencyConverted": "money",
    "bool": "boolean",
    "int": "number",
    "float": "number",
    "autoincrement": "number",
    "link": "reference",
    "linkParent": "reference",
    "linkMultiple": "reference",
    "linkOne": "reference",
    "foreign": "derived",
}


def test_n3_espocrm_composition_reproduces_landed_wire_type_map():
    assert normalize.composed_type_map("espocrm") == _LANDED_WIRE_TYPE_MAP
    assert audit_deposit.WIRE_TYPE_MAP == _LANDED_WIRE_TYPE_MAP


# ---------------------------------------------------------------------------
# §3.1 lookup precedence — computed-value flag and multivalued promotion
# ---------------------------------------------------------------------------


def test_calculated_flag_wins_over_declared_type():
    # Salesforce formula/rollup fields carry calculated: true plus a
    # declared result type; the flag wins (§3.1).
    assert normalize.normalize_type(
        "salesforce", "Currency", calculated=True
    ) == ("derived", None)
    assert normalize.normalize_type(
        "hubspot", "number", subtype="calculation_equation", calculated=True
    ) == ("derived", None)


def test_multivalued_promotion():
    # Attio is_multiselect / CiviCRM serialize promote single-valued
    # kinds; the catalog-level cardinality survives even where stage 2
    # collapses it (multireference -> reference).
    assert normalize.resolve_type("attio", "select", multivalued=True)[:2] == (
        "multienum",
        "multi_enum",
    )
    assert normalize.resolve_type(
        "attio", "record-reference", multivalued=True
    )[:2] == ("multireference", "reference")
    assert normalize.resolve_type(
        "civicrm", "StateProvince", multivalued=True
    )[:2] == ("multienum", "multi_enum")
    # No promotion exists for non-enum/reference kinds.
    assert normalize.resolve_type("attio", "text", multivalued=True)[:2] == (
        "string",
        "text",
    )


def test_resolve_type_exposes_stage1_catalog_type():
    # §2.2: the stage-1 type is recorded in evidence_detail
    # (catalog_attribute_type) so the finer shape is recoverable.
    catalog_type, field_type, anomaly = normalize.resolve_type(
        "salesforce", "Time"
    )
    assert (catalog_type, field_type, anomaly) == ("time", "text", None)


# ---------------------------------------------------------------------------
# N4 — per-system spot-check fixtures (types + §4.3 markers)
# ---------------------------------------------------------------------------

# Hand-pinned composed values per system: (native, subtype, expected
# FIELD_TYPES value). The N1 totality test already walks every table
# key programmatically; these pin the composed end values.
_N4_TYPE_CASES = {
    "espocrm": [
        ("varchar", None, "text"),
        ("multiEnum", None, "multi_enum"),
        ("currency", None, "money"),
        ("linkMultiple", None, "reference"),
        ("foreign", None, "derived"),
    ],
    "salesforce": [
        ("Text", None, "text"),
        ("MultiselectPicklist", None, "multi_enum"),
        ("MasterDetail", None, "reference"),
        ("Time", None, "text"),
        ("Summary", None, "derived"),
        ("Geolocation", None, "text"),
    ],
    "salesforce_npsp": [
        ("Currency", None, "money"),
        ("Picklist", None, "enum"),
        ("Lookup", None, "reference"),
    ],
    "hubspot": [
        ("string", "html", "long_text"),
        ("string", "file", "text"),
        ("enumeration", "checkbox", "multi_enum"),
        ("enumeration", "booleancheckbox", "boolean"),
        ("phone_number", None, "text"),
        ("number", None, "number"),
    ],
    "attio": [
        ("rating", None, "number"),
        ("status", None, "enum"),
        ("timestamp", None, "datetime"),
        ("location", None, "text"),
        ("actor-reference", None, "reference"),
    ],
    "civicrm": [
        ("String", "Text", "text"),
        ("String", "CheckBox", "multi_enum"),
        ("Memo", "RichTextEditor", "long_text"),
        ("Date", None, "date"),
        ("Date", "time_format", "datetime"),
        ("Money", None, "money"),
        ("Link", None, "text"),
        ("ContactReference", None, "reference"),
    ],
    "bloomerang": [
        ("text", None, "text"),
        ("text", "pick_one", "enum"),
        ("text", "pick_many", "multi_enum"),
        ("currency", None, "money"),
        ("note", None, "long_text"),
        ("reference", None, "reference"),
    ],
}

# One standard and one custom item of each of entity and attribute per
# that system's §4.3 markers: (item, expected class, expected tier).
_N4_PARTITION_CASES = {
    "espocrm": [
        (DiscoveredItem("entity", "CEngagement", marker={"class": "custom"}), "custom", 1),
        (DiscoveredItem("entity", "Contact", marker={"class": "native"}), "standard", 1),
        (DiscoveredItem("attribute", "cMentorStatus", marker={"class": "custom"}), "custom", 1),
        (DiscoveredItem("attribute", "firstName", marker={"class": "native"}), "standard", 1),
    ],
    "salesforce": [
        (DiscoveredItem("entity", "Account"), "standard", 1),
        (DiscoveredItem("entity", "Mentoring_Engagement__c"), "custom", 1),
        (DiscoveredItem("attribute", "Name"), "standard", 1),
        (DiscoveredItem("attribute", "Mentoring_Stage__c"), "custom", 1),
        # Another vendor's managed package: stock schema, installed
        # deliberately (§4.5).
        (DiscoveredItem("attribute", "mc__Campaign_Sync__c"), "standard", 1),
    ],
    "salesforce_npsp": [
        (DiscoveredItem("entity", "npe01__OppPayment__c"), "standard", 1),
        (DiscoveredItem("entity", "Mentoring_Engagement__c"), "custom", 1),
        (DiscoveredItem("attribute", "npsp__Primary_Contact__c"), "standard", 1),
        (DiscoveredItem("attribute", "Mentoring_Stage__c"), "custom", 1),
    ],
    "hubspot": [
        (DiscoveredItem("entity", "contacts", marker={"object_type_id": "0-1"}), "standard", 1),
        (DiscoveredItem("entity", "engagements", marker={"object_type_id": "2-12345"}), "custom", 1),
        (DiscoveredItem("attribute", "email", marker={"hubspot_defined": True}), "standard", 1),
        # hubspotDefined false/absent -> custom (§4.3).
        (DiscoveredItem("attribute", "mentoring_stage", marker={}), "custom", 1),
    ],
    "attio": [
        (DiscoveredItem("entity", "people", marker={"default_object": True}), "standard", 1),
        (DiscoveredItem("entity", "engagements", marker={"default_object": False}), "custom", 1),
        (DiscoveredItem("attribute", "name", marker={"default_attribute": True}), "standard", 1),
        # No flag relied on -> tier 2; no catalog here -> tier 3.
        (DiscoveredItem("attribute", "mentoring_stage"), "custom", 3),
    ],
    "civicrm": [
        (DiscoveredItem("entity", "Contact"), "standard", 1),
        (DiscoveredItem("entity", "Grant"), "standard", 1),  # extension entity
        (DiscoveredItem("attribute", "custom_42", marker={"custom_group": True}), "custom", 1),
        (DiscoveredItem("attribute", "first_name", marker={"custom_group": False}), "standard", 1),
    ],
    "bloomerang": [
        (DiscoveredItem("entity", "Constituent"), "standard", 1),
        (DiscoveredItem("attribute", "MentorStage", marker={"custom_field": True}), "custom", 1),
        (DiscoveredItem("attribute", "EmailAddress", marker={"custom_field": False}), "standard", 1),
    ],
}


def test_n4_fixture_dicts_cover_all_seven_systems():
    assert set(_N4_TYPE_CASES) == CATALOG_SYSTEMS
    assert set(_N4_PARTITION_CASES) == CATALOG_SYSTEMS


def test_n4_spot_check_composed_types_per_system():
    for system, cases in _N4_TYPE_CASES.items():
        for native, subtype, expected in cases:
            field_type, anomaly = normalize.normalize_type(
                system, native, subtype=subtype
            )
            assert anomaly is None, (system, native, subtype)
            assert field_type == expected, (system, native, subtype)


def test_n4_spot_check_partition_per_system():
    for system, cases in _N4_PARTITION_CASES.items():
        for item, expected_class, expected_tier in cases:
            result, anomaly = normalize.partition_detailed(system, item)
            assert result.catalog_class == expected_class, (system, item)
            assert result.tier == expected_tier, (system, item)
            assert (anomaly is not None) == (result.tier == 3), (system, item)


# ---------------------------------------------------------------------------
# N5 — partition coverage
# ---------------------------------------------------------------------------


def test_n5_every_item_partitions_to_exactly_one_class():
    for system, cases in _N4_PARTITION_CASES.items():
        for item, _, _ in cases:
            catalog_class, anomaly = normalize.partition(system, item)
            assert catalog_class in normalize.PARTITION_CLASSES
            if anomaly is not None:
                assert anomaly.kind == "unpartitioned"
                assert item.api_name in anomaly.message


# ---------------------------------------------------------------------------
# N6 — the NPSP discriminator
# ---------------------------------------------------------------------------


def _field_class(system: str, api_name: str) -> str:
    return normalize.partition(system, DiscoveredItem("attribute", api_name))[0]


def test_n6_npsp_discriminator():
    # The NPSP package's namespaced fields are stock schema for the
    # system the salesforce_npsp slug names, even though the raw
    # platform marks them custom (§3.5).
    assert _field_class("salesforce", "npsp__Primary_Contact__c") == "custom"
    assert _field_class("salesforce_npsp", "npsp__Primary_Contact__c") == "standard"
    assert _field_class("salesforce", "Mentoring_Stage__c") == "custom"
    assert _field_class("salesforce_npsp", "Mentoring_Stage__c") == "custom"
    assert _field_class("salesforce", "Name") == "standard"
    assert _field_class("salesforce_npsp", "Name") == "standard"


# ---------------------------------------------------------------------------
# §4.2 — tier-2 catalog oracle and disagreement handling
# ---------------------------------------------------------------------------


def test_tier2_catalog_lookup_decides_when_marker_silent():
    def lookup(system, api_name, *, kind, label=None):
        return {"mentoring_stage": "custom", "engagements": "partial"}.get(
            api_name
        )

    result, anomaly = normalize.partition_detailed(
        "attio", DiscoveredItem("attribute", "mentoring_stage"), lookup
    )
    assert (result.catalog_class, result.tier, anomaly) == ("custom", 2, None)
    # Entity `partial` partitions standard — some stock footing exists
    # (§4.4); `partial` never appears as an item's class.
    result, anomaly = normalize.partition_detailed(
        "attio", DiscoveredItem("entity", "engagements"), lookup
    )
    assert (result.catalog_class, result.tier, anomaly) == ("standard", 2, None)


def test_tier1_wins_over_catalog_with_disagreement_recorded():
    def lookup(system, api_name, *, kind, label=None):
        return "custom"

    result, anomaly = normalize.partition_detailed(
        "salesforce", DiscoveredItem("attribute", "Name"), lookup
    )
    assert (result.catalog_class, result.tier, anomaly) == ("standard", 1, None)
    assert result.disagreement == {"marker": "standard", "catalog": "custom"}


def test_tier3_conservative_default_with_anomaly():
    def lookup(system, api_name, *, kind, label=None):
        return None  # unseeded catalog DB — N9 degradation path

    item = DiscoveredItem("attribute", "mystery_attribute")
    result, anomaly = normalize.partition_detailed("attio", item, lookup)
    assert (result.catalog_class, result.tier) == ("custom", 3)
    assert anomaly is not None and anomaly.kind == "unpartitioned"


# ---------------------------------------------------------------------------
# N7 — engine-agnostic invariants
# ---------------------------------------------------------------------------


def test_n7_same_logical_schema_maps_identically_across_systems():
    # §6 N7(d): the same logical schema discovered from two different
    # source systems produces the same engine-agnostic types.
    logical = [
        ("varchar", "Text"),
        ("text", "LongTextArea"),
        ("enum", "Picklist"),
        ("multiEnum", "MultiselectPicklist"),
        ("date", "Date"),
        ("datetime", "DateTime"),
        ("currency", "Currency"),
        ("bool", "Checkbox"),
        ("int", "Number"),
        ("link", "Lookup"),
        ("foreign", "Formula"),
        ("email", "Email"),
    ]
    via_espocrm = [
        normalize.normalize_type("espocrm", native)[0] for native, _ in logical
    ]
    via_salesforce = [
        normalize.normalize_type("salesforce", native)[0]
        for _, native in logical
    ]
    assert via_espocrm == via_salesforce


def _mini_manifest() -> dict:
    """One custom entity with a mapped, an unknown-typed, and a
    fallback field — the smallest plan-level fixture."""
    return {
        "manifest_version": 1,
        "source_url": "https://crm.example.org",
        "source_name": "Fixture",
        "timestamp": "2026-06-11T17:00:00Z",
        "entities": [
            {
                "yaml_name": "Engagement",
                "espo_name": "CEngagement",
                "entity_class": "custom",
                "entity_type": "Base",
                "label_singular": "Engagement",
                "label_plural": "Engagements",
                "stream": False,
                "fields": [
                    {
                        "yaml_name": "stage",
                        "api_name": "stage",
                        "field_type": "enum",
                        "label": "Stage",
                        "properties": {"options": ["a", "b"]},
                    },
                    {
                        "yaml_name": "brochure",
                        "api_name": "brochure",
                        "field_type": "file",  # §3.3 named extension, unadopted
                        "label": "Brochure",
                        "properties": {},
                    },
                ],
                "layouts": [],
                "filtered_tabs": [],
            },
        ],
        "relationships": [],
        "roles": [],
        "teams": [],
        "warnings": [],
        "errors": [],
    }


def test_n7_plan_level_invariants():
    # §6 N7(a)-(c) on the plan object: every field candidate's type is
    # in FIELD_TYPES, no partition class lands on any candidate
    # payload, and native vocabulary appears only in the notes Source:
    # block and evidence detail.
    plan = audit_deposit.plan_deposit(
        _mini_manifest(), None, audit_deposit.ExistingState()
    )
    field_creates = [c for c in plan.creates if c.record_type == "field"]
    assert field_creates
    for create in plan.creates:
        assert "catalog_class" not in create.payload
        if create.record_type == "field":
            assert create.payload["type"] in FIELD_TYPES
            assert "field_type:" not in create.payload["name"]
        if create.evidence is not None:
            assert create.evidence["catalog_class"] in normalize.PARTITION_CLASSES


# ---------------------------------------------------------------------------
# N9 — fallback safety
# ---------------------------------------------------------------------------


def test_n9_unknown_types_still_plan_loudly():
    manifest = _mini_manifest()
    for field_result in manifest["entities"][0]["fields"]:
        field_result["field_type"] = "no-such-wire-type"
    plan = audit_deposit.plan_deposit(
        manifest, None, audit_deposit.ExistingState()
    )
    field_creates = [c for c in plan.creates if c.record_type == "field"]
    assert len(field_creates) == 2
    assert all(c.payload["type"] == "text" for c in field_creates)
    unmapped = [a for a in plan.anomalies if "unmapped wire type" in a]
    assert len(unmapped) == 2
    # Degradation is loud but never blocking: the anomaly PI is planned.
    assert any(c.record_type == "planning_item" for c in plan.creates)


# ---------------------------------------------------------------------------
# N8 — priority re-derivability + §5 band derivation
# ---------------------------------------------------------------------------

_PROFILED_AT = "2026-06-01T00:00:00+00:00"
_RECENT = "2026-05-20T00:00:00+00:00"
_ANCIENT = "2020-01-01T00:00:00+00:00"


def _evidence(
    catalog_class: str,
    *,
    subject_type: str = "field",
    metrics: dict | None = None,
    detail: dict | None = None,
    profiled_at: str = _PROFILED_AT,
) -> dict:
    return {
        "subject_type": subject_type,
        "subject_identifier": "FLD-001",
        "profiled_at": profiled_at,
        "source_label": "espocrm @ crm.example.org",
        "deposit_event": None,
        "catalog_class": catalog_class,
        "metrics": metrics or {},
        "flags": {},
        "detail": detail or {},
    }


def test_field_bands_from_partition_class_and_use():
    used = {"population_rate": 0.4, "last_populated_at": _RECENT}
    stale = {"population_rate": 0.4, "last_populated_at": _ANCIENT}
    low = {"population_rate": 0.01, "last_populated_at": _RECENT}
    derive = normalize.derive_priority_band
    assert derive(_evidence("custom", metrics=used)) == normalize.BAND_T1
    assert derive(_evidence("custom", metrics=stale)) == normalize.BAND_T2
    assert derive(_evidence("custom", metrics=low)) == normalize.BAND_T2
    assert derive(_evidence("standard", metrics=used)) == normalize.BAND_T3
    assert derive(_evidence("standard", metrics=stale)) == normalize.BAND_T4
    # §5.2: rate of exactly 0.05 IS real use (>=, matching the
    # profiler's strictly-below low_population flag).
    at_threshold = {"population_rate": 0.05, "last_populated_at": _RECENT}
    assert derive(_evidence("custom", metrics=at_threshold)) == normalize.BAND_T1


def test_entity_bands_from_partition_class_and_use():
    used = {"record_count": 12, "last_record_created_at": _RECENT}
    dormant = {"record_count": 12, "last_record_created_at": _ANCIENT}
    empty = {"record_count": 0}
    derive = normalize.derive_priority_band
    assert derive(_evidence("custom", subject_type="entity", metrics=used)) == normalize.BAND_T1
    assert derive(_evidence("custom", subject_type="entity", metrics=dormant)) == normalize.BAND_T2
    assert derive(_evidence("standard", subject_type="entity", metrics=used)) == normalize.BAND_T3
    assert derive(_evidence("standard", subject_type="entity", metrics=empty)) == normalize.BAND_T4


def test_schema_only_runs_collapse_to_the_partition_axis():
    derive = normalize.derive_priority_band
    schema_only = _evidence("custom", detail={"schema_only": True})
    assert derive(schema_only) == normalize.BAND_UNPROFILED_CUSTOM
    no_metrics = _evidence("standard")
    assert derive(no_metrics) == normalize.BAND_UNPROFILED_STANDARD


def test_recorded_thresholds_override_the_defaults():
    # Re-derivation uses the thresholds the row was profiled under
    # (WTK-097: re-derivable from the row alone).
    detail = {
        "thresholds": {
            "dormancy_window_days": 30,
            "low_population_threshold": 0.5,
        }
    }
    metrics = {"population_rate": 0.4, "last_populated_at": _RECENT}
    band = normalize.derive_priority_band(
        _evidence("custom", metrics=metrics, detail=detail)
    )
    assert band == normalize.BAND_T2  # 0.4 < 0.5 -> not real use


def test_missing_partition_class_is_an_error():
    evidence = _evidence("custom")
    evidence["catalog_class"] = None
    with pytest.raises(ValueError):
        normalize.derive_priority_band(evidence)


def test_n8_band_derivation_is_repeatable_and_never_stored():
    rows = [
        _evidence("custom", metrics={"population_rate": 0.4, "last_populated_at": _RECENT}),
        _evidence("custom", metrics={"population_rate": 0.2, "last_populated_at": _ANCIENT}),
        _evidence("standard", detail={"schema_only": True}),
    ]
    first = [normalize.derive_priority_band(row) for row in rows]
    second = [normalize.derive_priority_band(row) for row in rows]
    assert first == second
    for row in rows:
        assert "band" not in row and "priority" not in row
        assert "band" not in row["detail"] and "priority" not in row["detail"]


def test_within_band_ordering_is_deterministic():
    # T1: population_rate descending, ties by name ascending.
    t1_rows = [
        ("Alpha", _evidence("custom", metrics={"population_rate": 0.2, "last_populated_at": _RECENT})),
        ("Beta", _evidence("custom", metrics={"population_rate": 0.9, "last_populated_at": _RECENT})),
        ("Gamma", _evidence("custom", metrics={"population_rate": 0.2, "last_populated_at": _RECENT})),
    ]
    ordered = sorted(
        t1_rows,
        key=lambda pair: normalize.within_band_sort_key(
            normalize.BAND_T1, pair[1], pair[0]
        ),
    )
    assert [name for name, _ in ordered] == ["Beta", "Alpha", "Gamma"]
    # T2: most-recently-abandoned first, the freshest ghost trail.
    t2_rows = [
        ("Old", _evidence("custom", metrics={"population_rate": 0.4, "last_populated_at": _ANCIENT})),
        ("Fresh", _evidence("custom", metrics={"population_rate": 0.4, "last_populated_at": "2025-09-01T00:00:00+00:00"})),
    ]
    ordered = sorted(
        t2_rows,
        key=lambda pair: normalize.within_band_sort_key(
            normalize.BAND_T2, pair[1], pair[0]
        ),
    )
    assert [name for name, _ in ordered] == ["Fresh", "Old"]
    # Entities: record_count descending, then name.
    entity_rows = [
        ("Contacts", _evidence("standard", subject_type="entity", metrics={"record_count": 5, "last_record_created_at": _RECENT})),
        ("Engagements", _evidence("standard", subject_type="entity", metrics={"record_count": 50, "last_record_created_at": _RECENT})),
    ]
    ordered = sorted(
        entity_rows,
        key=lambda pair: normalize.within_band_sort_key(
            normalize.BAND_T3, pair[1], pair[0]
        ),
    )
    assert [name for name, _ in ordered] == ["Engagements", "Contacts"]
