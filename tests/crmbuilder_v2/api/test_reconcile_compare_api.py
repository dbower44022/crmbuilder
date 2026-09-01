

def test_compared_set_is_served_as_the_engine_sees_it(client):
    """PI-409 / DEC-989: the read-only declaration endpoint mirrors the code
    module exactly, so every surface reports against what is enforced."""
    from crmbuilder_v2.access import compared_set

    r = client.get("/reconcile/compared-set")
    assert r.status_code == 200, r.text
    assert r.json()["data"] == compared_set.serialized()
