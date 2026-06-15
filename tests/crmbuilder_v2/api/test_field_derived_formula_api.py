"""REST tests — PRJ-025 PI-197 derived/formula columns (DEC-438).

End-to-end through the FastAPI test client: ``field_derived_result_type``
and ``field_formula`` round-trip on a ``derived`` field; the cross-field
invariant (required-when-derived / forbidden-otherwise) is enforced as
422; a malformed formula AST surfaces as 422; PATCH re-checks the
invariant when the type flips.
"""

from __future__ import annotations


def _seed_entity(client, name: str = "Contact") -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


_CONCAT = {
    "kind": "concat",
    "parts": [{"field": "first_name"}, {"literal": " "}, {"field": "last_name"}],
}


def test_post_derived_field_with_result_type_and_formula(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "full_name",
            "field_description": "computed full name",
            "field_type": "derived",
            "field_belongs_to_entity_identifier": ent,
            "field_derived_result_type": "text",
            "field_formula": _CONCAT,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["field_derived_result_type"] == "text"
    assert data["field_formula"] == _CONCAT

    # GET round-trips both.
    got = client.get(f"/fields/{data['field_identifier']}").json()["data"]
    assert got["field_derived_result_type"] == "text"
    assert got["field_formula"] == _CONCAT


def test_post_derived_field_requires_result_type(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "computed",
            "field_description": "d",
            "field_type": "derived",
            "field_belongs_to_entity_identifier": ent,
            "field_formula": _CONCAT,
        },
    )
    assert resp.status_code == 422, resp.text
    assert "derived_result_type" in resp.text


def test_post_non_derived_field_rejects_result_type(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "plain",
            "field_description": "d",
            "field_type": "text",
            "field_belongs_to_entity_identifier": ent,
            "field_derived_result_type": "text",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "derived_result_type" in resp.text


def test_post_derived_field_rejects_bad_result_type(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "computed",
            "field_description": "d",
            "field_type": "derived",
            "field_belongs_to_entity_identifier": ent,
            "field_derived_result_type": "reference",
            "field_formula": _CONCAT,
        },
    )
    assert resp.status_code == 422, resp.text


def test_post_derived_field_rejects_malformed_formula(client):
    ent = _seed_entity(client)
    resp = client.post(
        "/fields",
        json={
            "field_name": "computed",
            "field_description": "d",
            "field_type": "derived",
            "field_belongs_to_entity_identifier": ent,
            "field_derived_result_type": "text",
            "field_formula": {"kind": "concat", "parts": []},
        },
    )
    assert resp.status_code == 422, resp.text
    assert "field_formula" in resp.text


def test_patch_flip_to_derived_requires_result_type(client):
    ent = _seed_entity(client)
    fid = client.post(
        "/fields",
        json={
            "field_name": "f",
            "field_description": "d",
            "field_type": "text",
            "field_belongs_to_entity_identifier": ent,
        },
    ).json()["data"]["field_identifier"]

    # Flipping to derived without a result type is rejected.
    bad = client.patch(f"/fields/{fid}", json={"field_type": "derived"})
    assert bad.status_code == 422, bad.text

    # Supplying both in the same PATCH succeeds.
    good = client.patch(
        f"/fields/{fid}",
        json={
            "field_type": "derived",
            "field_derived_result_type": "number",
            "field_formula": {
                "kind": "arithmetic",
                "expression": {
                    "op": "+",
                    "left": {"field": "a"},
                    "right": {"number": 1},
                },
            },
        },
    )
    assert good.status_code == 200, good.text
    assert good.json()["data"]["field_derived_result_type"] == "number"


def test_put_replaces_derived_attributes(client):
    ent = _seed_entity(client)
    fid = client.post(
        "/fields",
        json={
            "field_name": "computed",
            "field_description": "d",
            "field_type": "derived",
            "field_belongs_to_entity_identifier": ent,
            "field_derived_result_type": "text",
            "field_formula": _CONCAT,
        },
    ).json()["data"]["field_identifier"]

    # PUT back to a plain text field — derived attributes must clear, and a
    # leftover result type would be a 422 (forbidden on non-derived).
    resp = client.put(
        f"/fields/{fid}",
        json={
            "field_name": "computed",
            "field_description": "d",
            "field_type": "text",
            "field_required": False,
            "field_status": "candidate",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["field_type"] == "text"
    assert data["field_derived_result_type"] is None
    assert data["field_formula"] is None
