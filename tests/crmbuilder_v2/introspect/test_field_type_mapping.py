"""EspoCRM -> engine-neutral field-type mapping — PI-374 (REQ-435/436/437)."""

from __future__ import annotations

from crmbuilder_v2.adapters.espocrm.field_types import (
    ESPO_FIELD_SHAPE,
    ESPO_LINK_FIELD_TYPES,
    ESPO_LINK_TYPES_READ_AS_RELATIONSHIPS,
)
from crmbuilder_v2.introspect.reconcile import (
    _audited_field_attrs,
    _map_field_type,
    is_unmapped_field_type,
)


def test_foreign_maps_to_distinct_foreign_kind():
    """REQ-435: an EspoCRM 'foreign' field maps to neutral 'foreign', not 'derived'
    (which would surface as text)."""
    assert _map_field_type("foreign") == "foreign"
    assert _audited_field_attrs({"type": "foreign"})["field_type"] == "foreign"


def test_formula_still_maps_to_derived():
    """A formula field stays 'derived' — only 'foreign' was split out."""
    assert _map_field_type("formula") == "derived"


def test_unrecognised_type_falls_back_to_text_but_is_flagged():
    """REQ-437: an unmapped source kind still records (as text) but is reported
    via is_unmapped_field_type so it can be surfaced for review."""
    assert _map_field_type("someNewEspoType") == "text"
    assert is_unmapped_field_type("someNewEspoType") is True
    # A recognised kind is not flagged.
    assert is_unmapped_field_type("foreign") is False
    assert is_unmapped_field_type("varchar") is False


def test_foreign_field_attrs_do_not_assume_text_result_type():
    """REQ-436: the audit no longer assumes a foreign field's mirrored value is
    text — _audited_field_attrs reports the kind as foreign and carries no
    hardcoded result type (the create path leaves it unset until known)."""
    attrs = _audited_field_attrs({"type": "foreign"})
    assert attrs["field_type"] == "foreign"
    assert "field_derived_result_type" not in attrs


# --- links are not fields (PI-414 — REQ-505 / DEC-932) ----------------------

def test_every_link_type_is_absent_from_the_field_shape_table():
    """DEC-932: a link between records is described once, as a relationship. The
    field vocabulary has no entry for one, which is why the reader must skip
    them rather than let them fall through to the unmapped-type default."""
    for espo_type in ESPO_LINK_FIELD_TYPES:
        assert espo_type not in ESPO_FIELD_SHAPE, espo_type


def test_a_link_would_otherwise_be_recorded_as_text():
    """The gap DEC-932 closes, pinned so it cannot quietly reopen: nothing in the
    type mapping stops a link becoming text — only the reader's skip does. If a
    future change gives links a shape-table entry, this test says so."""
    for espo_type in ESPO_LINK_FIELD_TYPES:
        assert is_unmapped_field_type(espo_type) is True
        assert _map_field_type(espo_type) == "text"


def test_the_polymorphic_link_is_the_one_with_no_relationship_counterpart():
    """``link``, ``linkOne`` and ``linkMultiple`` are already recorded by the
    relationship reader from the link's owning side, so skipping them as fields
    loses nothing. ``linkParent`` is not yet described (REQ-506), so it is
    reported as a known gap instead — the distinction the reader's two summary
    buckets carry."""
    assert ESPO_LINK_TYPES_READ_AS_RELATIONSHIPS < ESPO_LINK_FIELD_TYPES
    assert ESPO_LINK_FIELD_TYPES - ESPO_LINK_TYPES_READ_AS_RELATIONSHIPS == {
        "linkParent"
    }
