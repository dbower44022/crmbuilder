"""WTK-108 verification suite — migration-mapping storage vs the WTK-104 spec.

Verifies the implemented storage layer (WTK-106 schema + WTK-107 repository)
against ``methodology-schema-specs/migration_mapping.md``, driving the
repository functions directly — the surface the future compiler and the MCP
tools use, below the HTTP envelope the WTK-107 API tests already cover.
Organized by the spec's §5.2 invariants:

* I1/I2 — atomic create of row + both mandatory edges, no orphans on failure
* I3 — one live mapping per disposed candidate, freed by delete/reject,
  re-checked on restore
* I4/I5 — edge targets live, baseline/confirmed, and level-typed
* I6/I7/I8 — split / keep / transform shape couplings
* I9 — transform-rule well-formedness for all four kinds (§4), positive
  byte-identical round-trips and parametrized negatives
* I10 + Q1/Q5/Q6 — the derived gates on the §7 criterion-13 seeded fixture,
  including convergence to zero rows (criterion 16)
* I11 — attribute-per-level agreement at the repository layer
* I12 — soft-delete/restore edge atomicity; non-data capture types
  unrepresentable at the stored-CHECK level
* §6 — the compile contract: a confirmed mapping set mechanically supplies
  the ``ImportManager`` inputs and the stored rules suffice to transform a
  source record (Master PRD v0.2 §8)

Fixture vocabulary matches the WTK-107 API tests: a *baseline* candidate
carries audit-deposit provenance (an inbound ``deposit_event_wrote_record``
edge); a transform source is a rejected baseline candidate superseded by a
new record (``supersedes`` at field level, ``entity_variant_of_entity`` at
entity level).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    DuplicateMappingForCandidateError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import ChangeLog, MigrationMapping, Reference
from crmbuilder_v2.access.repositories import (
    decisions,
    entity,
    field,
    references,
)
from crmbuilder_v2.access.repositories import (
    migration_mapping as mm,
)
from sqlalchemy import select

_LABEL = "espocrm @ crm.test"
_FROM = "migration_mapping_migrates_from_record"
_TO = "migration_mapping_migrates_to_record"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _decision(s) -> str:
    return decisions.create(
        s,
        title="Triage rejection rationale",
        decision_date="06-12-26",
        status="Active",
        executive_summary=(
            "Records the rationale for rejecting a triage candidate "
            "during the migration-mapping verification fixture build. " * 3
        ),
    )["identifier"]


def _entity(s, name, *, status="confirmed", baseline=True) -> str:
    identifier = entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]
    if baseline:
        references.create(
            s,
            source_type="deposit_event",
            source_id="DEP-001",
            target_type="entity",
            target_id=identifier,
            relationship="deposit_event_wrote_record",
        )
    if status != "candidate":
        entity.patch_entity(s, identifier, status=status)
    return identifier


def _field(s, entity_identifier, name, *, status="confirmed", baseline=True) -> str:
    identifier = field.create_field(
        s,
        field_belongs_to_entity_identifier=entity_identifier,
        name=name,
        description="seed",
        type="text",
    )["field_identifier"]
    if baseline:
        references.create(
            s,
            source_type="deposit_event",
            source_id="DEP-001",
            target_type="field",
            target_id=identifier,
            relationship="deposit_event_wrote_record",
        )
    if status != "candidate":
        field.patch_field(s, identifier, status=status)
    return identifier


def _reject(s, entity_type, identifier, decision) -> None:
    """Edge-first WTK-088 admission, then the status flip."""
    references.create(
        s,
        source_type=entity_type,
        source_id=identifier,
        target_type="decision",
        target_id=decision,
        relationship="rejected_by_decision",
    )
    if entity_type == "entity":
        entity.patch_entity(s, identifier, status="rejected")
    else:
        field.patch_field(s, identifier, status="rejected")


def _supersede(s, entity_type, new_identifier, old_identifier) -> None:
    kind = (
        "entity_variant_of_entity" if entity_type == "entity" else "supersedes"
    )
    references.create(
        s,
        source_type=entity_type,
        source_id=new_identifier,
        target_type=entity_type,
        target_id=old_identifier,
        relationship=kind,
    )


def _mapping(s, *, level, disposition, source, targets, **overrides) -> dict:
    kwargs = {
        "level": level,
        "disposition": disposition,
        "source_system_label": _LABEL,
        "source_entity_name": "Contact",
        "migrates_from_identifier": source,
        "migrates_to_identifiers": targets,
        "status": "confirmed",
    }
    if level == "field":
        kwargs["source_attribute_name"] = "cAttr"
    kwargs.update(overrides)
    return mm.create_migration_mapping(s, **kwargs)


def _transform_pair(s) -> tuple[str, str, str]:
    """One baseline confirmed source field and one confirmed target field."""
    ent = _entity(s, "Contact")
    old = _field(s, ent, "old_attr")
    new = _field(s, ent, "new_attr", baseline=False)
    return ent, old, new


def _merge_rule(order, *, group="contact-full-name", separator=" "):
    return {
        "rule_kind": "merge",
        "merge_group": group,
        "combinator": "concat",
        "separator": separator,
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
    "value_map": {"Mentor Candidate": "candidate", "Active Mentor": "active"},
    "unmapped_policy": "error",
}


def _mapping_count(s) -> int:
    return len(
        s.scalars(
            select(MigrationMapping.migration_mapping_identifier)
        ).all()
    )


def _edges_of(s, mapping_identifier) -> set[tuple[str, str]]:
    rows = s.scalars(
        select(Reference).where(
            Reference.source_type == "migration_mapping",
            Reference.source_id == mapping_identifier,
        )
    ).all()
    return {(row.relationship_kind, row.target_id) for row in rows}


# ---------------------------------------------------------------------------
# I1 / I2 — atomic create: row + exactly one from-edge + >= 1 to-edge
# ---------------------------------------------------------------------------


def test_i1_i2_create_writes_row_and_both_edges_atomically(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        record = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )
        mig = record["migration_mapping_identifier"]
    with session_scope() as s:
        assert _edges_of(s, mig) == {(_FROM, old), (_TO, new)}
        links = mm.get_migration_mapping(s, mig)["migration_mapping_links"]
        assert links["migrates_from"]["identifier"] == old
        assert links["migrates_from"]["entity_type"] == "field"
        assert [t["identifier"] for t in links["migrates_to"]] == [new]


def test_i1_create_without_source_refused_no_orphan(v2_env):
    with session_scope() as s:
        _ent, _old, new = _transform_pair(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s, level="field", disposition="transform", source=None, targets=[new]
        )
    assert any(e.code == "missing_source_candidate" for e in exc.value.errors)
    with session_scope() as s:
        assert _mapping_count(s) == 0


def test_i2_create_without_targets_refused_no_orphan(v2_env):
    with session_scope() as s:
        _ent, old, _new = _transform_pair(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s, level="field", disposition="transform", source=old, targets=[]
        )
    assert any(e.code == "missing_target_record" for e in exc.value.errors)
    with session_scope() as s:
        assert _mapping_count(s) == 0
        assert not s.scalars(
            select(Reference).where(
                Reference.source_type == "migration_mapping"
            )
        ).all()


def test_post_insert_edge_failure_rolls_back_the_row(v2_env):
    """A failure *after* the row insert (edge creation) leaves no orphan —
    the spec §7 criterion-4 mid-transaction posture. Forced by pre-creating
    the exact from-edge the create would write, so ``references.create``
    raises on the duplicate tuple."""
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        nxt = mm.next_migration_mapping_identifier(s)
        references.create(
            s,
            source_type="migration_mapping",
            source_id=nxt,
            target_type="field",
            target_id=old,
            relationship=_FROM,
        )
    with pytest.raises(ConflictError):
        with session_scope() as s:
            _mapping(
                s,
                level="field",
                disposition="transform",
                source=old,
                targets=[new],
                identifier=nxt,
            )
    with session_scope() as s:
        assert mm.get_migration_mapping(s, nxt, include_deleted=True) is None


# ---------------------------------------------------------------------------
# I3 — one mapping per disposition (source-side uniqueness)
# ---------------------------------------------------------------------------


def test_i3_second_live_mapping_for_candidate_refused(v2_env):
    with session_scope() as s:
        ent, old, new = _transform_pair(s)
        first = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
        other = _field(s, ent, "other_target", baseline=False)
    with session_scope() as s, pytest.raises(
        DuplicateMappingForCandidateError
    ) as exc:
        _mapping(
            s, level="field", disposition="transform", source=old, targets=[other]
        )
    assert exc.value.candidate_identifier == old
    assert exc.value.existing_mapping == first


def test_i3_soft_delete_frees_the_candidate(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        first = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
        mm.delete_migration_mapping(s, first)
        second = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )
    assert second["migration_mapping_identifier"] != first


def test_i3_rejection_frees_the_candidate(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        dec = _decision(s)
        first = _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new],
            status="candidate",
        )["migration_mapping_identifier"]
        mm.patch_migration_mapping(
            s, first, status="rejected", rejected_by_decision=dec
        )
        second = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )
    assert second["migration_mapping_identifier"] != first


def test_i3_restore_recheck_refuses_a_remapped_candidate(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        first = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
        mm.delete_migration_mapping(s, first)
        second = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
    with session_scope() as s, pytest.raises(
        DuplicateMappingForCandidateError
    ) as exc:
        mm.restore_migration_mapping(s, first)
    assert exc.value.existing_mapping == second


# ---------------------------------------------------------------------------
# I4 / I5 — edge-target liveness, baseline provenance, status, and level
# ---------------------------------------------------------------------------


def test_i4_source_must_exist_and_be_live_baseline(v2_env):
    with session_scope() as s:
        ent, _old, new = _transform_pair(s)
        interview_born = _field(s, ent, "interview_born", baseline=False)
        deleted = _field(s, ent, "deleted_source")
        field.delete_field(s, deleted)
    for source in ("FLD-999", interview_born, deleted):
        with session_scope() as s, pytest.raises(UnprocessableError) as exc:
            _mapping(
                s,
                level="field",
                disposition="transform",
                source=source,
                targets=[new],
            )
        assert any(
            e.code == "invalid_source_candidate" for e in exc.value.errors
        ), source


def test_i4_target_must_be_live_and_confirmed(v2_env):
    with session_scope() as s:
        ent, old, _new = _transform_pair(s)
        unconfirmed = _field(s, ent, "unconfirmed", status="candidate", baseline=False)
        deleted = _field(s, ent, "deleted_target", baseline=False)
        field.delete_field(s, deleted)
    for target in ("FLD-999", unconfirmed, deleted):
        with session_scope() as s, pytest.raises(UnprocessableError) as exc:
            _mapping(
                s,
                level="field",
                disposition="transform",
                source=old,
                targets=[target],
            )
        assert any(
            e.code == "invalid_target_record" for e in exc.value.errors
        ), target


def test_i5_edge_targets_must_match_the_level(v2_env):
    with session_scope() as s:
        ent, old, new = _transform_pair(s)
    # Field-level mapping naming the entity as source — level mismatch.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s, level="field", disposition="transform", source=ent, targets=[new]
        )
    assert any(
        e.code == "invalid_source_candidate" and "level mismatch" in e.message
        for e in exc.value.errors
    )
    # Entity-level mapping naming a field as target.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s, level="entity", disposition="transform", source=ent, targets=[old]
        )
    assert any(e.code == "invalid_target_record" for e in exc.value.errors)


# ---------------------------------------------------------------------------
# I6 / I7 / I8 — split, keep, and transform shape couplings
# ---------------------------------------------------------------------------


def test_i7_keep_shape_violations_refused(v2_env):
    with session_scope() as s:
        ent, old, new = _transform_pair(s)
        extra = _field(s, ent, "extra", baseline=False)
    cases = [
        {"source": old, "targets": [new]},  # source != target
        {"source": old, "targets": [old, extra]},  # two targets
        {
            "source": old,
            "targets": [old],
            "transform_rules": [_ENUM_RULE],
        },  # rules on a keep
    ]
    for case in cases:
        with session_scope() as s, pytest.raises(UnprocessableError) as exc:
            _mapping(s, level="field", disposition="keep", **case)
        assert any(e.code == "invalid_keep_shape" for e in exc.value.errors)


def test_i7_valid_keep_round_trips(v2_env):
    with session_scope() as s:
        ent = _entity(s, "Contact")
        record = _mapping(
            s, level="entity", disposition="keep", source=ent, targets=[ent]
        )
        mig = record["migration_mapping_identifier"]
    with session_scope() as s:
        stored = mm.get_migration_mapping(s, mig)
        assert stored["migration_mapping_disposition"] == "keep"
        assert stored["migration_mapping_transform_rules"] is None
        links = stored["migration_mapping_links"]
        assert links["migrates_from"]["identifier"] == ent
        assert [t["identifier"] for t in links["migrates_to"]] == [ent]


def test_i8_transform_source_must_not_be_a_target(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new, old],
            transform_rules=[_split_rule([new, old])],
        )
    assert any(e.code == "invalid_transform_shape" for e in exc.value.errors)


def test_i8_mapping_recordable_before_disposition_finalizes(v2_env):
    """The state half of I8 is deferred to the gates: a transform mapping
    may be recorded while its source candidate is still ``confirmed``
    (mappings and dispositions land in either order within a session)."""
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        record = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )
    assert record["migration_mapping_identifier"]


def test_i6_multiple_targets_require_a_covering_split_rule(v2_env):
    with session_scope() as s:
        ent, old, _new = _transform_pair(s)
        city = _field(s, ent, "city", baseline=False)
        state = _field(s, ent, "state", baseline=False)
    # Two targets, no split rule.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[city, state],
        )
    assert any(e.code == "split_rule_required" for e in exc.value.errors)
    # Split rule whose assignment set does not equal the edge-target set.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[city, state],
            transform_rules=[_split_rule([city, "FLD-999"])],
        )
    assert any(e.code == "invalid_transform_rule" for e in exc.value.errors)
    # The biconditional's other arm: a split rule with a single target.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[city],
            transform_rules=[_split_rule([city])],
        )
    assert any(e.code == "invalid_transform_rule" for e in exc.value.errors)


def test_i6_valid_split_round_trips(v2_env):
    with session_scope() as s:
        ent, old, _new = _transform_pair(s)
        city = _field(s, ent, "city", baseline=False)
        state = _field(s, ent, "state", baseline=False)
        rule = _split_rule([city, state])
        record = _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[city, state],
            transform_rules=[rule],
        )
        mig = record["migration_mapping_identifier"]
    with session_scope() as s:
        stored = mm.get_migration_mapping(s, mig)
        assert stored["migration_mapping_transform_rules"] == [rule]
        targets = [
            t["identifier"]
            for t in stored["migration_mapping_links"]["migrates_to"]
        ]
        assert targets == sorted([city, state])


# ---------------------------------------------------------------------------
# I9 — transform-rule well-formedness (§4): negatives across all four kinds
# ---------------------------------------------------------------------------

_BAD_RULES = [
    # --- list shape
    ("field", {"rule_kind": "enum_value_map"}),  # not a list
    ("field", ["not-an-object"]),
    ("field", [{"rule_kind": "bogus_kind"}]),
    # --- required / unknown keys
    ("field", [{"rule_kind": "type_change"}]),  # missing from/to
    (
        "field",
        [
            {
                "rule_kind": "type_change",
                "from_type": "text",
                "to_type": "date",
                "surprise": 1,
            }
        ],
    ),
    # --- level applicability (§4.6)
    ("entity", [{"rule_kind": "type_change", "from_type": "text", "to_type": "date"}]),
    ("entity", [_ENUM_RULE]),
    # --- type_change couplings (§4.2)
    ("field", [{"rule_kind": "type_change", "from_type": "text", "to_type": "text"}]),
    ("field", [{"rule_kind": "type_change", "from_type": "varchar", "to_type": "date"}]),
    (
        "field",
        [
            {
                "rule_kind": "type_change",
                "from_type": "text",
                "to_type": "date",
                "conversion": {"strategy": "cast", "format": "%Y-%m-%d"},
            }
        ],
    ),  # format only with parse
    (
        "field",
        [
            {
                "rule_kind": "type_change",
                "from_type": "text",
                "to_type": "date",
                "conversion": {"strategy": "custom"},
            }
        ],
    ),  # custom requires description
    (
        "field",
        [
            {
                "rule_kind": "type_change",
                "from_type": "text",
                "to_type": "date",
                "conversion": {"strategy": "cast", "on_error": "explode"},
            }
        ],
    ),
    # --- enum_value_map couplings (§4.3)
    ("field", [{"rule_kind": "enum_value_map", "value_map": {}, "unmapped_policy": "error"}]),
    (
        "field",
        [
            {
                "rule_kind": "enum_value_map",
                "value_map": {"a": 1},
                "unmapped_policy": "error",
            }
        ],
    ),
    (
        "field",
        [
            {
                "rule_kind": "enum_value_map",
                "value_map": {"a": "b"},
                "unmapped_policy": "coerce",
            }
        ],
    ),
    (
        "field",
        [
            {
                "rule_kind": "enum_value_map",
                "value_map": {"a": "b"},
                "unmapped_policy": "default",
            }
        ],
    ),  # default policy without default_value
    (
        "field",
        [
            {
                "rule_kind": "enum_value_map",
                "value_map": {"a": "b"},
                "unmapped_policy": "error",
                "default_value": "x",
            }
        ],
    ),  # default_value without default policy
    # --- merge couplings (§4.4)
    ("field", [_merge_rule(1, group="  ")]),
    (
        "field",
        [
            {
                "rule_kind": "merge",
                "merge_group": "g",
                "combinator": "average",
                "merge_order": 1,
            }
        ],
    ),
    ("entity", [_merge_rule(1)]),  # entity-level merge admits only coalesce
    ("field", [_merge_rule(0)]),  # merge_order >= 1
    ("field", [_merge_rule(True)]),  # bool is not an integer order
    (
        "field",
        [
            {
                "rule_kind": "merge",
                "merge_group": "g",
                "combinator": "concat",
                "merge_order": 1,
            }
        ],
    ),  # concat requires separator
    (
        "field",
        [
            {
                "rule_kind": "merge",
                "merge_group": "g",
                "combinator": "coalesce",
                "merge_order": 1,
                "separator": " ",
            }
        ],
    ),  # separator only with concat
    # --- split couplings (§4.5)
    ("field", [{"rule_kind": "split", "assignments": []}]),
    ("field", [{"rule_kind": "split", "assignments": [{"extractor": {"strategy": "pattern", "pattern": "x"}}]}]),
    ("field", [{"rule_kind": "split", "assignments": [{"target": "FLD-001"}]}]),
    (
        "field",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {"target": "FLD-001", "extractor": {"strategy": "regex"}}
                ],
            }
        ],
    ),
    (
        "field",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {"target": "FLD-001", "extractor": {"strategy": "delimiter", "delimiter": ","}}
                ],
            }
        ],
    ),  # delimiter requires index
    (
        "field",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {"target": "FLD-001", "extractor": {"strategy": "pattern"}}
                ],
            }
        ],
    ),
    (
        "field",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {"target": "FLD-001", "extractor": {"strategy": "custom"}}
                ],
            }
        ],
    ),
    (
        "field",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {
                        "target": "FLD-001",
                        "extractor": {
                            "strategy": "delimiter",
                            "delimiter": ",",
                            "index": 0,
                        },
                    }
                ],
                "unrouted_policy": "error",
            }
        ],
    ),  # unrouted_policy is entity-level only
    (
        "entity",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {
                        "target": "ENT-001",
                        "extractor": {
                            "strategy": "delimiter",
                            "delimiter": ",",
                            "index": 0,
                        },
                    }
                ],
                "unrouted_policy": "error",
            }
        ],
    ),  # entity-level split requires value_router
    (
        "entity",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {
                        "target": "ENT-001",
                        "extractor": {
                            "strategy": "value_router",
                            "router_attribute": "cType",
                            "router_values": ["Mentor"],
                        },
                    }
                ],
            }
        ],
    ),  # entity-level split requires unrouted_policy
    (
        "entity",
        [
            {
                "rule_kind": "split",
                "assignments": [
                    {
                        "target": "ENT-001",
                        "extractor": {"strategy": "value_router"},
                    }
                ],
                "unrouted_policy": "error",
            }
        ],
    ),  # value_router requires router_attribute + router_values
]


@pytest.mark.parametrize("level,rules", _BAD_RULES)
def test_i9_malformed_rules_refused(level, rules):
    with pytest.raises(UnprocessableError) as exc:
        mm.validate_transform_rules(rules, level)
    assert any(e.code == "invalid_transform_rule" for e in exc.value.errors)


def test_i9_error_names_the_offending_rule_index():
    rules = [_ENUM_RULE, {"rule_kind": "bogus_kind"}]
    with pytest.raises(UnprocessableError) as exc:
        mm.validate_transform_rules(rules, "field")
    assert exc.value.errors[0].field == "migration_mapping_transform_rules[1]"


def test_i9_empty_and_null_rule_lists_normalize_to_none():
    assert mm.validate_transform_rules(None, "field") is None
    assert mm.validate_transform_rules([], "field") is None


def test_criterion_9_all_four_kinds_round_trip_byte_identically(v2_env):
    """A valid example of each rule kind survives create → get unchanged,
    including ordered multi-rule lists (map values first, then convert)."""
    type_change = {
        "rule_kind": "type_change",
        "from_type": "text",
        "to_type": "date",
        "conversion": {
            "strategy": "parse",
            "format": "%m-%d-%y",
            "on_error": "error",
        },
    }
    enum_with_default = {
        "rule_kind": "enum_value_map",
        "value_map": {"Mentor Candidate": "candidate"},
        "unmapped_policy": "default",
        "default_value": "unknown",
    }
    with session_scope() as s:
        ent, old, new = _transform_pair(s)
        ordered = _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new],
            transform_rules=[enum_with_default, type_change],
        )["migration_mapping_identifier"]
        first = _field(s, ent, "first_raw")
        full = _field(s, ent, "full_name", baseline=False)
        merge = _mapping(
            s,
            level="field",
            disposition="transform",
            source=first,
            targets=[full],
            transform_rules=[_merge_rule(1)],
        )["migration_mapping_identifier"]
        combined = _field(s, ent, "city_state")
        city = _field(s, ent, "city", baseline=False)
        state = _field(s, ent, "state", baseline=False)
        split = _mapping(
            s,
            level="field",
            disposition="transform",
            source=combined,
            targets=[city, state],
            transform_rules=[_split_rule([city, state])],
        )["migration_mapping_identifier"]
    with session_scope() as s:
        assert mm.get_migration_mapping(s, ordered)[
            "migration_mapping_transform_rules"
        ] == [enum_with_default, type_change]
        assert mm.get_migration_mapping(s, merge)[
            "migration_mapping_transform_rules"
        ] == [_merge_rule(1)]
        assert mm.get_migration_mapping(s, split)[
            "migration_mapping_transform_rules"
        ] == [_split_rule([city, state])]


def test_entity_level_split_with_value_router_round_trips(v2_env):
    with session_scope() as s:
        src = _entity(s, "Contact")
        mentor = _entity(s, "Mentor", baseline=False)
        client = _entity(s, "Client", baseline=False)
        rule = {
            "rule_kind": "split",
            "assignments": [
                {
                    "target": mentor,
                    "extractor": {
                        "strategy": "value_router",
                        "router_attribute": "cContactType",
                        "router_values": ["Mentor", "Mentor Candidate"],
                    },
                },
                {
                    "target": client,
                    "extractor": {
                        "strategy": "value_router",
                        "router_attribute": "cContactType",
                        "router_values": ["Client"],
                    },
                },
            ],
            "unrouted_policy": "error",
        }
        record = _mapping(
            s,
            level="entity",
            disposition="transform",
            source=src,
            targets=[mentor, client],
            transform_rules=[rule],
        )
        mig = record["migration_mapping_identifier"]
    with session_scope() as s:
        assert mm.get_migration_mapping(s, mig)[
            "migration_mapping_transform_rules"
        ] == [rule]


# ---------------------------------------------------------------------------
# I11 — attribute-per-level agreement at the repository layer
# ---------------------------------------------------------------------------


def test_i11_repository_enforces_attribute_per_level(v2_env):
    with session_scope() as s:
        ent, old, new = _transform_pair(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new],
            source_attribute_name=None,
        )
    assert any(
        e.code == "attribute_name_level_mismatch" for e in exc.value.errors
    )
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="entity",
            disposition="keep",
            source=ent,
            targets=[ent],
            source_attribute_name="cAttr",
        )
    assert any(
        e.code == "attribute_name_level_mismatch" for e in exc.value.errors
    )


def test_i11_patch_recheck(v2_env):
    with session_scope() as s:
        ent = _entity(s, "Contact")
        mig = _mapping(
            s, level="entity", disposition="keep", source=ent, targets=[ent]
        )["migration_mapping_identifier"]
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        mm.patch_migration_mapping(s, mig, source_attribute_name="cAttr")
    assert any(
        e.code == "attribute_name_level_mismatch" for e in exc.value.errors
    )


# ---------------------------------------------------------------------------
# Lifecycle (spec §3.4 / criterion 10)
# ---------------------------------------------------------------------------


def test_lifecycle_rejected_is_not_a_starter(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new],
            status="rejected",
        )
    assert any(e.code == "invalid_status" for e in exc.value.errors)


def test_lifecycle_one_way_gate_and_wave_rescoping(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        mig = _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new],
            status="candidate",
        )["migration_mapping_identifier"]
        mm.patch_migration_mapping(s, mig, status="confirmed")
        # confirmed <-> deferred supports migration-wave re-scoping.
        mm.patch_migration_mapping(s, mig, status="deferred")
        mm.patch_migration_mapping(s, mig, status="confirmed")
    # No status lists `candidate` as a successor.
    with session_scope() as s, pytest.raises(StatusTransitionError):
        mm.patch_migration_mapping(s, mig, status="candidate")
    # confirmed -> rejected is not an arc (mirrors `domain`).
    with session_scope() as s, pytest.raises(StatusTransitionError):
        mm.patch_migration_mapping(s, mig, status="rejected")


def test_lifecycle_rejected_requires_decision_and_is_terminal(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        dec = _decision(s)
        mig = _mapping(
            s,
            level="field",
            disposition="transform",
            source=old,
            targets=[new],
            status="candidate",
        )["migration_mapping_identifier"]
    # Without the atomic key or a pre-existing edge the flip is refused.
    with session_scope() as s, pytest.raises(UnprocessableError):
        mm.patch_migration_mapping(s, mig, status="rejected")
    with session_scope() as s:
        mm.patch_migration_mapping(
            s, mig, status="rejected", rejected_by_decision=dec
        )
        edge = s.scalar(
            select(Reference).where(
                Reference.source_type == "migration_mapping",
                Reference.source_id == mig,
                Reference.relationship_kind == "rejected_by_decision",
            )
        )
        assert edge is not None and edge.target_id == dec
    with session_scope() as s, pytest.raises(StatusTransitionError):
        mm.patch_migration_mapping(s, mig, status="confirmed")


# ---------------------------------------------------------------------------
# I12 — soft-delete/restore atomicity; unrepresentable capture types
# ---------------------------------------------------------------------------


def test_i12_delete_restore_round_trips_row_and_edges(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        mig = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
        mm.delete_migration_mapping(s, mig)
        # Idempotent delete.
        mm.delete_migration_mapping(s, mig)
    with session_scope() as s:
        assert mm.get_migration_mapping(s, mig) is None
        deleted = mm.get_migration_mapping(s, mig, include_deleted=True)
        # The soft-deleted record's links still resolve (edge liveness is
        # derived from the row, the physical edge rows stay in place).
        assert deleted["migration_mapping_links"]["migrates_from"][
            "identifier"
        ] == old
        assert mm.list_migration_mappings(s) == []
        assert len(mm.list_migration_mappings(s, include_deleted=True)) == 1
        mm.restore_migration_mapping(s, mig)
    with session_scope() as s:
        assert mm.get_migration_mapping(s, mig) is not None
        # The restored mapping re-occupies the candidate's I3 slot.
        with pytest.raises(DuplicateMappingForCandidateError):
            _mapping(
                s,
                level="field",
                disposition="transform",
                source=old,
                targets=[new],
            )


def test_i12_restore_blocked_when_edge_target_soft_deleted(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        mig = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
        mm.delete_migration_mapping(s, mig)
        field.delete_field(s, old)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        mm.restore_migration_mapping(s, mig)
    error = exc.value.errors[0]
    assert error.code == "restore_blocked"
    assert error.field == f"migrates_from[{old}]"
    with session_scope() as s:
        field.restore_field(s, old)
        mm.restore_migration_mapping(s, mig)


def test_i12_restore_of_a_live_mapping_refused(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        mig = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        mm.restore_migration_mapping(s, mig)
    assert any(e.code == "not_deleted" for e in exc.value.errors)


def test_i12_non_data_capture_types_unrepresentable(v2_env):
    """Spec I12: persona/process/manual_config mappings are unrepresentable
    through the two stated enforcement layers — the vocab pair rules admit
    the mapping kinds only for (migration_mapping, entity|field) pairs, and
    the repository resolves edge identifiers exclusively as entity or field
    rows, so a non-data identifier never validates as a source."""
    from crmbuilder_v2.access.vocab import _kinds_for_pair

    for target in ("persona", "process", "manual_config"):
        kinds = _kinds_for_pair("migration_mapping", target)
        assert _FROM not in kinds and _TO not in kinds, target
    with session_scope() as s:
        ent = _entity(s, "Contact")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _mapping(
            s,
            level="entity",
            disposition="keep",
            source="PER-001",
            targets=[ent],
        )
    assert any(e.code == "invalid_source_candidate" for e in exc.value.errors)


# ---------------------------------------------------------------------------
# Q1 / Q5 / Q6 — the derived gates on the criterion-13 fixture, with the
# criterion-16 convergence to zero rows
# ---------------------------------------------------------------------------


def _seed_criterion_13(s) -> dict:
    """One keep, one rename-only transform, one enum-map transform, one
    two-source merge, one one-source-two-target split — plus the negative
    rows: one unmapped kept field, one incoherent merge group, and one
    field mapping on an entity with no entity-level mapping (Q6)."""
    ids = {"ent": _entity(s, "Contact")}
    ent = ids["ent"]
    ids["fld_unmapped"] = _field(s, ent, "email")
    ids["fld_old_phone"] = _field(s, ent, "phone_raw")
    ids["fld_new_phone"] = _field(s, ent, "phone", baseline=False)
    ids["fld_old_type"] = _field(s, ent, "contact_type")
    ids["fld_new_stage"] = _field(s, ent, "mentor_stage", baseline=False)
    ids["fld_first"] = _field(s, ent, "first_name_raw")
    ids["fld_last"] = _field(s, ent, "last_name_raw")
    ids["fld_full"] = _field(s, ent, "full_name", baseline=False)
    ids["fld_combined"] = _field(s, ent, "city_state")
    ids["fld_city"] = _field(s, ent, "city", baseline=False)
    ids["fld_state"] = _field(s, ent, "state", baseline=False)

    ids["keep"] = _mapping(
        s, level="entity", disposition="keep", source=ent, targets=[ent]
    )["migration_mapping_identifier"]
    ids["rename"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_old_phone"],
        targets=[ids["fld_new_phone"]],
    )["migration_mapping_identifier"]
    ids["enum"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_old_type"],
        targets=[ids["fld_new_stage"]],
        transform_rules=[_ENUM_RULE],
    )["migration_mapping_identifier"]
    ids["merge_1"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_first"],
        targets=[ids["fld_full"]],
        transform_rules=[_merge_rule(1)],
    )["migration_mapping_identifier"]
    ids["merge_2"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_last"],
        targets=[ids["fld_full"]],
        transform_rules=[_merge_rule(2)],
    )["migration_mapping_identifier"]
    ids["split"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_combined"],
        targets=[ids["fld_city"], ids["fld_state"]],
        transform_rules=[_split_rule([ids["fld_city"], ids["fld_state"]])],
    )["migration_mapping_identifier"]

    # Incoherent merge group: same group, distinct separators (passes
    # per-rule write validation; only the cross-row Q5 gate can see it).
    ids["fld_bad_a"] = _field(s, ent, "bad_a")
    ids["fld_bad_b"] = _field(s, ent, "bad_b")
    ids["fld_bad_target"] = _field(s, ent, "bad_target", baseline=False)
    ids["bad_merge_1"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_bad_a"],
        targets=[ids["fld_bad_target"]],
        transform_rules=[_merge_rule(1, group="bad-group", separator=" ")],
    )["migration_mapping_identifier"]
    ids["bad_merge_2"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_bad_b"],
        targets=[ids["fld_bad_target"]],
        transform_rules=[_merge_rule(2, group="bad-group", separator="-")],
    )["migration_mapping_identifier"]

    # Q6 negative: a field mapping whose entity has no entity-level mapping.
    # The entity is itself a kept-but-unmapped baseline candidate, so it
    # also appears in Q1 until the convergence phase maps it.
    ids["ent2"] = _entity(s, "Orphan")
    ids["fld_orphan_src"] = _field(s, ids["ent2"], "orphan_src")
    ids["fld_orphan_tgt"] = _field(
        s, ids["ent2"], "orphan_tgt", baseline=False
    )
    ids["orphan"] = _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_orphan_src"],
        targets=[ids["fld_orphan_tgt"]],
    )["migration_mapping_identifier"]
    return ids


def test_q1_q5_q6_gates_flag_exactly_the_negative_rows(v2_env):
    with session_scope() as s:
        ids = _seed_criterion_13(s)
    with session_scope() as s:
        completeness = mm.triage_completeness(s)
        assert completeness["complete"] is False
        # Sorted (entity_type, identifier): the unmapped kept entity first,
        # then the unmapped kept field.
        assert [item["identifier"] for item in completeness["unmapped"]] == [
            ids["ent2"],
            ids["fld_unmapped"],
        ]
        assert {item["disposition"] for item in completeness["unmapped"]} == {
            "keep"
        }
        assert completeness["counts"]["keep_unmapped"] == 2
        assert completeness["counts"]["transform_unmapped"] == 0

        preflight = mm.compile_preflight(s)
        assert preflight["ready"] is False
        assert [
            group["merge_group"]
            for group in preflight["incoherent_merge_groups"]
        ] == ["bad-group"]
        assert preflight["incoherent_merge_groups"][0]["problems"] == [
            "distinct_separators"
        ]
        assert sorted(preflight["incoherent_merge_groups"][0]["mappings"]) == sorted(
            [ids["bad_merge_1"], ids["bad_merge_2"]]
        )
        assert [
            row["mapping"]
            for row in preflight["fields_without_entity_context"]
        ] == [ids["orphan"]]
        assert preflight["fields_without_entity_context"][0][
            "source_entity"
        ] == ids["ent2"]


def test_criterion_16_gates_converge_to_zero_rows(v2_env):
    with session_scope() as s:
        ids = _seed_criterion_13(s)
    with session_scope() as s:
        # Map the two unmapped keeps and fix the bad separator — the keep
        # mapping for the orphan entity simultaneously supplies the Q6
        # entity-level context its field mapping was missing.
        _mapping(
            s,
            level="field",
            disposition="keep",
            source=ids["fld_unmapped"],
            targets=[ids["fld_unmapped"]],
        )
        _mapping(
            s,
            level="entity",
            disposition="keep",
            source=ids["ent2"],
            targets=[ids["ent2"]],
        )
        mm.patch_migration_mapping(
            s,
            ids["bad_merge_2"],
            transform_rules=[_merge_rule(2, group="bad-group", separator=" ")],
        )
    with session_scope() as s:
        assert mm.triage_completeness(s)["complete"] is True
        assert mm.compile_preflight(s)["ready"] is True


def test_q1_transform_arm_and_exclusions(v2_env):
    """The Q1 transform arm: a rejected baseline candidate superseded by a
    new record owes a mapping; a plain drop (rejected, no supersession), an
    undisposed candidate, and an interview-born record never appear."""
    with session_scope() as s:
        ent = _entity(s, "Contact")
        dec = _decision(s)
        # Rejection enters from `candidate` (the one-way gate has no
        # confirmed -> rejected arc, mirroring `domain`).
        transformed = _field(s, ent, "transformed_src", status="candidate")
        replacement = _field(s, ent, "replacement", baseline=False)
        _supersede(s, "field", replacement, transformed)
        _reject(s, "field", transformed, dec)
        dropped = _field(s, ent, "dropped", status="candidate")
        _reject(s, "field", dropped, dec)
        _field(s, ent, "undisposed", status="candidate")
        _field(s, ent, "interview_born", baseline=False)
        # Map the entity itself so only the transform obligation remains.
        _mapping(s, level="entity", disposition="keep", source=ent, targets=[ent])
    with session_scope() as s:
        completeness = mm.triage_completeness(s, level="field")
        assert [item["identifier"] for item in completeness["unmapped"]] == [
            transformed
        ]
        item = completeness["unmapped"][0]
        assert item["disposition"] == "transform"
        assert replacement in item["detail"]
        # Recording the mapping clears the obligation.
        _mapping(
            s,
            level="field",
            disposition="transform",
            source=transformed,
            targets=[replacement],
        )
        assert mm.triage_completeness(s, level="field")["complete"] is True


def test_q2_worksheet_list_filters(v2_env):
    """The §3.5.5 list filters back the Q2/Q3 reads: the source filter is
    the disposition lookup, the target filter assembles a merge group."""
    with session_scope() as s:
        ids = _seed_criterion_13(s)
    with session_scope() as s:
        by_source = mm.list_migration_mappings(
            s, source_identifier=ids["fld_old_phone"]
        )
        assert [
            r["migration_mapping_identifier"] for r in by_source
        ] == [ids["rename"]]
        merge_members = mm.list_migration_mappings(
            s, target_identifier=ids["fld_full"]
        )
        assert sorted(
            r["migration_mapping_identifier"] for r in merge_members
        ) == sorted([ids["merge_1"], ids["merge_2"]])
        entity_level = mm.list_migration_mappings(s, level="entity")
        assert [
            r["migration_mapping_identifier"] for r in entity_level
        ] == [ids["keep"]]


# ---------------------------------------------------------------------------
# Criterion 14 — change-log coverage under entity type `migration_mapping`
# ---------------------------------------------------------------------------


def test_change_log_rows_emitted_for_mapping_writes(v2_env):
    with session_scope() as s:
        _ent, old, new = _transform_pair(s)
        mig = _mapping(
            s, level="field", disposition="transform", source=old, targets=[new]
        )["migration_mapping_identifier"]
        mm.patch_migration_mapping(s, mig, notes="stakeholder context")
        mm.delete_migration_mapping(s, mig)
    with session_scope() as s:
        rows = s.scalars(
            select(ChangeLog).where(
                ChangeLog.entity_type == "migration_mapping",
                ChangeLog.entity_identifier == mig,
            )
        ).all()
        assert [row.operation for row in rows] == ["insert", "update", "update"]


# ---------------------------------------------------------------------------
# §6 — compile contract: the stored structure supplies the ImportManager
# inputs and the rules suffice to transform a record (Master PRD v0.2 §8)
# ---------------------------------------------------------------------------


def _seed_compile_batch(s) -> dict:
    """An entity keep plus one mapping of each value-bearing rule kind,
    with literal source attribute names a compiler would extract by."""
    ids = {"ent": _entity(s, "Contact")}
    ent = ids["ent"]
    ids["fld_type"] = _field(s, ent, "contact_type")
    ids["fld_stage"] = _field(s, ent, "mentor_stage", baseline=False)
    ids["fld_first"] = _field(s, ent, "first_name")
    ids["fld_last"] = _field(s, ent, "last_name")
    ids["fld_full"] = _field(s, ent, "full_name", baseline=False)
    ids["fld_combined"] = _field(s, ent, "city_state")
    ids["fld_city"] = _field(s, ent, "city", baseline=False)
    ids["fld_state"] = _field(s, ent, "state", baseline=False)

    _mapping(s, level="entity", disposition="keep", source=ent, targets=[ent])
    _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_type"],
        targets=[ids["fld_stage"]],
        source_attribute_name="cContactType",
        transform_rules=[_ENUM_RULE],
    )
    _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_first"],
        targets=[ids["fld_full"]],
        source_attribute_name="cFirstName",
        transform_rules=[_merge_rule(1)],
    )
    _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_last"],
        targets=[ids["fld_full"]],
        source_attribute_name="cLastName",
        transform_rules=[_merge_rule(2)],
    )
    _mapping(
        s,
        level="field",
        disposition="transform",
        source=ids["fld_combined"],
        targets=[ids["fld_city"], ids["fld_state"]],
        source_attribute_name="cCityState",
        transform_rules=[_split_rule([ids["fld_city"], ids["fld_state"]])],
    )
    return ids


def _apply_stored_rules(field_maps: list[dict], record: dict) -> dict:
    """A minimal §6.2 rule interpreter: transforms one source record using
    ONLY what the stored mappings carry — proving the schema is
    self-sufficient for compilation. Output is keyed by target-record
    identifier (platform-name resolution is deliberately compile-time
    work per §6.3)."""
    out: dict[str, str] = {}
    merge_parts: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
    for record_map in field_maps:
        source_key = record_map["migration_mapping_source_attribute_name"]
        value = record[source_key]
        targets = [
            t["identifier"]
            for t in record_map["migration_mapping_links"]["migrates_to"]
        ]
        rules = record_map["migration_mapping_transform_rules"] or []
        for rule in rules:  # list order is application order (§4.1)
            kind = rule["rule_kind"]
            if kind == "enum_value_map":
                if value not in rule["value_map"]:
                    assert rule["unmapped_policy"] == "error"
                    raise AssertionError(f"unmapped value {value!r}")
                value = rule["value_map"][value]
            elif kind == "merge":
                merge_parts.setdefault(
                    (rule["merge_group"], targets[0]), []
                ).append((rule["merge_order"], rule["separator"], value))
                value = None
            elif kind == "split":
                for assignment in rule["assignments"]:
                    extractor = assignment["extractor"]
                    assert extractor["strategy"] == "delimiter"
                    out[assignment["target"]] = value.split(
                        extractor["delimiter"]
                    )[extractor["index"]]
                value = None
        if value is not None:
            out[targets[0]] = value
    for (_group, target), parts in merge_parts.items():
        parts.sort()
        out[target] = parts[0][1].join(part[2] for part in parts)
    return out


def test_compile_contract_stored_structure_supplies_import_inputs(v2_env):
    with session_scope() as s:
        ids = _seed_compile_batch(s)
    with session_scope() as s:
        worksheet = mm.list_migration_mappings(s)
        entity_maps = [
            r for r in worksheet if r["migration_mapping_level"] == "entity"
        ]
        field_maps = [
            r for r in worksheet if r["migration_mapping_level"] == "field"
        ]
        assert len(entity_maps) == 1 and len(field_maps) == 4

        # §6.2: extraction coordinates are literal strings denormalized on
        # the rows — the compiler never needs a methodology-record name.
        batch_entity = entity_maps[0]
        assert batch_entity["migration_mapping_source_system_label"] == _LABEL
        assert batch_entity["migration_mapping_source_entity_name"] == "Contact"
        for record_map in field_maps:
            assert record_map["migration_mapping_source_attribute_name"]
            assert record_map["migration_mapping_links"]["migrates_to"]

        # §3.3.3: the field-under-entity grouping is derivable from the
        # `field_belongs_to_entity` edges — every field map's source field
        # parents to the batch entity's source record.
        parent_edges = {
            edge.source_id: edge.target_id
            for edge in s.scalars(
                select(Reference).where(
                    Reference.relationship_kind == "field_belongs_to_entity"
                )
            )
        }
        batch_source = batch_entity["migration_mapping_links"][
            "migrates_from"
        ]["identifier"]
        for record_map in field_maps:
            source_field = record_map["migration_mapping_links"][
                "migrates_from"
            ]["identifier"]
            assert parent_edges[source_field] == batch_source

        # §6.1: the `field_mapping` dict shape `ImportManager.check`
        # consumes assembles directly from the stored coordinates.
        field_mapping = {
            record_map["migration_mapping_source_attribute_name"]: [
                t["identifier"]
                for t in record_map["migration_mapping_links"]["migrates_to"]
            ]
            for record_map in field_maps
        }
        assert set(field_mapping) == {
            "cContactType",
            "cFirstName",
            "cLastName",
            "cCityState",
        }

        # The stored rules alone transform a source record end to end.
        transformed = _apply_stored_rules(
            field_maps,
            {
                "cContactType": "Mentor Candidate",
                "cFirstName": "Ada",
                "cLastName": "Lovelace",
                "cCityState": "Cleveland, OH",
            },
        )
        assert transformed == {
            ids["fld_stage"]: "candidate",
            ids["fld_full"]: "Ada Lovelace",
            ids["fld_city"]: "Cleveland",
            ids["fld_state"]: "OH",
        }

        # The no-silent-behavior posture (§4.1): an observed value the
        # stakeholder never mapped fails loudly, never coerces.
        with pytest.raises(AssertionError, match="unmapped value"):
            _apply_stored_rules(
                field_maps,
                {
                    "cContactType": "Board Member",
                    "cFirstName": "Ada",
                    "cLastName": "Lovelace",
                    "cCityState": "Cleveland, OH",
                },
            )


def test_compile_contract_import_manager_signature_unchanged():
    """§6.1 names `ImportManager.check(records, field_mapping, fixed_values)`
    as the compile target — pin the contract so a signature drift in the
    import machinery surfaces here, not in the future compiler."""
    import inspect

    from espo_impl.core.import_manager import ImportManager

    parameters = inspect.signature(ImportManager.check).parameters
    assert {"entity", "records", "field_mapping", "fixed_values"} <= set(
        parameters
    )
    assert "plans" in inspect.signature(ImportManager.execute).parameters
