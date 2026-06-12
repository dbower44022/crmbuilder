"""Migration-mapping REST endpoint tests (WTK-107).

Covers the ``migration-mapping-api.md`` §7 acceptance checks end-to-end
through the FastAPI test client: the atomic two-edge POST and its
deterministic validation sequence (F), the embedded-links list reads and
filters (A), the two derived gates — triage-completeness (C) and
compile-preflight (D) — plus replace/patch/delete/restore semantics
(G/H/I/J) and the flat-shape error contracts.

Fixture vocabulary: a *baseline* candidate is one carrying audit-deposit
provenance (an inbound ``deposit_event_wrote_record`` edge); transform
sources are rejected baseline candidates superseded by a new record
(``supersedes`` at field level, ``entity_variant_of_entity`` at entity
level, the rejected record on the target side).
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine

_LABEL = "espocrm @ crm.test"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _ref(client, source_type, source_id, target_type, target_id, relationship):
    response = client.post(
        "/references",
        json={
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "relationship": relationship,
        },
    )
    assert response.status_code == 201, response.text
    return response


def _decision(client) -> str:
    response = client.post(
        "/decisions",
        json={
            "title": "Triage rejection rationale",
            "decision_date": "06-12-26",
            "status": "Active",
            "executive_summary": (
                "Records the rationale for rejecting a triage candidate "
                "during the migration-mapping test fixture build. " * 3
            ),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["identifier"]


def _entity(client, name, *, status="confirmed", baseline=True) -> str:
    response = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert response.status_code == 201, response.text
    identifier = response.json()["data"]["entity_identifier"]
    if baseline:
        _ref(
            client,
            "deposit_event",
            "DEP-001",
            "entity",
            identifier,
            "deposit_event_wrote_record",
        )
    if status != "candidate":
        response = client.patch(
            f"/entities/{identifier}", json={"entity_status": status}
        )
        assert response.status_code == 200, response.text
    return identifier


def _field(
    client, entity_identifier, name, *, status="confirmed", baseline=True
) -> str:
    response = client.post(
        "/fields",
        json={
            "field_name": name,
            "field_description": "seed",
            "field_type": "text",
            "field_belongs_to_entity_identifier": entity_identifier,
        },
    )
    assert response.status_code == 201, response.text
    identifier = response.json()["data"]["field_identifier"]
    if baseline:
        _ref(
            client,
            "deposit_event",
            "DEP-001",
            "field",
            identifier,
            "deposit_event_wrote_record",
        )
    if status != "candidate":
        response = client.patch(
            f"/fields/{identifier}", json={"field_status": status}
        )
        assert response.status_code == 200, response.text
    return identifier


def _reject(client, entity_type, identifier, decision) -> None:
    """Edge-first WTK-088 admission, then the status flip."""
    _ref(
        client, entity_type, identifier, "decision", decision,
        "rejected_by_decision",
    )
    path = "entities" if entity_type == "entity" else "fields"
    response = client.patch(
        f"/{path}/{identifier}",
        json={f"{entity_type}_status": "rejected"},
    )
    assert response.status_code == 200, response.text


def _supersede(client, entity_type, new_identifier, old_identifier) -> None:
    kind = (
        "entity_variant_of_entity" if entity_type == "entity" else "supersedes"
    )
    _ref(client, entity_type, new_identifier, entity_type, old_identifier, kind)


def _mapping_body(*, level, disposition, source, targets, **overrides) -> dict:
    body = {
        "migration_mapping_level": level,
        "migration_mapping_disposition": disposition,
        "migration_mapping_source_system_label": _LABEL,
        "migration_mapping_source_entity_name": "Contact",
        "migration_mapping_migrates_from_identifier": source,
        "migration_mapping_migrates_to_identifiers": targets,
        "migration_mapping_status": "confirmed",
    }
    if level == "field":
        body["migration_mapping_source_attribute_name"] = "cAttr"
    body.update(overrides)
    return body


def _post_mapping(client, **kwargs):
    return client.post("/migration-mappings", json=_mapping_body(**kwargs))


def _make_mapping(client, **kwargs) -> dict:
    response = _post_mapping(client, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _merge_rule(order, group="contact-full-name"):
    return {
        "rule_kind": "merge",
        "merge_group": group,
        "combinator": "concat",
        "separator": " ",
        "merge_order": order,
    }


def _split_rule(targets):
    return {
        "rule_kind": "split",
        "assignments": [
            {
                "target": target,
                "extractor": {
                    "strategy": "delimiter",
                    "delimiter": ", ",
                    "index": index,
                },
            }
            for index, target in enumerate(targets)
        ],
    }


_ENUM_RULE = {
    "rule_kind": "enum_value_map",
    "value_map": {"Mentor Candidate": "candidate"},
    "unmapped_policy": "error",
}


def _seed_six(client) -> dict:
    """The §7 A2 fixture: one entity-level keep, one rename-only transform,
    one enum-map transform, one two-mapping merge, one split — six mappings.
    All fields live on one baseline confirmed entity so the entity-level
    keep also supplies the Q6 context."""
    ids = {}
    ids["ent"] = _entity(client, "Contact")
    ids["fld_keep"] = _field(client, ids["ent"], "email")
    ids["fld_old_phone"] = _field(client, ids["ent"], "phone_raw")
    ids["fld_new_phone"] = _field(client, ids["ent"], "phone", baseline=False)
    ids["fld_old_type"] = _field(client, ids["ent"], "contact_type")
    ids["fld_new_stage"] = _field(
        client, ids["ent"], "mentor_stage", baseline=False
    )
    ids["fld_first"] = _field(client, ids["ent"], "first_name_raw")
    ids["fld_last"] = _field(client, ids["ent"], "last_name_raw")
    ids["fld_full"] = _field(client, ids["ent"], "full_name", baseline=False)
    ids["fld_combined"] = _field(client, ids["ent"], "city_state")
    ids["fld_city"] = _field(client, ids["ent"], "city", baseline=False)
    ids["fld_state"] = _field(client, ids["ent"], "state", baseline=False)

    ids["keep"] = _make_mapping(
        client,
        level="entity",
        disposition="keep",
        source=ids["ent"],
        targets=[ids["ent"]],
    )["migration_mapping_identifier"]
    ids["rename"] = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=ids["fld_old_phone"],
        targets=[ids["fld_new_phone"]],
    )["migration_mapping_identifier"]
    ids["enum"] = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=ids["fld_old_type"],
        targets=[ids["fld_new_stage"]],
        migration_mapping_transform_rules=[_ENUM_RULE],
    )["migration_mapping_identifier"]
    ids["merge_1"] = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=ids["fld_first"],
        targets=[ids["fld_full"]],
        migration_mapping_transform_rules=[_merge_rule(1)],
    )["migration_mapping_identifier"]
    ids["merge_2"] = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=ids["fld_last"],
        targets=[ids["fld_full"]],
        migration_mapping_transform_rules=[_merge_rule(2)],
    )["migration_mapping_identifier"]
    ids["split"] = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=ids["fld_combined"],
        targets=[ids["fld_city"], ids["fld_state"]],
        migration_mapping_transform_rules=[
            _split_rule([ids["fld_city"], ids["fld_state"]])
        ],
    )["migration_mapping_identifier"]
    return ids


# ---------------------------------------------------------------------------
# E1 — list (A1–A8)
# ---------------------------------------------------------------------------


def test_list_empty_engagement(client):
    response = client.get("/migration-mappings")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_list_seeded_fixture_with_links_and_filters(client):
    ids = _seed_six(client)
    response = client.get("/migration-mappings")
    assert response.status_code == 200
    data = response.json()["data"]
    assert [r["migration_mapping_identifier"] for r in data] == [
        f"MIG-{n:03d}" for n in range(1, 7)
    ]
    for record in data:
        links = record["migration_mapping_links"]
        assert links["migrates_from"]["identifier"]
        assert links["migrates_from"]["name"]
        assert links["migrates_to"]
    # Level partition (A3).
    entity_rows = client.get("/migration-mappings?level=entity").json()["data"]
    field_rows = client.get("/migration-mappings?level=field").json()["data"]
    assert len(entity_rows) == 1 and len(field_rows) == 5
    bogus = client.get("/migration-mappings?level=bogus")
    assert bogus.status_code == 422
    assert bogus.json()["errors"][0]["code"] == "invalid_filter"
    # Disposition lookup (A4).
    by_source = client.get(
        f"/migration-mappings?source_identifier={ids['fld_old_type']}"
    ).json()["data"]
    assert [r["migration_mapping_identifier"] for r in by_source] == [
        ids["enum"]
    ]
    unmapped = client.get(
        f"/migration-mappings?source_identifier={ids['fld_new_stage']}"
    ).json()["data"]
    assert unmapped == []
    # Merge-group assembly (A5).
    by_target = client.get(
        f"/migration-mappings?target_identifier={ids['fld_full']}"
    ).json()["data"]
    assert {r["migration_mapping_identifier"] for r in by_target} == {
        ids["merge_1"],
        ids["merge_2"],
    }


def test_list_include_deleted_resolves_links(client):
    ids = _seed_six(client)
    client.delete(f"/migration-mappings/{ids['enum']}")
    visible = client.get("/migration-mappings").json()["data"]
    assert ids["enum"] not in {
        r["migration_mapping_identifier"] for r in visible
    }
    everything = client.get(
        "/migration-mappings?include_deleted=true"
    ).json()["data"]
    deleted = next(
        r
        for r in everything
        if r["migration_mapping_identifier"] == ids["enum"]
    )
    assert deleted["migration_mapping_deleted_at"] is not None
    # Links still resolve through the (physically retained) edges.
    assert (
        deleted["migration_mapping_links"]["migrates_from"]["identifier"]
        == ids["fld_old_type"]
    )


def test_list_query_count_constant_in_rows(client):
    """A7 — the batched links assembly: statement count for the list read
    does not grow with the number of mappings (the N+1 guard)."""

    def count_list_statements() -> int:
        counter = {"n": 0}

        def before(*args, **kwargs):
            counter["n"] += 1

        event.listen(Engine, "before_cursor_execute", before)
        try:
            assert client.get("/migration-mappings").status_code == 200
        finally:
            event.remove(Engine, "before_cursor_execute", before)
        return counter["n"]

    ids = _seed_six(client)
    # Two mappings visible vs six.
    for key in ("rename", "enum", "merge_1", "merge_2"):
        client.delete(f"/migration-mappings/{ids[key]}")
    small = count_list_statements()
    for key in ("rename", "enum", "merge_1", "merge_2"):
        client.post(f"/migration-mappings/{ids[key]}/restore")
    large = count_list_statements()
    assert small == large


def test_list_scoped_to_engagement(client):
    _seed_six(client)
    response = client.post(
        "/engagements",
        json={
            "engagement_code": "BRAVO",
            "engagement_name": "Bravo",
            "engagement_purpose": "p",
        },
    )
    assert response.status_code == 201, response.text
    other = client.get(
        "/migration-mappings", headers={"X-Engagement": "BRAVO"}
    )
    assert other.status_code == 200
    assert other.json()["data"] == []


# ---------------------------------------------------------------------------
# E2 — next-identifier (B1)
# ---------------------------------------------------------------------------


def test_next_identifier_agrees_with_post(client):
    response = client.get("/migration-mappings/next-identifier")
    assert response.json()["data"] == {"next": "MIG-001"}
    ent = _entity(client, "Contact")
    _make_mapping(
        client, level="entity", disposition="keep", source=ent, targets=[ent]
    )
    response = client.get("/migration-mappings/next-identifier")
    assert response.json()["data"] == {"next": "MIG-002"}


# ---------------------------------------------------------------------------
# E3 — triage-completeness (C1–C6)
# ---------------------------------------------------------------------------


def test_triage_completeness_gate(client):
    decision = _decision(client)
    parent = _entity(client, "Parent", baseline=False)  # C6: never appears
    fld_keep = _field(client, parent, "referral_source")  # keep obligation
    # Transform obligation: rejected + superseded baseline entity.
    ent_old = _entity(client, "Workshop", status="candidate")
    ent_new = _entity(client, "Event", baseline=False)
    _reject(client, "entity", ent_old, decision)
    _supersede(client, "entity", ent_new, ent_old)
    # C3: an undisposed candidate and a drop never appear.
    _field(client, parent, "undisposed", status="candidate")
    fld_drop = _field(client, parent, "dropped", status="candidate")
    _reject(client, "field", fld_drop, decision)
    # C6: a non-baseline confirmed field never appears.
    _field(client, parent, "interview_born", baseline=False)

    report = client.get("/migration-mappings/triage-completeness").json()["data"]
    assert report["complete"] is False
    by_id = {item["identifier"]: item for item in report["unmapped"]}
    assert set(by_id) == {fld_keep, ent_old}
    assert by_id[fld_keep]["disposition"] == "keep"
    assert by_id[fld_keep]["detail"] == (
        "confirmed baseline candidate with no live mapping"
    )
    assert by_id[ent_old]["disposition"] == "transform"
    assert by_id[ent_old]["detail"] == (
        f"rejected baseline candidate superseded by {ent_new} "
        "with no live mapping"
    )
    assert report["counts"] == {
        "keep_unmapped": 1,
        "transform_unmapped": 1,
        "mapped": 0,
    }

    # C5: the level filter narrows the sweep.
    field_arm = client.get(
        "/migration-mappings/triage-completeness?level=field"
    ).json()["data"]
    assert {item["identifier"] for item in field_arm["unmapped"]} == {fld_keep}

    # C2: recording the two missing mappings closes the gate.
    keep_mapping = _make_mapping(
        client,
        level="field",
        disposition="keep",
        source=fld_keep,
        targets=[fld_keep],
        migration_mapping_status="candidate",
    )["migration_mapping_identifier"]
    _make_mapping(
        client,
        level="entity",
        disposition="transform",
        source=ent_old,
        targets=[ent_new],
    )
    report = client.get("/migration-mappings/triage-completeness").json()["data"]
    assert report["complete"] is True
    assert report["unmapped"] == []
    assert report["counts"]["mapped"] == 2

    # C4: a rejected mapping stops satisfying its candidate; a deferred
    # mapping satisfies it.
    response = client.patch(
        f"/migration-mappings/{keep_mapping}",
        json={
            "migration_mapping_status": "rejected",
            "rejected_by_decision": decision,
        },
    )
    assert response.status_code == 200, response.text
    report = client.get("/migration-mappings/triage-completeness").json()["data"]
    assert {item["identifier"] for item in report["unmapped"]} == {fld_keep}
    deferred = _make_mapping(
        client,
        level="field",
        disposition="keep",
        source=fld_keep,
        targets=[fld_keep],
        migration_mapping_status="candidate",
    )["migration_mapping_identifier"]
    client.patch(
        f"/migration-mappings/{deferred}",
        json={"migration_mapping_status": "deferred"},
    )
    report = client.get("/migration-mappings/triage-completeness").json()["data"]
    assert report["complete"] is True


# ---------------------------------------------------------------------------
# E4 — compile-preflight (D1–D4)
# ---------------------------------------------------------------------------


def test_compile_preflight_gates(client):
    ids = _seed_six(client)
    # D1: the coherent fixture is ready.
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report == {
        "ready": True,
        "incoherent_merge_groups": [],
        "fields_without_entity_context": [],
    }

    # D2: a second merge group with distinct targets and a duplicate
    # merge_order.
    fld_a = _field(client, ids["ent"], "nick_a")
    fld_b = _field(client, ids["ent"], "nick_b")
    fld_t1 = _field(client, ids["ent"], "alias_one", baseline=False)
    fld_t2 = _field(client, ids["ent"], "alias_two", baseline=False)
    bad_1 = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_a,
        targets=[fld_t1],
        migration_mapping_transform_rules=[_merge_rule(1, group="aliases")],
    )["migration_mapping_identifier"]
    bad_2 = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_b,
        targets=[fld_t2],
        migration_mapping_transform_rules=[_merge_rule(1, group="aliases")],
    )["migration_mapping_identifier"]
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report["ready"] is False
    assert report["incoherent_merge_groups"] == [
        {
            "merge_group": "aliases",
            "mappings": sorted([bad_1, bad_2]),
            "problems": ["distinct_targets", "duplicate_merge_order"],
        }
    ]

    # D4: only confirmed mappings participate — deferring a member
    # dissolves the incoherence.
    client.patch(
        f"/migration-mappings/{bad_2}",
        json={"migration_mapping_status": "deferred"},
    )
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report["incoherent_merge_groups"] == []


def test_compile_preflight_entity_context(client):
    # D3: a confirmed field-level mapping whose source entity has no
    # confirmed entity-level mapping.
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "old")
    fld_new = _field(client, ent, "new", baseline=False)
    mapping = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_new],
    )["migration_mapping_identifier"]
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report["ready"] is False
    assert report["fields_without_entity_context"] == [
        {
            "mapping": mapping,
            "source_field": fld_old,
            "source_entity": ent,
            "problem": (
                f"no confirmed entity-level mapping migrates from {ent}"
            ),
        }
    ]
    # Adding the entity-level mapping clears it.
    _make_mapping(
        client, level="entity", disposition="keep", source=ent, targets=[ent]
    )
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report["ready"] is True


# ---------------------------------------------------------------------------
# E5 — get (E1t, E2t)
# ---------------------------------------------------------------------------


def test_get_round_trips_four_kind_rule_list(client):
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "combined")
    fld_t1 = _field(client, ent, "part_one", baseline=False)
    fld_t2 = _field(client, ent, "part_two", baseline=False)
    rules = [
        {"rule_kind": "type_change", "from_type": "text", "to_type": "date"},
        _ENUM_RULE,
        _merge_rule(1),
        _split_rule([fld_t1, fld_t2]),
    ]
    created = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_t1, fld_t2],
        migration_mapping_transform_rules=rules,
        migration_mapping_notes="round-trip",
    )
    identifier = created["migration_mapping_identifier"]
    fetched = client.get(f"/migration-mappings/{identifier}").json()["data"]

    # The POST response serializes the in-memory tz-aware datetimes
    # (``+00:00``); the GET re-reads them tz-naive from SQLite — a
    # cohort-wide quirk, not a column fidelity issue. Compare everything
    # else byte-identically.
    def _no_ts(record):
        return {
            key: value
            for key, value in record.items()
            if not key.endswith("_at")
        }

    assert _no_ts(fetched) == _no_ts(created)
    assert fetched["migration_mapping_transform_rules"] == rules
    assert fetched["migration_mapping_links"]["migrates_from"]["identifier"] == (
        fld_old
    )


def test_get_unknown_and_soft_deleted(client):
    response = client.get("/migration-mappings/MIG-999")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"
    ent = _entity(client, "Contact")
    mapping = _make_mapping(
        client, level="entity", disposition="keep", source=ent, targets=[ent]
    )["migration_mapping_identifier"]
    client.delete(f"/migration-mappings/{mapping}")
    assert client.get(f"/migration-mappings/{mapping}").status_code == 404
    response = client.get(
        f"/migration-mappings/{mapping}?include_deleted=true"
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# E6 — create (F1–F6)
# ---------------------------------------------------------------------------


def test_create_atomic_happy_path(client):
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "contact_type")
    fld_new = _field(client, ent, "mentor_stage", baseline=False)
    record = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_new],
        migration_mapping_transform_rules=[_ENUM_RULE],
    )
    assert record["migration_mapping_identifier"] == "MIG-001"
    assert record["migration_mapping_status"] == "confirmed"
    # The edge keys are body-only, not columns.
    assert "migration_mapping_migrates_from_identifier" not in record
    links = record["migration_mapping_links"]
    assert links["migrates_from"]["identifier"] == fld_old
    assert links["migrates_from"]["status"] == "confirmed"
    assert [t["identifier"] for t in links["migrates_to"]] == [fld_new]
    # Both edges landed atomically.
    refs = client.get(
        "/references?source_type=migration_mapping&source_id=MIG-001"
    ).json()["data"]
    assert {r["relationship"] for r in refs} == {
        "migration_mapping_migrates_from_record",
        "migration_mapping_migrates_to_record",
    }


def _assert_envelope_code(response, code, status=422):
    assert response.status_code == status, response.text
    assert response.json()["errors"][0]["code"] == code, response.text


def test_create_validation_refusals(client):
    decision = _decision(client)
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "old")
    fld_new = _field(client, ent, "new", baseline=False)
    fld_other = _field(client, ent, "other", baseline=False)
    fld_pending = _field(
        client, ent, "pending", status="candidate", baseline=False
    )

    def post(**overrides):
        return _post_mapping(
            client,
            level="field",
            disposition="transform",
            source=fld_old,
            targets=[fld_new],
            **overrides,
        )

    # Step 2 — scalar domain.
    _assert_envelope_code(
        post(migration_mapping_level="bogus"), "invalid_level"
    )
    _assert_envelope_code(
        post(migration_mapping_disposition="drop"), "invalid_disposition"
    )
    _assert_envelope_code(
        post(migration_mapping_status="bogus"), "invalid_status"
    )
    _assert_envelope_code(
        post(migration_mapping_source_system_label="  "), "nonempty_required"
    )
    _assert_envelope_code(
        post(migration_mapping_identifier="MIG-1"),
        "invalid_identifier_format",
    )
    # Step 3 — I11.
    _assert_envelope_code(
        post(migration_mapping_source_attribute_name=None),
        "attribute_name_level_mismatch",
    )
    # Step 4 — rule well-formedness, naming the index.
    bad_rule = post(
        migration_mapping_transform_rules=[
            _ENUM_RULE,
            {"rule_kind": "bogus"},
        ]
    )
    _assert_envelope_code(bad_rule, "invalid_transform_rule")
    assert (
        bad_rule.json()["errors"][0]["field"]
        == "migration_mapping_transform_rules[1]"
    )
    _assert_envelope_code(
        post(
            migration_mapping_transform_rules=[
                {"rule_kind": "enum_value_map", "value_map": {"a": "b"}}
            ]
        ),
        "invalid_transform_rule",
    )
    _assert_envelope_code(
        post(
            migration_mapping_transform_rules=[
                {
                    "rule_kind": "type_change",
                    "from_type": "text",
                    "to_type": "text",
                }
            ]
        ),
        "invalid_transform_rule",
    )
    # A field-only kind on an entity-level body.
    _assert_envelope_code(
        post(
            migration_mapping_level="entity",
            migration_mapping_source_attribute_name=None,
            migration_mapping_migrates_from_identifier=ent,
            migration_mapping_migrates_to_identifiers=[ent],
            migration_mapping_transform_rules=[_ENUM_RULE],
        ),
        "invalid_transform_rule",
    )
    # Step 5 — source edge.
    _assert_envelope_code(
        post(migration_mapping_migrates_from_identifier="  "),
        "missing_source_candidate",
    )
    missing = post(migration_mapping_migrates_from_identifier="FLD-999")
    _assert_envelope_code(missing, "invalid_source_candidate")
    # An entity-typed source on a field-level body.
    level_mismatch = post(migration_mapping_migrates_from_identifier=ent)
    _assert_envelope_code(level_mismatch, "invalid_source_candidate")
    assert "level mismatch" in level_mismatch.json()["errors"][0]["message"]
    # A non-baseline source.
    _assert_envelope_code(
        post(migration_mapping_migrates_from_identifier=fld_new),
        "invalid_source_candidate",
    )
    # Step 7 — target edges.
    _assert_envelope_code(
        post(migration_mapping_migrates_to_identifiers=[]),
        "missing_target_record",
    )
    _assert_envelope_code(
        post(migration_mapping_migrates_to_identifiers=["FLD-999"]),
        "invalid_target_record",
    )
    unconfirmed = post(migration_mapping_migrates_to_identifiers=[fld_pending])
    _assert_envelope_code(unconfirmed, "invalid_target_record")
    assert fld_pending in unconfirmed.json()["errors"][0]["message"]
    _assert_envelope_code(
        post(migration_mapping_migrates_to_identifiers=[fld_new, fld_new]),
        "invalid_target_record",
    )
    # Step 8 — shape couplings.
    _assert_envelope_code(
        post(migration_mapping_migrates_to_identifiers=[fld_new, fld_other]),
        "split_rule_required",
    )
    _assert_envelope_code(
        post(
            migration_mapping_disposition="keep",
            migration_mapping_migrates_to_identifiers=[fld_new],
        ),
        "invalid_keep_shape",
    )
    # Keep with rules (target = source so only the rules violate).
    keep_source = _field(client, ent, "kept")
    _assert_envelope_code(
        post(
            migration_mapping_disposition="keep",
            migration_mapping_migrates_from_identifier=keep_source,
            migration_mapping_migrates_to_identifiers=[keep_source],
            migration_mapping_transform_rules=[_ENUM_RULE],
        ),
        "invalid_keep_shape",
    )
    # Transform with source among the targets.
    _assert_envelope_code(
        post(migration_mapping_migrates_to_identifiers=[fld_old]),
        "invalid_transform_shape",
    )
    # Split rule whose assignment set mismatches the target list.
    _assert_envelope_code(
        post(
            migration_mapping_migrates_to_identifiers=[fld_new, fld_other],
            migration_mapping_transform_rules=[
                _split_rule([fld_new, "FLD-998"])
            ],
        ),
        "invalid_transform_rule",
    )
    # F4 — every refusal above left no orphan row or edge.
    assert (
        client.get("/migration-mappings?include_deleted=true").json()["data"]
        == []
    )
    assert (
        client.get("/references?source_type=migration_mapping").json()["data"]
        == []
    )

    # Step 6 — I3, the flat shape (and F3 ordering: a body violating both
    # step 4 and step 6 fails with step 4's error).
    _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_new],
    )
    duplicate = post()
    assert duplicate.status_code == 422
    assert duplicate.json() == {
        "error": "duplicate_mapping_for_candidate",
        "candidate_identifier": fld_old,
        "existing_mapping": "MIG-001",
    }
    both = post(migration_mapping_transform_rules=[{"rule_kind": "bogus"}])
    _assert_envelope_code(both, "invalid_transform_rule")
    # Identifier collision is 409 (vs format 422 above).
    second_source = _field(client, ent, "second")
    collision = post(
        migration_mapping_migrates_from_identifier=second_source,
        migration_mapping_migrates_to_identifiers=[fld_other],
        migration_mapping_identifier="MIG-001",
    )
    assert collision.status_code == 409
    # Decision edge intact for other tests' reuse.
    assert decision


def test_create_status_starter_and_unknown_key(client):
    ent = _entity(client, "Contact")
    # F5: explicit confirmed accepted (the seed helper uses it throughout);
    # explicit rejected refused as a starter.
    refused = _post_mapping(
        client,
        level="entity",
        disposition="keep",
        source=ent,
        targets=[ent],
        migration_mapping_status="rejected",
    )
    _assert_envelope_code(refused, "invalid_status")
    # F6: unknown body key → boundary 422.
    body = _mapping_body(
        level="entity", disposition="keep", source=ent, targets=[ent]
    )
    body["migration_mapping_links"] = {}
    response = client.post("/migration-mappings", json=body)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "request_validation_error"


# ---------------------------------------------------------------------------
# E7 — replace (G1–G4)
# ---------------------------------------------------------------------------


def _replace_body(record: dict, **overrides) -> dict:
    body = {
        key: record[key]
        for key in (
            "migration_mapping_identifier",
            "migration_mapping_level",
            "migration_mapping_disposition",
            "migration_mapping_source_system_label",
            "migration_mapping_source_entity_name",
            "migration_mapping_source_attribute_name",
            "migration_mapping_transform_rules",
            "migration_mapping_notes",
            "migration_mapping_status",
        )
    }
    body.update(overrides)
    return body


def test_put_full_replace(client):
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "combined")
    fld_t1 = _field(client, ent, "one", baseline=False)
    fld_t2 = _field(client, ent, "two", baseline=False)
    record = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_t1, fld_t2],
        migration_mapping_transform_rules=[_split_rule([fld_t1, fld_t2])],
    )
    identifier = record["migration_mapping_identifier"]
    # G1: scalar replace round-trips; edges untouched.
    response = client.put(
        f"/migration-mappings/{identifier}",
        json=_replace_body(record, migration_mapping_notes="replaced"),
    )
    assert response.status_code == 200, response.text
    replaced = response.json()["data"]
    assert replaced["migration_mapping_notes"] == "replaced"
    assert replaced["migration_mapping_links"] == record[
        "migration_mapping_links"
    ]
    # G2: an edge key in the body is a boundary refusal.
    response = client.put(
        f"/migration-mappings/{identifier}",
        json=_replace_body(
            record, migration_mapping_migrates_to_identifiers=[fld_t1]
        ),
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "request_validation_error"
    # G3: dropping the split rule while two target edges live.
    response = client.put(
        f"/migration-mappings/{identifier}",
        json=_replace_body(record, migration_mapping_transform_rules=None),
    )
    _assert_envelope_code(response, "split_rule_required")
    # G4: status changes via PUT are transition-validated (flat shape).
    response = client.put(
        f"/migration-mappings/{identifier}",
        json=_replace_body(record, migration_mapping_status="candidate"),
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_status_transition",
        "from": "confirmed",
        "to": "candidate",
    }
    # Constitutive columns are immutable via PUT.
    response = client.put(
        f"/migration-mappings/{identifier}",
        json=_replace_body(record, migration_mapping_disposition="keep"),
    )
    _assert_envelope_code(response, "immutable")


# ---------------------------------------------------------------------------
# E8 — patch (H1–H6)
# ---------------------------------------------------------------------------


def test_patch_semantics(client):
    decision = _decision(client)
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "old")
    fld_new = _field(client, ent, "new", baseline=False)
    record = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_new],
        migration_mapping_notes="keep me",
        migration_mapping_status="candidate",
    )
    identifier = record["migration_mapping_identifier"]
    # H1: omitted leaves unchanged; explicit null clears.
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_source_system_label": "espocrm @ new"},
    )
    assert response.json()["data"]["migration_mapping_notes"] == "keep me"
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_notes": None},
    )
    assert response.json()["data"]["migration_mapping_notes"] is None
    # H2: constitutive and edge keys are boundary refusals.
    for key, value in [
        ("migration_mapping_level", "entity"),
        ("migration_mapping_disposition", "keep"),
        ("migration_mapping_migrates_to_identifiers", [fld_new]),
    ]:
        response = client.patch(
            f"/migration-mappings/{identifier}", json={key: value}
        )
        assert response.status_code == 422, key
    # H6: nulling the attribute on a field-level mapping violates I11.
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_source_attribute_name": None},
    )
    _assert_envelope_code(response, "attribute_name_level_mismatch")
    # H5: a rules patch re-validates well-formedness and the edge coupling.
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={
            "migration_mapping_transform_rules": [{"rule_kind": "bogus"}]
        },
    )
    _assert_envelope_code(response, "invalid_transform_rule")
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={
            "migration_mapping_transform_rules": [_split_rule([fld_new])]
        },
    )
    _assert_envelope_code(response, "invalid_transform_rule")
    # H3: a valid transition succeeds; an invalid one gets the flat shape.
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_status": "confirmed"},
    )
    assert response.json()["data"]["migration_mapping_status"] == "confirmed"
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_status": "candidate"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_status_transition"
    # H4: → rejected refused without admission; atomic key admits it.
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_status": "deferred"},
    )
    assert response.status_code == 200
    keyless = client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_status": "rejected"},
    )
    _assert_envelope_code(keyless, "rejected_requires_decision_edge")
    response = client.patch(
        f"/migration-mappings/{identifier}",
        json={
            "migration_mapping_status": "rejected",
            "rejected_by_decision": decision,
        },
    )
    assert response.status_code == 200, response.text
    refs = client.get(
        f"/references?source_type=migration_mapping&source_id={identifier}"
        "&relationship_kind=rejected_by_decision"
    ).json()["data"]
    assert len(refs) == 1 and refs[0]["target_id"] == decision


def test_patch_rejected_edge_first_path(client):
    decision = _decision(client)
    ent = _entity(client, "Contact")
    mapping = _make_mapping(
        client,
        level="entity",
        disposition="keep",
        source=ent,
        targets=[ent],
        migration_mapping_status="candidate",
    )["migration_mapping_identifier"]
    _ref(
        client, "migration_mapping", mapping, "decision", decision,
        "rejected_by_decision",
    )
    response = client.patch(
        f"/migration-mappings/{mapping}",
        json={"migration_mapping_status": "rejected"},
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# E9 / E10 — delete and restore (I1t–I2t, J1–J4)
# ---------------------------------------------------------------------------


def test_delete_frees_candidate_and_restore_round_trips(client):
    ent = _entity(client, "Contact")
    fld_old = _field(client, ent, "old")
    fld_new = _field(client, ent, "new", baseline=False)
    fld_other = _field(client, ent, "other", baseline=False)
    record = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_new],
    )
    identifier = record["migration_mapping_identifier"]
    # I1t: soft-delete; idempotent on repeat.
    response = client.delete(f"/migration-mappings/{identifier}")
    assert response.status_code == 200
    deleted_at = response.json()["data"]["migration_mapping_deleted_at"]
    assert deleted_at is not None
    repeat = client.delete(f"/migration-mappings/{identifier}")
    assert repeat.status_code == 200
    # (The first response carries the in-memory tz-aware stamp, the second
    # the tz-naive SQLite re-read — same instant, the cohort-wide quirk.)
    assert deleted_at.startswith(
        repeat.json()["data"]["migration_mapping_deleted_at"]
    )
    # The candidate's I3 slot is freed: the disposition lookup is empty...
    assert (
        client.get(
            f"/migration-mappings?source_identifier={fld_old}"
        ).json()["data"]
        == []
    )
    # J1: restore brings the full record back (timestamps excluded —
    # updated_at legitimately moves; created_at hits the tz quirk above).
    response = client.post(f"/migration-mappings/{identifier}/restore")
    assert response.status_code == 200
    restored = response.json()["data"]
    assert {
        key: value
        for key, value in restored.items()
        if not key.endswith("_at")
    } == {
        key: value for key, value in record.items() if not key.endswith("_at")
    }
    assert restored["migration_mapping_deleted_at"] is None
    # J2: restoring a live mapping refuses.
    response = client.post(f"/migration-mappings/{identifier}/restore")
    _assert_envelope_code(response, "not_deleted")
    # J3: restore with a soft-deleted edge target names the blocked side.
    client.delete(f"/migration-mappings/{identifier}")
    client.delete(f"/fields/{fld_new}")
    response = client.post(f"/migration-mappings/{identifier}/restore")
    _assert_envelope_code(response, "restore_blocked")
    assert response.json()["errors"][0]["field"] == f"migrates_to[{fld_new}]"
    client.post(f"/fields/{fld_new}/restore")
    # I2t/J4: the freed candidate accepts a new mapping; restore of the
    # old one then trips the I3 re-check with the flat shape.
    replacement = _make_mapping(
        client,
        level="field",
        disposition="transform",
        source=fld_old,
        targets=[fld_other],
    )["migration_mapping_identifier"]
    response = client.post(f"/migration-mappings/{identifier}/restore")
    assert response.status_code == 422
    assert response.json() == {
        "error": "duplicate_mapping_for_candidate",
        "candidate_identifier": fld_old,
        "existing_mapping": replacement,
    }
