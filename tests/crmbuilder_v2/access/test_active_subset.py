"""Variable enum active subsets on data-bearing fields — PI-407 (REQ-486/487).

The construct has three parts and this file exercises each at the access
layer: the data-bearing classification recorded on the field; the refusal —
an error, never a warning — when an active subset is declared for a field
not so classified; and the active subset itself, a per-instance value on the
settings construct, checked against the field's complete option list.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import NotFoundError, UnprocessableError
from crmbuilder_v2.access.repositories import entity, field
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import system_settings as ss

_OPTIONS = [
    {"option_value": "Cuyahoga", "option_label": "Cuyahoga County"},
    {"option_value": "Summit", "option_label": "Summit County"},
    {"option_value": "Lorain", "option_label": "Lorain County"},
]


def _entity(s) -> str:
    return entity.create_entity(
        s, name="Account", description="d", kind="organization", status="confirmed"
    )["entity_identifier"]


def _enum(s, ent, name="areaOfService", *, data_bearing=None, options=_OPTIONS):
    kw = {} if data_bearing is None else {"data_bearing": data_bearing}
    return field.create_field(
        s,
        field_belongs_to_entity_identifier=ent,
        name=name,
        description="d",
        type="enum",
        status="confirmed",
        options=options,
        **kw,
    )


def _instance(s, name):
    return inst_repo.create_instance(
        s, name=name, url=f"https://{name}.example.org", role="both"
    )["instance_identifier"]


def _subset_setting(s, fid, key="activeAreasOfService"):
    return ss.create_system_setting(
        s,
        key=key,
        name="Active areas of service",
        value_type="enum",
        status="confirmed",
        active_subset_field=fid,
    )


def _errors(exc: UnprocessableError) -> list[tuple[str, str, str]]:
    return [(e.field, e.code, e.message) for e in exc.errors]


# --- the classification ------------------------------------------------------


def test_a_field_is_not_data_bearing_until_someone_says_so(v2_env):
    """The default is "not classified", which reads as ineligible. Eligibility
    is a ruling reached by reading the consumers, never an inference."""
    with session_scope() as s:
        f = _enum(s, _entity(s))
        assert f["field_data_bearing"] is False


def test_the_classification_is_recorded_and_read_back(v2_env):
    with session_scope() as s:
        ent = _entity(s)
        f = _enum(s, ent, data_bearing=True)
        assert f["field_data_bearing"] is True
        assert field.get_field(s, f["field_identifier"])["field_data_bearing"] is True
        # And it is patchable like the other flags.
        out = field.patch_field(s, f["field_identifier"], data_bearing=False)
        assert out["field_data_bearing"] is False


def test_the_classification_is_queryable(v2_env):
    """REQ-487: recorded in the design so a consuming codebase can be checked
    against it rather than trusted to remember."""
    with session_scope() as s:
        ent = _entity(s)
        yes = _enum(s, ent, "a", data_bearing=True)["field_identifier"]
        no = _enum(s, ent, "b")["field_identifier"]
        ids = lambda rows: [r["field_identifier"] for r in rows]  # noqa: E731
        assert ids(field.list_fields(s, data_bearing=True)) == [yes]
        assert ids(field.list_fields(s, data_bearing=False)) == [no]
        assert ids(field.list_fields(s)) == [yes, no]


# --- the refusal --------------------------------------------------------------


def test_an_active_subset_on_an_unclassified_field_is_refused(v2_env):
    """The refusal names the field and the reason (REQ-487)."""
    with session_scope() as s:
        f = _enum(s, _entity(s))
        with pytest.raises(UnprocessableError) as exc:
            _subset_setting(s, f["field_identifier"])
        [(where, code, message)] = _errors(exc.value)
        assert where == "system_setting_active_subset_field"
        assert code == "not_data_bearing"
        assert f["field_identifier"] in message
        assert "areaOfService" in message
        assert "REQ-487" in message
        # Refused means nothing was written.
        assert ss.list_system_settings(s) == []


def test_an_active_subset_on_a_data_bearing_field_is_accepted(v2_env):
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        out = _subset_setting(s, f["field_identifier"])
        assert out["system_setting_active_subset_field"] == f["field_identifier"]


def test_an_ordinary_setting_names_no_field(v2_env):
    with session_scope() as s:
        out = ss.create_system_setting(
            s, key="siteUrl", name="Site URL", value_type="text"
        )
        assert out["system_setting_active_subset_field"] is None


def test_pointing_an_existing_setting_at_an_unclassified_field_is_refused(v2_env):
    with session_scope() as s:
        f = _enum(s, _entity(s))
        sid = ss.create_system_setting(
            s, key="k", name="n", value_type="enum"
        )["system_setting_identifier"]
        with pytest.raises(UnprocessableError) as exc:
            ss.patch_system_setting(s, sid, active_subset_field=f["field_identifier"])
        assert _errors(exc.value)[0][1] == "not_data_bearing"


def test_only_an_enum_field_can_carry_an_active_subset(v2_env):
    """A text field has no complete option list to draw a subset from, whatever
    its classification."""
    with session_scope() as s:
        ent = _entity(s)
        t = field.create_field(
            s,
            field_belongs_to_entity_identifier=ent,
            name="notes",
            description="d",
            type="text",
            data_bearing=True,
        )
        with pytest.raises(UnprocessableError) as exc:
            _subset_setting(s, t["field_identifier"])
        assert _errors(exc.value)[0][1] == "not_an_option_field"


def test_an_unknown_or_malformed_field_is_refused(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as exc:
            _subset_setting(s, "FLD-999")
        assert _errors(exc.value)[0][1] == "field_not_found"
        with pytest.raises(UnprocessableError) as exc:
            _subset_setting(s, "areaOfService")
        assert _errors(exc.value)[0][1] == "invalid_format"


def test_a_field_carrying_an_active_subset_cannot_be_declassified(v2_env):
    """The safety property must hold years later: while any setting narrows the
    field, the classification cannot be turned off underneath it."""
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        fid = f["field_identifier"]
        sid = _subset_setting(s, fid)["system_setting_identifier"]
        with pytest.raises(UnprocessableError) as exc:
            field.patch_field(s, fid, data_bearing=False)
        [(where, code, message)] = _errors(exc.value)
        assert (where, code) == ("field_data_bearing", "active_subset_declared")
        assert sid in message and fid in message
        # Still data-bearing.
        assert field.get_field(s, fid)["field_data_bearing"] is True
        # Withdraw the setting, and the field may be declassified.
        ss.delete_system_setting(s, sid)
        assert field.patch_field(s, fid, data_bearing=False)["field_data_bearing"] is False


def test_a_full_replace_that_declassifies_is_refused_too(v2_env):
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        fid = f["field_identifier"]
        _subset_setting(s, fid)
        with pytest.raises(UnprocessableError):
            field.update_field(
                s,
                fid,
                name=f["field_name"],
                description="d",
                type="enum",
                required=False,
                status="confirmed",
                data_bearing=False,
            )


# --- the per-instance active subset ------------------------------------------


def test_each_instance_names_its_own_active_subset(v2_env):
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        fid = f["field_identifier"]
        sid = _subset_setting(s, fid)["system_setting_identifier"]
        cle = _instance(s, "cleveland")
        akr = _instance(s, "akron")
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=cle,
            value=["Cuyahoga", "Lorain"],
        )
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=akr,
            value=["Summit"],
        )
        assert ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=cle
        )["value"] == ["Cuyahoga", "Lorain"]
        assert ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=akr
        )["value"] == ["Summit"]
        # The complete option list on the field is untouched by either.
        assert [o["option_value"] for o in field.get_field(s, fid)["field_options"]] == [
            "Cuyahoga", "Summit", "Lorain"
        ]


def test_an_active_subset_may_only_name_values_every_instance_holds(v2_env):
    """REQ-486: the subset names *which* of the deployed values are active. A
    value outside the complete list is refused, naming the value and the list."""
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        sid = _subset_setting(s, f["field_identifier"])["system_setting_identifier"]
        inst = _instance(s, "cleveland")
        with pytest.raises(UnprocessableError) as exc:
            ss.set_value(
                s, system_setting_identifier=sid, instance_identifier=inst,
                value=["Cuyahoga", "Franklin"],
            )
        [(where, code, message)] = _errors(exc.value)
        assert (where, code) == ("value", "not_in_complete_option_list")
        assert "Franklin" in message and "Cuyahoga" in message
        assert ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=inst
        ) is None


def test_an_active_subset_must_be_a_list_of_option_values(v2_env):
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        sid = _subset_setting(s, f["field_identifier"])["system_setting_identifier"]
        inst = _instance(s, "cleveland")
        for bad in ("Cuyahoga", None, {"Cuyahoga": True}, [1, 2]):
            with pytest.raises(UnprocessableError) as exc:
                ss.set_value(
                    s, system_setting_identifier=sid,
                    instance_identifier=inst, value=bad,
                )
            assert _errors(exc.value)[0][1] == "invalid_value"


def test_the_subset_is_stored_in_the_complete_lists_order_without_repeats(v2_env):
    """The subset is a set; the complete list carries the order."""
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        sid = _subset_setting(s, f["field_identifier"])["system_setting_identifier"]
        inst = _instance(s, "cleveland")
        out = ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=inst,
            value=["Lorain", "Cuyahoga", "Lorain"],
        )
        assert out["value"] == ["Cuyahoga", "Lorain"]


def test_an_ordinary_setting_value_is_not_subset_checked(v2_env):
    with session_scope() as s:
        sid = ss.create_system_setting(
            s, key="siteUrl", name="Site URL", value_type="text"
        )["system_setting_identifier"]
        inst = _instance(s, "cleveland")
        out = ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=inst,
            value="https://cleveland.example.org",
        )
        assert out["value"] == "https://cleveland.example.org"


def test_retiring_a_value_a_declared_subset_still_names_is_refused(v2_env):
    """Narrow the subsets first, then the list — never leave a subset asserting
    a value the deployed list no longer holds."""
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        fid = f["field_identifier"]
        sid = _subset_setting(s, fid)["system_setting_identifier"]
        inst = _instance(s, "cleveland")
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=inst,
            value=["Lorain"],
        )
        with pytest.raises(UnprocessableError) as exc:
            field.patch_field(s, fid, options=_OPTIONS[:2])
        [(where, code, message)] = _errors(exc.value)
        assert (where, code) == ("field_options", "active_subset_names_retired_value")
        assert "Lorain" in message and inst in message
        # The list is intact.
        assert len(field.get_field(s, fid)["field_options"]) == 3
        # Narrow the subset, and the value may be retired.
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=inst,
            value=["Cuyahoga"],
        )
        out = field.patch_field(s, fid, options=_OPTIONS[:2])
        assert [o["option_value"] for o in out["field_options"]] == ["Cuyahoga", "Summit"]


def test_adding_a_value_to_the_complete_list_needs_no_subset_change(v2_env):
    """Growing the list is always safe: every instance receives the new value,
    and no instance's subset activates it until that instance says so."""
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        fid = f["field_identifier"]
        sid = _subset_setting(s, fid)["system_setting_identifier"]
        inst = _instance(s, "cleveland")
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=inst,
            value=["Lorain"],
        )
        out = field.patch_field(
            s, fid, options=[*_OPTIONS, {"option_value": "Medina"}]
        )
        assert len(out["field_options"]) == 4
        assert ss.get_value(
            s, system_setting_identifier=sid, instance_identifier=inst
        )["value"] == ["Lorain"]


# --- querying the design ------------------------------------------------------


def test_the_classification_is_returned_alongside_the_active_subsets(v2_env):
    """REQ-487's third clause: ask the design about a field carrying a variable
    active subset and its classification comes back with it."""
    with session_scope() as s:
        f = _enum(s, _entity(s), data_bearing=True)
        fid = f["field_identifier"]
        sid = _subset_setting(s, fid)["system_setting_identifier"]
        cle = _instance(s, "cleveland")
        ss.set_value(
            s, system_setting_identifier=sid, instance_identifier=cle,
            value=["Cuyahoga"],
        )
        out = ss.active_subsets_for_field(s, fid)
        assert out["field_identifier"] == fid
        assert out["field_data_bearing"] is True
        assert out["complete_option_list"] == ["Cuyahoga", "Summit", "Lorain"]
        [subset] = out["active_subsets"]
        assert subset["system_setting_identifier"] == sid
        assert subset["system_setting_key"] == "activeAreasOfService"
        assert [(v["instance_identifier"], v["value"]) for v in subset["values"]] == [
            (cle, ["Cuyahoga"])
        ]
        # The settings list narrows by field too.
        assert [
            r["system_setting_identifier"]
            for r in ss.list_system_settings(s, active_subset_field=fid)
        ] == [sid]


def test_a_field_with_no_active_subset_still_answers(v2_env):
    with session_scope() as s:
        f = _enum(s, _entity(s))
        out = ss.active_subsets_for_field(s, f["field_identifier"])
        assert out["field_data_bearing"] is False
        assert out["active_subsets"] == []
        with pytest.raises(NotFoundError):
            ss.active_subsets_for_field(s, "FLD-999")
