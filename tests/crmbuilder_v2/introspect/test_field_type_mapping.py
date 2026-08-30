"""EspoCRM -> engine-neutral field-type mapping — PI-374 (REQ-435/436/437)."""

from __future__ import annotations

from crmbuilder_v2.access.vocab import ASSOCIATION_CARDINALITIES
from crmbuilder_v2.adapters.espocrm.field_types import (
    ESPO_FIELD_SHAPE,
    ESPO_LINK_FIELD_TYPES,
    ESPO_LINK_TYPES_READ_AS_RELATIONSHIPS,
)
from crmbuilder_v2.introspect.reconcile import (
    _LINK_CARDINALITY,
    _audited_field_attrs,
    _map_field_type,
    _parent_link_kinds,
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
    """The mapper's own behaviour, which REQ-503 has since made unreachable from
    the reader: an unmapped kind still resolves to text here, but the readers now
    detect it with is_unmapped_field_type and skip before _audited_field_attrs is
    ever called, so nothing is stored from this fallback. Kept because the
    fallback is what makes the detection necessary."""
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


# --- the polymorphic parent link (PI-414 — REQ-506) ------------------------

def test_the_polymorphic_parent_is_recorded_from_the_child_side():
    """REQ-506: every other many-to-one link is recorded as one_to_many from its
    owning side, but a parent link's owning side is several entities at once.
    It is recorded from the child, which is what many_to_one exists to say."""
    assert _LINK_CARDINALITY["belongsToParent"] == "many_to_one"
    assert "many_to_one" in ASSOCIATION_CARDINALITIES


def test_the_reciprocal_of_the_parent_link_stays_unprocessed():
    """hasChildren appears on every permitted parent kind, so processing it
    would create one relationship per kind — the duplication DEC-932 removes."""
    assert "hasChildren" not in _LINK_CARDINALITY
    assert "belongsTo" not in _LINK_CARDINALITY


class _FieldListClient:
    def __init__(self, fields): self._fields = fields
    def get_entity_field_list(self, entity): return 200, self._fields


def test_permitted_kinds_are_read_from_the_field_not_the_link():
    """EspoCRM states a parent link's permitted kinds on the field
    (linkParent.entityList), never on the link, so describing one relationship
    needs both reads."""
    client = _FieldListClient(
        {"parent": {"type": "linkParent", "entityList": ["Account", "Contact"]}}
    )
    kinds = _parent_link_kinds(
        client, "Call", "parent", {"account": "ENT-1", "contact": "ENT-2"}
    )
    assert kinds == ["ENT-1", "ENT-2"]


def test_kinds_outside_the_canonical_inventory_are_dropped():
    """A kind the design does not carry is dropped, exactly as a single target
    outside the inventory is skipped."""
    client = _FieldListClient(
        {"parent": {"type": "linkParent",
                    "entityList": ["Account", "Contact", "Lead"]}}
    )
    kinds = _parent_link_kinds(
        client, "Call", "parent", {"account": "ENT-1", "contact": "ENT-2"}
    )
    assert kinds == ["ENT-1", "ENT-2"]


def test_fewer_than_two_surviving_kinds_is_undescribed_not_narrowed():
    """Recording one kind would claim the link is narrower than the CRM allows.
    The reader reports it undescribed instead — a known gap beats a false
    statement, which is the whole premise of this vocabulary work."""
    client = _FieldListClient(
        {"parent": {"type": "linkParent", "entityList": ["Account", "Lead"]}}
    )
    assert _parent_link_kinds(
        client, "Call", "parent", {"account": "ENT-1"}
    ) is None


def test_an_unreadable_field_list_is_undescribed_rather_than_assumed():
    """A failed read is not an empty answer."""
    class _Broken:
        def get_entity_field_list(self, entity): return 403, None
    assert _parent_link_kinds(_Broken(), "Call", "parent", {}) is None


# --- skipping must not read as absence (PI-414 — REQ-505 follow-up) ---------

class _Writer:
    """The sweep-relevant half of the membership writer."""

    def __init__(self):
        self.seen = set()
        self.verdicts = {}

    def upsert(self, mid, state, override=None):
        self.verdicts[mid] = state
        self.seen.add(mid)

    def mark_seen(self, mid):
        self.seen.add(mid)

    def swept_absent(self, design_ids):
        return {i for i in design_ids if i not in self.seen}


def test_a_skipped_link_does_not_sweep_its_design_record_to_absent():
    """The defect this guards: skipping a link-typed field means it never
    reaches upsert, so a design record still describing that link as a field
    falls out of the seen set and the sweep marks it absent — reporting the
    instance as missing a field it actually has. Absence must only ever be a
    positive observation; the design record is the wrong shape, which is a
    different statement."""
    w = _Writer()
    w.mark_seen("FLD-223")                      # the link the reader skipped
    w.upsert("FLD-100", "present")              # an ordinary field
    assert w.swept_absent({"FLD-223", "FLD-100"}) == set()


def test_mark_seen_records_no_verdict_of_its_own():
    """It suppresses a false absent without inventing a fresh claim: the prior
    verdict and its timestamp stand, which reads as an old reading rather than
    as a new assertion about a field the design should not hold."""
    w = _Writer()
    w.mark_seen("FLD-223")
    assert "FLD-223" not in w.verdicts


# --- unrecognized, not approximated (PI-414 — REQ-503 / DEC-930) ------------

def test_the_reader_detects_before_it_translates():
    """REQ-503 turns on order: is_unmapped_field_type is a check on the raw CRM
    type, so the reader can decide not to describe a field before
    _audited_field_attrs manufactures a kind for it."""
    assert is_unmapped_field_type("someNewEspoType") is True
    # ...and the translation it precedes would have produced a nearest match.
    assert _audited_field_attrs({"type": "someNewEspoType"})["field_type"] == "text"


def test_a_recognised_kind_is_not_diverted():
    """The skip must be narrow: every kind the vocabulary covers still
    translates and is still stored."""
    for espo_type in ("varchar", "foreign", "formula", "enum"):
        assert is_unmapped_field_type(espo_type) is False


def test_no_unrecognized_token_was_added_to_the_vocabulary():
    """DEC-930: expressiveness is added as qualifying attributes on a small
    base-type set, not as new type tokens. REQ-503 is satisfied by describing
    nothing and saying so, not by storing a kind that means 'no kind'."""
    from crmbuilder_v2.access.vocab import FIELD_TYPES
    assert "unrecognized" not in FIELD_TYPES
    assert "unknown" not in FIELD_TYPES
