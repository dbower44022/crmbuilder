"""AuditReport-to-candidate deposit transform tests (WTK-090 §8).

The fixture format is the manifest itself (§2.1): each test feeds a
literal ``audit-report.json`` structure (and optionally a profile) and
asserts on the resulting plan, rows, and edges. The mapping layer
(``plan_deposit``) is unit-tested with no API; the execute path drives
an access-layer-backed test client, one session per POST — mirroring
the spec's "each POST is its own transaction" posture without standing
up the REST surface.

Covers the spec's T1 (full small-report transform), T2 (provenance
completeness), T3 (idempotent re-run), T4 (incremental re-run), T5
(wire-type map coverage), T6 (evidence with/without profile), T7
(lifecycle non-interference), T9 (soft-deleted match), and T10 (scope
rules).
"""

from __future__ import annotations

import copy
import json

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    decisions,
    deposit_events,
    domain,
    manual_config,
    persona,
    planning_items,
    process,
    references,
    utilization_evidence,
)
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.transform import audit_deposit

SOURCE_LABEL = "espocrm @ crm.example.org"
PLACEHOLDER_DOMAIN = f"Baseline: {SOURCE_LABEL}"


def t1_manifest() -> dict:
    """The §8 T1 fixture: one custom entity (2 custom fields, one enum
    with 7 options, plus a link field deduped by the relationship), one
    native entity carrying 1 custom field, one relationship (both sides
    audited), 1 role, 1 team, 2 filtered tabs (one recovered filter,
    one ``filter: null``), 1 audit warning."""
    return {
        "manifest_version": 1,
        "source_url": "https://crm.example.org",
        "source_name": "CBM Test",
        "timestamp": "2026-06-11T17:00:00Z",
        "output_dir": "programs/audit-20260611-170000",
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
                        "yaml_name": "engagementStage",
                        "api_name": "engagementStage",
                        "field_type": "enum",
                        "label": "Engagement Stage",
                        "properties": {
                            "options": ["a", "b", "c", "d", "e", "f", "g"],
                            "required": True,
                        },
                    },
                    {
                        "yaml_name": "startDate",
                        "api_name": "startDate",
                        "field_type": "date",
                        "label": "Start Date",
                        "properties": {},
                    },
                    # Captured both as a field and as a relationship side;
                    # the relationship mapping wins (§3.3 dedup).
                    {
                        "yaml_name": "contact",
                        "api_name": "contact",
                        "field_type": "link",
                        "label": "Contact",
                        "properties": {},
                    },
                ],
                "layouts": [
                    {"layout_type": "detail", "data": {}},
                    {"layout_type": "list", "data": []},
                ],
                "filtered_tabs": [
                    {
                        "id": "activeEngagements",
                        "scope": "ActiveEngagements",
                        "label": "Active Engagements",
                        "filter": {
                            "all": [
                                {
                                    "field": "engagementStage",
                                    "op": "in",
                                    "value": ["active"],
                                }
                            ]
                        },
                        "nav_order": 3,
                        "acl": "boolean",
                    },
                    {
                        "id": "staleEngagements",
                        "scope": "StaleEngagements",
                        "label": "Stale Engagements",
                        "filter": None,
                        "nav_order": 4,
                        "acl": "boolean",
                    },
                ],
            },
            {
                "yaml_name": "Contact",
                "espo_name": "Contact",
                "entity_class": "native",
                "entity_type": "Person",
                "label_singular": "Contact",
                "label_plural": "Contacts",
                "stream": False,
                "fields": [
                    {
                        "yaml_name": "mentorStatus",
                        "api_name": "cMentorStatus",
                        "field_type": "varchar",
                        "label": "Mentor Status",
                        "properties": {},
                        "field_class": "custom",
                    },
                ],
                "layouts": [],
                "filtered_tabs": [],
            },
        ],
        "relationships": [
            {
                "name": "engagementContact",
                "entity": "Engagement",
                "entity_foreign": "Contact",
                "link_type": "manyToOne",
                "link": "contact",
                "link_foreign": "engagements",
                "label": "Contact",
                "label_foreign": "Engagements",
                "relation_name": None,
                "audited": True,
                "audited_foreign": True,
            },
        ],
        "roles": [
            {
                "name": "Mentor Coordinator",
                "description": "Coordinates mentor onboarding.",
                "persona": None,
                "scope_access": {"CEngagement": {"read": "all"}},
                "system_permissions": None,
            },
        ],
        "teams": [{"name": "Program Team", "description": None}],
        "errors": [],
        "warnings": [
            "Filtered tab StaleEngagements: unknown where-item type; "
            "filter not recovered"
        ],
    }


def t1_manifest_quiet() -> dict:
    """T1 without the audit warning. Anomalies are logged per run
    (§3.6), so a manifest carrying a warning legitimately creates a new
    anomaly Planning Item on every run — the §8 T3 "zero creations"
    criterion presumes an anomaly-free manifest."""
    manifest = t1_manifest()
    manifest["warnings"] = []
    return manifest


def t1_profile() -> dict:
    return {
        "manifest_version": 1,
        "profiled_at": "2026-06-11T18:00:00Z",
        "entities": {
            "CEngagement": {
                "record_count": 412,
                "last_record_created_at": "2026-06-09T14:22:00Z",
                "fields": {
                    "engagementStage": {
                        "populated_count": 398,
                        "population_rate": 0.966,
                        "last_populated_at": "2026-06-09T14:22:00Z",
                        "distinct_value_count": 5,
                        "declared_option_count": 7,
                        "used_option_count": 5,
                        "detail": {"value_distribution": {"active": 211}},
                    }
                },
            }
        },
    }


class AccessClient(audit_deposit.DepositClient):
    """Access-layer-backed client: one session per call, like one REST
    request per POST."""

    def list_entities(self):
        with session_scope() as s:
            return entity_repo.list_entities(s, include_deleted=True)

    def list_fields_with_parents(self):
        with session_scope() as s:
            rows = field_repo.list_fields(s, include_deleted=True)
            refs = references.list_references(
                s,
                source_type="field",
                relationship_kind="field_belongs_to_entity",
            )
            parent_by_field = {r["source_id"]: r["target_id"] for r in refs}
            for row in rows:
                row["parent_entity_identifier"] = parent_by_field.get(
                    row["field_identifier"]
                ) or row.get("field_previous_parent_entity_identifier")
            return rows

    def list_personas(self):
        with session_scope() as s:
            return persona.list_personas(s, include_deleted=True)

    def list_processes(self):
        with session_scope() as s:
            return process.list_processes(s, include_deleted=True)

    def list_manual_configs(self):
        with session_scope() as s:
            return manual_config.list_manual_configs(s, include_deleted=True)

    def list_domains(self):
        with session_scope() as s:
            return domain.list_domains(s, include_deleted=True)

    def next_deposit_event_identifier(self):
        with session_scope() as s:
            return deposit_events.next_deposit_event_identifier(s)

    def create_entity(self, **payload):
        with session_scope() as s:
            return entity_repo.create_entity(s, **payload)

    def create_field(self, **payload):
        with session_scope() as s:
            return field_repo.create_field(s, **payload)

    def create_persona(self, **payload):
        with session_scope() as s:
            return persona.create_persona(s, **payload)

    def create_process(self, **payload):
        with session_scope() as s:
            return process.create_process(s, **payload)

    def create_manual_config(self, **payload):
        with session_scope() as s:
            return manual_config.create_manual_config(s, **payload)

    def create_domain(self, **payload):
        with session_scope() as s:
            return domain.create_domain(s, **payload)

    def create_planning_item(self, **payload):
        with session_scope() as s:
            return planning_items.create(s, **payload)

    def create_deposit_event(self, **payload):
        with session_scope() as s:
            return deposit_events.create_deposit_event(s, **payload)

    def create_utilization_evidence(self, **payload):
        with session_scope() as s:
            return utilization_evidence.create_utilization_evidence(
                s, **payload
            )


def _run(manifest: dict, profile: dict | None = None) -> dict:
    client = AccessClient()
    plan = audit_deposit.plan_deposit(
        manifest, profile, audit_deposit.fetch_existing_state(client)
    )
    return audit_deposit.execute_plan(plan, client)


def _wrote_record_edges(dep_identifier: str) -> list[dict]:
    with session_scope() as s:
        return references.list_references(
            s,
            source_type="deposit_event",
            source_id=dep_identifier,
            relationship_kind="deposit_event_wrote_record",
        )


# ---------------------------------------------------------------------------
# Manifest loading (§2.1)
# ---------------------------------------------------------------------------


def test_manifest_roundtrip_and_version_check(tmp_path):
    path = tmp_path / "audit-report.json"
    path.write_text(json.dumps(t1_manifest()), encoding="utf-8")
    manifest = audit_deposit.load_manifest(path)
    assert audit_deposit.derive_source_label(manifest) == SOURCE_LABEL

    path.write_text(json.dumps({"manifest_version": 99}), encoding="utf-8")
    with pytest.raises(ValueError):
        audit_deposit.load_manifest(path)


# ---------------------------------------------------------------------------
# T1 — plan shape (pure, no API)
# ---------------------------------------------------------------------------


def test_t1_plan_shape():
    plan = audit_deposit.plan_deposit(
        t1_manifest(), None, audit_deposit.ExistingState()
    )
    by_type: dict[str, list] = {}
    for item in plan.creates:
        by_type.setdefault(item.record_type, []).append(item)

    assert len(by_type["entity"]) == 2
    # 2 plain custom on Engagement + 1 custom on Contact + 2 relationship
    # sides; the plain `contact` link field is deduped away (§3.3).
    assert len(by_type["field"]) == 5
    assert len(by_type["persona"]) == 2
    assert len(by_type["process"]) == 2
    assert len(by_type["manual_config"]) == 1
    assert len(by_type["domain"]) == 1
    assert len(by_type["planning_item"]) == 1  # the audit warning

    # The placeholder domain leads the write order.
    assert plan.creates[0].record_type == "domain"
    assert plan.creates[0].payload["name"] == PLACEHOLDER_DOMAIN

    # Every methodology record enters at candidate; nothing else.
    for item in plan.creates:
        if item.record_type in ("entity", "field", "persona", "manual_config"):
            assert item.payload["status"] == "candidate", item.key

    field_types = {
        item.payload["name"]: item.payload["type"] for item in by_type["field"]
    }
    assert field_types == {
        "Engagement Stage": "enum",
        "Start Date": "date",
        "Contact": "reference",
        "Mentor Status": "text",
        "Engagements": "reference",
    }

    # Native Contact maps because it carries a custom field; its kind
    # comes from the Person base type; Engagement (Base) has no kind.
    entity_payloads = {
        item.payload["name"]: item.payload for item in by_type["entity"]
    }
    assert entity_payloads["Contact"]["kind"] == "person"
    assert "kind" not in entity_payloads["Engagement"]

    # The enum's declared options ride evidence and notes.
    stage = next(
        i for i in by_type["field"] if i.payload["name"] == "Engagement Stage"
    )
    assert stage.evidence["declared_option_count"] == 7
    assert '"a"' in stage.payload["notes"]

    # The null-filter tab produced the one manual_config.
    assert by_type["manual_config"][0].payload["category"] == "saved_view"
    assert by_type["manual_config"][0].payload["name"] == (
        "Recreate filter: Stale Engagements"
    )


# ---------------------------------------------------------------------------
# T5 / T10 — wire-type map coverage and scope rules (pure)
# ---------------------------------------------------------------------------


def test_t5_wire_type_map_coverage():
    fields = [
        {
            "yaml_name": f"f{i}",
            "api_name": f"f{i}",
            "field_type": wire,
            "label": f"F{i} {wire}",
            "properties": {},
        }
        for i, wire in enumerate(sorted(audit_deposit.WIRE_TYPE_MAP))
    ]
    fields.append(
        {
            "yaml_name": "weird",
            "api_name": "weird",
            "field_type": "futureType",
            "label": "Weird",
            "properties": {},
        }
    )
    manifest = {
        "manifest_version": 1,
        "source_url": "https://crm.example.org",
        "source_name": "x",
        "timestamp": "2026-06-11T17:00:00Z",
        "output_dir": "o",
        "entities": [
            {
                "yaml_name": "Everything",
                "espo_name": "CEverything",
                "entity_class": "custom",
                "entity_type": "Base",
                "label_singular": "Everything",
                "fields": fields,
                "layouts": [],
                "filtered_tabs": [],
            }
        ],
        "relationships": [],
        "roles": [],
        "teams": [],
        "errors": [],
        "warnings": [],
    }
    plan = audit_deposit.plan_deposit(
        manifest, None, audit_deposit.ExistingState()
    )
    planned = {
        item.payload["name"]: item.payload["type"]
        for item in plan.creates
        if item.record_type == "field"
    }
    for i, wire in enumerate(sorted(audit_deposit.WIRE_TYPE_MAP)):
        assert planned[f"F{i} {wire}"] == audit_deposit.WIRE_TYPE_MAP[wire]
    assert planned["Weird"] == "text"
    assert any("futureType" in line for line in plan.anomalies)


def test_t10_scope_rules():
    manifest = t1_manifest()
    manifest["entities"].append(
        {
            "yaml_name": "Account",
            "espo_name": "Account",
            "entity_class": "native",
            "entity_type": "Company",
            "label_singular": "Account",
            "fields": [],
            "layouts": [],
            "filtered_tabs": [],
        }
    )
    manifest["entities"].append(
        {
            "yaml_name": "ScheduledJob",
            "espo_name": "ScheduledJob",
            "entity_class": "system",
            "entity_type": None,
            "label_singular": "Scheduled Job",
            "fields": [{"yaml_name": "x", "api_name": "x",
                        "field_type": "varchar", "label": "X",
                        "properties": {}}],
            "layouts": [],
            "filtered_tabs": [],
        }
    )
    # A native stock field on a captured native entity never maps.
    manifest["entities"][1]["fields"].append(
        {
            "yaml_name": "firstName",
            "api_name": "firstName",
            "field_type": "varchar",
            "label": "First Name",
            "properties": {},
            "field_class": "native",
        }
    )
    plan = audit_deposit.plan_deposit(
        manifest, None, audit_deposit.ExistingState()
    )
    entity_names = {
        item.payload["name"]
        for item in plan.creates
        if item.record_type == "entity"
    }
    assert entity_names == {"Engagement", "Contact"}
    field_names = {
        item.payload["name"]
        for item in plan.creates
        if item.record_type == "field"
    }
    assert "First Name" not in field_names


# ---------------------------------------------------------------------------
# T1 + T2 — full transform and provenance completeness (against the DB)
# ---------------------------------------------------------------------------


def test_t1_t2_full_transform_and_provenance(v2_env):
    summary = _run(t1_manifest())
    assert summary["records_summary"] == {
        "domains": 1,
        "entities": 2,
        "fields": 5,
        "personas": 2,
        "processes": 2,
        "manual_configs": 1,
        "planning_items": 1,
    }

    dep = summary["deposit_event_identifier"]
    with session_scope() as s:
        event = deposit_events.get_deposit_event(s, dep)
    assert event["deposit_event_kind"] == "audit_deposit"
    assert event["deposit_event_outcome"] == "success"
    context = event["deposit_event_apply_context"]
    assert context["source_system"] == "espocrm"
    assert context["source_instance"] == "https://crm.example.org"
    assert context["snapshot_at"] == "2026-06-11T17:00:00Z"
    assert context["source_label"] == SOURCE_LABEL

    # T2: every created record — including the placeholder domain and
    # the anomaly PI — is reachable via wrote_record, and the summary
    # sums to the edge count.
    edges = _wrote_record_edges(dep)
    assert len(edges) == sum(event["deposit_event_records_summary"].values())
    reachable = {(e["target_type"], e["target_id"]) for e in edges}
    for row in summary["created"]:
        assert (row["record_type"], row["identifier"]) in reachable

    with session_scope() as s:
        # Every methodology record is at candidate.
        for ent in entity_repo.list_entities(s):
            assert ent["entity_status"] == "candidate"
        for fld in field_repo.list_fields(s):
            assert fld["field_status"] == "candidate"
        # Both processes point at the placeholder domain.
        domains = {
            d["domain_name"]: d["domain_identifier"]
            for d in domain.list_domains(s)
        }
        for proc in process.list_processes(s):
            assert (
                proc["process_domain_identifier"]
                == domains[PLACEHOLDER_DOMAIN]
            )
        # Every field carries its parent-entity edge.
        for fld in field_repo.list_fields(s):
            parent_edges = references.list_references(
                s,
                source_type="field",
                source_id=fld["field_identifier"],
                relationship_kind="field_belongs_to_entity",
            )
            assert len(parent_edges) == 1

    # T6 (without profile): evidence rows exist for all 12 candidates
    # (the domain and the PI carry none), data-derived metrics NULL,
    # structural facts populated, profiled_at = report timestamp.
    with session_scope() as s:
        rows = utilization_evidence.list_utilization_evidence(s)
    assert len(rows) == 12
    assert summary["evidence_rows"] == 12
    assert {r["evidence_deposit_event_identifier"] for r in rows} == {dep}
    assert all(r["evidence_population_rate"] is None for r in rows)
    stage_row = next(
        r for r in rows if r["evidence_declared_option_count"] is not None
    )
    assert stage_row["evidence_declared_option_count"] == 7
    assert stage_row["evidence_profiled_at"].startswith("2026-06-11T17:00")


# ---------------------------------------------------------------------------
# T3 / T4 — idempotent and incremental re-runs
# ---------------------------------------------------------------------------


def test_t3_idempotent_rerun(v2_env):
    first = _run(t1_manifest_quiet())
    second = _run(t1_manifest_quiet())

    assert second["created"] == []
    assert second["records_summary"] == {}
    dep2 = second["deposit_event_identifier"]
    assert dep2 != first["deposit_event_identifier"]
    assert _wrote_record_edges(dep2) == []

    with session_scope() as s:
        assert len(entity_repo.list_entities(s)) == 2
        assert len(field_repo.list_fields(s)) == 5
        assert len(persona.list_personas(s)) == 2
        assert len(process.list_processes(s)) == 2
        assert len(domain.list_domains(s)) == 1
        rows = utilization_evidence.list_utilization_evidence(s)
    # One new evidence row per touched subject (12 + 12).
    assert len(rows) == 24
    assert second["evidence_rows"] == 12


def test_t4_incremental_rerun(v2_env):
    _run(t1_manifest_quiet())
    manifest = copy.deepcopy(t1_manifest_quiet())
    manifest["entities"][0]["fields"].append(
        {
            "yaml_name": "closedReason",
            "api_name": "closedReason",
            "field_type": "varchar",
            "label": "Closed Reason",
            "properties": {},
        }
    )
    second = _run(manifest)
    assert [row["record_type"] for row in second["created"]] == ["field"]
    assert second["records_summary"] == {"fields": 1}
    edges = _wrote_record_edges(second["deposit_event_identifier"])
    assert [(e["target_type"], e["target_id"]) for e in edges] == [
        ("field", second["created"][0]["identifier"])
    ]


# ---------------------------------------------------------------------------
# T6 — evidence with the profile supplied
# ---------------------------------------------------------------------------


def test_t6_evidence_with_profile(v2_env):
    _run(t1_manifest(), t1_profile())
    with session_scope() as s:
        rows = utilization_evidence.list_utilization_evidence(s)
        entities = {
            e["entity_name"]: e["entity_identifier"]
            for e in entity_repo.list_entities(s)
        }
        fields = {f["field_name"]: f["field_identifier"]
                  for f in field_repo.list_fields(s)}

    by_subject = {
        (r["evidence_subject_type"], r["evidence_subject_identifier"]): r
        for r in rows
    }
    engagement = by_subject[("entity", entities["Engagement"])]
    assert engagement["evidence_record_count"] == 412
    assert engagement["evidence_catalog_class"] == "custom"

    stage = by_subject[("field", fields["Engagement Stage"])]
    assert stage["evidence_population_rate"] == 0.966
    assert stage["evidence_populated_count"] == 398
    assert stage["evidence_distinct_value_count"] == 5
    assert stage["evidence_declared_option_count"] == 7
    assert stage["evidence_used_option_count"] == 5
    assert stage["evidence_profiled_at"].startswith("2026-06-11T18:00")

    contact = by_subject[("entity", entities["Contact"])]
    assert contact["evidence_catalog_class"] == "standard"
    assert contact["evidence_record_count"] is None


# ---------------------------------------------------------------------------
# T7 / T9 — lifecycle non-interference and soft-deleted match
# ---------------------------------------------------------------------------


def test_t7_rejected_candidate_untouched_but_evidenced(v2_env):
    _run(t1_manifest_quiet())
    with session_scope() as s:
        fld = next(
            f
            for f in field_repo.list_fields(s)
            if f["field_name"] == "Start Date"
        )["field_identifier"]
        dec = decisions.create(
            s,
            title="Drop Start Date",
            decision_date="2026-06-11",
            status="Active",
            executive_summary=(
                "Triage decision dropping the Start Date baseline candidate "
                "discovered by audit: the stakeholder confirmed the source "
                "field is dormant and the date is captured elsewhere in the "
                "process narrative, so it is deliberately not carried "
                "forward into the confirmed inventory per the PI-153 design."
            ),
        )["identifier"]
        field_repo.patch_field(
            s, fld, status="rejected", rejected_by_decision=dec
        )

    second = _run(t1_manifest_quiet())
    assert second["created"] == []
    with session_scope() as s:
        row = field_repo.get_field(s, fld)
        assert row["field_status"] == "rejected"
        rows = utilization_evidence.list_utilization_evidence(
            s, subject_type="field", subject_identifier=fld
        )
    assert len(rows) == 2  # first run + re-observation (WTK-088 I10)


def test_t9_soft_deleted_match_skipped_with_anomaly(v2_env):
    _run(t1_manifest())
    with session_scope() as s:
        per = next(
            p
            for p in persona.list_personas(s)
            if p["persona_name"] == "Program Team"
        )["persona_identifier"]
        persona.delete_persona(s, per)

    client = AccessClient()
    plan = audit_deposit.plan_deposit(
        t1_manifest(), None, audit_deposit.fetch_existing_state(client)
    )
    assert any(
        row["record_type"] == "persona" and row["identifier"] == per
        for row in plan.skipped_soft_deleted
    )
    assert any("soft-deleted match skipped" in line for line in plan.anomalies)
    # No twin is planned.
    assert not any(
        item.record_type == "persona" and item.key == "program team"
        for item in plan.creates
    )
    second = audit_deposit.execute_plan(plan, client)
    with session_scope() as s:
        live = persona.list_personas(s)
        assert len(live) == 1  # Mentor Coordinator only
    # The run's anomaly PI names the skip.
    assert {"planning_items": 1}.items() <= second["records_summary"].items()
