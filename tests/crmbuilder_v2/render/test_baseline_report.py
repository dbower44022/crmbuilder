"""Baseline Report renderer tests (WTK-116 §8, R1–R12).

Two harnesses, mirroring the spec's split: model-level checks run
offline against :func:`build_report_model` over a hand-built fixture
(a :class:`FakeRenderClient` serving the §8 graph shapes); end-to-end
checks deposit the WTK-090 T1 manifest + T6 profile through the landed
transform into a test DB and render through an access-layer-backed
client — the same one-session-per-call posture the transform tests
use.
"""

from __future__ import annotations

import copy
import json
from copy import deepcopy

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    deposit_events,
    domain,
    manual_config,
    persona,
    process,
    references,
    utilization_evidence,
)
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.render import baseline_report
from crmbuilder_v2.transform import audit_deposit
from crmbuilder_v2.transform.normalize import (
    BAND_UNPROFILED_CUSTOM,
    derive_priority_band,
)

from tests.crmbuilder_v2.transform.test_audit_deposit import (
    AccessClient,
    t1_manifest,
    t1_manifest_quiet,
    t1_profile,
)

SOURCE = "espocrm @ crm.example.org"
RENDERED_AT = "2026-06-12T09:00:00+00:00"
PROFILED_AT = "2026-06-11T18:00:00Z"
SNAPSHOT_AT = "2026-06-11T17:00:00Z"


# ---------------------------------------------------------------------------
# Offline fixture — the §8 known fixture graph as served API shapes
# ---------------------------------------------------------------------------


def evidence(
    subject_type: str,
    *,
    catalog_class: str | None = None,
    metrics: dict | None = None,
    flags: dict | None = None,
    detail: dict | None = None,
    source_label: str = SOURCE,
    profiled_at: str = PROFILED_AT,
) -> dict:
    full_detail = dict(detail or {})
    full_detail.update(flags or {})
    return {
        "subject_type": subject_type,
        "subject_identifier": None,
        "profiled_at": profiled_at,
        "source_label": source_label,
        "deposit_event": "DEP-001",
        "catalog_class": catalog_class,
        "metrics": dict(metrics or {}),
        "flags": dict(flags or {}),
        "detail": full_detail,
    }


def with_evidence(record: dict, *objects: dict) -> dict:
    record["utilization_evidence"] = {
        "snapshots": list(objects),
        "snapshot_count": len(objects),
        "sources": sorted({o["source_label"] for o in objects}),
    }
    return record


def fixture_manifest() -> dict:
    return {
        "manifest_version": 1,
        "source_url": "https://crm.example.org",
        "source_name": "Example",
        "timestamp": SNAPSHOT_AT,
        "entities": [
            {
                "yaml_name": "Engagement",
                "espo_name": "CEngagement",
                "entity_class": "custom",
                "entity_type": "Base",
                "label_singular": "Engagement",
                "fields": [
                    {
                        "yaml_name": "engagementStage",
                        "api_name": "engagementStage",
                        "field_type": "enum",
                        "label": "Engagement Stage",
                        "properties": {},
                    },
                    {
                        "yaml_name": "mentorNotes",
                        "api_name": "mentorNotes",
                        "field_type": "text",
                        "label": "Mentor Notes",
                        "properties": {},
                    },
                ],
                "layouts": [],
                "filtered_tabs": [],
            },
            {
                "yaml_name": "Contact",
                "espo_name": "Contact",
                "entity_class": "native",
                "entity_type": "Person",
                "label_singular": "Contact",
                "fields": [
                    {
                        "yaml_name": "businessName",
                        "api_name": "cBusinessName",
                        "field_type": "varchar",
                        "label": "Business Name",
                        "properties": {},
                        "field_class": "custom",
                    },
                ],
                "layouts": [],
                "filtered_tabs": [],
            },
            # The R9 bare native: profiled, in use, no candidate exists.
            {
                "yaml_name": "Account",
                "espo_name": "Account",
                "entity_class": "native",
                "entity_type": "Company",
                "label_singular": "Account",
                "fields": [],
                "layouts": [],
                "filtered_tabs": [],
            },
            # Bare native, dormant — the T4 noise floor.
            {
                "yaml_name": "Campaign",
                "espo_name": "Campaign",
                "entity_class": "native",
                "entity_type": "Base",
                "label_singular": "Campaign",
                "fields": [],
                "layouts": [],
                "filtered_tabs": [],
            },
            {
                "yaml_name": "ScheduledJob",
                "espo_name": "ScheduledJob",
                "entity_class": "system",
                "entity_type": None,
                "label_singular": "Scheduled Job",
                "fields": [
                    {
                        "yaml_name": "x",
                        "api_name": "x",
                        "field_type": "varchar",
                        "label": "X",
                        "properties": {},
                    }
                ],
                "layouts": [],
                "filtered_tabs": [],
            },
        ],
        "relationships": [],
        "roles": [],
        "teams": [],
        "errors": [],
        "warnings": [],
    }


def fixture_profile() -> dict:
    return {
        "manifest_version": 1,
        "profiled_at": PROFILED_AT,
        "profiler_version": "1.0.0",
        "options": {
            "dormancy_window_days": 365,
            "low_population_threshold": 0.05,
        },
        "anomalies": ["profiling anomaly: example"],
        "entities": {
            "Account": {
                "record_count": 250,
                "last_record_created_at": "2026-06-01T00:00:00Z",
            },
            "Campaign": {
                "record_count": 12,
                "last_record_created_at": "2023-01-01T00:00:00Z",
            },
        },
    }


def fixture_data() -> dict:
    """The seeded pathology graph (R3): one of each gap category."""
    entities = [
        with_evidence(
            {
                "entity_identifier": "ENT-001",
                "entity_name": "Engagement",
                "entity_status": "candidate",
                "entity_kind": None,
                "entity_notes": "Source:\n  espo_name: CEngagement\n"
                "  yaml_name: Engagement",
            },
            evidence(
                "entity",
                catalog_class="custom",
                metrics={
                    "record_count": 412,
                    "last_record_created_at": "2026-06-09T14:22:00Z",
                },
                detail={"wire_name": "CEngagement", "layouts_captured": ["detail"]},
            ),
        ),
        with_evidence(
            {
                "entity_identifier": "ENT-002",
                "entity_name": "Old Workshops",
                "entity_status": "candidate",
                "entity_kind": None,
                "entity_notes": None,
            },
            evidence(
                "entity",
                catalog_class="custom",
                metrics={
                    "record_count": 37,
                    "last_record_created_at": "2024-01-15T00:00:00Z",
                },
                flags={"dormant": True},
            ),
        ),
        with_evidence(
            {
                "entity_identifier": "ENT-003",
                "entity_name": "Scratch",
                "entity_status": "candidate",
                "entity_kind": None,
                "entity_notes": None,
            },
            evidence(
                "entity",
                catalog_class="custom",
                metrics={"record_count": 0},
                flags={"empty": True, "dormant": True},
            ),
        ),
    ]
    fields = [
        with_evidence(
            {
                "field_identifier": "FLD-001",
                "field_name": "Engagement Stage",
                "field_status": "candidate",
                "field_type": "enum",
                "parent_entity_identifier": "ENT-001",
            },
            evidence(
                "field",
                catalog_class="custom",
                metrics={
                    "populated_count": 398,
                    "population_rate": 0.966,
                    "last_populated_at": "2026-06-09T14:22:00Z",
                    "declared_option_count": 7,
                    "used_option_count": 5,
                },
                flags={"ghost_options": 2},
                detail={
                    "value_distribution": {"active": 211, "paused": 0, "void": 0},
                    "undeclared_values": ["zombie"],
                },
            ),
        ),
        with_evidence(
            {
                "field_identifier": "FLD-002",
                "field_name": "Mentor Notes",
                "field_status": "candidate",
                "field_type": "long_text",
                "parent_entity_identifier": "ENT-001",
            },
            evidence(
                "field",
                catalog_class="custom",
                metrics={
                    "populated_count": 8,
                    "population_rate": 0.02,
                    "last_populated_at": "2026-06-01T00:00:00Z",
                },
                flags={"low_population": True},
            ),
        ),
        with_evidence(
            {
                "field_identifier": "FLD-003",
                "field_name": "Legacy Code",
                "field_status": "candidate",
                "field_type": "text",
                "parent_entity_identifier": "ENT-001",
            },
            evidence(
                "field",
                catalog_class="custom",
                metrics={
                    "populated_count": 200,
                    "population_rate": 0.5,
                    "last_populated_at": "2024-03-01T00:00:00Z",
                },
                flags={"stale": True},
            ),
        ),
    ]
    personas = [
        with_evidence(
            {
                "persona_identifier": "PER-001",
                "persona_name": "Mentor Coordinator",
                "persona_status": "candidate",
            },
            evidence(
                "persona",
                detail={
                    "kind": "role",
                    "scope_access": {"CEngagement": {"read": "all"}},
                },
            ),
        ),
        with_evidence(
            {
                "persona_identifier": "PER-002",
                "persona_name": "Program Team",
                "persona_status": "candidate",
            },
            evidence("persona", detail={"kind": "team"}),
        ),
    ]
    processes = [
        # G5: filters on a field absent from the manifest's Contact.
        with_evidence(
            {
                "process_identifier": "PRC-001",
                "process_name": "Active Mentors",
                "process_purpose": "Filtered navigation tab over Contact",
                "process_classification": "unclassified",
                "process_status": "candidate",
                "process_domain_identifier": "DOM-901",
            },
            evidence(
                "process",
                detail={
                    "entity": "Contact",
                    "scope": "ActiveMentors",
                    "filter": {
                        "all": [
                            {"field": "mentorStatus", "op": "=", "value": "a"}
                        ]
                    },
                },
            ),
        ),
        # Resolvable filter — must NOT appear in G5.
        with_evidence(
            {
                "process_identifier": "PRC-002",
                "process_name": "Active Engagements",
                "process_purpose": "Filtered navigation tab over Engagement",
                "process_classification": "unclassified",
                "process_status": "candidate",
                "process_domain_identifier": "DOM-901",
            },
            evidence(
                "process",
                detail={
                    "entity": "Engagement",
                    "scope": "ActiveEngagements",
                    "filter": {
                        "all": [
                            {"field": "engagementStage", "op": "in", "value": []}
                        ]
                    },
                },
            ),
        ),
    ]
    manual_configs = [
        with_evidence(
            {
                "manual_config_identifier": "MC-001",
                "manual_config_name": "Recreate filter: Stale Engagements",
                "manual_config_category": "saved_view",
                "manual_config_instructions": "Recreate the Engagement filter.",
                "manual_config_status": "candidate",
            },
            evidence(
                "manual_config",
                detail={"origin": "unrecoverable_filter", "tab_scope": "Engagement"},
            ),
        ),
    ]
    domains = [
        {
            "domain_identifier": "DOM-001",
            "domain_name": "Mentor Recruitment",
            "domain_purpose": "Recruit and onboard mentors.",
        },
        {
            "domain_identifier": "DOM-002",
            "domain_name": "Engagement Management",
            "domain_purpose": "Track engagements between mentors and businesses.",
        },
        # The placeholder is never a grouping vocabulary member (§2.1).
        {
            "domain_identifier": "DOM-901",
            "domain_name": f"Baseline: {SOURCE}",
            "domain_purpose": "Mechanical container.",
        },
    ]
    events = [
        {
            "deposit_event_identifier": "DEP-001",
            "deposit_event_kind": "audit_deposit",
            "deposit_event_outcome": "success",
            "deposit_event_created_at": "2026-06-11T19:00:00Z",
            "deposit_event_apply_context": {
                "source_system": "espocrm",
                "source_instance": "https://crm.example.org",
                "snapshot_at": SNAPSHOT_AT,
                "source_label": SOURCE,
                "profiled_at": PROFILED_AT,
                "transform_version": "9.9.9",
            },
        },
        # Unrelated event for another source — must be ignored.
        {
            "deposit_event_identifier": "DEP-002",
            "deposit_event_kind": "audit_deposit",
            "deposit_event_outcome": "success",
            "deposit_event_created_at": "2026-06-11T20:00:00Z",
            "deposit_event_apply_context": {
                "source_system": "espocrm",
                "source_instance": "https://other.example.org",
                "snapshot_at": SNAPSHOT_AT,
                "source_label": "espocrm @ other.example.org",
            },
        },
    ]
    return {
        "entities": entities,
        "fields": fields,
        "personas": personas,
        "processes": processes,
        "manual_configs": manual_configs,
        "domains": domains,
        "deposit_events": events,
        "wrote_records": {
            "DEP-001": [{"target_type": "planning_item", "target_id": "PI-042"}]
        },
    }


class FakeRenderClient(baseline_report.RenderClient):
    """Serves fixture data, recording every call (the R8 tripwire)."""

    def __init__(self, data: dict, engagement: str | None = "ENG-001") -> None:
        self.data = data
        self.engagement = engagement
        self.calls: list[str] = []

    def _serve(self, key: str):
        self.calls.append(f"list_{key}")
        return deepcopy(self.data[key])

    def list_entities(self):
        return self._serve("entities")

    def list_fields_with_parents(self):
        return self._serve("fields")

    def list_personas(self):
        return self._serve("personas")

    def list_processes(self):
        return self._serve("processes")

    def list_manual_configs(self):
        return self._serve("manual_configs")

    def list_domains(self):
        return self._serve("domains")

    def list_deposit_events(self):
        return self._serve("deposit_events")

    def list_wrote_records(self, deposit_event_identifier: str):
        self.calls.append("list_wrote_records")
        return deepcopy(
            self.data.get("wrote_records", {}).get(deposit_event_identifier, [])
        )


def build_fixture_model(
    data: dict | None = None,
    *,
    manifest: dict | None = None,
    profile: dict | None = None,
    manifest_missing: bool = False,
) -> baseline_report.ReportModel:
    client = FakeRenderClient(data or fixture_data())
    inputs = baseline_report.fetch_render_inputs(client, SOURCE)
    if manifest_missing:
        inputs.manifest_note = "manifest unavailable at `/gone/audit-report.json`"
    else:
        inputs.manifest = manifest if manifest is not None else fixture_manifest()
        inputs.profile = profile if profile is not None else fixture_profile()
        inputs.manifest_path = "/repo/programs/audit-x/audit-report.json"
        inputs.profile_path = "/repo/programs/audit-x/utilization-profile.json"
    return baseline_report.build_report_model(inputs, rendered_at=RENDERED_AT)


# ---------------------------------------------------------------------------
# R1 — full render, every section, deterministic
# ---------------------------------------------------------------------------


def test_r1_full_render_sections_and_determinism():
    model_a = build_fixture_model()
    model_b = build_fixture_model()
    assert model_a == model_b  # two builds from the same inputs are equal

    doc_a = baseline_report.render_markdown(model_a)
    doc_b = baseline_report.render_markdown(model_b)
    assert doc_a == doc_b  # byte-identical with the same rendered_at

    for heading in (
        "## Provenance",
        "## Summary",
        "## Gaps and Ghosts",
        "## Candidates by Best-Guess Domain",
        "## Personas",
        "## Standard/Custom Partition and Stock Usage",
        "## Coverage Appendix",
        "## Phase 2/3 Handoff Notes",
    ):
        assert heading in doc_a

    # Grouping: Engagement lands in its name-token domain; the dormant
    # Old Workshops has no token overlap and lands Unassigned, last.
    groups = [g["name"] for g in model_a.domain_groups]
    assert "Engagement Management" in groups
    assert groups[-1] == "Unassigned"
    engagement_group = next(
        g for g in model_a.domain_groups if g["name"] == "Engagement Management"
    )
    assert [e["identifier"] for e in engagement_group["entities"]] == ["ENT-001"]
    # The placeholder domain is never a group heading (§2.1).
    assert f"Baseline: {SOURCE}" not in groups


def test_r1_field_ordering_band_then_within_band():
    model = build_fixture_model()
    group = next(
        g for g in model.domain_groups if g["name"] == "Engagement Management"
    )
    entity = group["entities"][0]
    # T1 (Engagement Stage) before the T2s; within T2,
    # most-recently-abandoned first (Mentor Notes 2026-06 > Legacy 2024-03).
    assert [f["identifier"] for f in entity["fields"]] == [
        "FLD-001",
        "FLD-002",
        "FLD-003",
    ]


# ---------------------------------------------------------------------------
# R2 — provenance header completeness (+ schema-only variant)
# ---------------------------------------------------------------------------


def test_r2_provenance_header():
    model = build_fixture_model()
    doc = baseline_report.render_markdown(model)
    header = model.header
    assert header["source_label"] == SOURCE
    assert header["source_instance"] == "https://crm.example.org"
    assert header["snapshot_at"] == SNAPSHOT_AT
    assert header["profiled_at"] == PROFILED_AT
    assert header["deposit_events"] == [
        {"identifier": "DEP-001", "outcome": "success"}
    ]
    assert header["anomaly_planning_items"] == ["PI-042"]
    assert header["transform_version"] == "9.9.9"
    assert header["profiler_version"] == "1.0.0"
    assert header["thresholds"] == {
        "dormancy_window_days": 365,
        "low_population_threshold": 0.05,
    }
    assert "DEP-001 (success)" in doc
    assert "PI-042" in doc
    assert "DEP-002" not in doc  # the other source's event is ignored


def schema_only_data() -> dict:
    data = fixture_data()
    for family in ("entities", "fields", "personas", "processes", "manual_configs"):
        for row in data[family]:
            for snap in row["utilization_evidence"]["snapshots"]:
                snap["metrics"] = {}
                snap["flags"] = {}
                snap["detail"] = {"schema_only": True}
                snap["profiled_at"] = SNAPSHOT_AT
    del data["deposit_events"][0]["deposit_event_apply_context"]["profiled_at"]
    return data


def test_r2_r4_schema_only_variant():
    model = build_fixture_model(schema_only_data(), profile=None)
    doc = baseline_report.render_markdown(model)
    assert model.header["schema_only"] is True
    assert "schema-only: true" in doc
    # Bands collapse to the exact landed strings (R4).
    assert BAND_UNPROFILED_CUSTOM in model.summary["bands"]
    assert "T1/T2 (use unprofiled)" in doc
    # G1–G4 print the not-evaluable note, not silence (§5.2).
    assert doc.count("schema-only deposit — data flags unavailable") == 4
    # The stock section states profiling is pending.
    assert "Profiling pending" in doc


# ---------------------------------------------------------------------------
# R3 — gaps-and-ghosts correctness from the seeded pathologies
# ---------------------------------------------------------------------------


def test_r3_gap_categories():
    model = build_fixture_model()
    by_category = {block["category"]: block for block in model.gaps}

    g1 = [(i["identifier"], i["line"]) for i in by_category["G1"]["items"]]
    # Empty and dormant render distinctly (different conversations).
    assert ("ENT-003", "empty — never used (0 records)") in g1
    assert any(
        ident == "ENT-002" and line.startswith("dormant") for ident, line in g1
    )
    # ENT-003 carries both flags but empty wins — one G1 entry, not two.
    assert sum(1 for ident, _ in g1 if ident == "ENT-003") == 1

    assert [i["identifier"] for i in by_category["G2"]["items"]] == ["FLD-002"]
    assert [i["identifier"] for i in by_category["G3"]["items"]] == ["FLD-003"]
    # FLD-001 matches both G4 derivations -> renders once per (§5.1).
    g4 = by_category["G4"]["items"]
    assert [i["identifier"] for i in g4] == ["FLD-001", "FLD-001"]
    assert any("paused, void" in i["line"] for i in g4)
    assert any("zombie" in i["line"] for i in g4)

    g5 = by_category["G5"]["items"]
    assert [i["identifier"] for i in g5] == ["PRC-001"]
    assert "mentorStatus" in g5[0]["line"]
    assert "unverified — stock fields not in catalog" in g5[0]["line"]

    # G6: not derivable in v1 for EspoCRM — honest note, no items.
    assert by_category["G6"]["items"] == []
    assert "role membership is not captured" in by_category["G6"]["note"]

    # Every evaluated item carries a probe seed.
    for block in model.gaps:
        for item in block["items"]:
            assert item["probe"]


def test_g6_lights_up_when_member_count_arrives():
    data = fixture_data()
    snap = data["personas"][1]["utilization_evidence"]["snapshots"][0]
    snap["detail"]["member_count"] = 0
    model = build_fixture_model(data)
    g6 = next(block for block in model.gaps if block["category"] == "G6")
    assert [i["identifier"] for i in g6["items"]] == ["PER-002"]
    assert g6["note"] is None


# ---------------------------------------------------------------------------
# R4 — empty and degraded sections
# ---------------------------------------------------------------------------


def test_r4_empty_personas_and_no_ghosts():
    data = fixture_data()
    data["personas"] = []
    # Strip every pathology: clear flags and gap-feeding detail keys.
    for family in ("entities", "fields"):
        for row in data[family]:
            for snap in row["utilization_evidence"]["snapshots"]:
                for key in list(snap["detail"]):
                    if key in ("dormant", "empty", "low_population", "stale",
                               "ghost_options", "undeclared_values"):
                        del snap["detail"][key]
                snap["flags"] = {}
    for row in data["processes"]:
        for snap in row["utilization_evidence"]["snapshots"]:
            snap["detail"]["filter"] = None
    model = build_fixture_model(data)
    doc = baseline_report.render_markdown(model)
    # P renders its empty state, never omission.
    assert "No roles or teams were discovered in this source." in doc
    assert "**No gaps or ghosts detected.**" in doc
    assert "none found" in doc


def test_r4_db_only_render_is_loud():
    model = build_fixture_model(manifest_missing=True)
    doc = baseline_report.render_markdown(model)
    assert model.stock["state"] == "manifest_unavailable"
    assert "/gone/audit-report.json" in doc
    assert "PARTIAL COVERAGE" in doc
    # G5 could not be evaluated — says why.
    g5 = next(block for block in model.gaps if block["category"] == "G5")
    assert "manifest pair unavailable" in g5["note"]


def test_r4_unknown_source_label_refused():
    client = FakeRenderClient(fixture_data())
    with pytest.raises(ValueError) as exc:
        baseline_report.fetch_render_inputs(client, "espocrm @ typo.example.org")
    assert SOURCE in str(exc.value)  # the labels that DO exist are named


# ---------------------------------------------------------------------------
# R7 — band parity and ordering
# ---------------------------------------------------------------------------


def test_r7_band_parity():
    model = build_fixture_model()
    for group in model.domain_groups:
        for entity in group["entities"]:
            if entity["evidence"] is not None:
                assert entity["band"] == derive_priority_band(entity["evidence"])
            for field_view in entity["fields"]:
                assert field_view["band"] == derive_priority_band(
                    field_view["evidence"]
                )


# ---------------------------------------------------------------------------
# R8 — read-only: the client saw GET-shaped list calls only
# ---------------------------------------------------------------------------


def test_r8_get_only_client():
    client = FakeRenderClient(fixture_data())
    inputs = baseline_report.fetch_render_inputs(client, SOURCE)
    inputs.manifest = fixture_manifest()
    inputs.profile = fixture_profile()
    model = baseline_report.build_report_model(inputs, rendered_at=RENDERED_AT)
    baseline_report.render_markdown(model)
    assert all(call.startswith("list_") for call in client.calls)
    # The protocol and the REST client define no mutating surface.
    for klass in (baseline_report.RenderClient, baseline_report.RestRenderClient):
        assert not [
            name
            for name in dir(klass)
            if name.startswith(("create", "patch", "put", "post", "delete"))
        ]


# ---------------------------------------------------------------------------
# R9 — stock section from the profile
# ---------------------------------------------------------------------------


def test_r9_stock_section():
    model = build_fixture_model()
    doc = baseline_report.render_markdown(model)
    # The bare native in real use renders with count + recency …
    assert model.stock["t3_entities"] == [
        {
            "name": "Account",
            "record_count": 250,
            "last_record_created_at": "2026-06-01T00:00:00Z",
            "band": "T3",
        }
    ]
    assert "| Account | 250 | 2026-06-01T00:00:00Z |" in doc
    # … the dormant bare native does not (it is T4, coverage only).
    assert "Campaign" not in [r["name"] for r in model.stock["t3_entities"]]
    assert any(item["name"] == "Campaign" for item in model.coverage["t4"])
    # include_native_fields unset -> the stock-fields note, not silence.
    assert "include_native_fields" in model.stock["stock_fields_note"]


# ---------------------------------------------------------------------------
# R10 — coverage reconciliation
# ---------------------------------------------------------------------------


def test_r10_reconciliation_balances():
    model = build_fixture_model()
    explained = sum(b["count"] for b in model.coverage["buckets"])
    # 5 entities + 4 fields in the fixture manifest, all explained.
    assert model.coverage["manifest_total"] == 9
    assert explained == 9
    assert model.coverage["unexplained"] == []
    doc = baseline_report.render_markdown(model)
    assert "RECONCILIATION FAILURE" not in doc
    assert "9 manifest items = 9 explained + 0 unexplained" in doc
    # The profile anomalies and the anomaly PI are visible.
    assert "profiling anomaly: example" in doc
    assert "Anomaly planning item: PI-042" in doc


def test_r10_orphaned_item_fails_loudly():
    manifest = fixture_manifest()
    manifest["entities"][3]["entity_class"] = "mystery"
    model = build_fixture_model(manifest=manifest)
    assert [item["name"] for item in model.coverage["unexplained"]] == ["Campaign"]
    doc = baseline_report.render_markdown(model)
    assert "RECONCILIATION FAILURE — 1 unexplained item(s)" in doc


# ---------------------------------------------------------------------------
# Manifest pair location (§2.2) and atomic write (§6.2)
# ---------------------------------------------------------------------------


def test_locate_manifest_pair():
    event = {
        "deposit_event_apply_context": {
            "audit_manifest_path": "/repo/programs/audit-x/audit-report.json"
        }
    }
    manifest_path, profile_path = baseline_report.locate_manifest_pair(event)
    assert manifest_path == "/repo/programs/audit-x/audit-report.json"
    assert profile_path == "/repo/programs/audit-x/utilization-profile.json"

    spreadsheet = {
        "deposit_event_apply_context": {
            "source_instance": "file:///snaps/cbm/20260611/workbook.xlsx"
        }
    }
    manifest_path, _ = baseline_report.locate_manifest_pair(spreadsheet)
    assert manifest_path == "/snaps/cbm/20260611/audit-report.json"

    # A historical event with neither key resolves to nothing — the
    # explicit overrides are then required.
    assert baseline_report.locate_manifest_pair(
        {"deposit_event_apply_context": {"source_instance": "https://x"}}
    ) == (None, None)


def test_attach_manifest_pair_degrades_loudly(tmp_path):
    inputs = baseline_report.RenderInputs(
        source_label=SOURCE,
        entities=[], fields=[], personas=[], processes=[], manual_configs=[],
        all_entities=[], all_processes=[], domains=[], deposit_events=[],
        anomaly_planning_items=[],
    )
    missing = tmp_path / "nowhere" / "audit-report.json"
    baseline_report.attach_manifest_pair(
        inputs, manifest_path=str(missing), profile_path=None
    )
    assert inputs.manifest is None
    assert str(missing) in inputs.manifest_note

    manifest_file = tmp_path / "audit-report.json"
    manifest_file.write_text(json.dumps(fixture_manifest()), encoding="utf-8")
    inputs2 = copy.copy(inputs)
    inputs2.manifest_note = None
    baseline_report.attach_manifest_pair(
        inputs2,
        manifest_path=str(manifest_file),
        profile_path=str(tmp_path / "utilization-profile.json"),
    )
    assert inputs2.manifest is not None
    assert inputs2.profile is None
    assert "utilization-profile.json" in inputs2.profile_note


def test_write_report_atomic(tmp_path):
    target = tmp_path / "baseline-report.md"
    written = baseline_report.write_report("# hello\n", target)
    assert written == target
    assert target.read_text(encoding="utf-8") == "# hello\n"
    assert list(tmp_path.iterdir()) == [target]  # no temp file left behind


# ---------------------------------------------------------------------------
# End-to-end — deposit the T1 fixture, render through the access layer
# (R1/R5/R6 against the real graph; the R8 DB-identity tripwire)
# ---------------------------------------------------------------------------


class AccessRenderClient(baseline_report.RenderClient):
    """Access-layer-backed render client — one session per call, like
    one REST request per GET, mirroring the transform tests'
    ``AccessClient``."""

    engagement = "ENG-001"

    @staticmethod
    def _attach(session, rows, subject_type, identifier_key):
        return utilization_evidence.attach_inline_evidence(
            session,
            rows,
            subject_type=subject_type,
            identifier_key=identifier_key,
            mode="latest",
        )

    def list_entities(self):
        with session_scope() as s:
            return self._attach(
                s, entity_repo.list_entities(s), "entity", "entity_identifier"
            )

    def list_fields_with_parents(self):
        with session_scope() as s:
            rows = self._attach(
                s, field_repo.list_fields(s), "field", "field_identifier"
            )
            refs = references.list_references(
                s,
                source_type="field",
                relationship_kind="field_belongs_to_entity",
            )
            parent_by_field = {r["source_id"]: r["target_id"] for r in refs}
            for row in rows:
                row["parent_entity_identifier"] = parent_by_field.get(
                    row["field_identifier"]
                )
            return rows

    def list_personas(self):
        with session_scope() as s:
            return self._attach(
                s, persona.list_personas(s), "persona", "persona_identifier"
            )

    def list_processes(self):
        with session_scope() as s:
            return self._attach(
                s, process.list_processes(s), "process", "process_identifier"
            )

    def list_manual_configs(self):
        with session_scope() as s:
            return self._attach(
                s,
                manual_config.list_manual_configs(s),
                "manual_config",
                "manual_config_identifier",
            )

    def list_domains(self):
        with session_scope() as s:
            return domain.list_domains(s)

    def list_deposit_events(self):
        with session_scope() as s:
            return deposit_events.list_deposit_events(s)

    def list_wrote_records(self, deposit_event_identifier: str):
        with session_scope() as s:
            return references.list_references(
                s,
                source_type="deposit_event",
                source_id=deposit_event_identifier,
                relationship_kind="deposit_event_wrote_record",
            )


def _deposit(manifest: dict, profile: dict | None = None) -> dict:
    client = AccessClient()
    plan = audit_deposit.plan_deposit(
        manifest, profile, audit_deposit.fetch_existing_state(client)
    )
    return audit_deposit.execute_plan(plan, client)


def test_end_to_end_render_from_deposited_t1(v2_env, tmp_path):
    _deposit(t1_manifest(), t1_profile())
    manifest_path = tmp_path / "audit-report.json"
    manifest_path.write_text(json.dumps(t1_manifest()), encoding="utf-8")
    profile_path = tmp_path / "utilization-profile.json"
    profile_path.write_text(json.dumps(t1_profile()), encoding="utf-8")

    output = tmp_path / "baseline-report.md"
    client = AccessRenderClient()
    written = baseline_report.render_baseline_report(
        client,
        SOURCE,
        output_path=output,
        rendered_at=RENDERED_AT,
        manifest_path=str(manifest_path),
        profile_path=str(profile_path),
    )
    doc = written.read_text(encoding="utf-8")

    # R6 — evidence parity: the printed numbers are the API's numbers.
    with session_scope() as s:
        fields = {
            f["field_name"]: f["field_identifier"]
            for f in field_repo.list_fields(s)
        }
        rows = utilization_evidence.list_utilization_evidence(
            s,
            subject_type="field",
            subject_identifier=fields["Engagement Stage"],
        )
    stage_row = rows[0]
    assert (
        f"{stage_row['evidence_populated_count']} / 96.6%" in doc
    )  # 398 / 0.966 verbatim from the row
    assert "5 of 7 used" in doc

    # Identifier discipline: every candidate leads with its identifier.
    assert "ENT-" in doc and "FLD-" in doc and "PER-" in doc and "PROC-" in doc
    # The anomaly PI from the run's audit warning is in the header.
    assert "Anomaly planning item: PI-" in doc

    # Determinism end-to-end: a second render is byte-identical.
    second = baseline_report.render_baseline_report(
        client,
        SOURCE,
        output_path=tmp_path / "again.md",
        rendered_at=RENDERED_AT,
        manifest_path=str(manifest_path),
        profile_path=str(profile_path),
    )
    assert second.read_text(encoding="utf-8") == doc


def test_r5_per_source_isolation(v2_env, tmp_path):
    _deposit(t1_manifest_quiet())
    other = copy.deepcopy(t1_manifest_quiet())
    other["source_url"] = "https://crm.other.org"
    other["source_name"] = "Other"
    # A name-collided multi-source candidate (Engagement matches) plus
    # one entity unique to the second source.
    other["entities"].append(
        {
            "yaml_name": "Widget",
            "espo_name": "CWidget",
            "entity_class": "custom",
            "entity_type": "Base",
            "label_singular": "Widget",
            "fields": [],
            "layouts": [],
            "filtered_tabs": [],
        }
    )
    _deposit(other)

    client = AccessRenderClient()
    docs = {}
    for label in (SOURCE, "espocrm @ crm.other.org"):
        path = tmp_path / f"{label.split('@')[1].strip()}.md"
        baseline_report.render_baseline_report(
            client,
            label,
            output_path=path,
            rendered_at=RENDERED_AT,
            manifest_path=str(tmp_path / "missing.json"),  # DB-only render
        )
        docs[label] = path.read_text(encoding="utf-8")

    assert "Widget" not in docs[SOURCE]
    assert "Widget" in docs["espocrm @ crm.other.org"]
    # The multi-source candidate appears in both reports.
    assert "Engagement" in docs[SOURCE]
    assert "Engagement" in docs["espocrm @ crm.other.org"]
    # Neither report names the other's source label.
    assert "crm.other.org" not in docs[SOURCE].replace(
        "espocrm @ crm.other.org", ""
    ) or "crm.other.org" not in docs[SOURCE]
    assert SOURCE not in docs["espocrm @ crm.other.org"]


def test_r8_render_leaves_db_row_identical(v2_env, tmp_path):
    _deposit(t1_manifest_quiet(), t1_profile())

    def db_fingerprint():
        with session_scope() as s:
            return {
                "entities": entity_repo.list_entities(s, include_deleted=True),
                "fields": field_repo.list_fields(s, include_deleted=True),
                "personas": persona.list_personas(s, include_deleted=True),
                "processes": process.list_processes(s, include_deleted=True),
                "domains": domain.list_domains(s, include_deleted=True),
                "evidence": utilization_evidence.list_utilization_evidence(s),
                "events": deposit_events.list_deposit_events(s),
            }

    before = db_fingerprint()
    baseline_report.render_baseline_report(
        AccessRenderClient(),
        SOURCE,
        output_path=tmp_path / "report.md",
        rendered_at=RENDERED_AT,
        manifest_path=str(tmp_path / "missing.json"),
    )
    assert db_fingerprint() == before
