"""Utilization-evidence REST surface + inline read projection tests
(WTK-088 §4.5 / WTK-097 §6, acceptance criteria A1/A4/A6/A7).

Covers the append-only evidence endpoints (POST + GET only), the
headline triage list query, and the ``include_evidence`` parameter on
the candidate endpoint families: one-request sufficiency, per-source
latest snapshots, the present-but-empty block, the 422 refusals, and
post-disposition survival.
"""

from __future__ import annotations


def _make_entity(client, name="Engagement") -> str:
    response = client.post(
        "/entities",
        json={"entity_name": name, "entity_description": "d"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["entity_identifier"]


def _make_field(client, entity_identifier, name="Stage") -> str:
    response = client.post(
        "/fields",
        json={
            "field_name": name,
            "field_description": "d",
            "field_type": "enum",
            "field_belongs_to_entity_identifier": entity_identifier,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["field_identifier"]


def _post_evidence(client, **overrides) -> dict:
    body = {
        "subject_type": "field",
        "profiled_at": "2026-06-11T18:00:00Z",
        "source_label": "espocrm @ a",
    }
    body.update(overrides)
    response = client.post("/utilization-evidence", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# The evidence endpoints (WTK-088 §4.5)
# ---------------------------------------------------------------------------


def test_post_get_roundtrip_and_404(client):
    ent = _make_entity(client)
    row = _post_evidence(
        client,
        subject_type="entity",
        subject_identifier=ent,
        catalog_class="custom",
        record_count=412,
        detail={"wire_name": "CEngagement"},
    )
    assert row["id"] > 0
    assert row["evidence_record_count"] == 412

    fetched = client.get(f"/utilization-evidence/{row['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["evidence_subject_identifier"] == ent

    missing = client.get("/utilization-evidence/99999")
    assert missing.status_code == 404
    assert missing.json()["errors"][0]["code"] == "not_found"


def test_post_validation_422(client):
    response = client.post(
        "/utilization-evidence",
        json={
            "subject_type": "entity",
            "subject_identifier": "ENT-404",
            "profiled_at": "2026-06-11T18:00:00Z",
            "source_label": "espocrm @ a",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "subject_not_found"


def test_append_only_no_mutating_methods(client):
    ent = _make_entity(client)
    row = _post_evidence(client, subject_type="entity", subject_identifier=ent)
    for method in ("PUT", "PATCH", "DELETE"):
        response = client.request(
            method, f"/utilization-evidence/{row['id']}", json={}
        )
        assert response.status_code == 405, method


def test_headline_triage_list_query(client):
    # A6: Q1 (low-population, latest) runs against the typed columns.
    ent = _make_entity(client)
    fld = _make_field(client, ent)
    for profiled_at, rate in (
        ("2026-06-01T00:00:00Z", 0.50),
        ("2026-06-11T00:00:00Z", 0.03),
    ):
        _post_evidence(
            client,
            subject_identifier=fld,
            profiled_at=profiled_at,
            population_rate=rate,
        )
    listing = client.get(
        "/utilization-evidence"
        "?subject_type=field&max_population_rate=0.05&latest=true"
    )
    assert listing.status_code == 200
    rows = listing.json()["data"]
    assert [r["evidence_population_rate"] for r in rows] == [0.03]


# ---------------------------------------------------------------------------
# include_evidence — the §6 inline read projection
# ---------------------------------------------------------------------------


def test_a1_single_get_one_request_sufficiency(client):
    ent = _make_entity(client)
    fld = _make_field(client, ent)
    _post_evidence(
        client,
        subject_identifier=fld,
        deposit_event_identifier="DEP-001",
        catalog_class="custom",
        populated_count=398,
        population_rate=0.966,
        last_populated_at="2026-06-09T14:22:00Z",
        distinct_value_count=5,
        declared_option_count=7,
        used_option_count=5,
        detail={
            "evidence_schema_version": 1,
            "wire_name": "engagementStage",
            "wire_type": "enum",
            "ghost_options": 2,
            "value_distribution": {"active": 211},
        },
    )

    response = client.get(f"/fields/{fld}?include_evidence=latest")
    assert response.status_code == 200
    record = response.json()["data"]
    assert record["field_identifier"] == fld

    block = record["utilization_evidence"]
    assert block["snapshot_count"] == 1
    assert block["sources"] == ["espocrm @ a"]
    (obj,) = block["snapshots"]
    # The A2 field probes, each by its key path.
    assert obj["metrics"]["population_rate"] == 0.966
    assert obj["metrics"]["last_populated_at"].startswith("2026-06-09")
    assert obj["metrics"]["declared_option_count"] == 7
    assert obj["metrics"]["used_option_count"] == 5
    assert obj["detail"]["value_distribution"] == {"active": 211}
    assert obj["flags"]["ghost_options"] == 2
    assert obj["catalog_class"] == "custom"
    assert obj["deposit_event"] == "DEP-001"


def test_omitted_parameter_payload_unchanged(client):
    ent = _make_entity(client)
    _post_evidence(client, subject_type="entity", subject_identifier=ent)
    record = client.get(f"/entities/{ent}").json()["data"]
    assert "utilization_evidence" not in record
    listing = client.get("/entities").json()["data"]
    assert all("utilization_evidence" not in row for row in listing)


def test_no_evidence_gives_present_but_empty_block(client):
    ent = _make_entity(client)
    record = client.get(f"/entities/{ent}?include_evidence=latest").json()[
        "data"
    ]
    assert record["utilization_evidence"] == {
        "snapshots": [],
        "snapshot_count": 0,
        "sources": [],
    }


def test_a4_multi_source_latest_one_object_per_source(client):
    ent = _make_entity(client)
    fld = _make_field(client, ent)
    for source, profiled_at, rate in (
        ("espocrm @ a", "2026-06-01T00:00:00Z", 0.50),
        ("espocrm @ a", "2026-06-11T00:00:00Z", 0.03),
        ("espocrm @ b", "2026-06-05T00:00:00Z", 0.90),
    ):
        _post_evidence(
            client,
            subject_identifier=fld,
            source_label=source,
            profiled_at=profiled_at,
            population_rate=rate,
        )

    record = client.get(f"/fields/{fld}?include_evidence=latest").json()[
        "data"
    ]
    block = record["utilization_evidence"]
    assert block["snapshot_count"] == 3
    assert block["sources"] == ["espocrm @ a", "espocrm @ b"]
    by_source = {
        obj["source_label"]: obj["metrics"]["population_rate"]
        for obj in block["snapshots"]
    }
    assert by_source == {"espocrm @ a": 0.03, "espocrm @ b": 0.90}

    # include_evidence=all on a single GET returns full history,
    # newest first.
    record = client.get(f"/fields/{fld}?include_evidence=all").json()["data"]
    history = record["utilization_evidence"]["snapshots"]
    assert [obj["metrics"]["population_rate"] for obj in history] == [
        0.03,
        0.90,
        0.50,
    ]


def test_list_projection_latest_and_all_refused(client):
    ent = _make_entity(client)
    _post_evidence(client, subject_type="entity", subject_identifier=ent)

    listing = client.get("/entities?include_evidence=latest")
    assert listing.status_code == 200
    (row,) = listing.json()["data"]
    assert row["utilization_evidence"]["snapshot_count"] == 1

    refused = client.get("/entities?include_evidence=all")
    assert refused.status_code == 422
    assert refused.json()["errors"][0]["field"] == "include_evidence"

    invalid = client.get(f"/entities/{ent}?include_evidence=bogus")
    assert invalid.status_code == 422


def test_projection_on_all_five_families(client):
    # Each family accepts the parameter and embeds the block; subjects
    # without evidence get the empty block.
    ent = _make_entity(client)
    _make_field(client, ent)
    client.post(
        "/personas",
        json={"persona_name": "Coordinator", "persona_role_summary": "r"},
    )
    dom = client.post(
        "/domains",
        json={
            "domain_name": "Baseline",
            "domain_purpose": "p",
            "domain_description": "d",
        },
    ).json()["data"]["domain_identifier"]
    client.post(
        "/processes",
        json={
            "process_name": "Active view",
            "process_domain_identifier": dom,
            "process_purpose": "p",
        },
    )
    client.post(
        "/manual-configs",
        json={
            "manual_config_name": "Recreate filter",
            "manual_config_category": "saved_view",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
        },
    )
    for family in (
        "/entities",
        "/fields",
        "/personas",
        "/processes",
        "/manual-configs",
    ):
        listing = client.get(f"{family}?include_evidence=latest")
        assert listing.status_code == 200, family
        for row in listing.json()["data"]:
            assert row["utilization_evidence"]["snapshots"] == [], family


def test_a3_unprofiled_vs_profiled_empty_distinguishable(client):
    # A3 through the read path: a schema-only deposit's object carries
    # catalog_class, wire identity, the explicit schema_only marker,
    # declared_option_count for enums, and an EMPTY flags block — while
    # a profiled-but-empty field carries its zeros as present metrics.
    # "Unprofiled" and "profiled and empty" are never confusable.
    ent = _make_entity(client)
    unprofiled = _make_field(client, ent, name="Unprofiled")
    empty = _make_field(client, ent, name="Empty")

    _post_evidence(
        client,
        subject_identifier=unprofiled,
        catalog_class="custom",
        declared_option_count=7,
        detail={
            "evidence_schema_version": 1,
            "wire_name": "unprofiledStage",
            "wire_type": "enum",
            "schema_only": True,
        },
    )
    _post_evidence(
        client,
        subject_identifier=empty,
        catalog_class="custom",
        populated_count=0,
        population_rate=0.0,
        declared_option_count=7,
        used_option_count=0,
        detail={
            "evidence_schema_version": 1,
            "wire_name": "emptyStage",
            "wire_type": "enum",
            "low_population": True,
            "thresholds": {
                "dormancy_window_days": 365,
                "low_population_threshold": 0.05,
            },
        },
    )

    def latest_object(identifier):
        record = client.get(
            f"/fields/{identifier}?include_evidence=latest"
        ).json()["data"]
        (obj,) = record["utilization_evidence"]["snapshots"]
        return obj

    schema_only = latest_object(unprofiled)
    assert schema_only["catalog_class"] == "custom"
    assert schema_only["detail"]["wire_name"] == "unprofiledStage"
    assert schema_only["detail"]["wire_type"] == "enum"
    assert schema_only["detail"]["schema_only"] is True
    assert schema_only["metrics"] == {"declared_option_count": 7}
    assert schema_only["flags"] == {}

    profiled = latest_object(empty)
    assert "schema_only" not in profiled["detail"]
    assert profiled["metrics"]["populated_count"] == 0
    assert profiled["metrics"]["population_rate"] == 0.0
    assert profiled["metrics"]["used_option_count"] == 0
    assert profiled["flags"] == {"low_population": True}


def test_include_evidence_all_honored_on_every_family_single_get(client):
    # §6.1: single-record GET MUST honor include_evidence=all — pinned
    # per family, since each router carries its own parameter handling.
    # The list-GET refusal of 'all' rides along per family.
    ent = _make_entity(client)
    fld = _make_field(client, ent)
    per = client.post(
        "/personas",
        json={"persona_name": "Coordinator", "persona_role_summary": "r"},
    ).json()["data"]["persona_identifier"]
    dom = client.post(
        "/domains",
        json={
            "domain_name": "Baseline",
            "domain_purpose": "p",
            "domain_description": "d",
        },
    ).json()["data"]["domain_identifier"]
    proc = client.post(
        "/processes",
        json={
            "process_name": "Active view",
            "process_domain_identifier": dom,
            "process_purpose": "p",
        },
    ).json()["data"]["process_identifier"]
    mcf = client.post(
        "/manual-configs",
        json={
            "manual_config_name": "Recreate filter",
            "manual_config_category": "saved_view",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
        },
    ).json()["data"]["manual_config_identifier"]

    subjects = {
        "/entities": ("entity", ent),
        "/fields": ("field", fld),
        "/personas": ("persona", per),
        "/processes": ("process", proc),
        "/manual-configs": ("manual_config", mcf),
    }
    for family, (subject_type, identifier) in subjects.items():
        _post_evidence(
            client, subject_type=subject_type, subject_identifier=identifier
        )
        single = client.get(f"{family}/{identifier}?include_evidence=all")
        assert single.status_code == 200, family
        block = single.json()["data"]["utilization_evidence"]
        assert block["snapshot_count"] == 1, family
        assert len(block["snapshots"]) == 1, family

        refused = client.get(f"{family}?include_evidence=all")
        assert refused.status_code == 422, family


def test_a7_evidence_survives_rejection_and_delete(client):
    ent = _make_entity(client)
    fld = _make_field(client, ent)
    _post_evidence(client, subject_identifier=fld, population_rate=0.5)

    dec = client.post(
        "/decisions",
        json={
            "title": "Drop Stage",
            "decision_date": "2026-06-11",
            "status": "Active",
            "executive_summary": (
                "Triage decision dropping the Stage baseline candidate "
                "after stakeholder review: the source field is dormant "
                "and its content is captured elsewhere, so the candidate "
                "is deliberately not carried into the confirmed "
                "inventory, per the PI-153 candidate-lifecycle design."
            ),
        },
    ).json()["data"]["identifier"]
    edge = client.post(
        "/references",
        json={
            "source_type": "field",
            "source_id": fld,
            "target_type": "decision",
            "target_id": dec,
            "relationship": "rejected_by_decision",
        },
    )
    assert edge.status_code in (200, 201), edge.text
    patched = client.patch(f"/fields/{fld}", json={"field_status": "rejected"})
    assert patched.status_code == 200, patched.text

    # A later standalone re-profile (no deposit event) appends to the
    # rejected candidate's history — the drift seed.
    _post_evidence(
        client,
        subject_identifier=fld,
        profiled_at="2026-07-01T00:00:00Z",
        population_rate=0.6,
    )

    record = client.get(f"/fields/{fld}?include_evidence=all").json()["data"]
    assert record["field_status"] == "rejected"
    block = record["utilization_evidence"]
    assert block["snapshot_count"] == 2
    assert [
        obj["metrics"]["population_rate"] for obj in block["snapshots"]
    ] == [0.6, 0.5]
    assert block["snapshots"][0]["deposit_event"] is None

    # Soft-deleting the subject blocks new writes (I9 liveness) but the
    # full history still projects (I10).
    client.delete(f"/fields/{fld}")
    blocked = client.post(
        "/utilization-evidence",
        json={
            "subject_type": "field",
            "subject_identifier": fld,
            "profiled_at": "2026-08-01T00:00:00Z",
            "source_label": "espocrm @ a",
        },
    )
    assert blocked.status_code == 422
    record = client.get(
        f"/fields/{fld}?include_deleted=true&include_evidence=all"
    ).json()["data"]
    assert record["utilization_evidence"]["snapshot_count"] == 2
