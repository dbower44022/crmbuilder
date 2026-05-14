"""Catalog loader unit tests against fixture YAMLs.

The full-catalog integration test (Commit C) lives separately; this
suite uses a small fixture with 3 universals + 2 subclasses to keep
runtime fast while still exercising every loader code path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import (
    CatalogAttribute,
    CatalogAttributeEnumValue,
    CatalogAttributePresence,
    CatalogAttributeSynonym,
    CatalogEntity,
    CatalogEntitySynonym,
    CatalogEntitySystem,
    CatalogRelationship,
    CatalogRelationshipPresence,
    CatalogSource,
)
from crmbuilder_v2.bootstrap.catalog_loader import (
    CatalogLoaderError,
    load_catalog,
)
from sqlalchemy import func, select


_FIXTURES = Path(__file__).parent / "fixtures" / "catalog"


def test_full_fixture_load(v2_env):
    with session_scope(export=False) as s:
        report = load_catalog(s, _FIXTURES)
    assert report.entities_inserted == 5
    assert report.entities_updated == 0
    assert report.validation_failures == []

    with session_scope(export=False) as s:
        assert s.scalar(select(func.count()).select_from(CatalogEntity)) == 5
        # 2 + 1 + 1 + 1 + 1 = 6 attributes total across fixtures
        assert s.scalar(select(func.count()).select_from(CatalogAttribute)) == 6


def test_universals_loaded_with_metadata(v2_env):
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURES)

    with session_scope(export=False) as s:
        acct = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "account")
        )
        assert acct is not None
        assert acct.entry_kind == "universal"
        assert acct.parent_entity_id is None
        assert acct.data_model_role == "anchor"
        assert acct.typically_required is True
        assert acct.tier == 1
        assert "Test fixture" in acct.purpose


def test_subclass_parent_resolution(v2_env):
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURES)

    with session_scope(export=False) as s:
        nonprofit = s.scalar(
            select(CatalogEntity).where(
                CatalogEntity.catalog_id == "account-nonprofit"
            )
        )
        account = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "account")
        )
        assert nonprofit.entry_kind == "subclass"
        assert nonprofit.parent_entity_id == account.id
        assert nonprofit.discriminator_attribute == "accountType"
        assert nonprofit.discriminator_value == "Nonprofit Organization"


def test_donation_major_gift_discriminator(v2_env):
    """The v0.10 fix: donation-major-gift discriminates on donationType,
    which now exists on donation.yaml as an enum attribute."""
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURES)

    with session_scope(export=False) as s:
        major = s.scalar(
            select(CatalogEntity).where(
                CatalogEntity.catalog_id == "donation-major-gift"
            )
        )
        donation = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "donation")
        )
        assert major.parent_entity_id == donation.id
        assert major.discriminator_attribute == "donationType"
        assert major.discriminator_value == "Major Gift"

        # And donation.yaml must contain the donationType attribute it points to.
        dtype = s.scalar(
            select(CatalogAttribute).where(
                (CatalogAttribute.catalog_entity_id == donation.id)
                & (CatalogAttribute.name == "donationType")
            )
        )
        assert dtype is not None
        enum_vals = list(
            s.scalars(
                select(CatalogAttributeEnumValue.value)
                .where(CatalogAttributeEnumValue.catalog_attribute_id == dtype.id)
                .order_by(CatalogAttributeEnumValue.order_index)
            )
        )
        assert "Major Gift" in enum_vals


def test_attribute_presence_carries_api_name(v2_env):
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURES)

    with session_scope(export=False) as s:
        acct = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "account")
        )
        attr = s.scalar(
            select(CatalogAttribute).where(
                (CatalogAttribute.catalog_entity_id == acct.id)
                & (CatalogAttribute.name == "accountName")
            )
        )
        pres = list(
            s.scalars(
                select(CatalogAttributePresence).where(
                    CatalogAttributePresence.catalog_attribute_id == attr.id
                )
            )
        )
        by_sys = {p.system: p for p in pres}
        assert by_sys["salesforce"].status == "standard"
        assert by_sys["salesforce"].api_name == "Name"
        assert by_sys["civicrm"].api_name == "organization_name"


def test_relationships_loaded(v2_env):
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURES)

    with session_scope(export=False) as s:
        acct = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "account")
        )
        contact = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "contact")
        )
        rel = s.scalar(
            select(CatalogRelationship).where(
                (CatalogRelationship.source_entity_id == acct.id)
                & (CatalogRelationship.target_entity_id == contact.id)
            )
        )
        assert rel is not None
        assert rel.cardinality == "one-to-many"
        assert rel.role == "parent"

        pres = list(
            s.scalars(
                select(CatalogRelationshipPresence).where(
                    CatalogRelationshipPresence.catalog_relationship_id == rel.id
                )
            )
        )
        assert len(pres) == 3  # salesforce, hubspot, civicrm


def test_idempotent_rerun(v2_env):
    """Running the loader twice yields the same final state."""
    with session_scope(export=False) as s:
        r1 = load_catalog(s, _FIXTURES)
    with session_scope(export=False) as s:
        counts_after_first = _count_all_catalog_rows(s)

    with session_scope(export=False) as s:
        r2 = load_catalog(s, _FIXTURES)
    with session_scope(export=False) as s:
        counts_after_second = _count_all_catalog_rows(s)

    assert r1.entities_inserted == 5
    assert r1.entities_updated == 0
    assert r2.entities_inserted == 0
    assert r2.entities_updated == 5
    assert counts_after_first == counts_after_second


def test_yaml_edit_then_reload(v2_env, tmp_path):
    """Editing a fixture and reloading updates the row, not duplicates it."""
    import shutil

    work = tmp_path / "catalog"
    shutil.copytree(_FIXTURES, work)

    with session_scope(export=False) as s:
        load_catalog(s, work)

    # Tweak account.yaml: bump display_name
    yaml_path = work / "account.yaml"
    text = yaml_path.read_text()
    yaml_path.write_text(
        text.replace("display_name: Account", "display_name: Account (Edited)")
    )

    with session_scope(export=False) as s:
        r = load_catalog(s, work)
    assert r.entities_updated >= 1

    with session_scope(export=False) as s:
        acct = s.scalar(
            select(CatalogEntity).where(CatalogEntity.catalog_id == "account")
        )
        assert acct.display_name == "Account (Edited)"
        # Still only 5 entities; no duplication.
        assert s.scalar(select(func.count()).select_from(CatalogEntity)) == 5


def test_validation_failure_rolls_back(v2_env, tmp_path):
    """A bad subclass parent_entity reference triggers CatalogLoaderError."""
    import shutil

    work = tmp_path / "catalog"
    shutil.copytree(_FIXTURES, work)

    # Break the subclass — point at a non-existent parent.
    bad = work / "subclasses" / "account-nonprofit.yaml"
    bad.write_text(bad.read_text().replace("parent_entity: account", "parent_entity: nonexistent"))

    with pytest.raises(CatalogLoaderError):
        with session_scope(export=False) as s:
            load_catalog(s, work)

    # Database rolled back: no entities loaded.
    with session_scope(export=False) as s:
        assert s.scalar(select(func.count()).select_from(CatalogEntity)) == 0


def test_invalid_attribute_type_rejected(v2_env, tmp_path):
    import shutil

    work = tmp_path / "catalog"
    shutil.copytree(_FIXTURES, work)
    contact = work / "contact.yaml"
    contact.write_text(contact.read_text().replace("type: string", "type: bogus"))

    with pytest.raises(CatalogLoaderError, match="bad type"):
        with session_scope(export=False) as s:
            load_catalog(s, work)


def test_invalid_presence_status_rejected(v2_env, tmp_path):
    import shutil

    work = tmp_path / "catalog"
    shutil.copytree(_FIXTURES, work)
    contact = work / "contact.yaml"
    contact.write_text(
        contact.read_text().replace("status: standard", "status: bogus")
    )

    with pytest.raises(CatalogLoaderError, match="bad status"):
        with session_scope(export=False) as s:
            load_catalog(s, work)


def test_subclass_without_parent_entity_rejected(v2_env, tmp_path):
    import shutil

    work = tmp_path / "catalog"
    shutil.copytree(_FIXTURES, work)
    bad = work / "subclasses" / "account-nonprofit.yaml"
    text = bad.read_text()
    # Drop the parent_entity line.
    text = "\n".join(line for line in text.splitlines() if not line.startswith("parent_entity:"))
    bad.write_text(text)

    with pytest.raises(CatalogLoaderError, match="subclass missing parent_entity"):
        with session_scope(export=False) as s:
            load_catalog(s, work)


def test_missing_yaml_directory_rejected(v2_env, tmp_path):
    with pytest.raises(CatalogLoaderError, match="catalog directory not found"):
        with session_scope(export=False) as s:
            load_catalog(s, tmp_path / "does-not-exist")


# ---------- helpers ----------


def _count_all_catalog_rows(s) -> dict[str, int]:
    return {
        "entity": s.scalar(select(func.count()).select_from(CatalogEntity)),
        "entity_synonym": s.scalar(select(func.count()).select_from(CatalogEntitySynonym)),
        "entity_system": s.scalar(select(func.count()).select_from(CatalogEntitySystem)),
        "source": s.scalar(select(func.count()).select_from(CatalogSource)),
        "attribute": s.scalar(select(func.count()).select_from(CatalogAttribute)),
        "attribute_enum_value": s.scalar(
            select(func.count()).select_from(CatalogAttributeEnumValue)
        ),
        "attribute_synonym": s.scalar(
            select(func.count()).select_from(CatalogAttributeSynonym)
        ),
        "attribute_presence": s.scalar(
            select(func.count()).select_from(CatalogAttributePresence)
        ),
        "relationship": s.scalar(select(func.count()).select_from(CatalogRelationship)),
        "relationship_presence": s.scalar(
            select(func.count()).select_from(CatalogRelationshipPresence)
        ),
    }
