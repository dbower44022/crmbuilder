"""Pydantic schema tests for the catalog API contract.

These tests don't hit the database or the FastAPI app — they exercise
the Pydantic models in isolation so the request/response contract is
verified independent of the HTTP plumbing.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.schemas import (
    CatalogAttributeCreateIn,
    CatalogAttributeIn,
    CatalogAttributePatchIn,
    CatalogAttributeUpdateIn,
    CatalogEntityCreateIn,
    CatalogEntityPatchIn,
    CatalogEntityUpdateIn,
    CatalogGapCheckIn,
    CatalogPresenceIn,
    CatalogRelationshipIn,
    CatalogSourceIn,
    CatalogSystemIn,
)
from pydantic import ValidationError


def test_catalog_entity_create_minimal():
    """A bare-minimum create body parses cleanly."""
    body = CatalogEntityCreateIn(
        catalog_id="account",
        name="Account",
        display_name="Account",
        tier=1,
        entry_kind="universal",
        data_model_role="anchor",
    )
    assert body.catalog_id == "account"
    assert body.attributes == []
    assert body.relationships == []


def test_catalog_entity_create_full_nested():
    body = CatalogEntityCreateIn(
        catalog_id="account",
        name="Account",
        display_name="Account",
        tier=1,
        entry_kind="universal",
        data_model_role="anchor",
        purpose="The org anchor.",
        business_context="Anchors revenue data.",
        typically_required=True,
        common_synonyms=["Company", "Organization"],
        systems=[
            CatalogSystemIn(
                system="salesforce",
                name="Account",
                api_name="Account",
                is_standard="true",
            ),
        ],
        sources=[
            CatalogSourceIn(title="SF Docs", url="https://example.com"),
        ],
        attributes=[
            CatalogAttributeIn(
                name="accountName",
                display_name="Account Name",
                type="string",
                required=True,
                description="Primary identifier.",
                usage="Search, dedupe.",
                presence=[
                    CatalogPresenceIn(
                        system="salesforce", status="standard", api_name="Name"
                    ),
                ],
            ),
        ],
        relationships=[
            CatalogRelationshipIn(
                target="contact",
                cardinality="one-to-many",
                role="parent",
                description="Account has many contacts.",
            ),
        ],
    )
    assert len(body.attributes) == 1
    assert body.attributes[0].name == "accountName"
    assert body.attributes[0].presence[0].api_name == "Name"


def test_entry_kind_literal_enforced():
    with pytest.raises(ValidationError):
        CatalogEntityCreateIn(
            catalog_id="x",
            name="x",
            display_name="X",
            tier=1,
            entry_kind="bogus",  # not in Literal['universal','subclass']
            data_model_role="anchor",
        )


def test_extra_field_rejected():
    """`extra='forbid'` is inherited; unknown fields trigger 422-class errors."""
    with pytest.raises(ValidationError):
        CatalogEntityCreateIn(
            catalog_id="x",
            name="x",
            display_name="X",
            tier=1,
            entry_kind="universal",
            data_model_role="anchor",
            mystery_field="nope",
        )


def test_entity_update_in_same_shape_as_create():
    """PUT (full replace) accepts the same body as POST (create)."""
    payload = dict(
        catalog_id="account",
        name="Account",
        display_name="Account",
        tier=1,
        entry_kind="universal",
        data_model_role="anchor",
    )
    create = CatalogEntityCreateIn(**payload)
    update = CatalogEntityUpdateIn(**payload)
    assert create.model_dump() == update.model_dump()


def test_entity_patch_in_all_optional():
    """An empty PATCH body should validate; all fields default to None."""
    body = CatalogEntityPatchIn()
    dumped = body.model_dump(exclude_none=True)
    assert dumped == {}


def test_entity_patch_in_supports_partial():
    body = CatalogEntityPatchIn(typically_required=True, display_name="New")
    dumped = body.model_dump(exclude_none=True)
    assert dumped == {"typically_required": True, "display_name": "New"}


def test_attribute_patch_all_optional():
    body = CatalogAttributePatchIn()
    assert body.model_dump(exclude_none=True) == {}


def test_attribute_create_in_minimal():
    body = CatalogAttributeCreateIn(
        name="phone",
        display_name="Phone",
        type="phone",
    )
    assert body.required is False
    assert body.enum_values == []


def test_attribute_update_in_is_full_replace():
    body = CatalogAttributeUpdateIn(
        name="phone",
        display_name="Phone",
        type="phone",
        enum_values=[],
        presence=[CatalogPresenceIn(system="hubspot", status="custom")],
    )
    assert body.presence[0].system == "hubspot"


def test_gap_check_in_valid():
    body = CatalogGapCheckIn(
        based_on_catalog_id="account",
        draft_attribute_names=["accountName", "industry"],
    )
    assert body.min_systems == 5  # default


def test_gap_check_in_min_systems_bounds():
    with pytest.raises(ValidationError):
        CatalogGapCheckIn(
            based_on_catalog_id="account",
            draft_attribute_names=[],
            min_systems=8,  # > 7
        )
    with pytest.raises(ValidationError):
        CatalogGapCheckIn(
            based_on_catalog_id="account",
            draft_attribute_names=[],
            min_systems=0,
        )


def test_presence_in_optional_api_name():
    p = CatalogPresenceIn(system="attio", status="custom")
    assert p.api_name is None


def test_relationship_in_default_presence():
    r = CatalogRelationshipIn(
        target="contact",
        cardinality="one-to-many",
        role="parent",
    )
    assert r.presence == []
    assert r.description == ""


def test_round_trip_json():
    """A populated body round-trips through model_dump → model_validate."""
    body = CatalogEntityCreateIn(
        catalog_id="account",
        name="Account",
        display_name="Account",
        tier=1,
        entry_kind="universal",
        data_model_role="anchor",
        attributes=[
            CatalogAttributeIn(
                name="accountName",
                display_name="Account Name",
                type="string",
                required=True,
            ),
        ],
    )
    dumped = body.model_dump()
    again = CatalogEntityCreateIn.model_validate(dumped)
    assert again == body
