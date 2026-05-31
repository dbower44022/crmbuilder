"""Tests for the reference-target summary resolver (PRJ-015 references grid).

Two concerns:

1. *Coverage / correctness of the registry.* Every ``ENTITY_TYPES`` member
   is mapped (in ``_SPECS`` or ``_NO_SUMMARY``), and every column named in a
   ``_Spec`` actually exists on its model. This fails the moment a new entity
   type is added to the vocab without a summary mapping, or a column is
   renamed out from under the registry.

2. *Functional enrichment.* ``list_touching`` attaches ``other_summary`` for
   the far side of each edge, in both directions.
"""

from __future__ import annotations

from crmbuilder_v2.access import entity_summary as es
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    planning_items as pi,
    references,
)
from crmbuilder_v2.access.vocab import ENTITY_TYPES

_EXEC = (
    "This record exists solely to exercise the reference-summary resolver "
    "under test; it carries no production meaning and is created fresh per "
    "test run so the enrichment path can be verified end to end against a "
    "real row with a real title, status, and lifecycle timestamps present."
)


# --- registry coverage / correctness ---------------------------------------


def test_registry_covers_every_entity_type():
    assert es.KNOWN_TYPES == ENTITY_TYPES


def test_every_spec_column_exists_on_its_model():
    for entity_type, spec in es._SPECS.items():
        cols = {c.name for c in spec.model.__table__.columns}
        for slot in ("id_col", "title_col", "status_col", "created_col", "updated_col"):
            col = getattr(spec, slot)
            if col is not None:
                assert col in cols, (
                    f"{entity_type}: {slot}={col!r} not a column of "
                    f"{spec.model.__name__} ({sorted(cols)})"
                )


# --- functional enrichment -------------------------------------------------


def _seed(s):
    pi.create(
        s,
        identifier="PI-001",
        title="Blocked item",
        item_type="pending_work",
        status="Draft",
        executive_summary=_EXEC,
    )
    pi.create(
        s,
        identifier="PI-002",
        title="Blocking item",
        item_type="pending_work",
        status="Resolved",
        executive_summary=_EXEC,
    )
    # PI-001 blocked_by PI-002 (directed planning_item -> planning_item).
    references.create(
        s,
        source_type="planning_item",
        source_id="PI-001",
        target_type="planning_item",
        target_id="PI-002",
        relationship="blocked_by",
    )


def test_touching_enriches_outbound_other_summary(v2_env):
    with session_scope() as s:
        _seed(s)
    with session_scope() as s:
        payload = references.list_touching(
            s, entity_type="planning_item", entity_id="PI-001"
        )
    # PI-001 is the source; the far side is PI-002.
    assert len(payload["as_source"]) == 1
    summary = payload["as_source"][0]["other_summary"]
    assert summary is not None
    assert summary["identifier"] == "PI-002"
    assert summary["entity_type"] == "planning_item"
    assert summary["title"] == "Blocking item"
    assert summary["status"] == "Resolved"
    assert summary["created_at"] is not None


def test_touching_enriches_inbound_other_summary(v2_env):
    with session_scope() as s:
        _seed(s)
    with session_scope() as s:
        payload = references.list_touching(
            s, entity_type="planning_item", entity_id="PI-002"
        )
    # PI-002 is the target; the far side is PI-001.
    assert len(payload["as_target"]) == 1
    summary = payload["as_target"][0]["other_summary"]
    assert summary is not None
    assert summary["identifier"] == "PI-001"
    assert summary["entity_type"] == "planning_item"
    assert summary["title"] == "Blocked item"
    assert summary["status"] == "Draft"


def test_summary_none_for_missing_row(v2_env):
    with session_scope() as s:
        assert es.summarize(s, "decision", "DEC-404") is None


def test_summary_none_for_no_summary_type(v2_env):
    with session_scope() as s:
        assert es.summarize(s, "charter", "1") is None
