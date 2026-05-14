"""Catalog write-endpoint tests: create / update / patch / delete on
entities and attributes."""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.bootstrap.catalog_loader import load_catalog


_FIXTURE_CATALOG = (
    Path(__file__).resolve().parents[1] / "bootstrap" / "fixtures" / "catalog"
)


def _minimal_entity_body(catalog_id="widget", **overrides):
    body = {
        "catalog_id": catalog_id,
        "name": "Widget",
        "display_name": "Widget",
        "tier": 3,
        "entry_kind": "universal",
        "data_model_role": "anchor",
    }
    body.update(overrides)
    return body


# ---------- create entity ----------


def test_create_minimal_entity(client):
    r = client.post("/catalog/entities", json=_minimal_entity_body())
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["catalog_id"] == "widget"
    assert data["tier"] == 3


def test_create_then_get(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.get("/catalog/entities/widget")
    assert r.status_code == 200
    assert r.json()["data"]["catalog_id"] == "widget"


def test_create_duplicate_returns_409(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.post("/catalog/entities", json=_minimal_entity_body())
    assert r.status_code == 409


def test_create_invalid_data_model_role(client):
    r = client.post(
        "/catalog/entities",
        json=_minimal_entity_body(data_model_role="bogus"),
    )
    assert r.status_code == 400


def test_create_invalid_tier(client):
    r = client.post(
        "/catalog/entities", json=_minimal_entity_body(tier=99)
    )
    assert r.status_code == 400


def test_create_extra_field_rejected(client):
    body = _minimal_entity_body()
    body["mystery"] = "nope"
    r = client.post("/catalog/entities", json=body)
    # Pydantic extra='forbid' returns 422
    assert r.status_code == 422


def test_create_subclass_with_bad_parent_returns_400(client):
    body = _minimal_entity_body(
        catalog_id="nonprofit",
        entry_kind="subclass",
        parent_entity="nonexistent",
        discriminator_attribute="type",
        discriminator_value="x",
    )
    r = client.post("/catalog/entities", json=body)
    assert r.status_code == 400


def test_create_subclass_with_valid_parent(client):
    # First create the parent.
    client.post("/catalog/entities", json=_minimal_entity_body())
    # Then create a subclass.
    body = _minimal_entity_body(
        catalog_id="big-widget",
        name="Big Widget",
        display_name="Big Widget",
        entry_kind="subclass",
        parent_entity="widget",
        discriminator_attribute="size",
        discriminator_value="large",
    )
    r = client.post("/catalog/entities", json=body)
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["parent_catalog_id"] == "widget"
    assert data["discriminator_attribute"] == "size"


def test_create_with_full_nested_payload(client):
    body = _minimal_entity_body(
        common_synonyms=["Thing", "Doohickey"],
        systems=[
            {
                "system": "salesforce",
                "name": "Widget__c",
                "api_name": "Widget__c",
                "is_standard": "false",
            }
        ],
        sources=[{"title": "Widget Docs", "url": "https://example.com/widget"}],
        attributes=[
            {
                "name": "color",
                "display_name": "Color",
                "type": "string",
                "required": True,
                "description": "Color of the widget",
                "usage": "Display",
                "presence": [
                    {"system": "salesforce", "status": "custom"}
                ],
                "common_synonyms": ["hue"],
            }
        ],
    )
    r = client.post("/catalog/entities", json=body)
    assert r.status_code == 201
    data = r.json()["data"]
    assert "Doohickey" in data["common_synonyms"]
    assert len(data["systems"]) == 1
    assert data["systems"][0]["api_name"] == "Widget__c"
    assert len(data["attributes"]) == 1
    color = data["attributes"][0]
    assert color["name"] == "color"
    assert "hue" in color["common_synonyms"]


# ---------- PUT (full replace) ----------


def test_put_replaces_nested_data(client):
    body = _minimal_entity_body(
        common_synonyms=["Thing"],
        attributes=[
            {
                "name": "color",
                "display_name": "Color",
                "type": "string",
                "required": True,
            }
        ],
    )
    client.post("/catalog/entities", json=body)

    new_body = _minimal_entity_body(
        common_synonyms=["Doodad"],  # different synonym
        attributes=[
            {
                "name": "shape",  # different attribute
                "display_name": "Shape",
                "type": "string",
            }
        ],
    )
    r = client.put("/catalog/entities/widget", json=new_body)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["common_synonyms"] == ["Doodad"]
    assert {a["name"] for a in data["attributes"]} == {"shape"}


def test_put_immutable_catalog_id(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    bad = _minimal_entity_body(catalog_id="renamed")
    r = client.put("/catalog/entities/widget", json=bad)
    assert r.status_code == 400


def test_put_nonexistent_returns_404(client):
    r = client.put("/catalog/entities/none", json=_minimal_entity_body(catalog_id="none"))
    assert r.status_code == 404


# ---------- PATCH ----------


def test_patch_scalar_fields(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.patch(
        "/catalog/entities/widget",
        json={"display_name": "Big Widget", "typically_required": True},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["display_name"] == "Big Widget"
    assert data["typically_required"] is True


def test_patch_unknown_field_returns_422(client):
    """Pydantic extra='forbid' rejects unknown fields at body validation."""
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.patch("/catalog/entities/widget", json={"mystery": "nope"})
    assert r.status_code == 422


def test_patch_invalid_tier(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.patch("/catalog/entities/widget", json={"tier": 99})
    assert r.status_code == 400


def test_patch_empty_body_is_noop(client):
    """An empty PATCH should not change anything."""
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.patch("/catalog/entities/widget", json={})
    assert r.status_code == 200
    assert r.json()["data"]["catalog_id"] == "widget"


# ---------- DELETE (soft-delete) ----------


def test_delete_is_soft(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    r = client.delete("/catalog/entities/widget")
    assert r.status_code == 200
    assert r.json()["data"]["is_deleted"] is True


def test_delete_excludes_from_list(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    client.delete("/catalog/entities/widget")
    r = client.get("/catalog/entities")
    cids = [row["catalog_id"] for row in r.json()["data"]]
    assert "widget" not in cids


def test_delete_then_get_returns_404(client):
    """Soft-deleted entity is hidden from get_entity (consistent with list)."""
    client.post("/catalog/entities", json=_minimal_entity_body())
    client.delete("/catalog/entities/widget")
    r = client.get("/catalog/entities/widget")
    assert r.status_code == 404


def test_delete_include_deleted_param(client):
    client.post("/catalog/entities", json=_minimal_entity_body())
    client.delete("/catalog/entities/widget")
    r = client.get("/catalog/entities?include_deleted=true")
    cids = [row["catalog_id"] for row in r.json()["data"]]
    assert "widget" in cids


# ---------- Attribute writes ----------


@pytest.fixture
def with_widget(client):
    """Helper: pre-create a widget entity in the per-test DB."""
    client.post("/catalog/entities", json=_minimal_entity_body())
    return client


def test_create_attribute(with_widget):
    body = {
        "name": "color",
        "display_name": "Color",
        "type": "string",
        "required": True,
        "presence": [{"system": "salesforce", "status": "custom"}],
    }
    r = with_widget.post(
        "/catalog/entities/widget/attributes", json=body
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["name"] == "color"
    assert data["required"] is True
    assert data["presence"][0]["system"] == "salesforce"


def test_create_attribute_duplicate_returns_409(with_widget):
    body = {"name": "color", "display_name": "Color", "type": "string"}
    with_widget.post("/catalog/entities/widget/attributes", json=body)
    r = with_widget.post("/catalog/entities/widget/attributes", json=body)
    assert r.status_code == 409


def test_create_attribute_bad_type(with_widget):
    body = {"name": "color", "display_name": "Color", "type": "bogus"}
    r = with_widget.post("/catalog/entities/widget/attributes", json=body)
    assert r.status_code == 400


def test_put_attribute_replaces_presence(with_widget):
    body = {
        "name": "color",
        "display_name": "Color",
        "type": "string",
        "presence": [{"system": "salesforce", "status": "custom"}],
    }
    with_widget.post("/catalog/entities/widget/attributes", json=body)

    new_body = {
        "name": "color",
        "display_name": "Color",
        "type": "string",
        "presence": [{"system": "hubspot", "status": "custom"}],
    }
    r = with_widget.put(
        "/catalog/entities/widget/attributes/color", json=new_body
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert {p["system"] for p in data["presence"]} == {"hubspot"}


def test_patch_attribute_scalar(with_widget):
    body = {"name": "color", "display_name": "Color", "type": "string"}
    with_widget.post("/catalog/entities/widget/attributes", json=body)
    r = with_widget.patch(
        "/catalog/entities/widget/attributes/color",
        json={"required": True, "description": "Updated"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["required"] is True
    assert data["description"] == "Updated"


def test_delete_attribute_is_soft(with_widget):
    body = {"name": "color", "display_name": "Color", "type": "string"}
    with_widget.post("/catalog/entities/widget/attributes", json=body)
    r = with_widget.delete("/catalog/entities/widget/attributes/color")
    assert r.status_code == 200
    assert r.json()["data"]["is_deleted"] is True


def test_get_attribute_after_delete_returns_404(with_widget):
    body = {"name": "color", "display_name": "Color", "type": "string"}
    with_widget.post("/catalog/entities/widget/attributes", json=body)
    with_widget.delete("/catalog/entities/widget/attributes/color")
    r = with_widget.get("/catalog/entities/widget/attributes/color")
    assert r.status_code == 404


# ---------- Update with relationships against a populated DB ----------


def test_update_with_relationship_to_loaded_entity(client):
    """Create a new entity referencing a fixture entity as relationship target."""
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURE_CATALOG)

    body = _minimal_entity_body(
        catalog_id="widget",
        relationships=[
            {
                "target": "account",  # exists in fixture
                "cardinality": "many-to-one",
                "role": "child",
                "description": "Widget belongs to an Account.",
                "presence": [
                    {"system": "salesforce", "status": "custom"}
                ],
            }
        ],
    )
    r = client.post("/catalog/entities", json=body)
    assert r.status_code == 201
    rels = r.json()["data"]["relationships"]
    assert len(rels) == 1
    assert rels[0]["target"] == "account"
    assert rels[0]["presence"][0]["system"] == "salesforce"


def test_create_with_relationship_to_unknown_target_returns_400(client):
    body = _minimal_entity_body(
        relationships=[
            {
                "target": "ghost",
                "cardinality": "many-to-one",
                "role": "child",
                "description": "x",
            }
        ],
    )
    r = client.post("/catalog/entities", json=body)
    assert r.status_code == 400
