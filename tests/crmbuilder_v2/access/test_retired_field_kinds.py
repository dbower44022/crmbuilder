"""A retired field kind leaves use, not the vocabulary — PI-414 (REQ-505 / DEC-988)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.vocab import (
    FIELD_STATUSES,
    FIELD_TYPES,
    LIVE_FIELD_STATUSES,
    RETIRED_FIELD_TYPES,
)


def _entity(s, name="Account"):
    return entity_repo.create_entity(s, name=name, description="seed")[
        "entity_identifier"
    ]


def test_a_retired_kind_stays_in_the_vocabulary():
    """It must, or the CHECK would invalidate the records DEC-016 retained — a
    database constraint applies to every row whatever its status."""
    assert RETIRED_FIELD_TYPES <= FIELD_TYPES
    assert "reference" in RETIRED_FIELD_TYPES


def test_live_statuses_are_every_status_but_rejected():
    """Rejected is retained history and describes nothing; everything else
    asserts something about a CRM."""
    assert LIVE_FIELD_STATUSES | {"rejected"} == FIELD_STATUSES
    assert "rejected" not in LIVE_FIELD_STATUSES


@pytest.mark.parametrize("status", sorted(LIVE_FIELD_STATUSES))
def test_a_retired_kind_cannot_describe_a_live_field(v2_env, status):
    """REQ-505's guarantee, enforced where the harm is. DEC-932's stated harm is
    two live descriptions of one link, so every status that describes something
    refuses the kind."""
    with session_scope() as s:
        eid = _entity(s)
        with pytest.raises(UnprocessableError) as exc:
            field_repo.create_field(
                s, field_belongs_to_entity_identifier=eid, name="partnerProfile",
                description="x", type="reference", required=False, status=status,
            )
        assert "retired" in str(exc.value).lower()


def test_a_retired_kind_is_refused_when_no_status_is_stated(v2_env):
    """The safe reading: a retired kind arriving with no stated status is far
    more likely a new record than a retention, so it is refused."""
    with session_scope() as s:
        eid = _entity(s)
        with pytest.raises(UnprocessableError):
            field_repo.create_field(
                s, field_belongs_to_entity_identifier=eid, name="x",
                description="x", type="reference", required=False,
            )


def test_a_live_field_cannot_be_patched_onto_a_retired_kind(v2_env):
    """Creation is not the only way in. A field could otherwise be created as
    text and then moved to the retired kind, which is the same harm by a
    different route."""
    with session_scope() as s:
        eid = _entity(s)
        fid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="partnerProfile",
            description="x", type="text", required=False,
        )["field_identifier"]
        with pytest.raises(UnprocessableError):
            field_repo.patch_field(s, fid, type="reference")


def test_an_ordinary_kind_is_untouched(v2_env):
    """The refusal is narrow: every kind still in use creates normally."""
    with session_scope() as s:
        eid = _entity(s)
        out = field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="phone",
            description="x", type="text", required=False,
        )
        assert out["field_type"] == "text"
