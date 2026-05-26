"""Fields REST endpoint tests — v0.5+ (PI-004 first slice).

Covers ``field.md`` §3.7 acceptance criteria 7, 8, 9 end-to-end
through the FastAPI test client, including the atomic-POST + edge
landing in one round-trip and the v2 envelope on validation errors.
"""

from __future__ import annotations


def _seed_entity(client, name: str = "Contact") -> str:
    body = {"entity_name": name, "entity_description": "seed"}
    response = client.post("/entities", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]["entity_identifier"]


def _make(client, ent_id: str, **overrides) -> dict:
    body = {
        "field_name": overrides.pop("field_name", "email_address"),
        "field_description": overrides.pop(
            "field_description", "primary email"
        ),
        "field_type": overrides.pop("field_type", "text"),
        "field_belongs_to_entity_identifier": ent_id,
    }
    body.update(overrides)
    response = client.post("/fields", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_post_fields_endpoint_atomic_creation(client):
    """Single POST creates the row plus the parent-entity edge."""
    ent_id = _seed_entity(client)
    record = _make(client, ent_id)
    # Row landed with server-assigned identifier and defaults.
    assert record["field_identifier"] == "FLD-001"
    assert record["field_status"] == "candidate"
    assert record["field_required"] is False
    # field_belongs_to_entity_identifier is NOT a column on the row;
    # it's consumed as a body-only key to build the edge.
    assert "field_belongs_to_entity_identifier" not in record
    # The edge landed atomically.
    refs_response = client.get(
        f"/references?source_type=field&source_id={record['field_identifier']}"
    )
    assert refs_response.status_code == 200
    refs = refs_response.json()["data"]
    assert len(refs) == 1
    assert refs[0]["relationship"] == "field_belongs_to_entity"
    assert refs[0]["target_id"] == ent_id


def test_get_fields_filtered_by_entity_identifier(client):
    ent_contact = _seed_entity(client, "Contact")
    ent_mentor = _seed_entity(client, "Mentor")
    _make(client, ent_contact, field_name="email", field_type="text")
    _make(client, ent_contact, field_name="phone", field_type="text")
    _make(client, ent_mentor, field_name="expertise", field_type="multi_enum")

    response = client.get(f"/fields?entity_identifier={ent_contact}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert {f["field_name"] for f in data} == {"email", "phone"}

    response = client.get(f"/fields?entity_identifier={ent_mentor}")
    data = response.json()["data"]
    assert {f["field_name"] for f in data} == {"expertise"}


def test_patch_fields_endpoint_rejects_field_belongs_to_entity_identifier(
    client,
):
    """PATCH body that includes the parent-entity key is rejected (the
    Pydantic schema does not declare the field, so the body fails
    422)."""
    ent_id = _seed_entity(client)
    _make(client, ent_id)
    response = client.patch(
        "/fields/FLD-001",
        json={"field_belongs_to_entity_identifier": "ENT-999"},
    )
    assert response.status_code == 422


def test_delete_then_restore_roundtrip_via_api(client):
    ent_id = _seed_entity(client)
    _make(client, ent_id)
    # Delete.
    response = client.delete("/fields/FLD-001")
    assert response.status_code == 200
    assert response.json()["data"]["field_deleted_at"] is not None
    # Not visible in default list.
    response = client.get("/fields")
    assert response.json()["data"] == []
    # Visible with include_deleted.
    response = client.get("/fields?include_deleted=true")
    assert len(response.json()["data"]) == 1
    # Edge gone.
    response = client.get("/references?source_type=field&source_id=FLD-001")
    assert response.json()["data"] == []
    # Restore.
    response = client.post("/fields/FLD-001/restore")
    assert response.status_code == 200
    assert response.json()["data"]["field_deleted_at"] is None
    # Edge back.
    response = client.get("/references?source_type=field&source_id=FLD-001")
    refs = response.json()["data"]
    assert len(refs) == 1
    assert refs[0]["target_id"] == ent_id


def test_next_identifier_endpoint(client):
    response = client.get("/fields/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "FLD-001"}
    ent_id = _seed_entity(client)
    _make(client, ent_id)
    response = client.get("/fields/next-identifier")
    assert response.json()["data"] == {"next": "FLD-002"}


def test_post_fields_envelope_on_validation_error(client):
    """A bogus field_type returns the v2 envelope shape with errors."""
    ent_id = _seed_entity(client)
    body = {
        "field_name": "x",
        "field_description": "d",
        "field_type": "bogus_type",
        "field_belongs_to_entity_identifier": ent_id,
    }
    response = client.post("/fields", json=body)
    assert response.status_code == 422
    payload = response.json()
    assert "data" in payload
    assert "meta" in payload
    assert "errors" in payload
    assert payload["data"] is None
    assert any(e.get("field") == "field_type" for e in payload["errors"])


def test_post_without_parent_entity_returns_422(client):
    """Pydantic rejects the body up front when the required key is
    missing; the spec's missing_parent_entity error shape is surfaced
    by the access layer when the key is supplied empty."""
    body = {
        "field_name": "x",
        "field_description": "d",
        "field_type": "text",
        # field_belongs_to_entity_identifier deliberately omitted
    }
    response = client.post("/fields", json=body)
    assert response.status_code == 422


def test_post_with_nonexistent_parent_entity_returns_422(client):
    body = {
        "field_name": "x",
        "field_description": "d",
        "field_type": "text",
        "field_belongs_to_entity_identifier": "ENT-999",
    }
    response = client.post("/fields", json=body)
    assert response.status_code == 422
    errs = response.json()["errors"]
    assert any(
        e.get("field") == "field_belongs_to_entity_identifier" for e in errs
    )


def test_cardinality_violation_on_second_edge_via_references_post(client):
    """POST /references attempting to add a second
    field_belongs_to_entity edge returns 422 with the spec's
    cardinality_violation code."""
    ent_a = _seed_entity(client, "Contact")
    ent_b = _seed_entity(client, "Mentor")
    _make(client, ent_a)
    body = {
        "source_type": "field",
        "source_id": "FLD-001",
        "target_type": "entity",
        "target_id": ent_b,
        "relationship": "field_belongs_to_entity",
    }
    response = client.post("/references", json=body)
    assert response.status_code == 422
    errs = response.json()["errors"]
    assert any(e.get("code") == "cardinality_violation" for e in errs)


def test_cardinality_violation_on_delete_only_edge_via_references_delete(
    client,
):
    """DELETE /references/{id} on the only live edge of a live field
    returns 422 with cardinality_violation."""
    ent_id = _seed_entity(client)
    _make(client, ent_id)
    response = client.get(
        "/references?source_type=field&source_id=FLD-001"
    )
    edge_id = response.json()["data"][0]["id"]
    response = client.delete(f"/references/{edge_id}")
    assert response.status_code == 422
    errs = response.json()["errors"]
    assert any(e.get("code") == "cardinality_violation" for e in errs)
