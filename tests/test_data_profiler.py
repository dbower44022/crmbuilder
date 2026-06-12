"""Tests for ``espo_impl.core.data_profiler`` (WTK-096 / WTK-098).

Covers the spec's verification criteria P1–P9: metric exactness on a
small fixture, the per-type populated predicate, the created-at recency
proxy, dormancy threshold boundaries, deterministic pagination, the
sampling cap, count→scan fallback, the three failure tiers, and the
read-only invariant. The REST strategy is exercised against an
in-memory fake implementing the count/list semantics the profiler
relies on, so the metric math runs end-to-end without HTTP.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import espo_impl.core.data_profiler as dp
from espo_impl.core.audit_manager import (
    AuditReport,
    EntityAuditResult,
    FieldAuditResult,
    RelationshipAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.data_profiler import (
    DataProfiler,
    ProfileOptions,
    build_work_list,
    is_populated,
    populated_where_for,
    select_attributes_for,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(tz=UTC)


def _ts(dt: datetime) -> str:
    """Render a datetime in EspoCRM's list-payload format."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


RECENT = _ts(NOW - timedelta(days=2))


def _rec(i: int, created: str = RECENT, **fields: Any) -> dict[str, Any]:
    return {"id": f"r{i}", "createdAt": created, **fields}


def _matches(record: dict[str, Any], where: list[dict[str, Any]]) -> bool:
    for item in where:
        wtype = item["type"]
        attr = item.get("attribute")
        if wtype == "isNotNull":
            if record.get(attr) is None:
                return False
        elif wtype == "equals":
            if record.get(attr) != item.get("value"):
                return False
        elif wtype == "arrayIsNotEmpty":
            if not record.get(attr):
                return False
        elif wtype == "arrayAnyOf":
            values = record.get(attr) or []
            if not any(v in values for v in item.get("value", [])):
                return False
        elif wtype == "isTrue":
            if record.get(attr) is not True:
                return False
        elif wtype == "isLinked":
            if not record.get(f"{attr}Ids"):
                return False
        else:
            return False
    return True


class FakeEspoClient:
    """In-memory stand-in for the record-query surface the profiler uses.

    Implements ``count_records`` / ``list_records`` over per-entity
    record lists, with hook points for injecting error responses and a
    server-side page clamp.
    """

    def __init__(self, datasets: dict[str, list[dict[str, Any]]]) -> None:
        self.datasets = datasets
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.last_response_headers: dict[str, str] = {}
        # callable(entity, where) -> (status, value) | None to override
        self.count_hook = None
        self.list_hook = None
        self.page_clamp: int | None = None

    def count_records(self, entity, where=None):
        self.calls.append(("count_records", entity, {"where": where}))
        self.last_response_headers = {}
        if self.count_hook:
            override = self.count_hook(entity, where)
            if override is not None:
                return override
        if entity not in self.datasets:
            return 404, None
        rows = [r for r in self.datasets[entity] if _matches(r, where or [])]
        return 200, len(rows)

    def list_records(self, entity, select=None, where=None, order_by=None,
                     order=None, offset=0, max_size=200):
        self.calls.append(("list_records", entity, {
            "select": select, "where": where, "order_by": order_by,
            "order": order, "offset": offset, "max_size": max_size,
        }))
        self.last_response_headers = {}
        if self.list_hook:
            override = self.list_hook(entity, where)
            if override is not None:
                return override
        if entity not in self.datasets:
            return 404, None
        rows = [r for r in self.datasets[entity] if _matches(r, where or [])]
        if order_by:
            rows = sorted(
                rows,
                key=lambda r: r.get(order_by) or "",
                reverse=(order == "desc"),
            )
        total = len(rows)
        if self.page_clamp is not None:
            max_size = min(max_size, self.page_clamp)
        page = rows[offset:offset + max_size]
        if select:
            page = [{k: r.get(k) for k in select} for r in page]
        return 200, {"total": total, "list": page}


def _field(api_name: str, field_type: str, **props: Any) -> FieldAuditResult:
    return FieldAuditResult(
        yaml_name=api_name, api_name=api_name, field_type=field_type,
        label=api_name, properties=props,
    )


def _entity(
    espo_name: str,
    fields: list[FieldAuditResult],
    entity_class: EntityClass = EntityClass.CUSTOM,
) -> EntityAuditResult:
    return EntityAuditResult(
        yaml_name=espo_name.lstrip("C"), espo_name=espo_name,
        entity_class=entity_class, fields=fields,
    )


def _report(entities, relationships=None) -> AuditReport:
    return AuditReport(
        source_url="https://crm.example.org",
        source_name="profiler-test",
        timestamp="2026-06-11T00:00:00Z",
        output_dir="",
        entities=list(entities),
        relationships=list(relationships or []),
    )


def _run(report, client, options=None):
    profiler = DataProfiler(client, report, options=options)
    return profiler.run()


def _no_sleep(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(dp.time, "sleep", sleeps.append)
    return sleeps


# ---------------------------------------------------------------------------
# P1 — metric exactness on a small fixture
# ---------------------------------------------------------------------------

def _p1_dataset() -> list[dict[str, Any]]:
    stage = ["A"] * 5 + ["B"] * 3 + ["C"] + [None] * 3
    records = []
    for i in range(12):
        records.append(_rec(
            i,
            created=_ts(NOW - timedelta(days=2, minutes=12 - i)),
            notes=f"note {i}" if i < 9 else None,
            stage=stage[i],
            tags=["x"] if i < 4 else (["x", "y"] if i == 4 else None),
            mentorId=f"m{i % 3}" if i < 6 else None,
            active=i < 4,
            legacy=None,
        ))
    return records


def _p1_entity() -> EntityAuditResult:
    return _entity("CEngagement", [
        _field("notes", "varchar"),
        _field("stage", "enum", options=list("ABCDEFG")),
        _field("tags", "multiEnum", options=["x", "y", "z"]),
        _field("mentor", "link"),
        _field("active", "bool"),
        _field("legacy", "varchar"),
    ])


def test_p1_small_fixture_metrics():
    client = FakeEspoClient({"CEngagement": _p1_dataset()})
    profile = _run(_report([_p1_entity()]), client)

    assert profile.data is not None
    ent = profile.data["entities"]["CEngagement"]
    assert ent["record_count"] == 12
    assert ent["detail"]["empty"] is False
    assert ent["detail"]["dormant"] is False
    assert ent["detail"]["sampled"] is False
    fields = ent["fields"]

    notes = fields["notes"]
    assert notes["populated_count"] == 9
    assert notes["population_rate"] == 0.75
    assert notes["distinct_value_count"] == 9

    stage = fields["stage"]
    assert stage["populated_count"] == 9
    assert stage["declared_option_count"] == 7
    assert stage["used_option_count"] == 3
    assert stage["detail"]["ghost_options"] == 4
    assert stage["detail"]["value_distribution"] == {
        "A": 5, "B": 3, "C": 1, "D": 0, "E": 0, "F": 0, "G": 0,
    }
    assert stage["detail"]["undeclared_values"] == {}

    tags = fields["tags"]
    assert tags["populated_count"] == 5
    assert tags["used_option_count"] == 2
    # Distribution counts records containing each element (sums ≥ populated).
    assert tags["detail"]["value_distribution"] == {"x": 5, "y": 1, "z": 0}

    mentor = fields["mentor"]
    assert mentor["populated_count"] == 6
    assert mentor["distinct_value_count"] == 3  # m0/m1/m2

    active = fields["active"]
    assert active["populated_count"] == 12
    assert active["population_rate"] == 1.0
    assert active["detail"]["value_distribution"] == {"true": 4, "false": 8}

    legacy = fields["legacy"]
    assert legacy["populated_count"] == 0
    assert legacy["population_rate"] == 0.0
    assert "last_populated_at" not in legacy
    assert legacy["detail"]["low_population"] is True

    assert profile.data["anomalies"] == []


def test_p9_read_only_client_surface():
    """P9 — the profiler touches only the two GET-only client methods."""
    client = FakeEspoClient({"CEngagement": _p1_dataset()})
    _run(_report([_p1_entity()]), client)
    assert {name for name, _, _ in client.calls} <= {"count_records", "list_records"}


# ---------------------------------------------------------------------------
# P2 — populated predicate per type
# ---------------------------------------------------------------------------

def test_p2_numeric_zero_is_populated():
    records = [_rec(0, score=0), _rec(1, score=7), _rec(2, score=None)]
    client = FakeEspoClient({"CThing": records})
    profile = _run(_report([_entity("CThing", [_field("score", "int")])]), client)
    score = profile.data["entities"]["CThing"]["fields"]["score"]
    assert score["populated_count"] == 2
    assert score["distinct_value_count"] == 2


def test_p2_empty_string_refinement():
    records = (
        [_rec(i, notes=f"v{i}") for i in range(5)]
        + [_rec(i + 5, notes="") for i in range(3)]
        + [_rec(8, notes=None), _rec(9, notes=None)]
    )
    client = FakeEspoClient({"CThing": records})
    profile = _run(_report([_entity("CThing", [_field("notes", "varchar")])]), client)
    notes = profile.data["entities"]["CThing"]["fields"]["notes"]
    # Count mode saw 8 non-NULL; the strict predicate trims to 5.
    assert notes["populated_count"] == 5
    assert notes["population_rate"] == 0.5
    assert notes["detail"]["empty_string_count"] == 3


def test_p2_person_name_any_component():
    records = [
        _rec(0, firstName="Ada", lastName=None, middleName=None),
        _rec(1, firstName=None, lastName="Turing", middleName=None),
        _rec(2, firstName=None, lastName=None, middleName=None),
    ]
    client = FakeEspoClient({"Contact": records})
    profile = _run(
        _report([_entity("Contact", [_field("name", "personName")],
                         entity_class=EntityClass.NATIVE)]),
        client,
    )
    name = profile.data["entities"]["Contact"]["fields"]["name"]
    # The lastName count-query approximation sees 1; any-component sees 2.
    assert name["populated_count"] == 2


def test_p2_zero_record_entity_omits_rate():
    client = FakeEspoClient({"CGhost": []})
    profile = _run(
        _report([_entity("CGhost", [_field("notes", "varchar"),
                                    _field("kind", "enum", options=["a", "b"])])]),
        client,
    )
    ent = profile.data["entities"]["CGhost"]
    assert ent["record_count"] == 0
    assert "last_record_created_at" not in ent
    assert ent["detail"]["empty"] is True
    assert ent["detail"]["dormant"] is True
    notes = ent["fields"]["notes"]
    assert notes["populated_count"] == 0
    assert "population_rate" not in notes
    assert "low_population" not in notes.get("detail", {})


def test_p2_predicate_table():
    rec = {
        "id": "r0", "createdAt": RECENT,
        "amount": 0, "flag": False, "tags": [],
        "ownerId": None, "parentId": "p1",
    }
    assert is_populated("amount", "float", rec) is True
    assert is_populated("flag", "bool", rec) is True
    assert is_populated("tags", "multiEnum", rec) is False
    assert is_populated("owner", "link", rec) is False
    assert is_populated("parent", "linkParent", rec) is True


def test_populated_where_table():
    assert populated_where_for("f", "bool") is None
    assert populated_where_for("f", "multiEnum") == [
        {"type": "arrayIsNotEmpty", "attribute": "f"}]
    assert populated_where_for("f", "link") == [
        {"type": "isNotNull", "attribute": "fId"}]
    assert populated_where_for("f", "linkMultiple") == [
        {"type": "isLinked", "attribute": "f"}]
    assert populated_where_for("f", "personName") == [
        {"type": "isNotNull", "attribute": "lastName"}]
    assert populated_where_for("f", "address") == [
        {"type": "isNotNull", "attribute": "fCity"}]
    assert populated_where_for("f", "varchar") == [
        {"type": "isNotNull", "attribute": "f"}]


def test_select_attributes_exclude_link_multiple_and_bool():
    assert select_attributes_for("f", "linkMultiple") == []
    assert select_attributes_for("f", "bool") == []
    assert select_attributes_for("f", "link") == ["fId"]
    assert select_attributes_for("f", "address") == [
        "fStreet", "fCity", "fState", "fCountry", "fPostalCode"]


# ---------------------------------------------------------------------------
# P3 — recency proxy
# ---------------------------------------------------------------------------

def test_p3_last_populated_at_is_max_created_among_populated():
    newest_populated = NOW - timedelta(days=30)
    records = [
        _rec(0, created=_ts(NOW - timedelta(days=400)), notes="old"),
        _rec(1, created=_ts(newest_populated), notes="newer",
             modifiedAt=_ts(NOW)),  # modifiedAt must not be the basis
        _rec(2, created=_ts(NOW - timedelta(days=1)), notes=None),
    ]
    client = FakeEspoClient({"CThing": records})
    profile = _run(_report([_entity("CThing", [_field("notes", "varchar")])]), client)
    ent = profile.data["entities"]["CThing"]
    notes = ent["fields"]["notes"]
    assert notes["last_populated_at"] == newest_populated.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert notes["detail"]["last_populated_at_basis"] == "created_at"
    # Entity recency covers all records, populated or not.
    assert ent["last_record_created_at"] == (
        (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))


# ---------------------------------------------------------------------------
# P4 — dormancy and threshold boundaries
# ---------------------------------------------------------------------------

def test_p4_entity_dormancy_boundary():
    dormant_records = [_rec(0, created=_ts(NOW - timedelta(days=366)))]
    fresh_records = [_rec(0, created=_ts(NOW - timedelta(days=200)))]
    client = FakeEspoClient({"COld": dormant_records, "CFresh": fresh_records})
    profile = _run(
        _report([_entity("COld", []), _entity("CFresh", [])]), client,
    )
    assert profile.data["entities"]["COld"]["detail"]["dormant"] is True
    assert profile.data["entities"]["COld"]["detail"]["empty"] is False
    assert profile.data["entities"]["CFresh"]["detail"]["dormant"] is False


def test_p4_low_population_boundary():
    # 100 records, populated on exactly 5 → rate 0.05 → NOT flagged.
    at_threshold = [_rec(i, notes="v" if i < 5 else None) for i in range(100)]
    # 1000 records, populated on 49 → rate 0.049 → flagged.
    below = [_rec(i, notes="v" if i < 49 else None) for i in range(1000)]
    client = FakeEspoClient({"CAt": at_threshold, "CBelow": below})
    profile = _run(
        _report([
            _entity("CAt", [_field("notes", "varchar")]),
            _entity("CBelow", [_field("notes", "varchar")]),
        ]),
        client,
    )
    at = profile.data["entities"]["CAt"]["fields"]["notes"]
    assert at["population_rate"] == 0.05
    assert "low_population" not in at.get("detail", {})
    below_f = profile.data["entities"]["CBelow"]["fields"]["notes"]
    assert below_f["population_rate"] == 0.049
    assert below_f["detail"]["low_population"] is True


def test_p4_stale_field_flag():
    records = [
        _rec(0, created=_ts(NOW - timedelta(days=400)), notes="ancient"),
        _rec(1, created=_ts(NOW - timedelta(days=1)), notes=None),
    ]
    client = FakeEspoClient({"CThing": records})
    profile = _run(_report([_entity("CThing", [_field("notes", "varchar")])]), client)
    ent = profile.data["entities"]["CThing"]
    assert ent["detail"]["dormant"] is False  # entity itself is active
    assert ent["fields"]["notes"]["detail"]["stale"] is True


# ---------------------------------------------------------------------------
# P5 — pagination
# ---------------------------------------------------------------------------

def _scan_offsets(client: FakeEspoClient, entity: str) -> list[int]:
    return [
        kwargs["offset"]
        for name, ent, kwargs in client.calls
        if name == "list_records" and ent == entity
        and kwargs["max_size"] > 1  # exclude recency queries
    ]


def test_p5_pagination_offsets_and_termination():
    records = [_rec(i, notes=f"v{i}") for i in range(950)]
    client = FakeEspoClient({"CBig": records})
    profile = _run(_report([_entity("CBig", [_field("notes", "varchar")])]), client)
    assert _scan_offsets(client, "CBig") == [0, 200, 400, 600, 800]
    assert profile.data["entities"]["CBig"]["detail"]["sampled"] is False
    assert profile.data["entities"]["CBig"]["fields"]["notes"]["populated_count"] == 950


def test_p5_pagination_advances_by_returned_length_on_clamp():
    records = [_rec(i, notes=f"v{i}") for i in range(250)]
    client = FakeEspoClient({"CClamped": records})
    client.page_clamp = 100  # server clamps maxSize=200 down to 100
    profile = _run(_report([_entity("CClamped", [_field("notes", "varchar")])]), client)
    assert _scan_offsets(client, "CClamped") == [0, 100, 200]
    notes = profile.data["entities"]["CClamped"]["fields"]["notes"]
    assert notes["distinct_value_count"] == 250


# ---------------------------------------------------------------------------
# P6 — sampling cap
# ---------------------------------------------------------------------------

def test_p6_sampling_cap_recency_biased():
    # 25 records; the newest 10 carry values new-*, the older 15 old-*.
    records = [
        _rec(i, created=_ts(NOW - timedelta(days=i)),
             notes=f"new-{i}" if i < 10 else f"old-{i}")
        for i in range(25)
    ]
    client = FakeEspoClient({"CBig": records})
    options = ProfileOptions(scan_cap=10, page_size=4)
    profile = _run(_report([_entity("CBig", [_field("notes", "varchar")])]), client,
                   options=options)
    ent = profile.data["entities"]["CBig"]
    detail = ent["detail"]
    assert detail["sampled"] is True
    assert detail["scan_count"] == 10
    assert detail["sample_fraction"] == 0.4
    assert detail["sample_basis"] == "most_recent_by_created_at"
    notes = ent["fields"]["notes"]
    # Count-mode metrics stay exact at any scale.
    assert notes["populated_count"] == 25
    assert notes["population_rate"] == 1.0
    # Scan-derived metrics come from the newest 10 only — no extrapolation.
    assert notes["distinct_value_count"] == 10
    assert all(v.startswith("new-") for v in notes["detail"]["top_values"])


def test_p6_options_echoed_in_output():
    client = FakeEspoClient({"CThing": []})
    options = ProfileOptions(scan_cap=10, dormancy_window_days=180,
                             low_population_threshold=0.1)
    profile = _run(_report([_entity("CThing", [])]), client, options=options)
    assert profile.data["options"] == {
        "dormancy_window_days": 180,
        "low_population_threshold": 0.1,
        "scan_cap": 10,
    }


# ---------------------------------------------------------------------------
# P7 — count→scan fallback
# ---------------------------------------------------------------------------

def test_p7_count_to_scan_fallback_isolated_to_one_metric():
    records = [_rec(i, legacyCode=f"L{i}" if i < 4 else None, notes=f"v{i}")
               for i in range(6)]
    client = FakeEspoClient({"CEngagement": records})

    def reject_legacy(entity, where):
        if where and where[0].get("attribute") == "legacyCode":
            return 400, None
        return None

    client.count_hook = reject_legacy
    profile = _run(
        _report([_entity("CEngagement", [_field("legacyCode", "varchar"),
                                         _field("notes", "varchar")])]),
        client,
    )
    legacy = profile.data["entities"]["CEngagement"]["fields"]["legacyCode"]
    # Scan-derived value is still exact on a full scan.
    assert legacy["populated_count"] == 4
    assert "last_populated_at" in legacy
    notes = profile.data["entities"]["CEngagement"]["fields"]["notes"]
    assert notes["populated_count"] == 6  # sibling unaffected

    anomalies = profile.data["anomalies"]
    assert len(anomalies) == 1
    assert anomalies[0]["scope"] == "metric"
    assert anomalies[0]["entity"] == "CEngagement"
    assert anomalies[0]["field"] == "legacyCode"
    assert anomalies[0]["status"] == 400
    assert "scan-derived" in anomalies[0]["note"]


# ---------------------------------------------------------------------------
# P8 — failure tiers
# ---------------------------------------------------------------------------

def test_p8_403_entity_omitted_run_continues():
    client = FakeEspoClient({"CDenied": [_rec(0)], "COpen": [_rec(0, notes="v")]})

    def deny(entity, where):
        if entity == "CDenied":
            return 403, None
        return None

    client.count_hook = deny
    profile = _run(
        _report([_entity("CDenied", []), _entity("COpen", [_field("notes", "varchar")])]),
        client,
    )
    assert "CDenied" not in profile.data["entities"]
    assert "COpen" in profile.data["entities"]
    assert profile.aborted is False
    entity_anomalies = [a for a in profile.data["anomalies"] if a["scope"] == "entity"]
    assert len(entity_anomalies) == 1
    assert entity_anomalies[0]["entity"] == "CDenied"
    assert entity_anomalies[0]["status"] == 403


def test_p8_401_mid_run_writes_partial_profile(tmp_path):
    client = FakeEspoClient({"CFirst": [_rec(0, notes="v")], "CSecond": [_rec(0)]})

    def unauthorized_second(entity, where):
        if entity == "CSecond":
            return 401, None
        return None

    client.count_hook = unauthorized_second
    profile = _run(
        _report([_entity("CFirst", [_field("notes", "varchar")]),
                 _entity("CSecond", []),
                 _entity("CThird", [])]),
        client,
    )
    assert profile.aborted is True
    assert profile.data is not None  # ≥ 1 entity completed → partial written
    assert list(profile.data["entities"]) == ["CFirst"]
    run_anomalies = [a for a in profile.data["anomalies"] if a["scope"] == "run"]
    assert len(run_anomalies) == 1
    assert "CThird" in run_anomalies[0]["note"]  # unprofiled remainder listed
    assert profile.write(tmp_path) == tmp_path / "utilization-profile.json"


def test_p8_401_on_first_entity_writes_nothing(tmp_path):
    client = FakeEspoClient({"COnly": [_rec(0)]})
    client.count_hook = lambda entity, where: (401, None)
    profile = _run(_report([_entity("COnly", [])]), client)
    assert profile.aborted is True
    assert profile.data is None
    assert profile.write(tmp_path) is None
    assert not (tmp_path / "utilization-profile.json").exists()


def test_p8_retry_after_header_honored(monkeypatch):
    sleeps = _no_sleep(monkeypatch)
    client = FakeEspoClient({"CThing": [_rec(0)]})
    state = {"failed": False}

    def rate_limit_once(entity, where):
        if not state["failed"]:
            state["failed"] = True
            client.last_response_headers = {"Retry-After": "3"}
            return 429, None
        return None

    client.count_hook = rate_limit_once
    profile = _run(_report([_entity("CThing", [])]), client)
    assert profile.data["entities"]["CThing"]["record_count"] == 1
    # Retry-After 3 wins over the computed first-step backoff of 1.
    assert 3.0 in sleeps


def test_p8_three_consecutive_exhaustions_abort(monkeypatch):
    _no_sleep(monkeypatch)
    client = FakeEspoClient({})
    client.count_hook = lambda entity, where: (503, None)
    profile = _run(
        _report([_entity(f"C{i}", []) for i in range(5)]), client,
    )
    assert profile.aborted is True
    assert profile.data is None  # nothing completed
    # Entities 4 and 5 were never attempted.
    attempted = {entity for _, entity, _ in client.calls}
    assert attempted == {"C0", "C1", "C2"}


def test_p8_exhausted_counter_resets_on_success(monkeypatch):
    _no_sleep(monkeypatch)
    client = FakeEspoClient({"CUp": [_rec(0)]})

    def down_except_cup(entity, where):
        if entity != "CUp":
            return 503, None
        return None

    client.count_hook = down_except_cup
    profile = _run(
        _report([_entity("CDown1", []), _entity("CDown2", []),
                 _entity("CUp", []), _entity("CDown3", [])]),
        client,
    )
    # Two exhaustions, a success resetting the counter, one more — no abort.
    assert profile.aborted is False
    assert list(profile.data["entities"]) == ["CUp"]


# ---------------------------------------------------------------------------
# Output contract and write semantics
# ---------------------------------------------------------------------------

def test_output_contract_header_and_write(tmp_path):
    client = FakeEspoClient({"CEngagement": _p1_dataset()})
    profile = _run(_report([_p1_entity()]), client)
    data = profile.data
    assert data["manifest_version"] == 1
    assert data["source_url"] == "https://crm.example.org"
    assert data["source_label"] == "espocrm @ crm.example.org"
    assert data["profiled_at"].endswith("Z")
    assert data["completed_at"] >= data["profiled_at"]
    assert "profiler_version" in data
    detail = data["entities"]["CEngagement"]["detail"]
    assert detail["request_count"] > 0
    assert "profiled_entity_at" in detail

    path = profile.write(tmp_path)
    assert path == tmp_path / "utilization-profile.json"
    import json
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == data
    # No temp files left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["utilization-profile.json"]


def test_warning_lines_render_anomalies():
    client = FakeEspoClient({"CDenied": [_rec(0)]})
    client.count_hook = lambda entity, where: (403, None) if entity == "CDenied" else None
    profile = _run(
        _report([_entity("CDenied", []), _entity("COpen", [])]), client,
    )
    # COpen missing from datasets → 404 entity anomaly too.
    lines = profile.warning_lines()
    assert any("CDenied" in line and "[entity]" in line for line in lines)


# ---------------------------------------------------------------------------
# Work-list derivation (§2.1)
# ---------------------------------------------------------------------------

def test_work_list_fields_and_options_from_manifest():
    report = _report([_p1_entity()])
    (item,) = build_work_list(report)
    assert item.espo_name == "CEngagement"
    by_name = {t.api_name: t for t in item.targets}
    assert by_name["stage"].declared_options == list("ABCDEFG")
    assert by_name["notes"].declared_options == []


def test_work_list_relationship_sides_and_dedup():
    engagement = _entity("CEngagement", [_field("mentor", "link")])
    mentor = _entity("CMentor", [])
    rel = RelationshipAuditResult(
        name="engagementToMentor", entity="Engagement", entity_foreign="Mentor",
        link_type="manyToOne", link="mentor", link_foreign="engagements",
        label="Mentor", label_foreign="Engagements",
    )
    report = _report([engagement, mentor], [rel])
    items = {i.espo_name: i for i in build_work_list(report)}
    # Primary side dedups against the existing link field target.
    assert [t.api_name for t in items["CEngagement"].targets] == ["mentor"]
    # Foreign side contributes a linkMultiple-shaped target.
    (foreign_target,) = items["CMentor"].targets
    assert foreign_target.api_name == "engagements"
    assert foreign_target.field_type == "linkMultiple"


def test_work_list_skips_unprofiled_relationship_side():
    engagement = _entity("CEngagement", [])
    rel = RelationshipAuditResult(
        name="engagementToAccount", entity="Engagement", entity_foreign="Account",
        link_type="manyToOne", link="account", link_foreign="engagements",
        label="Account", label_foreign="Engagements",
    )
    report = _report([engagement], [rel])  # Account not audited
    (item,) = build_work_list(report)
    assert [t.api_name for t in item.targets] == ["account"]
    assert item.targets[0].field_type == "link"
