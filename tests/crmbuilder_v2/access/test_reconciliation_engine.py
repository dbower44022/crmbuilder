"""Pure reconciliation-engine tests — PI-215 (PRJ-031), §5.4 / RC-2/RC-3.

Covers the facet taxonomy in crmbuilder_v2.access.reconciliation.reconcile_artifact:
NONE / IDENTICAL / COMPOSE / ADDITIVE-UNION auto-merge, facet_value and
remove_vs_modify conflicts, N-way order-independence, and merge against a base.
No database.
"""

from __future__ import annotations

from crmbuilder_v2.access.reconciliation import reconcile_artifact


def _d(req, field, facet, op, value=None):
    return {
        "requirement_identifier": req, "field": field, "facet": facet,
        "op": op, "value": value,
    }


def test_none_keeps_base():
    base = {"fields": {"email": {"required": False}}, "attributes": {}}
    out = reconcile_artifact(base, [])
    assert out["merged"] == base
    assert out["conflicts"] == []


def test_identical_dedupes():
    out = reconcile_artifact(
        {}, [_d("REQ-1", "email", "required", "set", True),
             _d("REQ-2", "email", "required", "set", True)]
    )
    assert out["merged"]["fields"]["email"]["required"] is True
    assert out["conflicts"] == []
    # provenance carries both requirements.
    prov = [p for p in out["provenance"] if p["field"] == "email"][0]
    assert prov["requirements"] == ["REQ-1", "REQ-2"]


def test_compose_different_facets_one_field():
    out = reconcile_artifact(
        {}, [_d("REQ-1", "email", "required", "set", True),
             _d("REQ-2", "email", "maxLength", "set", 255)]
    )
    assert out["merged"]["fields"]["email"] == {"required": True, "maxLength": 255}
    assert out["conflicts"] == []


def test_additive_union_of_options():
    out = reconcile_artifact(
        {}, [_d("REQ-1", "contactType", "options", "add", ["a", "b"]),
             _d("REQ-2", "contactType", "options", "add", ["b", "c"])]
    )
    assert out["merged"]["fields"]["contactType"]["options"] == ["a", "b", "c"]
    assert out["conflicts"] == []


def test_facet_value_conflict():
    out = reconcile_artifact(
        {}, [_d("REQ-1", "email", "required", "set", True),
             _d("REQ-2", "email", "required", "set", False)]
    )
    assert "email" not in out["merged"]["fields"]  # contradicted facet not applied
    assert len(out["conflicts"]) == 1
    c = out["conflicts"][0]
    assert c["conflict_type"] == "facet_value"
    assert {x["requirement"] for x in c["competing"]} == {"REQ-1", "REQ-2"}


def test_remove_vs_modify_conflict():
    out = reconcile_artifact(
        {"fields": {"phone": {"type": "phone"}}, "attributes": {}},
        [_d("REQ-1", "phone", "__field__", "remove"),
         _d("REQ-2", "phone", "type", "set", "varchar")],
    )
    assert len(out["conflicts"]) == 1
    assert out["conflicts"][0]["conflict_type"] == "remove_vs_modify"
    # the field survives (the remove was not applied — it's contended)
    assert out["merged"]["fields"]["phone"]["type"] == "phone"


def test_remove_applies_when_uncontended():
    out = reconcile_artifact(
        {"fields": {"phone": {"type": "phone"}}, "attributes": {}},
        [_d("REQ-1", "phone", "__field__", "remove")],
    )
    assert "phone" not in out["merged"]["fields"]
    assert out["conflicts"] == []


def test_merge_against_base():
    base = {"fields": {"email": {"required": False, "maxLength": 100}},
            "attributes": {}}
    out = reconcile_artifact(base, [_d("REQ-1", "email", "required", "set", True)])
    assert out["merged"]["fields"]["email"]["required"] is True
    assert out["merged"]["fields"]["email"]["maxLength"] == 100  # base preserved


def test_order_independence():
    deltas = [
        _d("REQ-1", "email", "required", "set", True),
        _d("REQ-2", "email", "maxLength", "set", 255),
        _d("REQ-3", "contactType", "options", "add", ["a", "b"]),
        _d("REQ-4", "contactType", "options", "add", ["c"]),
    ]
    a = reconcile_artifact({}, deltas)
    b = reconcile_artifact({}, list(reversed(deltas)))
    assert a["merged"] == b["merged"]


def test_attribute_level_facet():
    out = reconcile_artifact({}, [_d("REQ-1", "", "label", "set", "Contact")])
    assert out["merged"]["attributes"]["label"] == "Contact"
