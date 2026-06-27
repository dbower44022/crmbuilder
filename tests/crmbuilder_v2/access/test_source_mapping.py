"""Source mapping foundation tests — PI-255 (PRJ-027 / SES-230).

Covers the new vocab, the seven-table schema shape, and the five access-layer
repositories (source_mapping, source_mapping_targets, field_mapping,
value_mapping, mapping_candidate): create/list/patch/mark_stale/soft-delete,
the gated status lifecycle, target replacement, value-mapping supersession +
single-active-row enforcement, and candidate creation/resolution/bulk insert.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import (
    field_mapping,
    mapping_candidate,
    source_mapping,
    source_mapping_targets,
    value_mapping,
)
from crmbuilder_v2.access.vocab import (
    FIELD_MAPPING_DECISION_TYPES,
    INSTANCE_MEMBERSHIP_STATES,
    MAPPING_CANDIDATE_TYPES,
    SOURCE_MAPPING_DECISION_TYPES,
    SOURCE_MAPPING_STATUSES,
    VALUE_MAPPING_DECISION_TYPES,
)
from sqlalchemy import inspect

# --- vocab ------------------------------------------------------------------


def test_membership_states_canonical_only():
    # SES-247 / DEC-650: the membership join stays canonical-only — candidacy
    # lives in mapping_candidate and staleness on the mapping record's status, so
    # the once-proposed candidate_pending / mapping_stale states are removed.
    assert INSTANCE_MEMBERSHIP_STATES == {"present", "drifted", "absent"}


@pytest.mark.parametrize(
    "vocab",
    [
        SOURCE_MAPPING_DECISION_TYPES,
        SOURCE_MAPPING_STATUSES,
        FIELD_MAPPING_DECISION_TYPES,
        VALUE_MAPPING_DECISION_TYPES,
        MAPPING_CANDIDATE_TYPES,
    ],
)
def test_vocab_nonempty_frozensets(vocab):
    assert isinstance(vocab, frozenset)
    assert vocab


# --- schema shape -----------------------------------------------------------


def test_seven_tables_present(v2_env):
    names = set(inspect(get_engine()).get_table_names())
    assert {
        "source_mappings",
        "source_mapping_targets",
        "source_mapping_joins",
        "field_mappings",
        "field_mapping_translations",
        "value_mappings",
        "mapping_candidates",
    } <= names


# --- source_mapping ---------------------------------------------------------


def test_source_mapping_create_defaults(v2_env):
    with session_scope() as s:
        row = source_mapping.create_source_mapping(
            s,
            instance_identifier="INST-001",
            source_entity_name="Mentor",
            decision_type="direct",
        )
        assert row["source_mapping_identifier"] == "SMG-001"
        assert row["status"] == "unresolved"
        assert row["deleted_at"] is None


def test_source_mapping_identifier_autoassigns(v2_env):
    with session_scope() as s:
        a = source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        b = source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Company", decision_type="referential",
        )
        assert a["source_mapping_identifier"] == "SMG-001"
        assert b["source_mapping_identifier"] == "SMG-002"


def test_source_mapping_list_by_instance(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-002",
            source_entity_name="Mentor", decision_type="direct",
        )
        only_1 = source_mapping.list_source_mappings(
            s, instance_identifier="INST-001"
        )
        assert [r["instance_identifier"] for r in only_1] == ["INST-001"]


def test_source_mapping_patch_notes(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        patched = source_mapping.patch_source_mapping(
            s, "SMG-001", notes="needs review by SME"
        )
        assert patched["notes"] == "needs review by SME"


def test_source_mapping_mark_stale(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        stale = source_mapping.mark_stale(
            s, "SMG-001", reason="source_changed", severity="high"
        )
        assert stale["status"] == "stale"
        assert stale["stale_reason"] == "source_changed"
        assert stale["stale_severity"] == "high"


def test_source_mapping_resolve_sets_timestamp(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        resolved = source_mapping.update_source_mapping(
            s, "SMG-001",
            source_entity_name="Mentor", decision_type="direct",
            status="resolved",
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None


def test_source_mapping_soft_delete_restore(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        deleted = source_mapping.delete_source_mapping(s, "SMG-001")
        assert deleted["deleted_at"] is not None
        assert source_mapping.get_source_mapping(s, "SMG-001") is None
        restored = source_mapping.restore_source_mapping(s, "SMG-001")
        assert restored["deleted_at"] is None


def test_source_mapping_invalid_decision_type(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            source_mapping.create_source_mapping(
                s, instance_identifier="INST-001",
                source_entity_name="Mentor", decision_type="bogus",
            )


def test_source_mapping_invalid_status_transition(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
        )
        source_mapping.mark_stale(
            s, "SMG-001", reason="source_changed", severity="low"
        )
        # stale -> unresolved is not an allowed transition.
        with pytest.raises(StatusTransitionError):
            source_mapping.update_source_mapping(
                s, "SMG-001",
                source_entity_name="Mentor", decision_type="direct",
                status="unresolved",
            )


def test_source_mapping_explicit_identifier_collision(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="direct",
            identifier="SMG-010",
        )
        with pytest.raises(ConflictError):
            source_mapping.create_source_mapping(
                s, instance_identifier="INST-001",
                source_entity_name="Dup", decision_type="direct",
                identifier="SMG-010",
            )


# --- source_mapping_targets -------------------------------------------------


def test_targets_add_idempotent(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="decomposition",
        )
        source_mapping_targets.add_target(
            s, source_mapping_identifier="SMG-001", entity_identifier="ENT-001"
        )
        source_mapping_targets.add_target(
            s, source_mapping_identifier="SMG-001", entity_identifier="ENT-001"
        )
        rows = source_mapping_targets.list_targets(
            s, source_mapping_identifier="SMG-001"
        )
        assert len(rows) == 1


def test_targets_set_replaces(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="decomposition",
        )
        source_mapping_targets.set_targets(
            s, source_mapping_identifier="SMG-001",
            entity_identifiers=["ENT-001", "ENT-002"],
        )
        source_mapping_targets.set_targets(
            s, source_mapping_identifier="SMG-001",
            entity_identifiers=["ENT-003"],
        )
        rows = source_mapping_targets.list_targets(
            s, source_mapping_identifier="SMG-001"
        )
        assert {r["entity_identifier"] for r in rows} == {"ENT-003"}


def test_targets_remove_one(v2_env):
    with session_scope() as s:
        source_mapping.create_source_mapping(
            s, instance_identifier="INST-001",
            source_entity_name="Mentor", decision_type="decomposition",
        )
        source_mapping_targets.set_targets(
            s, source_mapping_identifier="SMG-001",
            entity_identifiers=["ENT-001", "ENT-002"],
        )
        source_mapping_targets.remove_target(
            s, source_mapping_identifier="SMG-001", entity_identifier="ENT-001"
        )
        rows = source_mapping_targets.list_targets(
            s, source_mapping_identifier="SMG-001"
        )
        assert {r["entity_identifier"] for r in rows} == {"ENT-002"}


# --- field_mapping ----------------------------------------------------------


def _seed_mapping(s):
    source_mapping.create_source_mapping(
        s, instance_identifier="INST-001",
        source_entity_name="Mentor", decision_type="direct",
    )


def test_field_mapping_create_and_list(v2_env):
    with session_scope() as s:
        _seed_mapping(s)
        fm = field_mapping.create_field_mapping(
            s, source_mapping_identifier="SMG-001",
            source_field_name="cContactType", decision_type="referential_exact",
        )
        assert fm["field_mapping_identifier"] == "FMP-001"
        assert fm["status"] == "unresolved"
        listed = field_mapping.list_field_mappings(
            s, source_mapping_identifier="SMG-001"
        )
        assert len(listed) == 1


def test_field_mapping_mark_stale_and_delete(v2_env):
    with session_scope() as s:
        _seed_mapping(s)
        field_mapping.create_field_mapping(
            s, source_mapping_identifier="SMG-001",
            source_field_name="cContactType", decision_type="direct",
        )
        stale = field_mapping.mark_stale(
            s, "FMP-001", reason="design_changed", severity="high"
        )
        assert stale["status"] == "stale"
        deleted = field_mapping.delete_field_mapping(s, "FMP-001")
        assert deleted["deleted_at"] is not None
        assert field_mapping.get_field_mapping(s, "FMP-001") is None


# --- value_mapping ----------------------------------------------------------


def _seed_field(s):
    _seed_mapping(s)
    field_mapping.create_field_mapping(
        s, source_mapping_identifier="SMG-001",
        source_field_name="cContactType",
        decision_type="referential_interpreted",
    )


def test_value_mapping_create_and_list_active(v2_env):
    with session_scope() as s:
        _seed_field(s)
        vm = value_mapping.create_value_mapping(
            s, field_mapping_identifier="FMP-001",
            source_value="E", decision_type="interpreted", target_value="email",
        )
        assert vm["source_value"] == "E"
        active = value_mapping.list_value_mappings(
            s, field_mapping_identifier="FMP-001"
        )
        assert len(active) == 1


def test_value_mapping_duplicate_active_rejected(v2_env):
    with session_scope() as s:
        _seed_field(s)
        value_mapping.create_value_mapping(
            s, field_mapping_identifier="FMP-001",
            source_value="E", decision_type="interpreted", target_value="email",
        )
        with pytest.raises(ConflictError):
            value_mapping.create_value_mapping(
                s, field_mapping_identifier="FMP-001",
                source_value="E", decision_type="interpreted",
                target_value="email2",
            )


def test_value_mapping_supersede_roundtrip(v2_env):
    with session_scope() as s:
        _seed_field(s)
        old = value_mapping.create_value_mapping(
            s, field_mapping_identifier="FMP-001",
            source_value="E", decision_type="interpreted", target_value="email",
        )
        # superseding frees the (field, value) slot for a new active row
        new = value_mapping.create_value_mapping(
            s, field_mapping_identifier="FMP-001",
            source_value="P", decision_type="interpreted", target_value="phone",
        )
        superseded = value_mapping.supersede_value_mapping(
            s, old["id"], replacement_id=new["id"]
        )
        assert superseded["superseded_by"] == new["id"]
        assert superseded["status"] == "superseded"
        active = value_mapping.list_value_mappings(
            s, field_mapping_identifier="FMP-001"
        )
        assert {r["id"] for r in active} == {new["id"]}
        all_rows = value_mapping.list_value_mappings(
            s, field_mapping_identifier="FMP-001", include_superseded=True
        )
        assert len(all_rows) == 2


# --- mapping_candidate ------------------------------------------------------


def test_candidate_create_entity_and_field(v2_env):
    with session_scope() as s:
        ent = mapping_candidate.create_candidate(
            s, instance_identifier="INST-001", candidate_type="entity",
            source_entity_name="Mentor",
        )
        fld = mapping_candidate.create_candidate(
            s, instance_identifier="INST-001", candidate_type="field",
            source_entity_name="Mentor", source_field_name="cContactType",
            suggestion_confidence="high", suggestion_basis="name_similarity",
        )
        assert ent["candidate_type"] == "entity"
        assert fld["candidate_type"] == "field"
        assert fld["resolved"] is False


def test_candidate_resolve(v2_env):
    with session_scope() as s:
        c = mapping_candidate.create_candidate(
            s, instance_identifier="INST-001", candidate_type="entity",
            source_entity_name="Mentor",
        )
        resolved = mapping_candidate.resolve_candidate(
            s, c["id"], resolved_to_source_mapping_identifier="SMG-001"
        )
        assert resolved["resolved"] is True
        assert resolved["resolved_at"] is not None
        assert resolved["resolved_to_source_mapping_identifier"] == "SMG-001"


def test_candidate_bulk_create(v2_env):
    with session_scope() as s:
        rows = mapping_candidate.bulk_create_candidates(
            s,
            [
                {
                    "instance_identifier": "INST-001",
                    "candidate_type": "entity",
                    "source_entity_name": "Mentor",
                },
                {
                    "instance_identifier": "INST-001",
                    "candidate_type": "entity",
                    "source_entity_name": "Company",
                },
            ],
        )
        assert len(rows) == 2
        listed = mapping_candidate.list_candidates(
            s, instance_identifier="INST-001", resolved=False
        )
        assert len(listed) == 2
