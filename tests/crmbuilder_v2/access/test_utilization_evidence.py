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


# ---------------------------------------------------------------------------
# WTK-097 verification (WTK-101) — claims the suites above left unpinned
# ---------------------------------------------------------------------------


def test_exact_tie_greatest_id_wins(v2_env):
    # WTK-097 §7.1: duplicate rows for one (subject, source,
    # profiled_at) — the failure-and-rerun re-append WTK-090 §5
    # tolerates — resolve to the greatest ``id`` in both the
    # ``latest=True`` list filter and the inline block's latest mode.
    with session_scope() as s:
        ent = _make_entity(s)
        fld = _make_field(s, ent)
        first = ue.create_utilization_evidence(
            s,
            subject_type="field",
            subject_identifier=fld,
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ a",
            population_rate=0.5,
            detail={"attempt": 1},
        )
        second = ue.create_utilization_evidence(
            s,
            subject_type="field",
            subject_identifier=fld,
            profiled_at="2026-06-11T18:00:00Z",
            source_label="espocrm @ a",
            population_rate=0.5,
            detail={"attempt": 2},
        )
        assert second["id"] > first["id"]

        latest = ue.list_utilization_evidence(
            s, subject_type="field", subject_identifier=fld, latest=True
        )
        assert [r["id"] for r in latest] == [second["id"]]

        block = ue.inline_evidence_block(
            s, subject_type="field", subject_identifier=fld, mode="latest"
        )
        assert block["snapshot_count"] == 2
        (obj,) = block["snapshots"]
        assert obj["detail"]["attempt"] == 2


# The WTK-088 §5.1 latest-snapshot CTE, verbatim from the spec.
_LATEST_CTE = """
WITH latest AS (
  SELECT ue.*,
         ROW_NUMBER() OVER (
           PARTITION BY ue.evidence_subject_type,
                        ue.evidence_subject_identifier,
                        ue.evidence_source_label
           ORDER BY ue.evidence_profiled_at DESC
         ) AS rn
  FROM utilization_evidence ue
)
"""

_Q2_DORMANT_ENTITIES = _LATEST_CTE + """
SELECT e.entity_identifier, e.entity_name,
       l.evidence_record_count, l.evidence_last_record_created_at
FROM entities e
JOIN latest l
  ON l.evidence_subject_type = 'entity'
 AND l.evidence_subject_identifier = e.entity_identifier
 AND l.rn = 1
WHERE e.entity_deleted_at IS NULL
  AND e.entity_status = 'candidate'
  AND (l.evidence_record_count = 0
       OR l.evidence_last_record_created_at < :twelve_months_ago)
"""

_Q3_GHOST_OPTIONS = _LATEST_CTE + """
SELECT f.field_identifier, f.field_name,
       l.evidence_declared_option_count - l.evidence_used_option_count
         AS ghost_options
FROM fields f
JOIN latest l
  ON l.evidence_subject_type = 'field'
 AND l.evidence_subject_identifier = f.field_identifier
 AND l.rn = 1
WHERE f.field_deleted_at IS NULL
  AND l.evidence_declared_option_count IS NOT NULL
  AND l.evidence_used_option_count < l.evidence_declared_option_count
ORDER BY ghost_options DESC
"""


def test_wtk088_q2_q3_sql_runs_against_typed_columns(v2_env):
    # WTK-097 §8 A6: Q2 (dormant entities) and Q3 (ghost options) run
    # unchanged against the typed columns (Q1 is pinned over REST in
    # the API suite). Each subject also carries an older superseded
    # snapshot that would invert the result if the rn=1 latest
    # discipline were broken.
    from datetime import UTC, datetime

    from sqlalchemy import text

    def evidence(s, subject_type, subject_identifier, profiled_at, **metrics):
        ue.create_utilization_evidence(
            s,
            subject_type=subject_type,
            subject_identifier=subject_identifier,
            profiled_at=profiled_at,
            source_label="espocrm @ a",
            **metrics,
        )

    with session_scope() as s:
        ghost_town = _make_entity(s, name="Ghost Town")
        old_timer = _make_entity(s, name="Old Timer")
        active = _make_entity(s, name="Active")
        stage = _make_field(s, active, name="Stage")
        clean = _make_field(s, active, name="Clean")

        # Q2 subjects: empty, recency-dormant, and active; the active
        # entity's older snapshot was empty (superseded).
        evidence(s, "entity", ghost_town, "2026-06-11T18:00:00Z", record_count=0)
        evidence(
            s,
            "entity",
            old_timer,
            "2026-06-11T18:00:00Z",
            record_count=50,
            last_record_created_at="2024-01-01T00:00:00Z",
        )
        evidence(s, "entity", active, "2026-06-01T00:00:00Z", record_count=0)
        evidence(
            s,
            "entity",
            active,
            "2026-06-11T18:00:00Z",
            record_count=412,
            last_record_created_at="2026-06-09T14:22:00Z",
        )

        # Q3 subjects: ghosts appeared in the latest snapshot only
        # (older snapshot had every option used), and a clean enum.
        evidence(
            s,
            "field",
            stage,
            "2026-06-01T00:00:00Z",
            declared_option_count=7,
            used_option_count=7,
        )
        evidence(
            s,
            "field",
            stage,
            "2026-06-11T18:00:00Z",
            declared_option_count=7,
            used_option_count=5,
        )
        evidence(
            s,
            "field",
            clean,
            "2026-06-11T18:00:00Z",
            declared_option_count=4,
            used_option_count=4,
        )

        dormant = s.execute(
            text(_Q2_DORMANT_ENTITIES),
            {"twelve_months_ago": datetime(2025, 6, 11, tzinfo=UTC)},
        ).all()
        assert {row.entity_identifier for row in dormant} == {
            ghost_town,
            old_timer,
        }

        ghosts = s.execute(text(_Q3_GHOST_OPTIONS)).all()
        assert [(row.field_identifier, row.ghost_options) for row in ghosts] == [
            (stage, 2)
        ]
