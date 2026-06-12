"""Inline evidence object assembler tests (WTK-097 §3).

Pure-function coverage: §3.4 determinism, the §3.3 flag lift, the
omitted-not-null metrics rule, envelope completeness, and verbatim
detail passthrough. No database — the assembler is a projection of one
already-serialized row.
"""

from __future__ import annotations

import json

from crmbuilder_v2.access.evidence_projection import (
    EVIDENCE_FLAG_KEYS,
    project_evidence_object,
)


def _field_row(**overrides) -> dict:
    """A serialized field-subject row as the repository returns it."""
    row = {
        "id": 7,
        "engagement_id": "ENG-001",
        "evidence_subject_type": "field",
        "evidence_subject_identifier": "FLD-042",
        "evidence_profiled_at": "2026-06-11T18:00:00+00:00",
        "evidence_source_label": "espocrm @ crm.cbmentors.org",
        "evidence_deposit_event_identifier": "DEP-012",
        "evidence_catalog_class": "custom",
        "evidence_record_count": None,
        "evidence_last_record_created_at": None,
        "evidence_populated_count": 398,
        "evidence_population_rate": 0.966,
        "evidence_last_populated_at": "2026-06-09T14:22:00+00:00",
        "evidence_distinct_value_count": 5,
        "evidence_declared_option_count": 7,
        "evidence_used_option_count": 5,
        "evidence_detail": {
            "evidence_schema_version": 1,
            "wire_name": "engagementStage",
            "wire_type": "enum",
            "ghost_options": 2,
            "value_distribution": {"active": 211},
            "thresholds": {
                "dormancy_window_days": 365,
                "low_population_threshold": 0.05,
            },
        },
        "evidence_created_at": "2026-06-11T18:00:05+00:00",
    }
    row.update(overrides)
    return row


def test_shape_partition_and_flag_lift():
    obj = project_evidence_object(_field_row())

    # Envelope — the §3.1 keys, evidence_ prefix dropped.
    assert obj["subject_type"] == "field"
    assert obj["subject_identifier"] == "FLD-042"
    assert obj["profiled_at"] == "2026-06-11T18:00:00+00:00"
    assert obj["source_label"] == "espocrm @ crm.cbmentors.org"
    assert obj["deposit_event"] == "DEP-012"
    assert obj["catalog_class"] == "custom"

    # Metrics — non-NULL typed columns only, key = column stem.
    assert obj["metrics"] == {
        "populated_count": 398,
        "population_rate": 0.966,
        "last_populated_at": "2026-06-09T14:22:00+00:00",
        "distinct_value_count": 5,
        "declared_option_count": 7,
        "used_option_count": 5,
    }

    # Flags — lifted from detail (§3.3), detail still carries them.
    assert obj["flags"] == {"ghost_options": 2}
    assert obj["detail"]["ghost_options"] == 2

    # Bookkeeping columns do not leak into the object.
    assert set(obj) == {
        "subject_type",
        "subject_identifier",
        "profiled_at",
        "source_label",
        "deposit_event",
        "catalog_class",
        "metrics",
        "flags",
        "detail",
    }


def test_metrics_omitted_not_null():
    # An entity-subject row: only the record-count pair is set.
    obj = project_evidence_object(
        _field_row(
            evidence_subject_type="entity",
            evidence_subject_identifier="ENT-001",
            evidence_record_count=412,
            evidence_last_record_created_at="2026-06-09T14:22:00+00:00",
            evidence_populated_count=None,
            evidence_population_rate=None,
            evidence_last_populated_at=None,
            evidence_distinct_value_count=None,
            evidence_declared_option_count=None,
            evidence_used_option_count=None,
            evidence_detail={"dormant": False, "empty": False},
        )
    )
    assert obj["metrics"] == {
        "record_count": 412,
        "last_record_created_at": "2026-06-09T14:22:00+00:00",
    }
    assert "population_rate" not in obj["metrics"]
    assert obj["flags"] == {"dormant": False, "empty": False}


def test_null_deposit_event_and_empty_detail():
    # Standalone re-profile (no deposit event) on a row without detail:
    # envelope keys stay present-with-null; flags/detail are
    # present-and-empty objects (§8 A3 — emptiness is signal).
    obj = project_evidence_object(
        _field_row(
            evidence_deposit_event_identifier=None, evidence_detail=None
        )
    )
    assert obj["deposit_event"] is None
    assert obj["flags"] == {}
    assert obj["detail"] == {}


def test_detail_passthrough_verbatim():
    detail = {
        "evidence_schema_version": 1,
        "wire_name": "x",
        "custom_future_key": {"nested": [1, 2]},
        "stale": True,
    }
    obj = project_evidence_object(_field_row(evidence_detail=detail))
    assert obj["detail"] == detail
    assert obj["flags"] == {"stale": True}


def test_determinism_two_renders_byte_identical():
    # §3.4: two surfaces rendering the same row produce byte-identical
    # objects under a canonical serializer.
    row = _field_row()
    first = json.dumps(project_evidence_object(dict(row)), sort_keys=True)
    second = json.dumps(project_evidence_object(dict(row)), sort_keys=True)
    assert first == second


def test_flag_key_set_matches_spec():
    # The §3.3 lift covers exactly the WTK-096 §5 flag vocabulary.
    assert set(EVIDENCE_FLAG_KEYS) == {
        "dormant",
        "empty",
        "low_population",
        "stale",
        "ghost_options",
    }
