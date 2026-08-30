"""PI-421 (REQ-123 audit half) — field dynamic logic audited into rule records.

Oracle: ``tests/test_audit_field_dynamic_logic.py`` (V1): isTrue/isFalse -> equals
true/false; isEmpty/isNotEmpty -> null operators; two top-level items are an
implicit AND; or-groups; custom attribute names on native entities are
c-prefix-stripped; readOnly logic is skipped; logic on an uncaptured field is
ignored; an unknown operator omits the field's logic with a warning. V2 stores
the neutral operator names the publish adapter compiles back to EspoCRM.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import rule as rule_repo
from crmbuilder_v2.adapters.espocrm.conditions import compile_condition
from crmbuilder_v2.api.routers.instances import _AUDIT_AREAS
from crmbuilder_v2.introspect.reconcile import (
    _reverse_logic_group,
    reconcile_field_rules,
)

from tests.crmbuilder_v2.access.test_instance_membership import (
    _custom,
    _FakeClient,
    _make_instance,
    _native,
)


def _ident(name: str) -> str:
    return name


def test_operator_translation_mirrors_v1():
    assert _reverse_logic_group([{"type": "isTrue", "attribute": "isFlag"}], _ident) == {
        "field": "isFlag", "op": "eq", "value": True,
    }
    assert _reverse_logic_group([{"type": "isFalse", "attribute": "isFlag"}], _ident) == {
        "field": "isFlag", "op": "eq", "value": False,
    }
    # Two top-level items -> implicit AND.
    assert _reverse_logic_group(
        [{"type": "isEmpty", "attribute": "a"}, {"type": "isNotEmpty", "attribute": "b"}],
        _ident,
    ) == {"all": [{"field": "a", "op": "is_empty"}, {"field": "b", "op": "is_not_empty"}]}
    assert _reverse_logic_group(
        [{"type": "or", "value": [
            {"type": "equals", "attribute": "status", "value": "On"},
            {"type": "in", "attribute": "tier", "value": ["a", "b"]},
        ]}],
        _ident,
    ) == {"any": [
        {"field": "status", "op": "eq", "value": "On"},
        {"field": "tier", "op": "in", "value": ["a", "b"]},
    ]}


def test_reversed_condition_compiles_back_to_espocrm():
    neutral = _reverse_logic_group(
        [{"type": "greaterThanOrEquals", "attribute": "age", "value": 18}], _ident
    )
    assert compile_condition(neutral, lambda ref: ref) == {
        "field": "age", "op": "greaterThanOrEqual", "value": 18,
    }


def test_area_registered():
    assert "field-rules" in _AUDIT_AREAS
    assert list(_AUDIT_AREAS).index("field-rules") > list(_AUDIT_AREAS).index("fields")


def _instance_with_field(s, iid, *, api="active", native=False):
    scopes = {"Contact": _native()} if native else {"CEngagement": _custom()}
    ent = entity_repo.create_entity(
        s, name="Contact" if native else "Engagement", description="x"
    )
    fld = field_repo.create_field(
        s, field_belongs_to_entity_identifier=ent["entity_identifier"],
        name="active", description="x", type="text", required=False,
    )
    return scopes, ent, fld


def _client(scopes, logic_by_scope):
    client = _FakeClient(scopes)
    client._client_defs = {
        scope: {"dynamicLogic": {"fields": logic}} for scope, logic in logic_by_scope.items()
    }
    return client


def test_reconcile_creates_rules_and_detects_drift(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        scopes, ent, fld = _instance_with_field(s, iid)
        logic = {"active": {
            "required": {"conditionGroup": [{"type": "isNotEmpty", "attribute": "cA"}]},
            "visible": {"conditionGroup": [{"type": "isEmpty", "attribute": "cB"}]},
            "readOnly": {"conditionGroup": [{"type": "isTrue", "attribute": "cX"}]},
        }}
        summary = reconcile_field_rules(
            s, instance_identifier=iid, client=_client(scopes, {"CEngagement": logic})
        )
        assert summary["created"] == 2 and summary["present"] == 2
        rules = {r["rule_effect"]: r for r in rule_repo.list_rules(s)}
        assert set(rules) == {"required_when", "visible_when"}
        assert rules["required_when"]["rule_subject_identifier"] == fld["field_identifier"]
        # Custom entity: field and attribute names are kept verbatim (REQ-342).
        assert rules["required_when"]["rule_condition"] == {"field": "cA", "op": "is_not_empty"}

        logic2 = {"active": {
            "required": {"conditionGroup": [{"type": "isTrue", "attribute": "cA"}]},
            "visible": {"conditionGroup": [{"type": "isEmpty", "attribute": "cB"}]},
        }}
        s2 = reconcile_field_rules(
            s, instance_identifier=iid, client=_client(scopes, {"CEngagement": logic2})
        )
        assert s2["drifted"] == 1 and s2["present"] == 1 and s2["created"] == 0
        drifted = [
            m for m in mb.list_memberships(s, instance_identifier=iid, member_type="rule")
            if m["state"] == "drifted"
        ]
        assert drifted[0]["override"] == {
            "rule_condition": {"field": "cA", "op": "eq", "value": True}
        }


def test_native_entity_attribute_names_are_stripped(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        scopes, ent, fld = _instance_with_field(s, iid, native=True)
        client = _client(scopes, {"Contact": {"cActive": {
            "visible": {"conditionGroup": [{"type": "isTrue", "attribute": "cMentorFlag"}]},
        }}})
        client._fields = {"Contact": {"cActive": {"isCustom": True, "type": "bool"}}}
        summary = reconcile_field_rules(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1
        assert rule_repo.list_rules(s)[0]["rule_condition"]["field"] == "mentorFlag"


def test_unknown_operator_omits_logic_with_warning_and_uncaptured_field_ignored(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        scopes, ent, fld = _instance_with_field(s, iid)
        notes: list[tuple[str, str]] = []
        client = _client(scopes, {"CEngagement": {
            "active": {"visible": {"conditionGroup": [
                {"type": "weirdOp", "attribute": "cX", "value": 1}]}},
            "cGhost": {"visible": {"conditionGroup": [
                {"type": "isTrue", "attribute": "cA"}]}},
        }})
        summary = reconcile_field_rules(
            s, instance_identifier=iid, client=client, progress=lambda m, lvl: notes.append((m, lvl))
        )
        assert summary["created"] == 0 and summary["skipped"] == 1
        assert any("unsupported condition type" in m and lvl == "warning" for m, lvl in notes)
        assert rule_repo.list_rules(s) == []


def test_successful_empty_read_sweeps_absent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        scopes, ent, fld = _instance_with_field(s, iid)
        logic = {"active": {"visible": {"conditionGroup": [
            {"type": "isTrue", "attribute": "cA"}]}}}
        reconcile_field_rules(
            s, instance_identifier=iid, client=_client(scopes, {"CEngagement": logic})
        )
        s2 = reconcile_field_rules(
            s, instance_identifier=iid, client=_client(scopes, {"CEngagement": {}})
        )
        assert s2["absent"] == 1
