"""Catalog schema presence and constraint tests.

Verifies that the 10 catalog tables exist with the expected columns, that
CHECK constraints reject bad values, and that ON DELETE CASCADE cleans up
child rows.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.models import (
    CatalogAttribute,
    CatalogAttributeEnumValue,
    CatalogAttributePresence,
    CatalogAttributeSynonym,
    CatalogEntity,
    CatalogEntitySynonym,
    CatalogEntitySystem,
    CatalogRelationship,
    CatalogSource,
)
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError


_CATALOG_TABLES = (
    "catalog_entity",
    "catalog_entity_synonym",
    "catalog_entity_system",
    "catalog_source",
    "catalog_attribute",
    "catalog_attribute_enum_value",
    "catalog_attribute_synonym",
    "catalog_attribute_presence",
    "catalog_relationship",
    "catalog_relationship_presence",
)


def test_all_ten_tables_exist(v2_env):
    insp = inspect(get_engine())
    names = set(insp.get_table_names())
    for table in _CATALOG_TABLES:
        assert table in names, f"missing catalog table: {table}"


def test_catalog_entity_columns(v2_env):
    insp = inspect(get_engine())
    cols = {c["name"] for c in insp.get_columns("catalog_entity")}
    expected = {
        "id",
        "catalog_id",
        "name",
        "display_name",
        "tier",
        "entry_kind",
        "parent_entity_id",
        "discriminator_attribute",
        "discriminator_value",
        "purpose",
        "business_context",
        "data_model_role",
        "typically_required",
        "is_deleted",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols)


def test_catalog_attribute_columns(v2_env):
    insp = inspect(get_engine())
    cols = {c["name"] for c in insp.get_columns("catalog_attribute")}
    expected = {
        "id",
        "catalog_entity_id",
        "name",
        "display_name",
        "type",
        "required",
        "max_length",
        "reference_target",
        "description",
        "usage",
        "notes",
        "order_index",
        "is_deleted",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols)


def test_catalog_id_unique(v2_env):
    """catalog_entity.catalog_id is UNIQUE."""
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(_make_entity("account"))
            s.add(_make_entity("account"))


def test_attribute_unique_per_entity(v2_env):
    """(catalog_entity_id, name) is UNIQUE on catalog_attribute."""
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        ent_id = ent.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(_make_attribute(ent_id, "name"))
            s.add(_make_attribute(ent_id, "name"))


def test_entry_kind_check_constraint(v2_env):
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(_make_entity("bad", entry_kind="bogus"))


def test_data_model_role_check_constraint(v2_env):
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(_make_entity("bad", data_model_role="nope"))


def test_tier_check_constraint(v2_env):
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(_make_entity("bad", tier=6))


def test_attribute_type_check_constraint(v2_env):
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        ent_id = ent.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(_make_attribute(ent_id, "name", type="link"))


def test_attribute_presence_status_check(v2_env):
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        attr = _make_attribute(ent.id, "name")
        s.add(attr)
        s.flush()
        attr_id = attr.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                CatalogAttributePresence(
                    catalog_attribute_id=attr_id,
                    system="salesforce",
                    status="missing",
                )
            )


def test_system_check_constraint(v2_env):
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        attr = _make_attribute(ent.id, "name")
        s.add(attr)
        s.flush()
        attr_id = attr.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                CatalogAttributePresence(
                    catalog_attribute_id=attr_id,
                    system="zoho",
                    status="standard",
                )
            )


def test_relationship_cardinality_check(v2_env):
    with session_scope() as s:
        src = _make_entity("account")
        tgt = _make_entity("contact")
        s.add_all([src, tgt])
        s.flush()
        sid, tid = src.id, tgt.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                CatalogRelationship(
                    source_entity_id=sid,
                    target_entity_id=tid,
                    cardinality="quadratic",
                    role="parent",
                    description="bad",
                )
            )


def test_relationship_role_check(v2_env):
    with session_scope() as s:
        src = _make_entity("account")
        tgt = _make_entity("contact")
        s.add_all([src, tgt])
        s.flush()
        sid, tid = src.id, tgt.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                CatalogRelationship(
                    source_entity_id=sid,
                    target_entity_id=tid,
                    cardinality="one-to-many",
                    role="bogus",
                    description="bad",
                )
            )


def test_attribute_presence_unique_per_system(v2_env):
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        attr = _make_attribute(ent.id, "name")
        s.add(attr)
        s.flush()
        attr_id = attr.id
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(
                CatalogAttributePresence(
                    catalog_attribute_id=attr_id,
                    system="salesforce",
                    status="standard",
                )
            )
            s.add(
                CatalogAttributePresence(
                    catalog_attribute_id=attr_id,
                    system="salesforce",
                    status="custom",
                )
            )


def test_cascade_delete_attribute_children(v2_env):
    """Deleting an attribute cascades to enum_values, synonyms, presence rows."""
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        attr = _make_attribute(ent.id, "name")
        s.add(attr)
        s.flush()
        s.add(CatalogAttributeEnumValue(catalog_attribute_id=attr.id, value="A"))
        s.add(CatalogAttributeSynonym(catalog_attribute_id=attr.id, synonym="x"))
        s.add(
            CatalogAttributePresence(
                catalog_attribute_id=attr.id,
                system="salesforce",
                status="standard",
            )
        )
        s.flush()
        attr_id = attr.id
        s.delete(attr)
        s.flush()
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogAttributeEnumValue)
                .where(CatalogAttributeEnumValue.catalog_attribute_id == attr_id)
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogAttributeSynonym)
                .where(CatalogAttributeSynonym.catalog_attribute_id == attr_id)
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogAttributePresence)
                .where(CatalogAttributePresence.catalog_attribute_id == attr_id)
            )
            == 0
        )


def test_cascade_delete_entity_children(v2_env):
    """Deleting an entity cascades to all entity-child rows including attributes."""
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        s.add(CatalogEntitySynonym(catalog_entity_id=ent.id, synonym="Company"))
        s.add(
            CatalogEntitySystem(
                catalog_entity_id=ent.id,
                system="salesforce",
                system_name="Account",
                is_standard="true",
            )
        )
        s.add(
            CatalogSource(
                catalog_entity_id=ent.id,
                title="t",
                url="https://example.com",
                order_index=0,
            )
        )
        s.add(_make_attribute(ent.id, "name"))
        s.flush()
        ent_id = ent.id
        s.delete(ent)
        s.flush()
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogEntitySynonym)
                .where(CatalogEntitySynonym.catalog_entity_id == ent_id)
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogEntitySystem)
                .where(CatalogEntitySystem.catalog_entity_id == ent_id)
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogSource)
                .where(CatalogSource.catalog_entity_id == ent_id)
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(CatalogAttribute)
                .where(CatalogAttribute.catalog_entity_id == ent_id)
            )
            == 0
        )


def test_is_standard_admits_partial(v2_env):
    """is_standard on catalog_entity_system admits the 'partial' edge case."""
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        s.add(
            CatalogEntitySystem(
                catalog_entity_id=ent.id,
                system="hubspot",
                system_name="Company",
                is_standard="partial",
            )
        )
        s.flush()


def test_mechanism_admits_null(v2_env):
    """mechanism is NULL for universals; the CHECK admits NULL."""
    with session_scope() as s:
        ent = _make_entity("account")
        s.add(ent)
        s.flush()
        s.add(
            CatalogEntitySystem(
                catalog_entity_id=ent.id,
                system="salesforce",
                system_name="Account",
                is_standard="true",
                mechanism=None,
            )
        )
        s.flush()


# ---------- helpers ----------


def _make_entity(catalog_id: str, **overrides) -> CatalogEntity:
    base = dict(
        catalog_id=catalog_id,
        name=catalog_id.capitalize(),
        display_name=catalog_id.capitalize(),
        tier=1,
        entry_kind="universal",
        purpose="p",
        business_context="bc",
        data_model_role="anchor",
        typically_required=False,
        is_deleted=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return CatalogEntity(**base)


def _make_attribute(entity_id: int, name: str, **overrides) -> CatalogAttribute:
    base = dict(
        catalog_entity_id=entity_id,
        name=name,
        display_name=name.replace("_", " ").title(),
        type="string",
        required=False,
        description="d",
        usage="u",
        order_index=0,
        is_deleted=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return CatalogAttribute(**base)
