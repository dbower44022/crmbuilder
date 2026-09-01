"""Association repository tests — PRJ-025 PI-189 slice 1.

Covers schema shape, vocab/CHECK registration, CRUD, soft-delete/restore,
and the validation surfaces (bad cardinality / status, dead-or-missing
endpoint entity, disallowed status transition).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import association, entity
from crmbuilder_v2.access.vocab import (
    ASSOCIATION_CARDINALITIES,
    ASSOCIATION_STATUSES,
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "association_identifier": "VARCHAR",
    "association_name": "VARCHAR",
    "association_source_entity": "VARCHAR",
    "association_target_entity": "VARCHAR",
    "association_cardinality": "VARCHAR",
    "association_source_role": "VARCHAR",
    "association_target_role": "VARCHAR",
    # PI-414 (REQ-506 / REQ-507): what the retired reference field carried.
    "association_target_kinds": "JSON",
    "association_source_label": "VARCHAR",
    "association_target_label": "VARCHAR",
    "association_source_required": "BOOLEAN",
    "association_target_required": "BOOLEAN",
    "association_description": "TEXT",
    "association_notes": "TEXT",
    "association_status": "VARCHAR",
    "association_created_at": "DATETIME",
    "association_updated_at": "DATETIME",
    "association_deleted_at": "DATETIME",
    "engagement_id": "VARCHAR",
}


def _seed_entity(s, name: str) -> str:
    return entity.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_associations_table_has_expected_columns_with_correct_types(v2_env):
    insp = inspect(get_engine())
    assert "associations" in insp.get_table_names()
    columns = {c["name"]: c for c in insp.get_columns("associations")}
    assert set(columns) == set(_EXPECTED_COLUMNS)
    for name, affinity in _EXPECTED_COLUMNS.items():
        assert str(columns[name]["type"]).upper().startswith(affinity), name
    pk = insp.get_pk_constraint("associations")
    assert pk["constrained_columns"] == [
        "association_identifier",
        "engagement_id",
    ]


def test_association_registered_in_vocab():
    assert "association" in ENTITY_TYPES
    assert "association" in CHANGE_LOG_ENTITY_TYPES
    assert ASSOCIATION_CARDINALITIES == {
        "one_to_one",
        "one_to_many",
        "many_to_many",
        # PI-414 / REQ-506: the polymorphic parent link is recorded from the
        # child side, because its owning side is several entities at once.
        "many_to_one",
    }
    assert ASSOCIATION_STATUSES == {
        "candidate",
        "confirmed",
        "deferred",
        "rejected",
    }


def test_create_and_get_association(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "Mentor")
        b = _seed_entity(s, "Mentee")
        row = association.create_association(
            s,
            name="Mentor assignment",
            source_entity=a,
            target_entity=b,
            cardinality="many_to_many",
            source_role="mentor",
            target_role="mentee",
        )
    assert row["association_identifier"] == "ASN-001"
    assert row["association_status"] == "candidate"
    assert row["association_source_entity"] == a
    assert row["association_target_entity"] == b
    with session_scope() as s:
        got = association.get_association(s, "ASN-001")
        assert got["association_source_role"] == "mentor"


def test_create_with_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_many",
            identifier="ASN-050",
        )
    with session_scope() as s, pytest.raises(ConflictError):
        association.create_association(
            s,
            name="dup",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-050",
        )


def test_create_rejects_bad_cardinality(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        with pytest.raises(UnprocessableError):
            association.create_association(
                s,
                name="bad",
                source_entity=a,
                target_entity=b,
                cardinality="one_to_three",
            )


def test_create_rejects_bad_status(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        with pytest.raises(UnprocessableError):
            association.create_association(
                s,
                name="bad",
                source_entity=a,
                target_entity=b,
                cardinality="one_to_one",
                status="archived",
            )


def test_create_rejects_missing_source_entity(v2_env):
    with session_scope() as s:
        b = _seed_entity(s, "B")
        with pytest.raises(UnprocessableError) as exc:
            association.create_association(
                s,
                name="bad",
                source_entity="ENT-999",
                target_entity=b,
                cardinality="one_to_one",
            )
        assert "association_source_entity" in str(exc.value)


def test_create_rejects_soft_deleted_target_entity(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        entity.delete_entity(s, b)
        with pytest.raises(UnprocessableError) as exc:
            association.create_association(
                s,
                name="bad",
                source_entity=a,
                target_entity=b,
                cardinality="one_to_one",
            )
        assert "soft-deleted" in str(exc.value)


def test_update_and_status_transition(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-001",
        )
    # candidate -> confirmed allowed.
    with session_scope() as s:
        row = association.patch_association(s, "ASN-001", status="confirmed")
        assert row["association_status"] == "confirmed"
    # confirmed -> candidate is NOT allowed.
    with session_scope() as s, pytest.raises(StatusTransitionError):
        association.patch_association(s, "ASN-001", status="candidate")


def test_patch_rejects_unknown_field(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-001",
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        association.patch_association(s, "ASN-001", bogus="x")


def test_soft_delete_and_restore(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        association.create_association(
            s,
            name="link",
            source_entity=a,
            target_entity=b,
            cardinality="one_to_one",
            identifier="ASN-001",
        )
    with session_scope() as s:
        association.delete_association(s, "ASN-001")
        assert association.get_association(s, "ASN-001") is None
        assert (
            association.get_association(s, "ASN-001", include_deleted=True)
            is not None
        )
    with session_scope() as s:
        association.restore_association(s, "ASN-001")
        assert association.get_association(s, "ASN-001") is not None
    # Restoring a live row is a 422.
    with session_scope() as s, pytest.raises(UnprocessableError):
        association.restore_association(s, "ASN-001")


def test_get_missing_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        association.delete_association(s, "ASN-404")


def test_list_filters_by_endpoint(v2_env):
    with session_scope() as s:
        a = _seed_entity(s, "A")
        b = _seed_entity(s, "B")
        c = _seed_entity(s, "C")
        association.create_association(
            s, name="ab", source_entity=a, target_entity=b,
            cardinality="one_to_one",
        )
        association.create_association(
            s, name="ac", source_entity=a, target_entity=c,
            cardinality="one_to_one",
        )
    with session_scope() as s:
        assert len(association.list_associations(s)) == 2
        assert len(association.list_associations(s, target_entity=c)) == 1


# --- link properties the reference field used to carry (PI-414 — REQ-506/507) ---

def test_relationship_records_a_link_whose_target_may_be_several_kinds(v2_env):
    """REQ-506: EspoCRM's linkParent — Call.parent, Meeting.parent — may point at
    any of several kinds. association_target_entity names exactly one, so such a
    link previously fell through the field translation table and was recorded as
    plain text. The permitted kinds round-trip."""
    with session_scope() as s:
        call = _seed_entity(s, "Call")
        acct = _seed_entity(s, "Account")
        cont = _seed_entity(s, "Contact")
        out = association.create_association(
            s, name="parent", source_entity=call, target_entity=acct,
            cardinality="many_to_many", target_kinds=[acct, cont],
        )
        assert out["association_target_kinds"] == [acct, cont]
        again = association.get_association(s, out["association_identifier"])
        assert again["association_target_kinds"] == [acct, cont]


def test_a_single_target_kind_is_refused_as_a_second_way_to_say_one_thing(v2_env):
    """One kind is what association_target_entity already states. Admitting a
    one-element list would recreate the two-descriptions-of-one-link duplication
    DEC-932 exists to remove."""
    with session_scope() as s:
        call = _seed_entity(s, "Call")
        acct = _seed_entity(s, "Account")
        with pytest.raises(UnprocessableError):
            association.create_association(
                s, name="parent", source_entity=call, target_entity=acct,
                cardinality="many_to_many", target_kinds=[acct],
            )


def test_target_kinds_must_name_live_entities(v2_env):
    """Every named kind is validated exactly as the single target is."""
    with session_scope() as s:
        call = _seed_entity(s, "Call")
        acct = _seed_entity(s, "Account")
        with pytest.raises(UnprocessableError):
            association.create_association(
                s, name="parent", source_entity=call, target_entity=acct,
                cardinality="many_to_many", target_kinds=[acct, "ENT-999"],
            )


def test_each_side_carries_its_own_label_and_required_flag(v2_env):
    """REQ-507: the two ends of one link are labelled and required
    independently, and a reference field only ever described the end it sat on.
    Held per side so nothing is lost when the field side goes."""
    with session_scope() as s:
        acct = _seed_entity(s, "Account")
        cont = _seed_entity(s, "Contact")
        out = association.create_association(
            s, name="primaryContact", source_entity=acct, target_entity=cont,
            cardinality="one_to_many",
            source_label="Account", target_label="Primary Contact",
            source_required=False, target_required=True,
        )
        assert out["association_source_label"] == "Account"
        assert out["association_target_label"] == "Primary Contact"
        assert out["association_source_required"] is False
        assert out["association_target_required"] is True


def test_an_unstated_required_flag_stays_unstated(v2_env):
    """None is a real answer: a relationship read from an instance that does not
    report a side's required flag must say so rather than claim False."""
    with session_scope() as s:
        acct = _seed_entity(s, "Account")
        cont = _seed_entity(s, "Contact")
        out = association.create_association(
            s, name="primaryContact", source_entity=acct, target_entity=cont,
            cardinality="one_to_many",
        )
        assert out["association_source_required"] is None
        assert out["association_target_kinds"] is None


def test_patch_persists_every_patchable_link_property(v2_env):
    """The defect this guards: the five link properties were admitted to
    _PATCHABLE_FIELDS when their columns were added but never assigned, so a
    patch carrying them validated, reported success and discarded the values.

    A write path that silently drops input is worse than one that refuses it —
    the caller is told it worked, and in this case six field records were
    retired on the strength of a fold that had written nothing. So the assertion
    is deliberately over the whole patchable set rather than one property: the
    failure was a gap between what was accepted and what was applied, and only
    checking every member closes it."""
    with session_scope() as s:
        acct = _seed_entity(s, "Account")
        cont = _seed_entity(s, "Contact")
        other = _seed_entity(s, "Lead")
        aid = association.create_association(
            s, name="primaryContact", source_entity=acct, target_entity=cont,
            cardinality="one_to_many",
        )["association_identifier"]
        out = association.patch_association(
            s, aid,
            target_kinds=[cont, other],
            source_label="Account",
            target_label="Primary Contact",
            source_required=False,
            target_required=True,
        )
        assert out["association_target_kinds"] == [cont, other]
        assert out["association_source_label"] == "Account"
        assert out["association_target_label"] == "Primary Contact"
        assert out["association_source_required"] is False
        assert out["association_target_required"] is True
        # ...and it is persisted, not merely echoed back by the patch call.
        again = association.get_association(s, aid)
        assert again["association_target_label"] == "Primary Contact"
        assert again["association_target_required"] is True


def test_every_patchable_field_has_an_assignment(v2_env):
    """Structural guard: each name admitted by _PATCHABLE_FIELDS must actually
    change the record. Catches the next property added to the whitelist without
    a corresponding assignment, which is exactly how this one slipped in."""
    with session_scope() as s:
        acct = _seed_entity(s, "Account")
        cont = _seed_entity(s, "Contact")
        aid = association.create_association(
            s, name="link", source_entity=acct, target_entity=cont,
            cardinality="one_to_many",
        )["association_identifier"]
        probes = {
            "name": "renamed", "source_entity": cont, "target_entity": acct,
            "cardinality": "many_to_many", "source_role": "a", "target_role": "b",
            "target_kinds": [acct, cont], "source_label": "L", "target_label": "R",
            "source_required": True, "target_required": True,
            "description": "d", "notes": "n", "status": "confirmed",
        }
        missing = sorted(association._PATCHABLE_FIELDS - set(probes))
        assert not missing, f"no probe for patchable field(s): {missing}"
        before = association.get_association(s, aid)
        after = association.patch_association(s, aid, **probes)
        unchanged = [
            k for k in probes
            if after.get(f"association_{k}") == before.get(f"association_{k}")
            and after.get(f"association_{k}") != probes[k]
        ]
        assert not unchanged, f"patchable but not applied: {unchanged}"
