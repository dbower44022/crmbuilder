"""REST tests — PRJ-025 PI-182 intrinsic design-intent columns + options.

End-to-end through the FastAPI test client: the new ``field``/``entity``
neutral attributes and the ``field_options`` collection round-trip, PATCH
replaces the option set, and bad enum values surface as 422.
"""

from __future__ import annotations


def _seed_entity(client, name: str = "Contact") -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def _make_field(client, ent_id: str, **overrides) -> dict:
    body = {
        "field_name": overrides.pop("field_name", "status"),
        "field_description": overrides.pop("field_description", "d"),
        "field_type": overrides.pop("field_type", "enum"),
        "field_belongs_to_entity_identifier": ent_id,
    }
    body.update(overrides)
    resp = client.post("/fields", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def test_post_field_with_intrinsics_and_options(client):
    ent = _seed_entity(client)
    record = _make_field(
        client,
        ent,
        field_tooltip="pick one",
        field_format="email",
        field_read_only=True,
        field_unique=True,
        field_max_length=255,
        field_options=[
            {"option_value": "new", "option_label": "New"},
            {"option_value": "done"},
        ],
    )
    assert record["field_tooltip"] == "pick one"
    assert record["field_format"] == "email"
    assert record["field_read_only"] is True
    assert record["field_unique"] is True
    assert record["field_max_length"] == 255
    assert [o["option_value"] for o in record["field_options"]] == [
        "new",
        "done",
    ]

    # GET surfaces the same embedded options.
    got = client.get(f"/fields/{record['field_identifier']}").json()["data"]
    assert [o["option_value"] for o in got["field_options"]] == ["new", "done"]


def test_patch_field_replaces_options(client):
    ent = _seed_entity(client)
    fid = _make_field(client, ent, field_options=[{"option_value": "a"}])[
        "field_identifier"
    ]
    resp = client.patch(
        f"/fields/{fid}",
        json={"field_options": [{"option_value": "x"}, {"option_value": "y"}]},
    )
    assert resp.status_code == 200, resp.text
    assert [o["option_value"] for o in resp.json()["data"]["field_options"]] == [
        "x",
        "y",
    ]


def test_patch_field_intrinsic(client):
    ent = _seed_entity(client)
    fid = _make_field(client, ent, field_type="text")["field_identifier"]
    resp = client.patch(
        f"/fields/{fid}", json={"field_numeric_scale": "integer"}
    )
    # text fields can still carry numeric_scale at the model layer (the
    # neutral token is orthogonal); only enum-value validation is enforced.
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["field_numeric_scale"] == "integer"


def test_post_field_rejects_bad_format(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "f",
            "field_description": "d",
            "field_type": "text",
            "field_belongs_to_entity_identifier": ent,
            "field_format": "nope",
        },
    )
    assert resp.status_code == 422, resp.text


def test_post_field_rejects_duplicate_option(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "f",
            "field_description": "d",
            "field_type": "enum",
            "field_belongs_to_entity_identifier": ent,
            "field_options": [
                {"option_value": "dup"},
                {"option_value": "dup"},
            ],
        },
    )
    assert resp.status_code == 422, resp.text


def test_post_entity_with_intrinsics(client):
    resp = client.post(
        "/entities",
        json={
            "entity_name": "Mentor",
            "entity_description": "d",
            "entity_default_sort_field": "createdAt",
            "entity_default_sort_direction": "desc",
            "entity_track_activity": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["entity_default_sort_field"] == "createdAt"
    assert data["entity_default_sort_direction"] == "desc"
    assert data["entity_track_activity"] is True


def test_patch_entity_intrinsics(client):
    eid = _seed_entity(client, "Mentee")
    resp = client.patch(
        f"/entities/{eid}",
        json={"entity_track_activity": True, "entity_default_sort_direction": "asc"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["entity_track_activity"] is True
    assert data["entity_default_sort_direction"] == "asc"


def test_post_entity_with_collection_settings(client):
    # REQ-340 / PI-300 — the five collection-search settings round-trip via REST.
    resp = client.post(
        "/entities",
        json={
            "entity_name": "Engagement",
            "entity_description": "d",
            "entity_text_filter_fields": ["name", "emailAddress"],
            "entity_full_text_search": True,
            "entity_full_text_search_min_length": 4,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["entity_text_filter_fields"] == ["name", "emailAddress"]
    assert data["entity_full_text_search"] is True
    assert data["entity_full_text_search_min_length"] == 4


def test_patch_entity_collection_settings(client):
    eid = _seed_entity(client, "Partner")
    resp = client.patch(
        f"/entities/{eid}",
        json={
            "entity_text_filter_fields": ["name"],
            "entity_full_text_search": True,
            "entity_full_text_search_min_length": 3,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["entity_text_filter_fields"] == ["name"]
    assert data["entity_full_text_search"] is True
    assert data["entity_full_text_search_min_length"] == 3


def test_post_entity_rejects_bad_fts_min_length(client):
    resp = client.post(
        "/entities",
        json={
            "entity_name": "BadFts",
            "entity_description": "d",
            "entity_full_text_search_min_length": -1,
        },
    )
    assert resp.status_code == 422, resp.text


def test_post_entity_rejects_bad_sort_direction(client):
    resp = client.post(
        "/entities",
        json={
            "entity_name": "Bad",
            "entity_description": "d",
            "entity_default_sort_direction": "sideways",
        },
    )
    assert resp.status_code == 422, resp.text
