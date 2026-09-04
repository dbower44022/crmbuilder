"""Active-subset REST surface — PI-407 (REQ-486 / REQ-487).

The classification rides on the field record; the active subset rides on the
system-settings routes with a field-side read that returns the classification
alongside every subset declared on the field.
"""

from __future__ import annotations


def _seed_entity(client, name="Account") -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def _seed_enum(client, ent, *, data_bearing=None, name="areaOfService") -> str:
    body = {
        "field_name": name,
        "field_description": "d",
        "field_type": "enum",
        "field_belongs_to_entity_identifier": ent,
        "field_options": [
            {"option_value": "Cuyahoga"},
            {"option_value": "Summit"},
            {"option_value": "Lorain"},
        ],
    }
    if data_bearing is not None:
        body["field_data_bearing"] = data_bearing
    resp = client.post("/fields", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["field_identifier"]


def _seed_instance(client, name: str) -> str:
    resp = client.post(
        "/instances",
        json={
            "instance_name": name,
            "instance_url": f"https://{name}.example.org",
            "instance_role": "both",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["instance_identifier"]


def _subset_setting(client, fid, key="activeAreasOfService"):
    return client.post(
        "/system-settings",
        json={
            "system_setting_key": key,
            "system_setting_name": "Active areas of service",
            "system_setting_value_type": "enum",
            "system_setting_status": "confirmed",
            "system_setting_active_subset_field": fid,
        },
    )


def test_the_classification_defaults_off_and_is_settable(client):
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent)
    assert client.get(f"/fields/{fid}").json()["data"]["field_data_bearing"] is False
    resp = client.patch(f"/fields/{fid}", json={"field_data_bearing": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["field_data_bearing"] is True


def test_the_classification_is_queryable_through_the_list(client):
    ent = _seed_entity(client)
    yes = _seed_enum(client, ent, data_bearing=True, name="a")
    no = _seed_enum(client, ent, name="b")
    ids = lambda r: [f["field_identifier"] for f in r.json()["data"]]  # noqa: E731
    assert ids(client.get("/fields?data_bearing=true")) == [yes]
    assert ids(client.get("/fields?data_bearing=false")) == [no]


def test_a_full_replace_that_omits_the_classification_leaves_it_alone(client):
    """A ruling is changed by stating it, never by leaving it out of a PUT."""
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent, data_bearing=True)
    resp = client.put(
        f"/fields/{fid}",
        json={
            "field_name": "areaOfService",
            "field_description": "renamed description",
            "field_type": "enum",
            "field_required": False,
            "field_status": "candidate",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["field_data_bearing"] is True
    resp = client.put(
        f"/fields/{fid}",
        json={
            "field_name": "areaOfService",
            "field_description": "d",
            "field_type": "enum",
            "field_required": False,
            "field_status": "candidate",
            "field_data_bearing": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["field_data_bearing"] is False


def test_declaring_a_subset_on_an_unclassified_field_is_refused(client):
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent)
    resp = _subset_setting(client, fid)
    assert resp.status_code == 422, resp.text
    [err] = resp.json()["errors"]
    assert err["code"] == "not_data_bearing"
    assert fid in err["message"] and "REQ-487" in err["message"]
    assert client.get("/system-settings").json()["data"] == []


def test_declaring_a_subset_on_a_data_bearing_field_round_trips(client):
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent, data_bearing=True)
    resp = _subset_setting(client, fid)
    assert resp.status_code == 201, resp.text
    sid = resp.json()["data"]["system_setting_identifier"]
    got = client.get(f"/system-settings/{sid}").json()["data"]
    assert got["system_setting_active_subset_field"] == fid
    listed = client.get(f"/system-settings?active_subset_field={fid}").json()["data"]
    assert [r["system_setting_identifier"] for r in listed] == [sid]


def test_each_instance_declares_its_own_subset_within_the_complete_list(client):
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent, data_bearing=True)
    sid = _subset_setting(client, fid).json()["data"]["system_setting_identifier"]
    cle = _seed_instance(client, "cleveland")
    akr = _seed_instance(client, "akron")
    ok = client.put(
        f"/system-settings/{sid}/values/{cle}", json={"value": ["Cuyahoga", "Lorain"]}
    )
    assert ok.status_code == 200, ok.text
    ok = client.put(f"/system-settings/{sid}/values/{akr}", json={"value": ["Summit"]})
    assert ok.status_code == 200, ok.text
    bad = client.put(
        f"/system-settings/{sid}/values/{akr}", json={"value": ["Franklin"]}
    )
    assert bad.status_code == 422, bad.text
    assert bad.json()["errors"][0]["code"] == "not_in_complete_option_list"
    # The refusal changed nothing.
    assert client.get(f"/system-settings/{sid}/values/{akr}").json()["data"]["value"] == [
        "Summit"
    ]


def test_the_field_reports_its_classification_alongside_its_subsets(client):
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent, data_bearing=True)
    sid = _subset_setting(client, fid).json()["data"]["system_setting_identifier"]
    cle = _seed_instance(client, "cleveland")
    client.put(f"/system-settings/{sid}/values/{cle}", json={"value": ["Cuyahoga"]})
    resp = client.get(f"/fields/{fid}/active-subsets")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["field_data_bearing"] is True
    assert data["complete_option_list"] == ["Cuyahoga", "Summit", "Lorain"]
    [subset] = data["active_subsets"]
    assert subset["system_setting_identifier"] == sid
    assert subset["values"][0]["instance_identifier"] == cle
    assert subset["values"][0]["value"] == ["Cuyahoga"]
    assert client.get("/fields/FLD-999/active-subsets").status_code == 404


def test_declassifying_a_field_with_a_subset_is_refused(client):
    ent = _seed_entity(client)
    fid = _seed_enum(client, ent, data_bearing=True)
    sid = _subset_setting(client, fid).json()["data"]["system_setting_identifier"]
    resp = client.patch(f"/fields/{fid}", json={"field_data_bearing": False})
    assert resp.status_code == 422, resp.text
    [err] = resp.json()["errors"]
    assert err["code"] == "active_subset_declared"
    assert sid in err["message"]
