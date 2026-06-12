"""Candidate-inline evidence contract tests (WTK-097 / WTK-099).

The WTK-097 §8 acceptance criteria the transform and access layer own
together: the normative §4 ``evidence_detail`` key schema per subject
type, flags copied verbatim with their thresholds (A5), schema-only
degradation (A3), the conduct probes by key path (A2), plan/read
parity through the shared assembler (A8), and the REST wire shapes the
``RestDepositClient`` emits validated against the live API schemas.

Builds on the WTK-090 T-fixtures in ``test_audit_deposit``; A1/A4/A6/A7
(the read-projection criteria) live in
``tests/crmbuilder_v2/api/test_utilization_evidence_api.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.evidence_projection import EVIDENCE_FLAG_KEYS
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import utilization_evidence
from crmbuilder_v2.api import schemas as api_schemas
from crmbuilder_v2.transform import audit_deposit

from tests.crmbuilder_v2.transform.test_audit_deposit import (
    AccessClient,
    t1_manifest,
    t1_profile,
)

PROFILED_AT = "2026-06-11T18:00:00Z"
THRESHOLDS = {"dormancy_window_days": 365, "low_population_threshold": 0.05}


def rich_profile() -> dict:
    """T6 profile extended with the WTK-096 §5/§6 depth the §4 schema
    carries: profiler identity, options, entity/field detail blocks
    with flags, distribution, and recency basis."""
    profile = t1_profile()
    profile["profiler_version"] = "9.9.9-test"
    profile["options"] = dict(THRESHOLDS, scan_cap=5000)
    engagement = profile["entities"]["CEngagement"]
    engagement["detail"] = {
        "profiled_entity_at": PROFILED_AT,
        "dormant": False,
        "empty": False,
        "sampled": False,
        "request_count": 17,
    }
    stage = engagement["fields"]["engagementStage"]
    stage["detail"] = {
        "value_distribution": {
            "a": 211, "b": 102, "c": 50, "d": 30, "e": 5, "f": 0, "g": 0,
        },
        "last_populated_at_basis": "created_at",
        "ghost_options": 2,
    }
    # A second field: low-population AND stale, to exercise the field
    # flags end to end.
    engagement["fields"]["startDate"] = {
        "populated_count": 8,
        "population_rate": 0.019,
        "last_populated_at": "2024-02-01T00:00:00Z",
        "detail": {
            "last_populated_at_basis": "created_at",
            "low_population": True,
            "stale": True,
        },
    }
    return profile


def _evidence_by_key(plan: audit_deposit.DepositPlan) -> dict[str, dict]:
    return {
        item.key: item.evidence
        for item in plan.creates
        if item.evidence is not None
    }


# ---------------------------------------------------------------------------
# §4 detail conformance + A3 (schema-only degradation)
# ---------------------------------------------------------------------------


def test_a3_schema_only_detail_keys():
    plan = audit_deposit.plan_deposit(
        t1_manifest(), None, audit_deposit.ExistingState()
    )
    evidence = _evidence_by_key(plan)

    # Entity subject: §4.1 commons + §4.2 keys, schema_only marker.
    engagement = evidence["engagement"]
    detail = engagement["detail"]
    assert detail["evidence_schema_version"] == 1
    assert detail["wire_name"] == "CEngagement"
    assert detail["schema_only"] is True
    assert detail["layouts_captured"] == ["detail", "list"]
    assert "profiler_version" not in detail
    assert "thresholds" not in detail
    assert engagement["catalog_class"] == "custom"

    # Field subject: wire_name is the api_name, wire_type the EspoCRM
    # metadata type; the enum still carries declared_option_count.
    stage = evidence["engagement/engagement stage"]
    assert stage["detail"]["wire_name"] == "engagementStage"
    assert stage["detail"]["wire_type"] == "enum"
    assert stage["detail"]["schema_only"] is True
    assert stage["declared_option_count"] == 7

    # Relationship-side field: §4.3 relationship_pairing names the
    # opposite side's wire identity.
    engagements_side = evidence["contact/engagements"]
    pairing = engagements_side["detail"]["relationship_pairing"]
    assert pairing == {
        "relationship": "engagementContact",
        "link_type": "manyToOne",
        "entity": "Engagement",
        "link": "contact",
    }
    assert engagements_side["detail"]["wire_name"] == "engagements"

    # Persona: kind/kinds/scope_access (§4.4); the role+team merge is
    # impossible in T1, so each carries its own kind.
    coordinator = evidence["mentor coordinator"]
    assert coordinator["detail"]["kind"] == "role"
    assert coordinator["detail"]["scope_access"] == {
        "CEngagement": {"read": "all"}
    }
    team = evidence["program team"]
    assert team["detail"]["kind"] == "team"
    assert "scope_access" not in team["detail"]

    # Process: filter present even when null — null IS the
    # unrecoverable marker; scope/acl/nav_order named per §4.4.
    recovered = evidence["active engagements"]
    assert recovered["detail"]["filter"] == {
        "all": [{"field": "engagementStage", "op": "in", "value": ["active"]}]
    }
    assert recovered["detail"]["scope"] == "ActiveEngagements"
    assert recovered["detail"]["acl"] == "boolean"
    assert recovered["detail"]["nav_order"] == 3
    unrecovered = evidence["stale engagements"]
    assert unrecovered["detail"]["filter"] is None

    # Manual config: origin/tab_scope/tab_id (§4.4).
    mc = evidence["recreate filter: stale engagements"]
    assert mc["detail"]["origin"] == "unrecoverable_filter"
    assert mc["detail"]["tab_scope"] == "StaleEngagements"
    assert mc["detail"]["tab_id"] == "staleEngagements"
    assert mc["detail"]["wire_name"] == "staleEngagements"


def test_profiled_detail_carries_flags_thresholds_and_profiler():
    plan = audit_deposit.plan_deposit(
        t1_manifest(), rich_profile(), audit_deposit.ExistingState()
    )
    evidence = _evidence_by_key(plan)

    engagement = evidence["engagement"]
    detail = engagement["detail"]
    assert "schema_only" not in detail
    assert detail["profiler_version"] == "9.9.9-test"
    assert detail["dormant"] is False
    assert detail["empty"] is False
    assert detail["profiled_entity_at"] == PROFILED_AT
    # Thresholds travel with the flags, scan_cap excluded.
    assert detail["thresholds"] == THRESHOLDS

    stage = evidence["engagement/engagement stage"]
    # §4.3 keys arrive flattened at the detail top level, verbatim.
    assert stage["detail"]["value_distribution"]["a"] == 211
    assert stage["detail"]["last_populated_at_basis"] == "created_at"
    assert stage["detail"]["ghost_options"] == 2
    assert stage["detail"]["thresholds"] == THRESHOLDS

    start = evidence["engagement/start date"]
    assert start["detail"]["low_population"] is True
    assert start["detail"]["stale"] is True
    assert start["population_rate"] == 0.019

    # An unprofiled subject in a profiled run has no flags, hence no
    # thresholds — but carries the run's profiler identity.
    mentor_status = evidence["contact/mentor status"]
    assert "thresholds" not in mentor_status["detail"]
    assert mentor_status["detail"]["profiler_version"] == "9.9.9-test"


# ---------------------------------------------------------------------------
# A2 + A5 — conduct probes and flag/metric reconciliation (against the DB)
# ---------------------------------------------------------------------------


def test_a2_probes_and_a5_reconciliation(v2_env):
    client = AccessClient()
    plan = audit_deposit.plan_deposit(
        t1_manifest(), rich_profile(), audit_deposit.fetch_existing_state(client)
    )
    audit_deposit.execute_plan(plan, client)

    with session_scope() as s:
        entities = {
            e["entity_name"]: e["entity_identifier"]
            for e in entity_repo.list_entities(s)
        }
        fields = {
            f["field_name"]: f["field_identifier"]
            for f in field_repo.list_fields(s)
        }
        engagement = utilization_evidence.inline_evidence_block(
            s,
            subject_type="entity",
            subject_identifier=entities["Engagement"],
            mode="latest",
        )["snapshots"][0]
        stage = utilization_evidence.inline_evidence_block(
            s,
            subject_type="field",
            subject_identifier=fields["Engagement Stage"],
            mode="latest",
        )["snapshots"][0]
        start = utilization_evidence.inline_evidence_block(
            s,
            subject_type="field",
            subject_identifier=fields["Start Date"],
            mode="latest",
        )["snapshots"][0]

    # A2 — each probe by its key path, nothing outside the object:
    # "on 96.6% of your engagements"
    assert stage["metrics"]["population_rate"] == 0.966
    # "hasn't been filled in since 2024"
    assert start["metrics"]["last_populated_at"].startswith("2024-02-01")
    assert start["flags"]["stale"] is True
    # "7 declared options, 5 ever used"
    assert stage["metrics"]["declared_option_count"] == 7
    assert stage["metrics"]["used_option_count"] == 5
    assert stage["detail"]["value_distribution"]["f"] == 0
    # "records and recency on the entity"
    assert engagement["metrics"]["record_count"] == 412
    assert engagement["metrics"]["last_record_created_at"].startswith(
        "2026-06-09"
    )
    assert engagement["flags"]["dormant"] is False
    # "someone paid to add this"
    assert stage["catalog_class"] == "custom"

    # A5 — re-deriving every flag from the object's own metrics at
    # detail.thresholds reproduces the stored flag.
    for obj in (engagement, stage, start):
        if not obj["flags"]:
            continue
        thresholds = obj["detail"]["thresholds"]
        window = timedelta(days=thresholds["dormancy_window_days"])
        profiled = datetime.fromisoformat(
            obj["profiled_at"].replace("Z", "+00:00")
        )
        metrics = obj["metrics"]
        flags = obj["flags"]
        if "empty" in flags:
            assert flags["empty"] == (metrics["record_count"] == 0)
        if "dormant" in flags:
            last = datetime.fromisoformat(
                metrics["last_record_created_at"].replace("Z", "+00:00")
            )
            assert flags["dormant"] == (
                metrics["record_count"] == 0 or last < profiled - window
            )
        if "ghost_options" in flags:
            assert flags["ghost_options"] == (
                metrics["declared_option_count"]
                - metrics["used_option_count"]
            )
        if "low_population" in flags:
            assert flags["low_population"] == (
                metrics["population_rate"]
                < thresholds["low_population_threshold"]
            )
        if "stale" in flags:
            last = datetime.fromisoformat(
                metrics["last_populated_at"].replace("Z", "+00:00")
            )
            assert flags["stale"] == (
                metrics["populated_count"] > 0 and last < profiled - window
            )


# ---------------------------------------------------------------------------
# A8 — plan/read parity through the shared assembler
# ---------------------------------------------------------------------------


def _norm_dt(value: object) -> object:
    """Canonicalize a datetime string to a UTC instant.

    The typed datetime columns are the one representation difference
    between a plan-time object (the profiler's ``Z``-suffixed strings)
    and a read-back object (the storage round-trip's rendering); both
    denote the same instant."""
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat()
    return value


def _normalize_object(obj: dict) -> dict:
    """An evidence object with its typed datetime values canonicalized;
    everything else (detail included) is byte-stable across surfaces."""
    out = dict(obj)
    out["profiled_at"] = _norm_dt(out["profiled_at"])
    out["metrics"] = {
        key: (
            _norm_dt(value)
            if key in ("last_record_created_at", "last_populated_at")
            else value
        )
        for key, value in obj["metrics"].items()
    }
    return out


def test_a8_plan_read_parity(v2_env):
    client = AccessClient()
    for run, profile in enumerate((None, rich_profile())):
        plan = audit_deposit.plan_deposit(
            t1_manifest(),
            profile,
            audit_deposit.fetch_existing_state(client),
        )
        # Creates keyed by plan key (identifier unknown until execute),
        # matches keyed by identifier.
        planned = {
            item.key: audit_deposit.plan_evidence_object(
                item.evidence,
                profiled_at=plan.profiled_at,
                source_label=plan.source_label,
            )
            for item in plan.creates
            if item.evidence is not None
        }
        planned.update(
            {
                match.identifier: audit_deposit.plan_evidence_object(
                    match.evidence,
                    profiled_at=plan.profiled_at,
                    source_label=plan.source_label,
                    subject_identifier=match.identifier,
                )
                for match in plan.matches
            }
        )
        summary = audit_deposit.execute_plan(plan, client)
        key_by_identifier = {
            row["identifier"]: row["key"] for row in summary["created"]
        }

        with session_scope() as s:
            rows = utilization_evidence.list_utilization_evidence(
                s,
                deposit_event_identifier=summary["deposit_event_identifier"],
            )
        read = {
            key_by_identifier.get(
                row["evidence_subject_identifier"],
                row["evidence_subject_identifier"],
            ): utilization_evidence.project_evidence_object(row)
            for row in rows
        }

        # Every evidence row this run wrote has a planned twin, and the
        # two execute-time-resolved envelope values are the only
        # permitted difference (§3.4 determinism otherwise).
        assert set(read) == set(planned), f"run {run}"
        for key, read_obj in read.items():
            plan_obj = _normalize_object(planned[key])
            masked = _normalize_object(
                dict(
                    read_obj,
                    subject_identifier=plan_obj["subject_identifier"],
                    deposit_event=None,
                )
            )
            assert masked == plan_obj, (run, key)
        assert len(read) == 12


# ---------------------------------------------------------------------------
# REST wire shapes — the deposit path's bodies validate against the
# live API schemas (extra="forbid")
# ---------------------------------------------------------------------------


def test_rest_payloads_validate_against_api_schemas():
    plan = audit_deposit.plan_deposit(
        t1_manifest(), rich_profile(), audit_deposit.ExistingState()
    )
    schema_by_type = {
        "entity": ("entity_", api_schemas.EntityCreateIn),
        "field": ("field_", api_schemas.FieldCreateIn),
        "persona": ("persona_", api_schemas.PersonaCreateIn),
        "process": ("process_", api_schemas.ProcessCreateIn),
        "manual_config": ("manual_config_", api_schemas.ManualConfigCreateIn),
        "domain": ("domain_", api_schemas.DomainCreateIn),
        "planning_item": ("", api_schemas.PlanningItemCreateIn),
    }
    for item in plan.creates:
        prefix, schema = schema_by_type[item.record_type]
        payload = dict(item.payload)
        if item.record_type == "field":
            payload["field_belongs_to_entity_identifier"] = "ENT-001"
        if item.record_type == "process":
            payload.pop("domain_key")
            payload["domain_identifier"] = "DOM-001"
        if prefix:
            payload = audit_deposit._prefix_payload(prefix, payload)
        schema(**payload)  # raises on any unknown or missing key

    # The deposit-event body, kind included, against its schema.
    event_payload = audit_deposit._prefix_payload(
        "deposit_event_",
        {
            "identifier": "DEP-001",
            "title": "Audit deposit: x",
            "description": "d",
            "kind": "audit_deposit",
            "outcome": "success",
            "records_summary": {"entities": 2},
            "apply_context": plan.apply_context,
            "log_file_path": "PRDs/x/dep_001.log",
            "error_info": None,
            "references": [],
        },
        passthrough=frozenset({"references"}),
    )
    api_schemas.DepositEventCreateIn(**event_payload)
    assert event_payload["deposit_event_kind"] == "audit_deposit"

    # An evidence body as execute_plan posts it (unprefixed wire).
    first = next(item for item in plan.creates if item.evidence is not None)
    api_schemas.UtilizationEvidenceCreateIn(
        subject_identifier="FLD-001",
        profiled_at=plan.profiled_at,
        source_label=plan.source_label,
        deposit_event_identifier="DEP-001",
        **first.evidence,
    )


def test_flags_lift_into_plan_objects():
    # The rich profile exercises every §3.3 flag; each lifts from
    # detail into the plan-time object's flags block via the shared
    # vocabulary constant.
    plan = audit_deposit.plan_deposit(
        t1_manifest(), rich_profile(), audit_deposit.ExistingState()
    )
    lifted: set[str] = set()
    for item in plan.creates:
        if item.evidence is None:
            continue
        obj = audit_deposit.plan_evidence_object(
            item.evidence,
            profiled_at=plan.profiled_at,
            source_label=plan.source_label,
        )
        assert set(obj["flags"]) <= set(EVIDENCE_FLAG_KEYS), item.key
        lifted |= set(obj["flags"])
    assert lifted == {
        "dormant",
        "empty",
        "low_population",
        "stale",
        "ghost_options",
    }