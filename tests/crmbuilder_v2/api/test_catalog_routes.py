"""Catalog read-endpoint tests.

Uses a fixture that loads a small sample catalog (the same fixture
catalog used by the loader unit tests) into the per-test database, then
exercises every read endpoint.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.bootstrap.catalog_loader import load_catalog


_FIXTURE_CATALOG = (
    Path(__file__).resolve().parents[1] / "bootstrap" / "fixtures" / "catalog"
)


@pytest.fixture
def loaded_client(client):
    """A FastAPI TestClient with the fixture catalog pre-loaded."""
    with session_scope() as s:
        load_catalog(s, _FIXTURE_CATALOG)
    return client


# ---------- list endpoint ----------


def test_list_entities(loaded_client):
    r = loaded_client.get("/catalog/entities")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 5
    cids = {row["catalog_id"] for row in rows}
    assert cids == {
        "account",
        "contact",
        "donation",
        "account-nonprofit",
        "donation-major-gift",
    }


def test_list_entities_summary_shape(loaded_client):
    r = loaded_client.get("/catalog/entities")
    rows = r.json()["data"]
    acct = next(r for r in rows if r["catalog_id"] == "account")
    for key in (
        "catalog_id",
        "name",
        "display_name",
        "tier",
        "entry_kind",
        "data_model_role",
        "typically_required",
        "parent_catalog_id",
    ):
        assert key in acct
    assert acct["parent_catalog_id"] is None  # universal


def test_list_filter_tier(loaded_client):
    r = loaded_client.get("/catalog/entities?tier=1")
    rows = r.json()["data"]
    assert {row["catalog_id"] for row in rows} == {
        "account",
        "contact",
        "account-nonprofit",
    }


def test_list_filter_entry_kind(loaded_client):
    r = loaded_client.get("/catalog/entities?entry_kind=subclass")
    rows = r.json()["data"]
    assert {row["catalog_id"] for row in rows} == {
        "account-nonprofit",
        "donation-major-gift",
    }


def test_list_filter_parent(loaded_client):
    r = loaded_client.get("/catalog/entities?parent_entity=account")
    rows = r.json()["data"]
    assert [row["catalog_id"] for row in rows] == ["account-nonprofit"]
    assert rows[0]["parent_catalog_id"] == "account"


def test_list_filter_system(loaded_client):
    r = loaded_client.get("/catalog/entities?system=civicrm")
    rows = r.json()["data"]
    cids = {row["catalog_id"] for row in rows}
    # account, contact have civicrm? account does; contact doesn't in fixture.
    # donation has civicrm.
    assert "account" in cids
    assert "donation" in cids


def test_list_filter_data_model_role(loaded_client):
    r = loaded_client.get("/catalog/entities?data_model_role=anchor")
    rows = r.json()["data"]
    assert {row["catalog_id"] for row in rows} == {
        "account",
        "contact",
        "account-nonprofit",
    }


def test_list_unknown_system_rejected(loaded_client):
    r = loaded_client.get("/catalog/entities?system=zoho")
    assert r.status_code == 400


# ---------- detail ----------


def test_get_entity_full_nested(loaded_client):
    r = loaded_client.get("/catalog/entities/account")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["catalog_id"] == "account"
    assert data["entry_kind"] == "universal"
    assert "common_synonyms" in data
    assert "Company" in data["common_synonyms"]
    assert "systems" in data
    assert len(data["systems"]) == 3
    assert {s["system"] for s in data["systems"]} == {"salesforce", "hubspot", "civicrm"}
    assert "attributes" in data
    attr_names = {a["name"] for a in data["attributes"]}
    assert attr_names == {"accountName", "accountType"}
    assert "relationships" in data
    rel = data["relationships"][0]
    assert rel["target"] == "contact"
    assert rel["cardinality"] == "one-to-many"


def test_get_entity_subclass_parent(loaded_client):
    r = loaded_client.get("/catalog/entities/account-nonprofit")
    data = r.json()["data"]
    assert data["entry_kind"] == "subclass"
    assert data["parent_catalog_id"] == "account"
    assert data["discriminator_attribute"] == "accountType"
    assert data["discriminator_value"] == "Nonprofit Organization"


def test_get_entity_not_found(loaded_client):
    r = loaded_client.get("/catalog/entities/nope")
    assert r.status_code == 404


def test_get_attribute(loaded_client):
    r = loaded_client.get("/catalog/entities/account/attributes/accountName")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "accountName"
    assert data["type"] == "string"
    assert data["required"] is True
    pres_by_sys = {p["system"]: p for p in data["presence"]}
    assert pres_by_sys["salesforce"]["api_name"] == "Name"


def test_get_attribute_with_enum_values(loaded_client):
    r = loaded_client.get("/catalog/entities/account/attributes/accountType")
    data = r.json()["data"]
    assert "Customer" in data["enum_values"]
    assert "Nonprofit Organization" in data["enum_values"]


def test_get_attribute_not_found(loaded_client):
    r = loaded_client.get("/catalog/entities/account/attributes/nope")
    assert r.status_code == 404


# ---------- search ----------


def test_search_entity_exact_match_ranks_first(loaded_client):
    r = loaded_client.get("/catalog/search?q=account")
    hits = r.json()["data"]
    assert hits[0]["catalog_id"] == "account"


def test_search_synonym_hit(loaded_client):
    r = loaded_client.get("/catalog/search?q=Company")
    hits = r.json()["data"]
    cids = [h["catalog_id"] for h in hits]
    assert "account" in cids


def test_search_attribute_hit(loaded_client):
    r = loaded_client.get("/catalog/search?q=accountType")
    hits = r.json()["data"]
    found = next(
        h for h in hits if h.get("kind") == "attribute" and h["attribute_name"] == "accountType"
    )
    assert found["catalog_id"] == "account"


def test_search_limit(loaded_client):
    r = loaded_client.get("/catalog/search?q=a&limit=3")
    hits = r.json()["data"]
    assert len(hits) <= 3


def test_search_empty_query(loaded_client):
    r = loaded_client.get("/catalog/search?q=")
    # FastAPI rejects min_length=1 violations with 422
    assert r.status_code in (400, 422)


# ---------- cross-system map ----------


def test_cross_system_map_all(loaded_client):
    r = loaded_client.get("/catalog/cross-system-map/account")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["entity"]["catalog_id"] == "account"
    # All 7 systems present even though only 3 have entity-level rows.
    assert len(data["systems"]) == 7
    sf = data["systems"]["salesforce"]
    assert sf["entity_name"] == "Account"
    sf_attrs = {a["catalog_name"]: a for a in sf["attributes"]}
    assert sf_attrs["accountName"]["api_name"] == "Name"
    # Attio missing in fixture → status defaults to 'absent', api_name None
    attio = data["systems"]["attio"]
    attio_attrs = {a["catalog_name"]: a for a in attio["attributes"]}
    assert attio_attrs["accountName"]["status"] == "absent"


def test_cross_system_map_filtered(loaded_client):
    r = loaded_client.get("/catalog/cross-system-map/account?system=hubspot")
    data = r.json()["data"]
    assert list(data["systems"].keys()) == ["hubspot"]
    assert data["systems"]["hubspot"]["entity_name"] == "Company"


def test_cross_system_map_unknown_system(loaded_client):
    r = loaded_client.get("/catalog/cross-system-map/account?system=zoho")
    assert r.status_code == 400


# ---------- gap check ----------


def test_gap_check_returns_missing(loaded_client):
    """min_systems=3: accountName is standard in 3 systems and missing from draft."""
    body = {
        "based_on_catalog_id": "account",
        "draft_attribute_names": [],
        "min_systems": 3,
    }
    r = loaded_client.post("/catalog/gap-check", json=body)
    assert r.status_code == 200
    data = r.json()["data"]
    names = [m["name"] for m in data["missing"]]
    assert "accountName" in names
    assert "accountType" in names


def test_gap_check_excludes_already_present(loaded_client):
    body = {
        "based_on_catalog_id": "account",
        "draft_attribute_names": ["accountName"],
        "min_systems": 3,
    }
    r = loaded_client.post("/catalog/gap-check", json=body)
    names = [m["name"] for m in r.json()["data"]["missing"]]
    assert "accountName" not in names
    assert "accountType" in names


def test_gap_check_min_systems_filter(loaded_client):
    body = {
        "based_on_catalog_id": "account",
        "draft_attribute_names": [],
        "min_systems": 7,  # nothing in fixture catalog hits 7
    }
    r = loaded_client.post("/catalog/gap-check", json=body)
    assert r.json()["data"]["missing"] == []


def test_gap_check_out_of_range_rejected(loaded_client):
    body = {
        "based_on_catalog_id": "account",
        "draft_attribute_names": [],
        "min_systems": 0,
    }
    r = loaded_client.post("/catalog/gap-check", json=body)
    # Pydantic rejects with 422 (validation), or 400 if it slipped past
    assert r.status_code in (400, 422)


def test_gap_check_unknown_entity(loaded_client):
    body = {
        "based_on_catalog_id": "nonexistent",
        "draft_attribute_names": [],
    }
    r = loaded_client.post("/catalog/gap-check", json=body)
    assert r.status_code == 404
