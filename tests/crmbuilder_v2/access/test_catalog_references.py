"""Catalog ↔ universal references integration tests.

Verifies that catalog_entity and catalog_attribute have been added to
the universal references vocabulary; that other v2 entities can target
catalog rows; and that inbound references surface on catalog detail
responses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import catalog, decisions, references
from crmbuilder_v2.access.vocab import ENTITY_TYPES
from crmbuilder_v2.bootstrap.catalog_loader import load_catalog


_FIXTURE_CATALOG = (
    Path(__file__).resolve().parents[1] / "bootstrap" / "fixtures" / "catalog"
)


def test_entity_types_include_catalog_types():
    assert "catalog_entity" in ENTITY_TYPES
    assert "catalog_attribute" in ENTITY_TYPES


def test_create_reference_decision_to_catalog_entity(v2_env):
    """A decision can reference a catalog entity as target."""
    with session_scope() as s:
        load_catalog(s, _FIXTURE_CATALOG)
        decisions.create(
            s,
            identifier="DEC-001",
            title="Use Account model from catalog",
            decision_date="05-14-26",
            status="Active",
        )
    with session_scope() as s:
        ref = references.create(
            s,
            source_type="decision",
            source_id="DEC-001",
            target_type="catalog_entity",
            target_id="account",
            relationship="references",
        )
    assert ref["target_type"] == "catalog_entity"
    assert ref["target_id"] == "account"


def test_create_reference_to_catalog_attribute(v2_env):
    with session_scope() as s:
        load_catalog(s, _FIXTURE_CATALOG)
        decisions.create(
            s,
            identifier="DEC-002",
            title="Adopt accountName.api_name overrides",
            decision_date="05-14-26",
            status="Active",
        )
    with session_scope() as s:
        references.create(
            s,
            source_type="decision",
            source_id="DEC-002",
            target_type="catalog_attribute",
            target_id="account.accountName",
            relationship="is_about",
        )


def test_inbound_references_surface_on_entity(v2_env):
    """get_entity returns inbound_references for the catalog entity."""
    with session_scope() as s:
        load_catalog(s, _FIXTURE_CATALOG)
        decisions.create(
            s,
            identifier="DEC-001",
            title="x",
            decision_date="05-14-26",
            status="Active",
        )
        decisions.create(
            s,
            identifier="DEC-002",
            title="y",
            decision_date="05-14-26",
            status="Active",
        )
        references.create(
            s,
            source_type="decision",
            source_id="DEC-001",
            target_type="catalog_entity",
            target_id="account",
            relationship="references",
        )
        references.create(
            s,
            source_type="decision",
            source_id="DEC-002",
            target_type="catalog_entity",
            target_id="account",
            relationship="is_about",
        )
    with session_scope(export=False) as s:
        entity = catalog.get_entity(s, "account")
    inbound = entity["inbound_references"]
    assert len(inbound) == 2
    sources = {(r["source_type"], r["source_id"]) for r in inbound}
    assert sources == {("decision", "DEC-001"), ("decision", "DEC-002")}


def test_inbound_references_surface_on_attribute(v2_env):
    with session_scope() as s:
        load_catalog(s, _FIXTURE_CATALOG)
        decisions.create(
            s,
            identifier="DEC-010",
            title="Use accountName as primary",
            decision_date="05-14-26",
            status="Active",
        )
        references.create(
            s,
            source_type="decision",
            source_id="DEC-010",
            target_type="catalog_attribute",
            target_id="account.accountName",
            relationship="is_about",
        )
    with session_scope(export=False) as s:
        attr = catalog.get_attribute(s, "account", "accountName")
    inbound = attr["inbound_references"]
    assert any(
        r["source_type"] == "decision" and r["source_id"] == "DEC-010"
        for r in inbound
    )


def test_catalog_can_be_reference_source(v2_env):
    """The CHECK is symmetric — catalog rows can be sources too (the PRD's
    'don't naturally source' is a usage convention, not a constraint)."""
    with session_scope() as s:
        load_catalog(s, _FIXTURE_CATALOG)
        decisions.create(
            s,
            identifier="DEC-100",
            title="x",
            decision_date="05-14-26",
            status="Active",
        )
        # Doesn't error — catalog_entity is in source_type vocabulary.
        references.create(
            s,
            source_type="catalog_entity",
            source_id="account",
            target_type="decision",
            target_id="DEC-100",
            relationship="references",
        )
