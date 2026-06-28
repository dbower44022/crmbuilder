"""Audit-deposit provenance-gap report — REQ-339 / PI-299 (PRJ-057).

Every record the audit deposits should carry an inbound
``deposit_event_wrote_record`` edge to the deposit that produced it. The
report surfaces design records (entities, fields, personas) that lack one —
candidates that entered the design without provenance — so the gap is reported
rather than silently accepted.
"""

from __future__ import annotations

from crmbuilder_v2.access import coverage
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Entity
from crmbuilder_v2.access.repositories import references


def _entity(s, ident, name):
    s.add(Entity(entity_identifier=ident, entity_name=name, entity_description="d"))
    s.flush()


def _provenance(s, target_id):
    references.create(
        s, source_type="deposit_event", source_id="DEP-001",
        target_type="entity", target_id=target_id,
        relationship="deposit_event_wrote_record",
    )


def test_unprovenanced_entity_is_reported(v2_env):
    with session_scope() as s:
        _entity(s, "ENT-001", "Provenanced")
        _entity(s, "ENT-002", "Orphaned")
        _provenance(s, "ENT-001")  # ENT-002 left without provenance

    with session_scope() as s:
        report = coverage.provenance_gaps(s)

    assert "ENT-002" in report["unprovenanced"]["entities"]
    assert "ENT-001" not in report["unprovenanced"]["entities"]
    assert report["unprovenanced_count"] >= 1
    assert report["clean"] is False
    assert report["provenanced_records"] >= 1


def test_clean_when_every_record_is_provenanced(v2_env):
    with session_scope() as s:
        _entity(s, "ENT-010", "P")
        _provenance(s, "ENT-010")

    with session_scope() as s:
        report = coverage.provenance_gaps(s)

    assert "ENT-010" not in report["unprovenanced"]["entities"]
    assert report["unprovenanced"]["entities"] == []


def test_soft_deleted_records_are_not_flagged(v2_env):
    """A soft-deleted candidate is not a live provenance gap."""
    from datetime import datetime

    from crmbuilder_v2.access._helpers import get_by_identifier

    with session_scope() as s:
        _entity(s, "ENT-020", "Deleted")
        row = get_by_identifier(s, Entity, Entity.entity_identifier, "ENT-020")
        row.entity_deleted_at = datetime(2026, 1, 1)
        s.flush()

    with session_scope() as s:
        report = coverage.provenance_gaps(s)

    assert "ENT-020" not in report["unprovenanced"]["entities"]


def test_baseline_cutoff_excuses_legacy_records(v2_env):
    """A ``since`` cutoff counts pre-cutoff un-provenanced records as legacy
    baseline debt, while post-cutoff ones stay live gaps (REQ-339 / Option B)."""
    from datetime import datetime

    with session_scope() as s:
        s.add(Entity(
            entity_identifier="ENT-100", entity_name="Legacy",
            entity_description="d", entity_created_at=datetime(2026, 1, 1),
        ))
        s.add(Entity(
            entity_identifier="ENT-101", entity_name="New",
            entity_description="d", entity_created_at=datetime(2026, 12, 1),
        ))
        s.flush()

    with session_scope() as s:
        rep = coverage.provenance_gaps(s, since=datetime(2026, 6, 1))

    assert "ENT-100" not in rep["unprovenanced"]["entities"]  # legacy, excused
    assert "ENT-101" in rep["unprovenanced"]["entities"]       # live gap
    assert rep["baseline_summary"]["entities"] >= 1
    assert rep["baseline_since"] is not None


def test_no_cutoff_counts_all_as_live(v2_env):
    """Without a cutoff every un-provenanced record is a live gap."""
    from datetime import datetime

    with session_scope() as s:
        s.add(Entity(
            entity_identifier="ENT-110", entity_name="Old",
            entity_description="d", entity_created_at=datetime(2026, 1, 1),
        ))
        s.flush()

    with session_scope() as s:
        rep = coverage.provenance_gaps(s)  # since=None

    assert "ENT-110" in rep["unprovenanced"]["entities"]
    assert rep["baseline_summary"] == {"entities": 0, "fields": 0, "personas": 0}
