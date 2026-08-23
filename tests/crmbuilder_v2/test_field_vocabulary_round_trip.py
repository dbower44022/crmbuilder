"""The field vocabulary must round-trip in both directions — PI-414 (REQ-501).

REQ-501 says a field read from a CRM can be described in design terms and
rendered back to that CRM as the same field, with nothing lost in between.
That is not a claim a review can settle; it is a property, and this is the
check that measures it.

**Two directions, both required.**

* engine → design → engine, for every field type the engine declares. A type
  that comes back as something else did not survive.
* design → engine → design, for every kind the design permits, including its
  qualifying properties. A kind that comes back as something else did not
  survive either.

**Today it fails, and that is the point.** Thirteen of EspoCRM's forty-six field
types survive; thirty-three do not. Rich text returns as plain multi-line text.
Every type the translation table does not recognise — an attachment, an image, a
duration, a colour, a barcode, a postal address, structured data — falls through
to text and returns as ``varchar``, silently. That silent fallback is why the gap
was invisible from reading the code, and why REQ-503 replaces it with an
unrecognized outcome.

It was nine when this check was first written. Reading the two qualifying
properties the design already stored but never filled — the format that separates
an email address, a phone number and a web address from plain text, and the scale
that separates a decimal from a whole number — moved four types from lost to
surviving without a single new word entering the vocabulary.

**The round trip runs through the whole field, not just its type.** ``varchar``
and ``email`` are the same neutral kind and are told apart only by the format, so
a check that compared kinds alone would measure the wrong thing and could never
record an improvement.

The surviving set is frozen in :data:`SURVIVES_TODAY` rather than asserted
loosely, so this check does two jobs at once: it fails if a type that used to
survive stops surviving, and it fails when a type *starts* surviving without the
baseline being updated. The second is the one that matters while PI-414 runs —
the number is meant to climb, and each climb should be a deliberate edit here
with the ruling that caused it.

**Not yet reflected.** The rulings recorded on 2026-08-23 (DEC-932 to DEC-940)
are approved but unbuilt. When they land, the losses these tests record become
either survivals or *declared* exceptions naming what is lost. Nothing in this
module encodes the new vocabulary; it measures what exists.

Run ``pytest -s`` on this module to print the full table.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import FIELD_TYPES
from crmbuilder_v2.adapters.espocrm.model import _map_field_type as emit_type
from crmbuilder_v2.introspect.reconcile import _audited_field_attrs
from crmbuilder_v2.introspect.reconcile import _map_field_type as capture_type

#: Every field type EspoCRM declares, one per file in
#: ``application/Espo/Resources/metadata/fields/`` on the ``espocrm/espocrm``
#: default branch, read 2026-08-23. ``base`` is the shared definition the others
#: extend rather than a type an administrator picks; it is kept so the inventory
#: matches the source directory exactly.
ESPOCRM_FIELD_TYPES: tuple[str, ...] = (
    "address", "array", "arrayInt", "attachmentMultiple", "autoincrement",
    "barcode", "base", "bool", "checklist", "colorpicker", "currency",
    "currencyConverted", "date", "datetime", "datetimeOptional", "decimal",
    "duration", "email", "enum", "enumFloat", "enumInt", "file", "float",
    "foreign", "image", "int", "jsonArray", "jsonObject", "link",
    "linkMultiple", "linkOne", "linkParent", "map", "multiEnum", "number",
    "password", "personName", "phone", "rangeCurrency", "rangeFloat",
    "rangeInt", "text", "url", "urlMultiple", "varchar", "wysiwyg",
)

#: The EspoCRM types that survive engine → design → engine unchanged, as of
#: 2026-08-23. Thirteen of forty-six. Update this deliberately, naming the change
#: that moved it — never to make a failing run pass.
#:
#: History: nine at the baseline. ``email``, ``phone``, ``url`` and ``float``
#: joined when the reader began recording the format and numeric scale it had
#: always been able to derive but never wrote (PI-414 / REQ-501).
SURVIVES_TODAY: frozenset[str] = frozenset({
    "bool", "currency", "date", "datetime", "email", "enum", "float", "int",
    "multiEnum", "phone", "text", "url", "varchar",
})

#: Design kinds that do not reach the engine at all: the emitter returns no type
#: for them, so they cannot round-trip by construction. ``reference`` leaves the
#: field vocabulary entirely under DEC-932 — a link is described once, as a
#: relationship — so it will drop out of this set rather than be fixed in it.
NOT_EMITTED_TODAY: frozenset[str] = frozenset({"derived", "foreign", "reference"})

#: Kinds the design can express that the EspoCRM adapter cannot yet produce.
#: Each has a genuine EspoCRM counterpart — ``address``, ``personName``, ``map``,
#: ``file``, ``jsonObject`` — so these are unfinished work, not engine limits,
#: and the set should empty as the emitter is taught them. Declaring the kinds
#: before the adapter can build them is deliberate: the vocabulary is settled
#: first (DEC-934, DEC-936), the adapters follow.
AWAITING_EMITTER: frozenset[str] = frozenset({
    "postal_address", "person_name", "place", "file", "structured_data",
})

#: Kinds EspoCRM genuinely cannot hold, however much work is done. EspoCRM has no
#: plain time-of-day type — its 46 types include ``datetime`` and
#: ``datetimeOptional`` but nothing for a time alone — so a design that says
#: ``time`` has no faithful EspoCRM rendering. This is the declared exception
#: REQ-502 requires: the translation must say what is lost rather than
#: substitute a near equivalent, and a per-CRM not-comparable declaration
#: (DEC-930) follows for it.
ENGINE_CANNOT_HOLD: frozenset[str] = frozenset({"time"})


def _round_trip_engine(espo_type: str) -> tuple[str, str | None]:
    """Return ``(design_kind, engine_type_returned)`` for one engine type.

    Reads the whole field, not just its type: ``varchar`` and ``email`` share a
    neutral kind and are separated only by the format the reader derives, so
    comparing kinds alone would measure the wrong thing.
    """
    audited = _audited_field_attrs({"type": espo_type})
    return audited["field_type"], emit_type(audited)


def _round_trip_design(field_row: dict) -> tuple[str | None, str | None]:
    """Return ``(engine_type, design_kind_returned)`` for one design field."""
    engine = emit_type(field_row)
    return engine, capture_type(engine) if engine else None


# ---------------------------------------------------------------------------
# engine → design → engine
# ---------------------------------------------------------------------------


def test_every_engine_type_is_accounted_for():
    """No engine type may be silently absent from the inventory this measures."""
    assert len(ESPOCRM_FIELD_TYPES) == 46
    assert len(set(ESPOCRM_FIELD_TYPES)) == 46


@pytest.mark.parametrize("espo_type", ESPOCRM_FIELD_TYPES)
def test_engine_type_round_trip_matches_the_frozen_baseline(espo_type: str):
    """Each engine type either survives the round trip or is a recorded loss.

    A parametrized case per type so a failure names the type that moved rather
    than reporting one opaque set difference.
    """
    _, returned = _round_trip_engine(espo_type)
    survives = returned == espo_type
    expected = espo_type in SURVIVES_TODAY
    assert survives == expected, (
        f"{espo_type!r} now returns {returned!r}; the frozen baseline says it "
        f"{'survives' if expected else 'does not survive'}. If a ruling changed "
        f"this, update SURVIVES_TODAY and name the ruling."
    )


def test_the_survival_rate_is_recorded_not_assumed():
    """Thirteen of forty-six. The number is the point; it should climb deliberately."""
    survivors = {t for t in ESPOCRM_FIELD_TYPES if _round_trip_engine(t)[1] == t}
    assert survivors == SURVIVES_TODAY


def test_the_silent_fallback_is_what_hides_the_loss():
    """An unrecognised engine type becomes text and returns as ``varchar``.

    REQ-503 replaces this with an unrecognized outcome. Until it does, a colour
    picker, a barcode, an attachment and a postal address are indistinguishable
    in the design from a plain text box — which is why the gap was invisible
    from reading the code.
    """
    for espo_type in ("colorpicker", "barcode", "attachmentMultiple", "address"):
        kind, returned = _round_trip_engine(espo_type)
        assert kind == "text"
        assert returned == "varchar"


# ---------------------------------------------------------------------------
# design → engine → design
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(FIELD_TYPES))
def test_design_kind_round_trip(kind: str):
    """Every design kind survives, or is accounted for in exactly one category.

    The three categories are not interchangeable and the distinction is the
    point. A kind that leaves the field vocabulary is settled. A kind waiting on
    the emitter is unfinished work with a known destination. A kind the engine
    cannot hold at all is a declared exception that will never close — and under
    REQ-502 the translation has to say so rather than quietly substitute
    something near it.
    """
    engine, returned = _round_trip_design({"field_type": kind})
    if kind in NOT_EMITTED_TODAY | AWAITING_EMITTER | ENGINE_CANNOT_HOLD:
        assert engine is None, (
            f"{kind!r} now emits {engine!r} — it is recorded as not reaching the "
            f"engine, so move it out of that set and say why"
        )
        return
    assert returned == kind, (
        f"design kind {kind!r} emitted as {engine!r} and returned as {returned!r}"
    )


def test_the_categories_do_not_overlap_and_cover_what_they_claim():
    """A kind belongs to exactly one category, and every kind is accounted for.

    Without this, a kind could sit in two sets and its real status would depend
    on which one was read first.
    """
    assert not NOT_EMITTED_TODAY & AWAITING_EMITTER
    assert not NOT_EMITTED_TODAY & ENGINE_CANNOT_HOLD
    assert not AWAITING_EMITTER & ENGINE_CANNOT_HOLD
    accounted = NOT_EMITTED_TODAY | AWAITING_EMITTER | ENGINE_CANNOT_HOLD
    assert accounted <= FIELD_TYPES, "a category names a kind the design does not have"


def test_every_kind_awaiting_the_emitter_has_an_espocrm_counterpart():
    """The distinction between unfinished work and an engine limit must be real.

    Each kind in :data:`AWAITING_EMITTER` is claimed to have somewhere to go in
    EspoCRM. If one does not, it belongs in :data:`ENGINE_CANNOT_HOLD` instead,
    and calling it unfinished work would be a standing false promise.
    """
    counterparts = {
        "postal_address": "address",
        "person_name": "personName",
        "place": "map",
        "file": "file",
        "structured_data": "jsonObject",
    }
    assert set(counterparts) == set(AWAITING_EMITTER)
    for kind, espo_type in counterparts.items():
        assert espo_type in ESPOCRM_FIELD_TYPES, (
            f"{kind!r} is recorded as awaiting the emitter, but EspoCRM has no "
            f"{espo_type!r} — it belongs in ENGINE_CANNOT_HOLD"
        )


def test_a_time_of_day_has_no_espocrm_counterpart():
    """The one declared exception, verified against the engine's own type list.

    EspoCRM carries ``datetime`` and ``datetimeOptional`` but nothing for a time
    alone, so a design that says ``time`` cannot be rendered faithfully. Pinned
    so the exception rests on the engine's inventory rather than on memory.
    """
    assert "time" not in ESPOCRM_FIELD_TYPES
    assert "datetime" in ESPOCRM_FIELD_TYPES
    assert ENGINE_CANNOT_HOLD == {"time"}


# ---------------------------------------------------------------------------
# The qualifying properties
# ---------------------------------------------------------------------------


def test_format_survives_the_round_trip_in_both_directions():
    """The asymmetry REQ-501 exists to remove, now closed for these three.

    The emitter always refined a text field to the richer engine type from its
    format; the reader never wrote one back, so a design could build an email
    field and then fail to recognise it. Both halves now hold, which is why the
    format property being empty on all 254 CBM design fields is a backfill
    question rather than a missing capability.
    """
    for fmt, expected_engine in (("email", "email"), ("phone", "phone"), ("url", "url")):
        engine, returned = _round_trip_design({"field_type": "text", "field_format": fmt})
        assert engine == expected_engine, f"format {fmt!r} did not refine the emitted type"
        assert returned == "text", "the returned kind should still be text"
        assert _audited_field_attrs({"type": engine})["field_format"] == fmt, (
            f"the reader lost the {fmt!r} format on the way back"
        )


def test_numeric_scale_survives_the_round_trip_in_both_directions():
    """Whole versus decimal numbers, the one loss that changed a field's value.

    A decimal used to emit as ``float``, return as the ``number`` kind with no
    scale, and emit again as ``int`` — the round trip silently turned a decimal
    into a whole number. Reading the scale back closes it.
    """
    for scale, expected_engine in (("decimal", "float"), ("integer", "int")):
        row = {"field_type": "number", "field_numeric_scale": scale}
        engine, returned = _round_trip_design(row)
        assert engine == expected_engine
        assert returned == "number"
        read_back = _audited_field_attrs({"type": engine})
        assert read_back["field_numeric_scale"] == scale
        # The second pass now reproduces the same engine type, not int-by-default.
        assert emit_type(read_back) == expected_engine


def test_report(capsys):
    """Print the full two-direction table. Visible under ``pytest -s``."""
    lines = ["", "engine -> design -> engine", ""]
    survivors = 0
    for espo_type in ESPOCRM_FIELD_TYPES:
        kind, returned = _round_trip_engine(espo_type)
        ok = returned == espo_type
        survivors += ok
        lines.append(
            f"  {espo_type:<20} {kind:<14} {str(returned):<10} {'ok' if ok else 'LOST'}"
        )
    lines += ["", f"  {survivors} of {len(ESPOCRM_FIELD_TYPES)} survive", ""]
    lines += ["design -> engine -> design", ""]
    for kind in sorted(FIELD_TYPES):
        engine, returned = _round_trip_design({"field_type": kind})
        ok = returned == kind
        state = "ok" if ok else ("not emitted" if engine is None else "LOST")
        lines.append(f"  {kind:<16} {str(engine):<10} {str(returned):<16} {state}")
    with capsys.disabled():
        print("\n".join(lines))
