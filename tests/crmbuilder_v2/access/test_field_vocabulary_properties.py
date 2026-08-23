"""The four qualifying field properties — PI-414 (REQ-508/510/512/514).

The field vocabulary gained four properties so it can describe any CRM's fields
without loss: how a field is **displayed**, how constrained its **values** are,
how many it **holds**, and who **supplied** it. Each is stored as a nullable
column and validated against its own vocabulary at the access layer, following
the intrinsic-attribute precedent from PI-182 rather than a database CHECK.

Two properties are worth pinning beyond "the column exists".

*They do not constrain each other.* The reason display was split out of format
(DEC-933) is that one property answering two questions let a field be declared
both an email address and a tick-list, which is meaningless. A field must be able
to carry a value-kind and a display at once without either rejecting the other.

*A bad value is refused, not stored.* These are enum-valued in code only, so
nothing in the database stops a typo. If the access layer does not reject one,
nothing does.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import entity, field
from crmbuilder_v2.access.vocab import (
    FIELD_DISPLAYS,
    FIELD_HOLDS,
    FIELD_SUPPLIED_BY,
    FIELD_TYPES,
    FIELD_VALUES,
)

#: The kinds DEC-934 and DEC-936 added, which the ``field_type`` CHECK must admit.
_NEW_KINDS = (
    "postal_address",
    "person_name",
    "place",
    "file",
    "time",
    "structured_data",
)

_PROPERTY_VOCABULARIES = {
    "display": FIELD_DISPLAYS,
    "values": FIELD_VALUES,
    "holds": FIELD_HOLDS,
    "supplied_by": FIELD_SUPPLIED_BY,
}


def _seed_entity(s, name: str = "VocabHost") -> str:
    return entity.create_entity(
        s, name=name, description="Fixture for field-vocabulary tests."
    )["entity_identifier"]


def _make(s, parent_id: str, name: str, **kwargs) -> dict:
    return field.create_field(
        s,
        field_belongs_to_entity_identifier=parent_id,
        name=name,
        description="Field-vocabulary test fixture.",
        **kwargs,
    )


def test_the_new_kinds_are_accepted(v2_env):
    """Each kind added by DEC-934 / DEC-936 stores and reads back."""
    with session_scope() as s:
        parent = _seed_entity(s)
        for kind in _NEW_KINDS:
            assert kind in FIELD_TYPES
            row = _make(s, parent, f"f{kind}", type=kind)
            assert row["field_type"] == kind


def test_every_value_in_each_vocabulary_round_trips(v2_env):
    """No vocabulary value is declared but unstorable."""
    with session_scope() as s:
        parent = _seed_entity(s)
        for kwarg, vocab in _PROPERTY_VOCABULARIES.items():
            for index, value in enumerate(sorted(vocab)):
                row = _make(
                    s, parent, f"{kwarg}{index}", type="text", **{kwarg: value}
                )
                assert row[f"field_{kwarg}"] == value


@pytest.mark.parametrize("kwarg", sorted(_PROPERTY_VOCABULARIES))
def test_a_value_outside_the_vocabulary_is_refused(v2_env, kwarg):
    """Nothing in the database stops a typo, so the access layer must."""
    with session_scope() as s:
        parent = _seed_entity(s)
        with pytest.raises(UnprocessableError):
            _make(s, parent, f"bad{kwarg}", type="text", **{kwarg: "not_a_value"})


def test_the_properties_do_not_constrain_one_another(v2_env):
    """The split exists so a field can answer both questions at once.

    An email address shown as a plain box, a choice that holds several and admits
    values outside its list, a system-numbered field — none of these should be
    unsayable, and before DEC-933 the first was.
    """
    with session_scope() as s:
        parent = _seed_entity(s)
        row = _make(
            s,
            parent,
            "combined",
            type="text",
            format="email",
            display="multiline",
            values="suggested",
            holds="several",
            supplied_by="this_crm",
        )
    assert row["field_format"] == "email"
    assert row["field_display"] == "multiline"
    assert row["field_values"] == "suggested"
    assert row["field_holds"] == "several"
    assert row["field_supplied_by"] == "this_crm"


def test_the_properties_default_to_unset(v2_env):
    """A field that says nothing about them carries null, not a guessed default.

    The backfill of existing design records is a separate, reviewable step; an
    audit must not silently invent values for 254 fields that never declared any.
    """
    with session_scope() as s:
        parent = _seed_entity(s)
        row = _make(s, parent, "bare", type="text")
    for column in (
        "field_display",
        "field_values",
        "field_holds",
        "field_supplied_by",
    ):
        assert row[column] is None


def test_a_property_can_be_cleared(v2_env):
    """Setting a property back to null is a legitimate correction, not an error."""
    with session_scope() as s:
        parent = _seed_entity(s)
        row = _make(s, parent, "clearable", type="text", holds="several")
        updated = field.patch_field(s, row["field_identifier"], holds=None)
    assert updated["field_holds"] is None
