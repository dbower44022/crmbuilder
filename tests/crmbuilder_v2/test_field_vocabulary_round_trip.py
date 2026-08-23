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

**Today it fails, and that is the point.** Nine of EspoCRM's forty-six field
types survive; thirty-seven do not. An email address, a phone number and a web
address all collapse into plain text and return as ``varchar``. Rich text
returns as plain multi-line text. Every type the translation table does not
recognise — an attachment, an image, a duration, a colour, a barcode, a postal
address, structured data — falls through to text and returns as ``varchar``,
silently. That silent fallback is why the gap was invisible from reading the
code, and why REQ-503 replaces it with an unrecognized outcome.

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
#: 2026-08-23. Nine of forty-six. Update this deliberately, naming the ruling
#: that changed it — never to make a failing run pass.
SURVIVES_TODAY: frozenset[str] = frozenset({
    "bool", "currency", "date", "datetime", "enum", "int", "multiEnum",
    "text", "varchar",
})

#: Design kinds that do not reach the engine at all: the emitter returns no type
#: for them, so they cannot round-trip by construction. ``reference`` leaves the
#: field vocabulary entirely under DEC-932 — a link is described once, as a
#: relationship — so it will drop out of this set rather than be fixed in it.
NOT_EMITTED_TODAY: frozenset[str] = frozenset({"derived", "foreign", "reference"})


def _round_trip_engine(espo_type: str) -> tuple[str, str | None]:
    """Return ``(design_kind, engine_type_returned)`` for one engine type."""
    kind = capture_type(espo_type)
    return kind, emit_type({"field_type": kind})


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
    """Nine of forty-six. The number is the point; it should climb deliberately."""
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
    """Every design kind either survives, or is one that never reaches the engine."""
    engine, returned = _round_trip_design({"field_type": kind})
    if kind in NOT_EMITTED_TODAY:
        assert engine is None, f"{kind!r} now emits {engine!r} — update NOT_EMITTED_TODAY"
        return
    assert returned == kind, (
        f"design kind {kind!r} emitted as {engine!r} and returned as {returned!r}"
    )


# ---------------------------------------------------------------------------
# The qualifying properties
# ---------------------------------------------------------------------------


def test_format_reaches_the_engine_but_does_not_come_back():
    """A format refines the emitted type, and the reading loses it again.

    This is the asymmetry REQ-501 exists to remove: the design can say a field
    is an email address and the CRM will build one, but reading that CRM back
    yields a design that no longer knows. It is also why the format property is
    empty on all 254 CBM design fields — nothing ever writes it.
    """
    for fmt, expected_engine in (("email", "email"), ("phone", "phone"), ("url", "url")):
        row = {"field_type": "text", "field_format": fmt}
        engine, returned = _round_trip_design(row)
        assert engine == expected_engine, f"format {fmt!r} did not refine the type"
        assert returned == "text", "the returned kind should still be text"
        # The kind survives; the format does not, because nothing reads it back.


def test_numeric_scale_reaches_the_engine_but_does_not_come_back():
    """The same asymmetry for whole versus decimal numbers.

    A decimal number emits as ``float`` and returns as the ``number`` kind with
    no scale, so a second emit produces ``int`` — the round trip changes the
    field. This is the one loss in this module that is a *silent value change*
    rather than a lost distinction.
    """
    decimal = {"field_type": "number", "field_numeric_scale": "decimal"}
    engine, returned = _round_trip_design(decimal)
    assert engine == "float"
    assert returned == "number"
    # Second pass, with the scale no longer known:
    assert emit_type({"field_type": returned}) == "int"


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
