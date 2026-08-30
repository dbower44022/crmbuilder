"""System-settings REST endpoints — PI-406 (REQ-485 / DEC-918).

Covers the governed-setting routes and the per-instance value routes, and in
particular the distinction the whole construct turns on: an instance with no
declared value is *absent*, never a null row.
"""

from __future__ import annotations


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


def _seed_setting(client, key="outboundEmailFromAddress") -> str:
    resp = client.post(
        "/system-settings",
        json={
            "system_setting_key": key,
            "system_setting_name": "Outbound email address",
            "system_setting_value_type": "text",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["system_setting_identifier"]


def test_create_get_list_setting(client):
    sid = _seed_setting(client)
    assert sid == "SET-001"
    got = client.get(f"/system-settings/{sid}")
    assert got.status_code == 200
    assert got.json()["data"]["system_setting_value_type"] == "text"
    assert got.json()["data"]["system_setting_status"] == "candidate"
    listed = client.get("/system-settings")
    assert [r["system_setting_identifier"] for r in listed.json()["data"]] == [sid]


def test_next_identifier_route_precedes_the_identifier_route(client):
    """Route order is load-bearing: a static segment that follows
    ``/{identifier}`` is swallowed by it."""
    resp = client.get("/system-settings/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "SET-001"


def test_a_value_shape_outside_the_field_vocabulary_is_refused(client):
    resp = client.post(
        "/system-settings",
        json={
            "system_setting_key": "x",
            "system_setting_name": "X",
            "system_setting_value_type": "not_a_kind",
        },
    )
    assert resp.status_code == 422, resp.text


def test_declaring_the_same_key_twice_is_a_conflict(client):
    _seed_setting(client, "siteUrl")
    resp = client.post(
        "/system-settings",
        json={
            "system_setting_key": "siteUrl",
            "system_setting_name": "Other",
            "system_setting_value_type": "text",
        },
    )
    assert resp.status_code == 409, resp.text


# --- per-instance values ----------------------------------------------------


def test_each_instance_declares_its_own_value(client):
    """REQ-485: two instances holding different values is not drift."""
    sid = _seed_setting(client)
    a = _seed_instance(client, "alpha")
    b = _seed_instance(client, "beta")
    for iid, value in ((a, "info@alpha.org"), (b, "info@beta.org")):
        resp = client.put(
            f"/system-settings/{sid}/values/{iid}", json={"value": value}
        )
        assert resp.status_code == 200, resp.text
    listed = client.get(f"/system-settings/{sid}/values").json()["data"]
    assert {r["instance_identifier"]: r["value"] for r in listed} == {
        a: "info@alpha.org",
        b: "info@beta.org",
    }


def test_an_undeclared_instance_is_absent_not_null(client):
    """The distinction REQ-485's third outcome depends on: nobody having said
    what an instance should hold is not a declaration that it holds nothing, so
    the undeclared instance does not appear at all rather than appearing null."""
    sid = _seed_setting(client)
    declared = _seed_instance(client, "alpha")
    _seed_instance(client, "beta")  # never declared
    client.put(f"/system-settings/{sid}/values/{declared}", json={"value": "x"})

    listed = client.get(f"/system-settings/{sid}/values").json()["data"]
    assert [r["instance_identifier"] for r in listed] == [declared]

    missing = client.get(f"/system-settings/{sid}/values/INST-002")
    assert missing.status_code == 404


def test_declaring_null_is_a_declaration(client):
    """Sending null says the instance should hold nothing — a real answer, and
    distinguishable from never having declared."""
    sid = _seed_setting(client)
    iid = _seed_instance(client, "alpha")
    resp = client.put(f"/system-settings/{sid}/values/{iid}", json={"value": None})
    assert resp.status_code == 200
    got = client.get(f"/system-settings/{sid}/values/{iid}")
    assert got.status_code == 200
    assert got.json()["data"]["value"] is None


def test_clearing_returns_the_instance_to_undeclared(client):
    sid = _seed_setting(client)
    iid = _seed_instance(client, "alpha")
    client.put(f"/system-settings/{sid}/values/{iid}", json={"value": "x"})
    assert client.delete(f"/system-settings/{sid}/values/{iid}").status_code == 200
    assert client.get(f"/system-settings/{sid}/values/{iid}").status_code == 404
    assert client.delete(f"/system-settings/{sid}/values/{iid}").status_code == 404


def test_values_of_an_unknown_setting_are_not_found(client):
    assert client.get("/system-settings/SET-999/values").status_code == 404


def test_soft_delete_and_restore(client):
    sid = _seed_setting(client)
    assert client.delete(f"/system-settings/{sid}").status_code == 200
    assert client.get(f"/system-settings/{sid}").status_code == 404
    assert client.get("/system-settings").json()["data"] == []
    assert client.post(f"/system-settings/{sid}/restore").status_code == 200
    assert client.get(f"/system-settings/{sid}").status_code == 200
