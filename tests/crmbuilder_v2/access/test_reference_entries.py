"""Reference Entry repository tests — REL-016 / PI-063 (REQ-398; DEC-886/887).

Covers the cross-engagement reference-library entity: schema shape, identifier
format + auto-assignment, kind + status enums, per-kind content validation,
trigger-keyword validation, the system|engagement scope (reused registry
pattern), update/delete, and the initial Domain Knowledge seed.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import (
    reference_entries,
    reference_entry_seed,
)
from sqlalchemy import inspect

_DK = {"body": "How this domain works."}


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


def test_reference_entries_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "reference_entries" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("reference_entries")}
    assert cols == {
        "identifier",
        "engagement_id",
        "name",
        "kind",
        "applies_to",
        "trigger_keywords",
        "content",
        "version",
        "status",
        "created_at",
        "updated_at",
    }
    pk = inspector.get_pk_constraint("reference_entries")
    assert pk["constrained_columns"] == ["identifier"]


# ---------------------------------------------------------------------------
# Identifier + auto-assignment
# ---------------------------------------------------------------------------


def test_auto_assign_sequence(v2_env):
    with session_scope() as s:
        a = reference_entries.create(
            s, name="A", kind="domain_knowledge", content=_DK
        )
        b = reference_entries.create(
            s, name="B", kind="domain_knowledge", content=_DK
        )
    assert a["identifier"] == "RFE-001"
    assert b["identifier"] == "RFE-002"


def test_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        r = reference_entries.create(
            s, name="X", kind="domain_knowledge", content=_DK, identifier="RFE-050"
        )
    assert r["identifier"] == "RFE-050"
    with session_scope() as s, pytest.raises(ConflictError):
        reference_entries.create(
            s, name="Y", kind="domain_knowledge", content=_DK, identifier="RFE-050"
        )


def test_malformed_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s, name="Z", kind="domain_knowledge", content=_DK, identifier="RFE-1"
        )


# ---------------------------------------------------------------------------
# Enums + content validation
# ---------------------------------------------------------------------------


def test_invalid_kind_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(s, name="A", kind="nonsense", content=_DK)


def test_domain_knowledge_requires_body(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s, name="A", kind="domain_knowledge", content={"notes": "x"}
        )


def test_empty_content_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s, name="A", kind="organization_structure", content={}
        )


# --- organization_structure content (PI-064 / REQ-399) ---

_ORG = {
    "typical_entities": ["Grant", "Donor"],
    "typical_relationships": ["A Grant is awarded to a Grantee"],
}
_INV = {
    "entities": ["Grant", "Grantee"],
    "personas": ["Program Officer"],
    "processes": ["Award grants"],
}


def test_organization_structure_valid(v2_env):
    with session_scope() as s:
        r = reference_entries.create(
            s, name="OrgShape", kind="organization_structure", content=_ORG
        )
    assert r["kind"] == "organization_structure"


def test_organization_structure_requires_typical_entities(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s,
            name="A",
            kind="organization_structure",
            content={"typical_entities": [], "typical_relationships": []},
        )


def test_organization_structure_requires_relationships_list(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s,
            name="A",
            kind="organization_structure",
            content={"typical_entities": ["Grant"]},
        )


# --- inventory_items content (PI-065 / REQ-400) ---


def test_inventory_items_valid(v2_env):
    with session_scope() as s:
        r = reference_entries.create(
            s, name="Checklist", kind="inventory_items", content=_INV
        )
    assert r["kind"] == "inventory_items"


def test_inventory_items_all_empty_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s,
            name="A",
            kind="inventory_items",
            content={"entities": [], "personas": [], "processes": []},
        )


def test_inventory_items_non_list_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s,
            name="A",
            kind="inventory_items",
            content={"entities": "Grant", "personas": [], "processes": []},
        )


def test_trigger_keywords_must_be_string_list(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s,
            name="A",
            kind="domain_knowledge",
            content=_DK,
            trigger_keywords=["ok", 5],
        )


def test_invalid_status_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.create(
            s, name="A", kind="domain_knowledge", content=_DK, status="draft"
        )


# ---------------------------------------------------------------------------
# Scope (reused registry system|engagement pattern)
# ---------------------------------------------------------------------------


def test_default_scope_is_system(v2_env):
    with session_scope() as s:
        r = reference_entries.create(
            s, name="Sys", kind="domain_knowledge", content=_DK
        )
    assert r["scope"] == "system"
    assert r["engagement_id"] is None


def test_engagement_scope(v2_env):
    with session_scope() as s:
        r = reference_entries.create(
            s, name="Eng", kind="domain_knowledge", content=_DK, scope="ENG-001"
        )
    assert r["scope"] == "ENG-001"
    assert r["engagement_id"] == "ENG-001"


def test_unknown_scope_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        reference_entries.create(
            s, name="Bad", kind="domain_knowledge", content=_DK, scope="ENG-999"
        )


def test_list_filters_by_kind_and_scope(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s, name="Sys1", kind="domain_knowledge", content=_DK
        )
        reference_entries.create(
            s, name="Eng1", kind="domain_knowledge", content=_DK, scope="ENG-001"
        )
        reference_entries.create(
            s,
            name="OrgSys",
            kind="organization_structure",
            content={
                "typical_entities": ["Grant"],
                "typical_relationships": [],
            },
        )
    with session_scope() as s:
        dk = reference_entries.list_all(s, kind="domain_knowledge")
        assert {r["name"] for r in dk} == {"Sys1", "Eng1"}
        sys_only = reference_entries.list_all(s, scope="system")
        assert "Eng1" not in {r["name"] for r in sys_only}


# ---------------------------------------------------------------------------
# Update / delete
# ---------------------------------------------------------------------------


def test_update_content_revalidated_against_kind(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s, name="A", kind="domain_knowledge", content=_DK
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        reference_entries.update(s, "RFE-001", content={"no": "body"})


def test_update_unknown_field_rejected(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s, name="A", kind="domain_knowledge", content=_DK
        )
    with session_scope() as s, pytest.raises(ValidationError):
        reference_entries.update(s, "RFE-001", bogus="x")


def test_update_and_rescope(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s, name="A", kind="domain_knowledge", content=_DK
        )
    with session_scope() as s:
        r = reference_entries.update(
            s, "RFE-001", name="A2", scope="ENG-001"
        )
    assert r["name"] == "A2"
    assert r["scope"] == "ENG-001"


def test_delete(v2_env):
    with session_scope() as s:
        reference_entries.create(
            s, name="A", kind="domain_knowledge", content=_DK
        )
    with session_scope() as s:
        reference_entries.delete(s, "RFE-001")
    with session_scope() as s, pytest.raises(NotFoundError):
        reference_entries.get(s, "RFE-001")


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def test_seed_creates_all_kinds(v2_env):
    with session_scope() as s:
        summary = reference_entry_seed.seed_reference_entries(s)
    # 3 domain_knowledge + 3 organization_structure + 3 inventory_items.
    assert len(summary["created"]) == 9
    with session_scope() as s:
        dk = reference_entries.list_all(s, kind="domain_knowledge")
        org = reference_entries.list_all(s, kind="organization_structure")
        inv = reference_entries.list_all(s, kind="inventory_items")
    assert len(dk) == 3 and len(org) == 3 and len(inv) == 3
    assert {r["name"] for r in dk} == {
        "Nonprofit Mentoring Organization",
        "Charitable Foundation",
        "Social Marketing Program",
    }
    # Every seeded entry is system-scoped, keyworded, and content-valid.
    for r in dk + org + inv:
        assert r["scope"] == "system"
        assert isinstance(r["trigger_keywords"], list) and r["trigger_keywords"]
    for r in org:
        assert r["content"]["typical_entities"]
    for r in inv:
        assert any(
            r["content"].get(k) for k in ("entities", "personas", "processes")
        )


def test_seed_is_idempotent(v2_env):
    with session_scope() as s:
        reference_entry_seed.seed_reference_entries(s)
    with session_scope() as s:
        summary = reference_entry_seed.seed_reference_entries(s)
    assert summary["created"] == []
    assert len(summary["skipped"]) == 9
    with session_scope() as s:
        rows = reference_entries.list_all(s)
    assert len(rows) == 9
