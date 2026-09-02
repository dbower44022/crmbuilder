"""Utilization audit area tests — PI-426 / REQ-524.

Ports the meaningful V1 profiler cases (``tests/test_data_profiler.py``): the
per-type populated / option where-clauses, the strict populated predicate and
distinct-value extraction, the §5 flags, scan-cap sampling, and the §7 retry /
abort tiers. Then the V2-specific half: the work list comes from the design's
membership on the instance, evidence rows are written per entity and field
against ENT- / FLD- identifiers with the run's deposit event stamped on them, an
instance with nothing present writes nothing, and the area is opt-in — absent
from the all-in-one audit, run by the per-area endpoint, flagged in the area
list.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import deposit_events as deposit_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import references as references_repo
from crmbuilder_v2.access.repositories import utilization_evidence as ue
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.routers import instances as instances_router
from crmbuilder_v2.introspect import utilization as ut
from crmbuilder_v2.introspect.utilization import (
    EntityWorkItem,
    ProfileOptions,
    Profiler,
    ProfileTarget,
    build_work_list,
    derive_entity_flags,
    is_low_population,
    is_populated,
    is_stale,
    option_where_for,
    populated_where_for,
    reconcile_utilization,
    scan_values,
    select_attributes_for,
    wire_entity_name,
    wire_field_name,
    wire_field_type,
)
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.api.test_instance_audit_api import (
    _FakeClient as _StructuralFake,
)
from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _stamp(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Fake record client
# ---------------------------------------------------------------------------


def _matches(where, record) -> bool:
    for item in where or []:
        t, attr, value = item["type"], item.get("attribute"), item.get("value")
        got = record.get(attr)
        if t == "isNotNull" and got is None:
            return False
        if t == "arrayIsNotEmpty" and not (isinstance(got, list) and got):
            return False
        if t == "equals" and got != value:
            return False
        if t == "arrayAnyOf" and not (isinstance(got, list) and set(got) & set(value)):
            return False
        if t == "isTrue" and got is not True:
            return False
        if t == "isLinked" and not record.get(f"{attr}Ids"):
            return False
    return True


class _RecordsFake:
    """Serves ``count_records`` / ``list_records`` from in-memory records.

    ``failures`` maps an entity to a list of statuses to return (one per call)
    before the real answer; ``reject_where`` lists where types answered 400.
    """

    def __init__(self, records=None, failures=None, reject_where=()):
        self.records = records or {}
        self.failures = {k: list(v) for k, v in (failures or {}).items()}
        self.reject_where = set(reject_where)
        self.calls: list[tuple[str, str, dict]] = []
        self.last_response_headers: dict = {}

    def _fail(self, entity):
        queue = self.failures.get(entity)
        if queue:
            return queue.pop(0)
        return None

    def list_records(self, entity, *, select=None, where=None, order_by=None,
                     order=None, offset=0, max_size=200):
        self.calls.append(("list", entity, {"where": where, "offset": offset,
                                            "max_size": max_size}))
        status = self._fail(entity)
        if status is not None:
            return status, None
        if entity not in self.records:
            return 404, None
        if any(w["type"] in self.reject_where for w in where or []):
            return 400, {"message": "bad where"}
        rows = [r for r in self.records[entity] if _matches(where, r)]
        if order_by == "createdAt":
            rows.sort(key=lambda r: r.get("createdAt") or "", reverse=order == "desc")
        page = rows[offset: offset + max_size] if max_size else []
        return 200, {"total": len(rows), "list": page}

    def get_records(self, entity, **kwargs):
        """The settings reader's one call (PI-406) — records API semantics:
        an unknown scope is 404, matching the absent-carrier outcome."""
        self.calls.append(("get", entity, dict(kwargs)))
        if entity not in self.records:
            return 404, None
        rows = list(self.records[entity])
        return 200, {"total": len(rows), "list": rows}

    def count_records(self, entity, where=None):
        self.calls.append(("count", entity, {"where": where}))
        if entity in getattr(self, "count_disabled", ()):
            return 200, -1  # EspoCRM's answer for an entity with countDisabled
        status, body = self.list_records(entity, where=where, max_size=0)
        if status == 200:
            return 200, body["total"]
        return status, None


def _item(espo="CEngagement", targets=(), native=False, identifier="ENT-001"):
    return EntityWorkItem(
        espo_name=espo, entity_identifier=identifier, native=native,
        targets=list(targets),
    )


def _target(name, ftype, options=(), fid="FLD-001"):
    return ProfileTarget(
        api_name=name, field_type=ftype, field_identifier=fid,
        declared_options=list(options),
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(ut.time, "sleep", lambda s: slept.append(s))
    return slept


# ---------------------------------------------------------------------------
# Pure functions (V1 parity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ftype,expected", [
    ("varchar", [{"type": "isNotNull", "attribute": "f"}]),
    ("int", [{"type": "isNotNull", "attribute": "f"}]),
    ("currency", [{"type": "isNotNull", "attribute": "f"}]),
    ("enum", [{"type": "isNotNull", "attribute": "f"}]),
    ("multiEnum", [{"type": "arrayIsNotEmpty", "attribute": "f"}]),
    ("checklist", [{"type": "arrayIsNotEmpty", "attribute": "f"}]),
    ("array", [{"type": "arrayIsNotEmpty", "attribute": "f"}]),
    ("link", [{"type": "isNotNull", "attribute": "fId"}]),
    ("foreign", [{"type": "isNotNull", "attribute": "fId"}]),
    ("linkParent", [{"type": "isNotNull", "attribute": "fId"}]),
    ("linkMultiple", [{"type": "isLinked", "attribute": "f"}]),
    ("personName", [{"type": "isNotNull", "attribute": "lastName"}]),
    ("address", [{"type": "isNotNull", "attribute": "fCity"}]),
    ("bool", None),
])
def test_populated_where_per_type(ftype, expected):
    assert populated_where_for("f", ftype) == expected


def test_option_where_per_type():
    assert option_where_for("f", "enum", "a") == [
        {"type": "equals", "attribute": "f", "value": "a"}
    ]
    assert option_where_for("f", "multiEnum", "a") == [
        {"type": "arrayAnyOf", "attribute": "f", "value": ["a"]}
    ]


def test_select_attributes_per_type():
    assert select_attributes_for("f", "varchar") == ["f"]
    assert select_attributes_for("f", "link") == ["fId"]
    assert select_attributes_for("f", "linkMultiple") == []
    assert select_attributes_for("f", "bool") == []
    assert select_attributes_for("f", "personName") == ["firstName", "lastName", "middleName"]
    assert select_attributes_for("home", "address") == [
        "homeStreet", "homeCity", "homeState", "homeCountry", "homePostalCode",
    ]


def test_is_populated_strict_predicate():
    assert is_populated("f", "varchar", {"f": "x"})
    assert not is_populated("f", "varchar", {"f": "   "})
    assert not is_populated("f", "varchar", {"f": None})
    assert is_populated("f", "int", {"f": 0})
    assert not is_populated("f", "int", {})
    assert is_populated("f", "multiEnum", {"f": ["a"]})
    assert not is_populated("f", "multiEnum", {"f": []})
    assert is_populated("f", "link", {"fId": "abc"})
    assert not is_populated("f", "link", {"f": "Name only"})
    assert is_populated("f", "personName", {"firstName": "A"})
    assert not is_populated("f", "personName", {"firstName": " ", "lastName": None})
    assert is_populated("home", "address", {"homeCity": "Cleveland"})
    assert is_populated("f", "bool", {})
    assert not is_populated("f", "linkMultiple", {"fIds": ["a"]})


def test_scan_values_normalization():
    assert scan_values("f", "varchar", {"f": " Open "}) == ["Open"]
    assert scan_values("f", "int", {"f": 3}) == ["3"]
    assert scan_values("f", "multiEnum", {"f": ["a", "b"]}) == ["a", "b"]
    assert scan_values("f", "link", {"fId": "abc"}) == ["abc"]
    assert scan_values("f", "personName", {"firstName": "A", "lastName": "B"}) == ["A B"]
    assert scan_values("f", "bool", {"f": True}) == []
    assert scan_values("f", "varchar", {"f": ""}) == []


def test_entity_flags_and_field_flags():
    assert derive_entity_flags(0, None, NOW, 365) == {"dormant": True, "empty": True}
    assert derive_entity_flags(5, NOW - timedelta(days=400), NOW, 365) == {
        "dormant": True, "empty": False,
    }
    assert derive_entity_flags(5, NOW - timedelta(days=10), NOW, 365) == {
        "dormant": False, "empty": False,
    }
    assert is_low_population(0.049, 0.05)
    assert not is_low_population(0.05, 0.05)  # the threshold itself is not flagged
    assert not is_low_population(None, 0.05)
    assert is_stale(3, NOW - timedelta(days=366), NOW, 365)
    assert not is_stale(3, NOW - timedelta(days=364), NOW, 365)
    assert not is_stale(0, NOW - timedelta(days=900), NOW, 365)


def test_wire_names_reverse_the_reconcile_strip():
    assert wire_entity_name("Engagement") == "CEngagement"
    assert wire_entity_name("Contact") == "Contact"
    assert wire_field_name("contactType", entity_native=True, built_in=False) == "cContactType"
    assert wire_field_name("emailAddress", entity_native=True, built_in=True) == "emailAddress"
    assert wire_field_name("cBMValueProvided", entity_native=False, built_in=False) == "cBMValueProvided"


def test_wire_field_type_via_emitter_table():
    assert wire_field_type({"field_type": "text"}) == "varchar"
    assert wire_field_type({"field_type": "text", "field_format": "email"}) == "email"
    assert wire_field_type({"field_type": "enum", "field_holds": "several"}) == "multiEnum"
    assert wire_field_type({"field_type": "number", "field_numeric_scale": "integer"}) == "int"
    assert wire_field_type({"field_type": "person_name"}) == "personName"
    assert wire_field_type({"field_type": "reference"}) == "link"
    assert wire_field_type({"field_type": "foreign"}) == "foreign"
    assert wire_field_type({"field_type": "derived", "field_derived_result_type": "boolean"}) == "bool"
    assert wire_field_type({"field_type": "time"}) is None


# ---------------------------------------------------------------------------
# Profiler over a fake client
# ---------------------------------------------------------------------------


def _engagement_records(n=3):
    return [
        {"id": f"r{i}", "createdAt": _stamp(i), "stage": "open" if i else "won",
         "tags": ["a"] if i % 2 else [], "flag": i == 0, "notes": "" if i == 1 else "n"}
        for i in range(n)
    ]


def test_profiler_counts_scans_and_flags():
    fake = _RecordsFake({"CEngagement": _engagement_records(3)})
    item = _item(targets=[
        _target("stage", "enum", ["open", "won", "lost"], fid="FLD-001"),
        _target("tags", "multiEnum", ["a", "b"], fid="FLD-002"),
        _target("flag", "bool", fid="FLD-003"),
        _target("notes", "varchar", fid="FLD-004"),
    ])
    run = Profiler(fake, ProfileOptions()).run([item])
    assert not run.aborted and run.anomalies == []
    ent = run.entities["CEngagement"]
    assert ent["record_count"] == 3
    assert ent["last_record_created_at"] is not None
    assert ent["detail"]["sampled"] is False and ent["detail"]["empty"] is False
    stage = ent["fields"]["stage"]
    assert stage["populated_count"] == 3 and stage["population_rate"] == 1.0
    assert stage["declared_option_count"] == 3 and stage["used_option_count"] == 2
    assert stage["detail"]["value_distribution"] == {"open": 2, "won": 1, "lost": 0}
    assert stage["detail"]["ghost_options"] == 1
    tags = ent["fields"]["tags"]
    assert tags["populated_count"] == 1
    assert tags["detail"]["value_distribution"] == {"a": 1, "b": 0}
    flag = ent["fields"]["flag"]
    assert flag["population_rate"] == 1.0
    assert flag["detail"]["value_distribution"] == {"true": 1, "false": 2}
    notes = ent["fields"]["notes"]
    # The complete scan refines the isNotNull count by the empty-string delta.
    assert notes["populated_count"] == 2
    assert notes["detail"]["empty_string_count"] == 1
    assert notes["detail"]["top_values"] == {"n": 2}


def test_profiler_empty_entity_writes_no_field_queries():
    fake = _RecordsFake({"CDues": []})
    item = _item(espo="CDues", targets=[_target("amount", "currency")])
    run = Profiler(fake, ProfileOptions()).run([item])
    ent = run.entities["CDues"]
    assert ent["record_count"] == 0
    assert ent["detail"] == {
        "profiled_entity_at": ent["detail"]["profiled_entity_at"],
        "dormant": True, "empty": True, "sampled": False, "request_count": 1,
    }
    assert ent["fields"]["amount"]["populated_count"] == 0
    assert "population_rate" not in ent["fields"]["amount"]


def test_profiler_scan_cap_samples_newest_first():
    fake = _RecordsFake({"CEngagement": _engagement_records(30)})
    item = _item(targets=[_target("notes", "varchar")])
    run = Profiler(fake, ProfileOptions(scan_cap=10, page_size=4)).run([item])
    detail = run.entities["CEngagement"]["detail"]
    assert detail["sampled"] is True
    assert detail["scan_count"] == 10
    assert detail["sample_fraction"] == round(10 / 30, 3)
    assert detail["sample_basis"] == "most_recent_by_created_at"
    pages = [c for c in fake.calls if c[0] == "list" and c[2]["max_size"] > 1]
    assert [c[2]["offset"] for c in pages] == [0, 4, 8]
    assert pages[-1][2]["max_size"] == 2  # capped at scan_cap - scanned
    # A sample never refines the exact count-mode (isNotNull) populated count,
    # even though one scanned record carries an empty string.
    assert run.entities["CEngagement"]["fields"]["notes"]["populated_count"] == 30
    assert "empty_string_count" not in run.entities["CEngagement"]["fields"]["notes"]["detail"]


def test_profiler_count_where_rejected_falls_back_to_scan():
    fake = _RecordsFake(
        {"CEngagement": _engagement_records(3)}, reject_where=("arrayIsNotEmpty",)
    )
    item = _item(targets=[_target("tags", "multiEnum", ["a", "b"])])
    run = Profiler(fake, ProfileOptions()).run([item])
    tags = run.entities["CEngagement"]["fields"]["tags"]
    assert tags["populated_count"] == 1  # scan-derived
    assert any(a["metric"] == "populated_count" and a["status"] == 400 for a in run.anomalies)


def test_profiler_retries_then_marks_entity_exhausted(_no_sleep):
    fake = _RecordsFake(
        {"CEngagement": _engagement_records(2)},
        failures={"CEngagement": [503, 503, 503, 503, 503]},
    )
    item = _item(targets=[_target("notes", "varchar")])
    run = Profiler(fake, ProfileOptions()).run([item])
    assert run.entities == {} and not run.aborted
    assert _no_sleep == [1.0, 2.0, 4.0, 8.0]
    assert run.anomalies[0]["scope"] == "entity"
    assert "retries exhausted" in run.anomalies[0]["note"]


def test_profiler_retry_recovers_after_transient_failures(_no_sleep):
    fake = _RecordsFake(
        {"CEngagement": _engagement_records(2)},
        failures={"CEngagement": [-1, 429]},
    )
    fake.last_response_headers = {"Retry-After": "30"}
    item = _item(targets=[_target("notes", "varchar")])
    run = Profiler(fake, ProfileOptions()).run([item])
    assert run.entities["CEngagement"]["record_count"] == 2
    # 1 s after the transport failure; the 429's Retry-After (30) beats 2 s.
    assert _no_sleep == [1.0, 30.0]


def test_profiler_three_consecutive_exhausted_entities_abort(_no_sleep):
    fake = _RecordsFake(
        {"A": [], "B": [], "C": [], "D": []},
        failures={k: [502] * 5 for k in ("A", "B", "C")},
    )
    items = [_item(espo=k, identifier=f"ENT-00{i}") for i, k in enumerate("ABCD", 1)]
    log: list = []
    run = Profiler(fake, ProfileOptions(), lambda m, lvl: log.append((m, lvl))).run(items)
    assert run.aborted and run.entities == {}
    run_rows = [a for a in run.anomalies if a["scope"] == "run"]
    assert len(run_rows) == 1 and "unprofiled: ['D']" in run_rows[0]["note"]
    assert not any(c[1] == "D" for c in fake.calls)
    assert any(lvl == "error" for _, lvl in log)


def test_profiler_401_aborts_the_run_immediately(_no_sleep):
    fake = _RecordsFake({"A": [], "B": []}, failures={"A": [401]})
    items = [_item(espo="A"), _item(espo="B", identifier="ENT-002")]
    run = Profiler(fake, ProfileOptions()).run(items)
    assert run.aborted and run.entities == {}
    assert run.anomalies == [{
        "scope": "run", "entity": "A", "status": 401,
        "note": "HTTP 401 — credentials rejected mid-run; unprofiled: ['A', 'B']",
    }]
    assert _no_sleep == []
    assert [c for c in fake.calls if c[0] == "count"] == [("count", "A", {"where": None})]


# ---------------------------------------------------------------------------
# The area against the store
# ---------------------------------------------------------------------------


def _design(s, *, native_contact=False):
    """A custom Engagement (stage enum, notes text) and, optionally, a native
    Contact carrying a custom field and a built-in one."""
    eng = entity_repo.create_entity(s, name="Engagement", description="x")["entity_identifier"]
    stage = field_repo.create_field(
        s, field_belongs_to_entity_identifier=eng, name="stage", description="x",
        type="enum", options=[{"option_value": "open"}, {"option_value": "won"}],
    )["field_identifier"]
    notes = field_repo.create_field(
        s, field_belongs_to_entity_identifier=eng, name="notes", description="x",
        type="text",
    )["field_identifier"]
    ids = {"eng": eng, "stage": stage, "notes": notes}
    if native_contact:
        con = entity_repo.create_entity(s, name="Contact", description="x")["entity_identifier"]
        ids["con"] = con
        ids["contactType"] = field_repo.create_field(
            s, field_belongs_to_entity_identifier=con, name="contactType",
            description="x", type="text",
        )["field_identifier"]
        ids["emailAddress"] = field_repo.create_field(
            s, field_belongs_to_entity_identifier=con, name="emailAddress",
            description="x", type="text", format="email", built_in=True,
        )["field_identifier"]
    return ids


def _member(s, iid, member_type, identifier, state="present"):
    mb.upsert_membership(
        s, instance_identifier=iid, member_type=member_type,
        member_identifier=identifier, state=state,
    )


def test_work_list_from_design_membership_maps_wire_names(v2_env):
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="src", url="https://crm.example.org", role="both"
        )["instance_identifier"]
        ids = _design(s, native_contact=True)
        _member(s, iid, "entity", ids["eng"])
        _member(s, iid, "entity", ids["con"], state="drifted")
        _member(s, iid, "field", ids["stage"])
        _member(s, iid, "field", ids["notes"], state="absent")  # not on the instance
        _member(s, iid, "field", ids["contactType"])
        _member(s, iid, "field", ids["emailAddress"], state="drifted")
        items = build_work_list(s, instance_identifier=iid)
    by_name = {i.espo_name: i for i in items}
    assert set(by_name) == {"CEngagement", "Contact"}
    eng = by_name["CEngagement"]
    assert not eng.native
    assert [(t.api_name, t.field_type, t.declared_options) for t in eng.targets] == [
        ("stage", "enum", ["open", "won"]),
    ]
    con = by_name["Contact"]
    assert con.native
    assert {(t.api_name, t.field_type, t.built_in) for t in con.targets} == {
        ("cContactType", "varchar", False),
        ("emailAddress", "email", True),
    }


def test_reconcile_writes_evidence_per_entity_and_field_with_provenance(v2_env):
    fake = _RecordsFake({"CEngagement": [
        {"id": "r1", "createdAt": _stamp(1), "stage": "open", "notes": "hello"},
        {"id": "r2", "createdAt": _stamp(400), "stage": "open", "notes": None},
    ]})
    log: list = []
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="src", url="https://crm.example.org", role="both"
        )["instance_identifier"]
        ids = _design(s)
        _member(s, iid, "entity", ids["eng"])
        _member(s, iid, "field", ids["stage"])
        _member(s, iid, "field", ids["notes"], state="drifted")
        summary = reconcile_utilization(
            s, instance_identifier=iid, client=fake,
            progress=lambda m, lvl: log.append((m, lvl)),
        )
        assert summary["entities"] == 1 and summary["fields"] == 2
        assert summary["evidence_rows"] == 3 and summary["aborted"] is False
        assert summary["anomalies"] == []
        dep = summary["deposit_event_identifier"]
        assert dep.startswith("DEP-")

        event = deposit_repo.get_deposit_event(s, dep)
        assert event["deposit_event_kind"] == "audit_deposit"
        assert event["deposit_event_outcome"] == "success"
        ctx = event["deposit_event_apply_context"]
        assert ctx["source_system"] == "espocrm"
        assert ctx["source_instance"] == "https://crm.example.org"
        assert ctx["instance_identifier"] == iid
        assert ctx["options"]["dormancy_window_days"] == 365

        rows = ue.list_utilization_evidence(s)
        assert len(rows) == 3
        assert {r["evidence_deposit_event_identifier"] for r in rows} == {dep}
        assert {r["evidence_source_label"] for r in rows} == {"espocrm @ crm.example.org"}
        by_subject = {r["evidence_subject_identifier"]: r for r in rows}
        assert set(by_subject) == {ids["eng"], ids["stage"], ids["notes"]}
        assert all(k.startswith(("ENT-", "FLD-")) for k in by_subject)

        ent = by_subject[ids["eng"]]
        assert ent["evidence_subject_type"] == "entity"
        assert ent["evidence_catalog_class"] == "custom"
        assert ent["evidence_record_count"] == 2
        assert ent["evidence_last_record_created_at"] is not None
        d = ent["evidence_detail"]
        assert d["evidence_schema_version"] == 1
        assert d["wire_name"] == "CEngagement"
        assert d["dormant"] is False and d["empty"] is False and d["sampled"] is False
        assert d["thresholds"] == {
            "dormancy_window_days": 365, "low_population_threshold": 0.05,
        }
        assert "profiler_version" in d and "transform_version" not in d

        stage = by_subject[ids["stage"]]
        assert stage["evidence_subject_type"] == "field"
        assert stage["evidence_populated_count"] == 2
        assert stage["evidence_population_rate"] == 1.0
        assert stage["evidence_declared_option_count"] == 2
        assert stage["evidence_used_option_count"] == 1
        assert stage["evidence_detail"]["wire_name"] == "stage"
        assert stage["evidence_detail"]["wire_type"] == "enum"
        assert stage["evidence_detail"]["value_distribution"] == {"open": 2, "won": 0}
        assert stage["evidence_detail"]["ghost_options"] == 1

        notes = by_subject[ids["notes"]]
        assert notes["evidence_populated_count"] == 1
        assert notes["evidence_population_rate"] == 0.5
        assert notes["evidence_detail"]["wire_type"] == "varchar"
        assert notes["evidence_last_populated_at"] is not None

        # Observational provenance: each subject points at the observing event.
        edges = references_repo.list_references(
            s, target_type="deposit_event", target_id=dep
        )
        assert {(e["source_type"], e["source_id"]) for e in edges} == {
            ("entity", ids["eng"]), ("field", ids["stage"]), ("field", ids["notes"]),
        }
        assert {e["relationship"] for e in edges} == {"observed_in"}
    assert any("CEngagement: 2 records, 2 fields profiled" in m for m, _ in log)


def test_reconcile_nothing_present_writes_nothing(v2_env):
    fake = _RecordsFake({"CEngagement": _engagement_records(2)})
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="src", url="https://crm.example.org", role="both"
        )["instance_identifier"]
        ids = _design(s)
        _member(s, iid, "entity", ids["eng"], state="absent")
        summary = reconcile_utilization(s, instance_identifier=iid, client=fake)
        assert summary == {
            "entities": 0, "fields": 0, "evidence_rows": 0, "anomalies": [],
            "aborted": False, "deposit_event_identifier": None,
        }
        assert ue.list_utilization_evidence(s) == []
        assert deposit_repo.list_deposit_events(s) == []
        assert fake.calls == []


def test_reconcile_aborted_before_any_entity_records_failure(v2_env, _no_sleep):
    fake = _RecordsFake({"CEngagement": []}, failures={"CEngagement": [401]})
    with session_scope() as s:
        iid = inst_repo.create_instance(
            s, name="src", url="https://crm.example.org", role="both"
        )["instance_identifier"]
        ids = _design(s)
        _member(s, iid, "entity", ids["eng"])
        summary = reconcile_utilization(s, instance_identifier=iid, client=fake)
        assert summary["aborted"] is True and summary["evidence_rows"] == 0
        event = deposit_repo.get_deposit_event(s, summary["deposit_event_identifier"])
        assert event["deposit_event_outcome"] == "failure"
        assert event["deposit_event_error_info"]["anomalies"][0]["status"] == 401
        assert ue.list_utilization_evidence(s) == []


# ---------------------------------------------------------------------------
# Opt-in through the API
# ---------------------------------------------------------------------------


class _ApiFake(_StructuralFake, _RecordsFake):
    """The structural audit fake plus record reads for its custom entities."""

    def __init__(self, *args, **kwargs):
        _RecordsFake.__init__(self, records={
            "CEngagement": [
                {"id": "r1", "createdAt": _stamp(1), "name": "One", "cStatus": "open"},
                {"id": "r2", "createdAt": _stamp(2), "name": "Two", "cStatus": None},
            ],
            "CDues": [],
        })


@pytest.fixture(autouse=True)
def _keyring_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def api(v2_env, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _ApiFake)
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return tc


def _both_instance(api) -> str:
    return api.post("/instances", json={
        "instance_name": "src", "instance_url": "https://src.example.org",
        "instance_role": "both", "secret": "api-key",
    }).json()["data"]["instance_identifier"]


def test_area_list_flags_utilization_opt_in(api):
    areas = api.get("/instances/audit/areas").json()["data"]
    assert areas[-1] == {"area": "utilization", "label": "Utilization", "opt_in": True}
    assert all(a["opt_in"] is False for a in areas[:-1])


def test_all_in_one_audit_does_not_run_utilization(api):
    iid = _both_instance(api)
    r = api.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    assert "utilization" not in r.json()["data"]
    with session_scope() as s:
        assert ue.list_utilization_evidence(s) == []


def test_audit_run_executes_utilization_end_to_end(api):
    """PI-448 (REQ-551): the utilization pass runs as a background audit run.

    Same end-to-end assertions the synchronous endpoint used to carry, now
    through the job path: start returns the ARN immediately, the worker
    executes the real reconciler, and the polled record carries the summary,
    progress counters and log while the store holds the evidence rows tied to
    one deposit event. The synchronous per-area endpoint now refuses the
    area (covered in test_audit_runs_api.py)."""
    from crmbuilder_v2.introspect.audit_run_worker import AuditRunWorker

    iid = _both_instance(api)
    assert api.post(f"/instances/{iid}/audit").status_code == 200
    started = api.post(f"/instances/{iid}/audit-runs")
    assert started.status_code == 202, started.text
    arn = started.json()["data"]["audit_run_identifier"]

    assert AuditRunWorker(worker_id="test-worker").run_once() is True

    polled = api.get(f"/audit-runs/{arn}")
    assert polled.status_code == 200
    run = polled.json()["data"]
    assert run["audit_run_status"] == "succeeded"
    summary = run["audit_run_summary"]
    assert summary["entities"] == 2 and summary["aborted"] is False
    assert summary["evidence_rows"] == 2 + summary["fields"]
    assert run["audit_run_progress"] == {"entities_done": 2, "entities_total": 2}
    assert any("CEngagement: 2 records" in line[2] for line in run["audit_run_log"])
    with session_scope() as s:
        rows = ue.list_utilization_evidence(s)
        assert len(rows) == summary["evidence_rows"]
        assert {r["evidence_source_label"] for r in rows} == {"espocrm @ src.example.org"}
        assert {r["evidence_deposit_event_identifier"] for r in rows} == {
            summary["deposit_event_identifier"]
        }


def test_profiler_count_disabled_entity_is_counted_by_the_scan():
    """``total: -1`` (countDisabled) — V1 wrote it through; V2 must not store a
    negative count. The scan supplies the count and every field metric."""
    fake = _RecordsFake({"CEngagement": _engagement_records(3)})
    fake.count_disabled = {"CEngagement"}
    item = _item(targets=[
        _target("stage", "enum", ["open", "won", "lost"], fid="FLD-001"),
        _target("notes", "varchar", fid="FLD-004"),
    ])
    run = Profiler(fake, ProfileOptions()).run([item])
    assert not run.aborted
    ent = run.entities["CEngagement"]
    assert ent["record_count"] == 3
    assert ent["detail"]["count_disabled"] is True
    assert "count_lower_bound" not in ent["detail"]
    assert ent["fields"]["stage"]["populated_count"] == 3
    assert ent["fields"]["stage"]["detail"]["value_distribution"] == {"open": 2, "won": 1, "lost": 0}
    assert any(a["metric"] == "record_count" for a in run.anomalies)
    # No per-field count query was issued — the platform would answer -1 to each.
    assert not [c for c in fake.calls if c[0] == "count" and c[2]["where"]]


def test_profiler_count_disabled_entity_hitting_the_cap_is_a_lower_bound():
    fake = _RecordsFake({"CEngagement": _engagement_records(5)})
    fake.count_disabled = {"CEngagement"}
    item = _item(targets=[_target("notes", "varchar", fid="FLD-004")])
    run = Profiler(fake, ProfileOptions(scan_cap=2, page_size=2)).run([item])
    ent = run.entities["CEngagement"]
    assert ent["record_count"] == 2
    assert ent["detail"]["count_lower_bound"] is True and ent["detail"]["sampled"] is True


def test_profiler_count_disabled_entity_without_scannable_fields_still_counts():
    fake = _RecordsFake({"CEngagement": _engagement_records(3)})
    fake.count_disabled = {"CEngagement"}
    run = Profiler(fake, ProfileOptions()).run([_item(targets=[])])
    assert run.entities["CEngagement"]["record_count"] == 3
