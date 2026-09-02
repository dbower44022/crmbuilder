

def test_compared_set_is_served_as_the_engine_sees_it(client):
    """PI-409 / DEC-989: the read-only declaration endpoint mirrors the code
    module exactly, so every surface reports against what is enforced.
    PI-408 / REQ-489 adds DEC-921's construct sets beside the attributes."""
    from crmbuilder_v2.access import compared_set

    r = client.get("/reconcile/compared-set")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["attributes"] == compared_set.serialized()
    assert data["construct_sets"] == compared_set.construct_sets_serialized()
    assert data["construct_sets"]["saved_view"]["sets"] == ["captured"]
    assert data["construct_sets"]["workflow"]["sets"] == [
        "captured", "compared",
    ]
