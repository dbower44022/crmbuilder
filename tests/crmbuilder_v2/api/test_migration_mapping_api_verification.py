"""Migration-mapping API verification (WTK-109).

Independent verification of the WTK-107 endpoints against the WTK-105
design spec (``migration-mapping-api.md``) — the wire-layer companion to
the WTK-108 storage verification. The sibling WTK-107 suite
(``test_migration_mappings_api.py``) is the implementer's coverage of the
§7 acceptance checks; this suite re-executes the contract from the spec
text with its own fixtures and closes the checks that suite left open:

* B1's two-create next-identifier agreement; the ``invalid_filter``
  refusal on the triage-completeness ``level`` param; engagement scoping
  on the single GET and both gate reads (A8 beyond the list).
* The F2 refusals not yet exercised: boundary-missing edge keys, empty
  ``source_entity_name``, ``source_attribute_name`` on an entity-level
  body, soft-deleted source/target candidates, keep with two targets,
  a split rule on a single-target mapping (the I6 biconditional), and
  the §5.2 conditional-coupling matrix (separator ⇔ concat,
  ``default_value`` ⇔ ``unmapped_policy='default'``, entity-level
  merge/split admissibility, ``merge_order`` domain, unknown rule keys).
* F3 first-error determinism across more step pairs than the single
  4-vs-6 case (2v4, 3v4, 4v5, 5v7, 6v7, 7v8).
* F4 orphan-freedom probed at the DB layer (rows, edges, AND change-log
  emits — stronger than the API-level list probe).
* D2's ``distinct_combinators``/``distinct_separators`` problem codes and
  D3's target-parent-mismatch arm of Q6, neither driven before.
* G/H 404s, the PUT body-identifier ``path_mismatch``, the PATCH
  empty-body no-op, J recovery (restore succeeds after the blocked edge
  target is itself restored).
* K1 at the wire level (change-log rows for create/update/delete/restore
  through the API), K2 route order, and K3 — the CBM-scale triage-order
  batch (20 mappings, both levels, all four rule kinds) driving E3
  ``complete: false → true`` and E4 to ``ready: true`` with no write
  ever blocked by engagement-level incompleteness.

Spec-deviation findings from this verification are recorded in the V2
DB as FND-003 (spec §4.10 wording — edge liveness is derived from the
row, not stamped onto the edges; behavior-equivalent) and FND-004 (K1
wording — delete/restore emits carry ``operation='update'``, the cohort
soft-delete convention), both ``finding_relates_to`` → WTK-109.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import ChangeLog, MigrationMapping, Reference
from sqlalchemy import select

_LABEL = "espocrm @ crm.cbmentors.org"


# ---------------------------------------------------------------------------
# Seed helpers (independent of the WTK-107 suite's)
# ---------------------------------------------------------------------------


def _ref(client, source_type, source_id, target_type, target_id, kind):
    response = client.post(
        "/references",
        json={
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "relationship": kind,
        },
    )
    assert response.status_code == 201, response.text


def _decision(client) -> str:
    response = client.post(
        "/decisions",
        json={
            "title": "Verification triage rejection rationale",
            "decision_date": "06-12-26",
            "status": "Active",
            "executive_summary": (
                "Records the rationale for rejecting triage candidates "
                "while verifying the migration-mapping API surface. " * 3
            ),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["identifier"]


def _entity(client, name, *, status="confirmed", baseline=True) -> str:
    response = client.post(
        "/entities",
        json={"entity_name": name, "entity_description": "verification seed"},
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


def _field(client, entity, name, *, status="confirmed", baseline=True) -> str:
    response = client.post(
        "/fields",
        json={
            "field_name": name,
            "field_description": "verification seed",
            "field_type": "text",
            "field_belongs_to_entity_identifier": entity,
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
    """The WTK-088 edge-first admission, then the status flip."""
    _ref(
        client, entity_type, identifier, "decision", decision,
        "rejected_by_decision",
    )
    path = "entities" if entity_type == "entity" else "fields"
    response = client.patch(
        f"/{path}/{identifier}", json={f"{entity_type}_status": "rejected"}
    )
    assert response.status_code == 200, response.text


def _supersede(client, entity_type, new, old) -> None:
    kind = (
        "entity_variant_of_entity" if entity_type == "entity" else "supersedes"
    )
    _ref(client, entity_type, new, entity_type, old, kind)


def _body(*, level, disposition, source, targets, **overrides) -> dict:
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
        body["migration_mapping_source_attribute_name"] = "cVerify"
    body.update(overrides)
    return body


def _post(client, **kwargs):
    return client.post("/migration-mappings", json=_body(**kwargs))


def _create(client, **kwargs) -> dict:
    response = _post(client, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _merge(order, *, group="full-name", combinator="concat", **extra):
    rule = {
        "rule_kind": "merge",
        "merge_group": group,
        "combinator": combinator,
        "merge_order": order,
    }
    if combinator == "concat":
        rule["separator"] = " "
    rule.update(extra)
    return rule


def _split(targets):
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


_ENUM = {
    "rule_kind": "enum_value_map",
    "value_map": {"Mentor Candidate": "candidate"},
    "unmapped_policy": "error",
}
_TYPE_CHANGE = {"rule_kind": "type_change", "from_type": "text", "to_type": "date"}


def _err(response, code, *, status=422):
    assert response.status_code == status, response.text
    error = response.json()["errors"][0]
    assert error["code"] == code, response.text
    return error


def _transform_pair(client):
    """A baseline source field + a confirmed non-baseline target field."""
    ent = _entity(client, "Contact")
    src = _field(client, ent, "old_attr")
    dst = _field(client, ent, "new_attr", baseline=False)
    return ent, src, dst


# ---------------------------------------------------------------------------
# E2 / B1 — next-identifier agreement over two creates
# ---------------------------------------------------------------------------


def test_b1_next_identifier_agrees_across_two_creates(client):
    assert client.get("/migration-mappings/next-identifier").json()["data"] == {
        "next": "MIG-001"
    }
    ent_a = _entity(client, "Contact")
    ent_b = _entity(client, "Organization")
    _create(client, level="entity", disposition="keep",
            source=ent_a, targets=[ent_a])
    _create(client, level="entity", disposition="keep",
            source=ent_b, targets=[ent_b])
    assert client.get("/migration-mappings/next-identifier").json()["data"] == {
        "next": "MIG-003"
    }
    # The helper agrees with what the next identifier-omitted POST assigns.
    ent_c = _entity(client, "Workshop")
    created = _create(client, level="entity", disposition="keep",
                      source=ent_c, targets=[ent_c])
    assert created["migration_mapping_identifier"] == "MIG-003"


# ---------------------------------------------------------------------------
# E1 / E3 — filter validation and unknown-param tolerance
# ---------------------------------------------------------------------------


def test_a3_c5_level_filter_refusals_and_unknown_param(client):
    _err(client.get("/migration-mappings?level=bogus"), "invalid_filter")
    _err(
        client.get("/migration-mappings/triage-completeness?level=bogus"),
        "invalid_filter",
    )
    # Unknown query params are ignored (FastAPI default, spec §4.2).
    response = client.get("/migration-mappings?bogus=1")
    assert response.status_code == 200
    assert response.json()["data"] == []


# ---------------------------------------------------------------------------
# A8 — engagement scoping beyond the list read
# ---------------------------------------------------------------------------


def test_a8_scoping_covers_get_gates_and_next_identifier(client):
    ent = _entity(client, "Contact")
    fld = _field(client, ent, "unmapped_keep")  # an open keep obligation
    mapping = _create(
        client, level="entity", disposition="keep", source=ent, targets=[ent]
    )["migration_mapping_identifier"]
    assert fld
    response = client.post(
        "/engagements",
        json={
            "engagement_code": "BRAVO",
            "engagement_name": "Bravo",
            "engagement_purpose": "scoping probe",
        },
    )
    assert response.status_code == 201, response.text
    bravo = {"X-Engagement": "BRAVO"}
    assert (
        client.get(f"/migration-mappings/{mapping}", headers=bravo).status_code
        == 404
    )
    # The default engagement's open obligation never leaks into BRAVO's
    # gates, and the identifier sequence is per-engagement.
    completeness = client.get(
        "/migration-mappings/triage-completeness", headers=bravo
    ).json()["data"]
    assert completeness == {
        "complete": True,
        "unmapped": [],
        "counts": {"keep_unmapped": 0, "transform_unmapped": 0, "mapped": 0},
    }
    preflight = client.get(
        "/migration-mappings/compile-preflight", headers=bravo
    ).json()["data"]
    assert preflight["ready"] is True
    assert client.get(
        "/migration-mappings/next-identifier", headers=bravo
    ).json()["data"] == {"next": "MIG-001"}


# ---------------------------------------------------------------------------
# E6 / F2 — refusals the implementer's suite left unexercised
# ---------------------------------------------------------------------------


def test_f2_boundary_missing_edge_keys(client):
    # Step 1: the edge keys are REQUIRED in the body; omission is a
    # boundary 422, not the repository's missing_source_candidate.
    body = _body(
        level="entity", disposition="keep", source="ENT-001",
        targets=["ENT-001"],
    )
    del body["migration_mapping_migrates_from_identifier"]
    response = client.post("/migration-mappings", json=body)
    _err(response, "request_validation_error")
    body = _body(
        level="entity", disposition="keep", source="ENT-001",
        targets=["ENT-001"],
    )
    del body["migration_mapping_migrates_to_identifiers"]
    _err(
        client.post("/migration-mappings", json=body),
        "request_validation_error",
    )


def test_f2_scalar_refusals(client):
    _, src, dst = _transform_pair(client)

    def post(**overrides):
        return _post(
            client, level="field", disposition="transform",
            source=src, targets=[dst], **overrides,
        )

    _err(
        post(migration_mapping_source_entity_name=" "), "nonempty_required"
    )
    # F2: the attribute on an entity-level body (the spec names this arm
    # explicitly; the sibling suite only drove null-on-field-level).
    ent = _entity(client, "Organization")
    _err(
        _post(
            client, level="entity", disposition="keep",
            source=ent, targets=[ent],
            migration_mapping_source_attribute_name="cAttr",
        ),
        "attribute_name_level_mismatch",
    )
    # Four digits fail the ^MIG-\d{3}$ format.
    _err(
        post(migration_mapping_identifier="MIG-1000"),
        "invalid_identifier_format",
    )


def test_f2_soft_deleted_source_and_target_refused(client):
    ent = _entity(client, "Contact")
    src = _field(client, ent, "live_source")
    dst = _field(client, ent, "live_target", baseline=False)
    gone_src = _field(client, ent, "gone_source")
    gone_dst = _field(client, ent, "gone_target", baseline=False)
    client.delete(f"/fields/{gone_src}")
    client.delete(f"/fields/{gone_dst}")
    refusal = _post(
        client, level="field", disposition="transform",
        source=gone_src, targets=[dst],
    )
    error = _err(refusal, "invalid_source_candidate")
    assert "soft-deleted" in error["message"]
    refusal = _post(
        client, level="field", disposition="transform",
        source=src, targets=[gone_dst],
    )
    error = _err(refusal, "invalid_target_record")
    assert "soft-deleted" in error["message"]


def test_f2_keep_with_two_targets_refused(client):
    ent = _entity(client, "Contact")
    src = _field(client, ent, "kept")
    other = _field(client, ent, "other", baseline=False)
    _err(
        _post(
            client, level="field", disposition="keep",
            source=src, targets=[src, other],
            migration_mapping_transform_rules=[_split([src, other])],
        ),
        "invalid_keep_shape",
    )


def test_f2_split_rule_on_single_target_refused(client):
    # I6 is a biconditional: a split rule with one target edge is as
    # malformed as two target edges without one.
    _, src, dst = _transform_pair(client)
    error = _err(
        _post(
            client, level="field", disposition="transform",
            source=src, targets=[dst],
            migration_mapping_transform_rules=[_split([dst])],
        ),
        "invalid_transform_rule",
    )
    assert error["field"] == "migration_mapping_transform_rules[0]"


def test_f2_rule_conditional_couplings(client):
    """The §5.2 coupling matrix. Rule validation is POST step 4, ahead of
    the edge steps, so placeholder edge identifiers never mask the rule
    refusal — itself a property of the deterministic ordering."""

    def rule_refusal(level, rule, *, index=0):
        overrides = {"migration_mapping_transform_rules": [rule]}
        if level == "entity":
            overrides["migration_mapping_source_attribute_name"] = None
        error = _err(
            _post(
                client, level=level, disposition="transform",
                source="FLD-998", targets=["FLD-999"], **overrides,
            ),
            "invalid_transform_rule",
        )
        assert error["field"] == (
            f"migration_mapping_transform_rules[{index}]"
        )
        return error["message"]

    # separator ⇔ combinator = concat (both directions).
    rule = _merge(1)
    rule["combinator"] = "coalesce"  # keeps the separator key
    assert "separator" in rule_refusal("field", rule)
    rule = _merge(1)
    del rule["separator"]
    assert "separator" in rule_refusal("field", rule)
    # default_value ⇔ unmapped_policy = 'default' (both directions).
    assert "default_value" in rule_refusal(
        "field", {**_ENUM, "unmapped_policy": "default"}
    )
    assert "default_value" in rule_refusal(
        "field", {**_ENUM, "default_value": "candidate"}
    )
    # to_type/from_type domain membership.
    assert "from_type" in rule_refusal(
        "field", {**_TYPE_CHANGE, "from_type": "varchar"}
    )
    # merge_order is an integer >= 1 (and not a bool).
    assert "merge_order" in rule_refusal("field", _merge(0))
    assert "merge_order" in rule_refusal("field", _merge(True))
    # Entity-level admissibility: merge only with coalesce; split only
    # with value_router extractors + unrouted_policy; field-only kinds
    # inadmissible outright.
    assert "coalesce" in rule_refusal("entity", _merge(1))
    assert "not applicable" in rule_refusal("entity", _TYPE_CHANGE)
    assert "value_router" in rule_refusal("entity", _split(["ENT-001"]))
    # unrouted_policy is entity-level only.
    field_split = _split(["FLD-001", "FLD-002"])
    field_split["unrouted_policy"] = "error"
    assert "entity-level" in rule_refusal("field", field_split)
    # Unknown keys are refused per rule (the extra=forbid mirror).
    assert "unknown" in rule_refusal("field", {**_ENUM, "bogus": 1})
    # The list itself must be a list.
    _err(
        _post(
            client, level="field", disposition="transform",
            source="FLD-998", targets=["FLD-999"],
            migration_mapping_transform_rules={"rule_kind": "merge"},
        ),
        "request_validation_error",
    )


def test_f3_first_error_determinism_across_step_pairs(client):
    ent = _entity(client, "Contact")
    src = _field(client, ent, "ordered_source")
    dst = _field(client, ent, "ordered_target", baseline=False)
    pending = _field(client, ent, "pending", status="candidate",
                     baseline=False)
    bad_rule = [{"rule_kind": "bogus"}]

    def post(**overrides):
        return _post(
            client, level="field", disposition="transform",
            source=src, targets=[dst], **overrides,
        )

    # Step 2 (scalar) beats step 4 (rules).
    _err(
        post(migration_mapping_status="bogus",
             migration_mapping_transform_rules=bad_rule),
        "invalid_status",
    )
    # Step 3 (I11) beats step 4.
    _err(
        post(migration_mapping_source_attribute_name=None,
             migration_mapping_transform_rules=bad_rule),
        "attribute_name_level_mismatch",
    )
    # Step 4 beats step 5 (source).
    _err(
        post(migration_mapping_transform_rules=bad_rule,
             migration_mapping_migrates_from_identifier="FLD-999"),
        "invalid_transform_rule",
    )
    # Step 5 beats step 7 (targets).
    _err(
        post(migration_mapping_migrates_from_identifier="FLD-999",
             migration_mapping_migrates_to_identifiers=["FLD-998"]),
        "invalid_source_candidate",
    )
    # Step 7 beats step 8 (shape): an unconfirmed target wins over the
    # source-in-targets violation.
    _err(
        post(migration_mapping_migrates_to_identifiers=[pending, src]),
        "invalid_target_record",
    )
    # Step 6 (I3, the flat shape) beats step 7.
    _create(client, level="field", disposition="transform",
            source=src, targets=[dst])
    duplicate = post(migration_mapping_migrates_to_identifiers=["FLD-999"])
    assert duplicate.status_code == 422
    assert duplicate.json()["error"] == "duplicate_mapping_for_candidate"


def test_f4_refusals_leave_no_rows_edges_or_change_log(client):
    """Orphan-freedom probed beneath the API: a step-7 and a step-8
    refusal leave zero mapping rows, zero mapping edges, and zero
    change-log emits (the single-transaction guarantee)."""
    ent = _entity(client, "Contact")
    src = _field(client, ent, "probe_source")
    dst = _field(client, ent, "probe_target", baseline=False)
    other = _field(client, ent, "probe_other", baseline=False)
    _err(
        _post(client, level="field", disposition="transform",
              source=src, targets=["FLD-999"]),
        "invalid_target_record",
    )
    _err(
        _post(client, level="field", disposition="transform",
              source=src, targets=[dst, other]),
        "split_rule_required",
    )
    with session_scope() as s:
        assert s.scalars(select(MigrationMapping)).all() == []
        assert (
            s.scalars(
                select(Reference).where(
                    Reference.source_type == "migration_mapping"
                )
            ).all()
            == []
        )
        assert (
            s.scalars(
                select(ChangeLog).where(
                    ChangeLog.entity_type == "migration_mapping"
                )
            ).all()
            == []
        )


# ---------------------------------------------------------------------------
# E7 / E8 — replace and patch contracts beyond the happy paths
# ---------------------------------------------------------------------------


def test_g_put_unknown_404_and_body_identifier_must_match(client):
    ent = _entity(client, "Contact")
    record = _create(client, level="entity", disposition="keep",
                     source=ent, targets=[ent])
    put_body = {
        key: record[key]
        for key in (
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
    response = client.put("/migration-mappings/MIG-999", json=put_body)
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"
    # §4.8: the body identifier is optional-but-must-match.
    mismatch = client.put(
        f"/migration-mappings/{record['migration_mapping_identifier']}",
        json={**put_body, "migration_mapping_identifier": "MIG-777"},
    )
    _err(mismatch, "path_mismatch")
    # Omitting it entirely is the optional half.
    response = client.put(
        f"/migration-mappings/{record['migration_mapping_identifier']}",
        json=put_body,
    )
    assert response.status_code == 200, response.text


def test_h_patch_unknown_404_and_empty_body_noop(client):
    response = client.patch("/migration-mappings/MIG-999", json={})
    assert response.status_code == 404
    ent = _entity(client, "Contact")
    record = _create(client, level="entity", disposition="keep",
                     source=ent, targets=[ent])
    identifier = record["migration_mapping_identifier"]
    response = client.patch(f"/migration-mappings/{identifier}", json={})
    assert response.status_code == 200
    after = response.json()["data"]
    assert {k: v for k, v in after.items() if not k.endswith("_at")} == {
        k: v for k, v in record.items() if not k.endswith("_at")
    }


# ---------------------------------------------------------------------------
# E4 / D2–D3 — the preflight problem codes not yet driven
# ---------------------------------------------------------------------------


def test_d2_distinct_combinators_and_separators(client):
    ent = _entity(client, "Contact")
    src_a = _field(client, ent, "given_name")
    src_b = _field(client, ent, "family_name")
    dst = _field(client, ent, "display_name", baseline=False)
    _create(client, level="entity", disposition="keep",
            source=ent, targets=[ent])
    a = _create(
        client, level="field", disposition="transform",
        source=src_a, targets=[dst],
        migration_mapping_transform_rules=[_merge(1, group="display")],
    )["migration_mapping_identifier"]
    b = _create(
        client, level="field", disposition="transform",
        source=src_b, targets=[dst],
        migration_mapping_transform_rules=[
            _merge(2, group="display", combinator="coalesce")
        ],
    )["migration_mapping_identifier"]
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report["ready"] is False
    # Same target, distinct merge_order: only the combinator/separator
    # incoherences fire, in the spec's closed-vocabulary order.
    assert report["incoherent_merge_groups"] == [
        {
            "merge_group": "display",
            "mappings": sorted([a, b]),
            "problems": ["distinct_combinators", "distinct_separators"],
        }
    ]


def test_d3_target_parent_outside_entity_mapping_targets(client):
    ent_src = _entity(client, "Contact")
    ent_other = _entity(client, "Organization", baseline=False)
    src = _field(client, ent_src, "org_note")
    dst = _field(client, ent_other, "note", baseline=False)
    _create(client, level="entity", disposition="keep",
            source=ent_src, targets=[ent_src])
    mapping = _create(
        client, level="field", disposition="transform",
        source=src, targets=[dst],
    )["migration_mapping_identifier"]
    report = client.get("/migration-mappings/compile-preflight").json()["data"]
    assert report["ready"] is False
    [problem] = report["fields_without_entity_context"]
    assert problem["mapping"] == mapping
    assert problem["source_field"] == src
    assert problem["source_entity"] == ent_src
    assert dst in problem["problem"]
    assert ent_other in problem["problem"]


# ---------------------------------------------------------------------------
# E10 / J — recovery after a blocked restore
# ---------------------------------------------------------------------------


def test_j3_restore_succeeds_after_blocked_target_is_restored(client):
    ent = _entity(client, "Contact")
    src = _field(client, ent, "old")
    dst = _field(client, ent, "new", baseline=False)
    mapping = _create(
        client, level="field", disposition="transform",
        source=src, targets=[dst],
    )["migration_mapping_identifier"]
    client.delete(f"/migration-mappings/{mapping}")
    client.delete(f"/fields/{dst}")
    blocked = client.post(f"/migration-mappings/{mapping}/restore")
    error = _err(blocked, "restore_blocked")
    assert error["field"] == f"migrates_to[{dst}]"
    client.post(f"/fields/{dst}/restore")
    response = client.post(f"/migration-mappings/{mapping}/restore")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["migration_mapping_deleted_at"] is None


# ---------------------------------------------------------------------------
# K1 / K2 — cross-cutting
# ---------------------------------------------------------------------------


def test_k1_change_log_rows_at_the_wire(client):
    """Change-log rows for create / update / delete / restore through the
    API. Cohort convention (observed, matching field.py): soft-delete and
    restore stamp a column, so their emits carry operation='update' — the
    spec's K1 wording names the four *endpoint* actions, all of which emit.
    The migrated-DB CHECK arm of K1 is covered by the WTK-106 migration
    test (test_0048_migration_mapping_entity)."""
    ent = _entity(client, "Contact")
    mapping = _create(client, level="entity", disposition="keep",
                      source=ent, targets=[ent])
    identifier = mapping["migration_mapping_identifier"]
    client.patch(
        f"/migration-mappings/{identifier}",
        json={"migration_mapping_notes": "annotated"},
    )
    client.delete(f"/migration-mappings/{identifier}")
    client.post(f"/migration-mappings/{identifier}/restore")
    with session_scope() as s:
        operations = [
            row.operation
            for row in s.scalars(
                select(ChangeLog)
                .where(
                    ChangeLog.entity_type == "migration_mapping",
                    ChangeLog.entity_identifier == identifier,
                )
                .order_by(ChangeLog.id)
            )
        ]
    assert operations == ["insert", "update", "update", "update"]


def test_k2_static_routes_resolve_before_identifier_capture(client):
    for path in (
        "/migration-mappings/next-identifier",
        "/migration-mappings/triage-completeness",
        "/migration-mappings/compile-preflight",
    ):
        assert client.get(path).status_code == 200, path
    # The dynamic route still resolves real identifiers (404 envelope for
    # an unknown one, not a routing miss).
    response = client.get("/migration-mappings/MIG-042")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


# ---------------------------------------------------------------------------
# K3 — the CBM-scale triage-order batch
# ---------------------------------------------------------------------------


def test_k3_cbm_scale_triage_batch_drives_both_gates_green(client):
    """Twenty mappings, both levels, all four rule kinds, authored in the
    order a live triage session produces them — dispositions and mappings
    interleaved, gates consulted mid-session — ending complete:true and
    ready:true with no write ever blocked by engagement incompleteness."""
    decision = _decision(client)

    def completeness():
        return client.get(
            "/migration-mappings/triage-completeness"
        ).json()["data"]

    def preflight():
        return client.get(
            "/migration-mappings/compile-preflight"
        ).json()["data"]

    # --- Audit deposit: the baseline candidate inventory.
    # Sources triage will reject start at ``candidate`` — the one-way
    # status gate admits ``rejected`` from ``candidate``/``deferred``
    # only, mirroring how a live session disposes them.
    contact = _entity(client, "Contact")
    org = _entity(client, "Organization")
    workshop = _entity(client, "Workshop", status="candidate")
    event = _entity(client, "Event", baseline=False)  # interview-born

    c_keeps = [
        _field(client, contact, name)
        for name in (
            "email", "notes", "referral", "address1", "address2", "zip",
            "county",
        )
    ]
    c_phone_raw = _field(client, contact, "phone_raw", status="candidate")
    c_phone = _field(client, contact, "phone", baseline=False)
    c_type = _field(client, contact, "contact_type", status="candidate")
    c_stage = _field(client, contact, "mentor_stage", baseline=False)
    c_first = _field(client, contact, "first_name", status="candidate")
    c_last = _field(client, contact, "last_name", status="candidate")
    c_full = _field(client, contact, "full_name", baseline=False)
    c_city_state = _field(client, contact, "city_state", status="candidate")
    c_city = _field(client, contact, "city", baseline=False)
    c_state = _field(client, contact, "state", baseline=False)
    o_keeps = [_field(client, org, name) for name in ("org_name", "org_phone")]
    w_title = _field(client, workshop, "w_title")
    e_title = _field(client, event, "e_title", baseline=False)
    w_date = _field(client, workshop, "w_date")
    e_date = _field(client, event, "e_date", baseline=False)
    w_notes = _field(client, workshop, "w_notes")
    e_notes = _field(client, event, "e_notes", baseline=False)
    # A drop and an undisposed candidate: never obligations, never block.
    c_fax = _field(client, contact, "legacy_fax", status="candidate")
    _reject(client, "field", c_fax, decision)
    _field(client, contact, "tmp_flag", status="candidate")

    # --- Mid-session gate read: everything confirmed-baseline is an open
    # keep obligation; nothing is mapped yet.
    report = completeness()
    assert report["complete"] is False
    assert report["counts"]["mapped"] == 0
    assert len(report["unmapped"]) == (
        report["counts"]["keep_unmapped"]
        + report["counts"]["transform_unmapped"]
    )

    # --- Entity triage: Workshop is rejected in favor of Event (a
    # transform disposition), Contact and Organization are keeps. A
    # Workshop field mapping recorded BEFORE the entity-level context
    # exists must not be blocked (the I8 any-order posture) — it simply
    # surfaces in compile-preflight until the entity mapping lands.
    _reject(client, "entity", workshop, decision)
    _supersede(client, "entity", event, workshop)
    _create(client, level="field", disposition="transform",
            source=w_title, targets=[e_title])
    assert preflight()["ready"] is False  # no entity context yet — a read,
    # never a write refusal.
    _create(client, level="entity", disposition="keep",
            source=contact, targets=[contact])
    _create(client, level="entity", disposition="keep",
            source=org, targets=[org])
    _create(client, level="entity", disposition="transform",
            source=workshop, targets=[event])
    assert preflight()["ready"] is True

    # --- Field triage, Contact: seven keeps, then the four transform
    # kinds with their sources rejected+superseded as triage decides.
    for fld in c_keeps:
        _create(client, level="field", disposition="keep",
                source=fld, targets=[fld])
    _reject(client, "field", c_phone_raw, decision)
    _supersede(client, "field", c_phone, c_phone_raw)
    _create(
        client, level="field", disposition="transform",
        source=c_phone_raw, targets=[c_phone],
        migration_mapping_transform_rules=[
            {"rule_kind": "type_change", "from_type": "text",
             "to_type": "long_text"}
        ],
    )
    _reject(client, "field", c_type, decision)
    _supersede(client, "field", c_stage, c_type)
    _create(
        client, level="field", disposition="transform",
        source=c_type, targets=[c_stage],
        migration_mapping_transform_rules=[_ENUM],
    )
    _reject(client, "field", c_first, decision)
    _reject(client, "field", c_last, decision)
    _supersede(client, "field", c_full, c_first)
    _supersede(client, "field", c_full, c_last)
    _create(
        client, level="field", disposition="transform",
        source=c_first, targets=[c_full],
        migration_mapping_transform_rules=[_merge(1)],
    )
    _create(
        client, level="field", disposition="transform",
        source=c_last, targets=[c_full],
        migration_mapping_transform_rules=[_merge(2)],
    )
    _reject(client, "field", c_city_state, decision)
    _supersede(client, "field", c_city, c_city_state)
    _create(
        client, level="field", disposition="transform",
        source=c_city_state, targets=[c_city, c_state],
        migration_mapping_transform_rules=[_split([c_city, c_state])],
    )

    # --- Mid-session: Organization and the remaining Workshop fields are
    # still open; the session keeps writing without any gate blocking.
    assert completeness()["complete"] is False
    for fld in o_keeps:
        _create(client, level="field", disposition="keep",
                source=fld, targets=[fld])
    _create(client, level="field", disposition="transform",
            source=w_date, targets=[e_date],
            migration_mapping_transform_rules=[
                {"rule_kind": "type_change", "from_type": "date",
                 "to_type": "datetime"}
            ])
    _create(client, level="field", disposition="transform",
            source=w_notes, targets=[e_notes])

    # --- Phase 3 close: both gates green, twenty mappings recorded.
    report = completeness()
    assert report == {
        "complete": True,
        "unmapped": [],
        "counts": {
            "keep_unmapped": 0,
            "transform_unmapped": 0,
            "mapped": 20,
        },
    }
    assert preflight() == {
        "ready": True,
        "incoherent_merge_groups": [],
        "fields_without_entity_context": [],
    }
    listing = client.get("/migration-mappings").json()["data"]
    assert len(listing) == 20
    kinds = {
        rule["rule_kind"]
        for record in listing
        for rule in record["migration_mapping_transform_rules"] or []
    }
    assert kinds == {"type_change", "enum_value_map", "merge", "split"}
    assert {r["migration_mapping_level"] for r in listing} == {
        "entity", "field",
    }
