"""Utilization-evidence repository tests (PI-153 / WTK-088 §4).

Covers the I8/I9/I10 invariants the repository layer owns: insert
validation (subject existence/liveness/type, enum and range
constraints), the append-only surface (create + reads only), the
latest-snapshot list rule, the headline triage filter, and the
change_log emission under the ``utilization_evidence`` log-only type.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.models import ChangeLog
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import utilization_evidence as ue
from crmbuilder_v2.access.repositories.entity import (
    create_entity,
    delete_entity,
)
from sqlalchemy import select


def _make_entity(s, name="Engagement") -> str:
    return create_entity(s, name=name, description="d")["entity_identifier"]


def _make_field(s, entity_identifier, name="Stage") -> str:
    return field_repo.create_field(
        s,
        field_belongs_to_entity_identifier=entity_identifier,
        name=name,
        description="d",
        type="enum",
    )["field_identifier"]


def test_create_entity_evidence_happy_path(v2_env):
    with session_scope() as s:
        ent = _make_entity(s)
        row = ue.create_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier=ent,
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ crm.example.org",
            catalog_class="custom",
            record_count=412,
            detail={"layouts_captured": ["detail", "list"]},
        )
    assert row["evidence_subject_identifier"] == ent
    assert row["evidence_record_count"] == 412
    assert row["evidence_population_rate"] is None
    assert row["id"] > 0


def test_create_emits_change_log_row(v2_env):
    with session_scope() as s:
        ent = _make_entity(s)
        row = ue.create_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier=ent,
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ crm.example.org",
        )
    with session_scope() as s:
        entry = s.scalar(
            select(ChangeLog).where(
                ChangeLog.entity_type == "utilization_evidence",
                ChangeLog.entity_identifier == str(row["id"]),
            )
        )
        assert entry is not None
        assert entry.operation == "insert"


def test_subject_must_exist(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        ue.create_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier="ENT-999",
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ x",
        )
    assert exc.value.errors[0].code == "subject_not_found"


def test_subject_must_be_live(v2_env):
    with session_scope() as s:
        ent = _make_entity(s)
        delete_entity(s, ent)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        ue.create_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier=ent,
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ x",
        )
    assert exc.value.errors[0].code == "subject_soft_deleted"


def test_subject_type_must_match_table(v2_env):
    # An entity identifier declared as a field subject is not found in
    # the fields table — the type-match half of I9.
    with session_scope() as s:
        ent = _make_entity(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        ue.create_utilization_evidence(
            s,
            subject_type="field",
            subject_identifier=ent,
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ x",
        )
    assert exc.value.errors[0].code == "subject_not_found"


def test_invalid_subject_type_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        ue.create_utilization_evidence(
            s,
            subject_type="decision",
            subject_identifier="DEC-001",
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ x",
        )
    assert exc.value.errors[0].code == "invalid_value"


def test_range_and_enum_validation(v2_env):
    with session_scope() as s:
        ent = _make_entity(s)
    base = {
        "subject_type": "entity",
        "subject_identifier": None,  # filled per case
        "profiled_at": "2026-06-11T18:00:00Z",
        "source_label": "espocrm @ x",
    }
    cases = [
        ({"population_rate": 1.5}, "evidence_population_rate"),
        ({"record_count": -1}, "evidence_record_count"),
        ({"catalog_class": "bespoke"}, "evidence_catalog_class"),
        ({"deposit_event_identifier": "DEP-1"},
         "evidence_deposit_event_identifier"),
        ({"detail": ["not", "an", "object"]}, "evidence_detail"),
    ]
    for extra, expected_field in cases:
        kwargs = dict(base, subject_identifier=ent, **extra)
        with session_scope() as s, pytest.raises(UnprocessableError) as exc:
            ue.create_utilization_evidence(s, **kwargs)
        assert exc.value.errors[0].field == expected_field, extra


def test_append_only_surface(v2_env):
    # I8: the repository module exposes no update/patch/delete/restore.
    assert not [
        name
        for name in dir(ue)
        if name.startswith(("update_", "patch_", "delete_", "restore_"))
    ]


def test_list_filters_and_latest_snapshot_rule(v2_env):
    with session_scope() as s:
        ent = _make_entity(s)
        fld = _make_field(s, ent)
        # Two snapshots of the same field from one source; one from a
        # second source; one entity row.
        for profiled_at, rate in (
            ("2026-06-01T00:00:00Z", 0.50),
            ("2026-06-11T00:00:00Z", 0.03),
        ):
            ue.create_utilization_evidence(
                s,
                subject_type="field",
                subject_identifier=fld,
                profiled_at=profiled_at,
                source_label="espocrm @ a",
                population_rate=rate,
            )
        ue.create_utilization_evidence(
            s,
            subject_type="field",
            subject_identifier=fld,
            profiled_at="2026-06-05T00:00:00Z",
            source_label="espocrm @ b",
            population_rate=0.90,
        )
        ue.create_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier=ent,
            profiled_at="2026-06-11T00:00:00Z",
            source_label="espocrm @ a",
            record_count=2,
        )

    with session_scope() as s:
        all_rows = ue.list_utilization_evidence(s)
        assert len(all_rows) == 4

        by_subject = ue.list_utilization_evidence(
            s, subject_type="field", subject_identifier=fld
        )
        assert len(by_subject) == 3
        # Newest snapshot first within a subject.
        assert by_subject[0]["evidence_population_rate"] == 0.03

        # Latest-snapshot rule: one row per (subject, source).
        latest = ue.list_utilization_evidence(
            s, subject_type="field", subject_identifier=fld, latest=True
        )
        assert len(latest) == 2
        assert {r["evidence_source_label"] for r in latest} == {
            "espocrm @ a",
            "espocrm @ b",
        }
        assert {r["evidence_population_rate"] for r in latest} == {0.03, 0.90}

        # The headline triage query over the repository surface.
        under_five = ue.list_utilization_evidence(
            s, subject_type="field", max_population_rate=0.05, latest=True
        )
        assert [r["evidence_population_rate"] for r in under_five] == [0.03]


def test_evidence_survives_subject_rejection_and_delete(v2_env):
    # I10: evidence never participates in lifecycle enforcement.
    from crmbuilder_v2.access.repositories import decisions
    from crmbuilder_v2.access.repositories.entity import patch_entity

    with session_scope() as s:
        ent = _make_entity(s)
        ue.create_utilization_evidence(
            s,
            subject_type="entity",
            subject_identifier=ent,
            profiled_at="2026-06-11T00:00:00Z",
            source_label="espocrm @ a",
        )
        dec = decisions.create(
            s,
            title="Drop",
            decision_date="2026-06-11",
            status="Active",
            executive_summary=(
                "Test decision recording the rationale for dropping a "
                "baseline candidate during Phase 3 triage. The candidate "
                "was reviewed with the stakeholder and deliberately not "
                "carried forward; this record is the durable answer to "
                "where it went and why, per the PI-153 design."
            ),
        )["identifier"]
        patch_entity(s, ent, status="rejected", rejected_by_decision=dec)
        delete_entity(s, ent)
    with session_scope() as s:
        rows = ue.list_utilization_evidence(
            s, subject_type="entity", subject_identifier=ent
        )
        assert len(rows) == 1
