"""The field vocabulary must round-trip in both directions — PI-414 (REQ-501).

REQ-501 says a field read from a CRM can be described in design terms and
rendered back to that CRM as the same field, with nothing lost in between. That
is a property, not a claim a review can settle, so this measures it.

**Two directions.** Engine → design → engine for every field type EspoCRM
declares, and design → engine → design for every kind the design permits. Both
run through the *whole field*, not just its type: ``varchar`` and ``email`` are
the same kind and are told apart only by the format, ``multiEnum`` and
``checklist`` only by the display. A check comparing kinds alone would measure
the wrong thing and could never record an improvement.

**Where the number has been.**

* 9 of 46 at the baseline, before any of this work.
* 13 after the reader began recording the format and numeric scale it had always
  been able to derive but never wrote.
* 38 of 41 in scope once both sides were taught the vocabulary DEC-932 to
  DEC-940 settled.

**Scope is 41, not 46.** Four link types leave the field vocabulary entirely — a
link between records is described once, as a relationship (DEC-932 / REQ-505) —
and ``base`` is the shared definition the other types extend rather than a type
an administrator picks. Counting them as field-vocabulary losses would be
counting work that was deliberately moved elsewhere.

**The three that do not survive are declared, not outstanding.** Two are cases
where EspoCRM spells one neutral shape two ways; one is emitted by a different
code path. None is unfinished work, and each is pinned below with the reason, so
a reader can tell a real gap from a settled one.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import FIELD_TYPES
from crmbuilder_v2.adapters.espocrm.field_types import properties_not_carried
from crmbuilder_v2.adapters.espocrm.model import _map_field_type as emit_type
from crmbuilder_v2.introspect.reconcile import _audited_field_attrs

#: Every field type EspoCRM declares, one per file in
#: ``application/Espo/Resources/metadata/fields/`` on the ``espocrm/espocrm``
#: default branch, read 2026-08-23.
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

#: Engine types that are not field-vocabulary concerns. The four link types are
#: described once, as relationships (DEC-932 / REQ-505); ``base`` is the shared
#: definition the others extend.
NOT_FIELD_VOCABULARY: frozenset[str] = frozenset({
    "link", "linkOne", "linkParent", "linkMultiple", "base",
})

IN_SCOPE: tuple[str, ...] = tuple(
    t for t in ESPOCRM_FIELD_TYPES if t not in NOT_FIELD_VOCABULARY
)

#: EspoCRM offers two type names for one neutral shape, so the design normalises
#: to one and the round trip returns the other. Nothing is lost about the field —
#: a ``decimal`` and a ``float`` are both a number with decimals, an
#: ``autoincrement`` and a ``number`` are both a value the CRM assigns — but the
#: type name changes, so REQ-501 requires it be declared rather than discovered.
ENGINE_SPELLS_IT_TWICE: dict[str, str] = {
    "decimal": "float",
    "number": "autoincrement",
}

#: Emitted by a path this function does not cover: a foreign field needs its
#: mirror coordinates, which ``_map_field_type`` never sees.
EMITTED_BY_ANOTHER_PATH: frozenset[str] = frozenset({"foreign"})

#: The engine types that survive engine → design → engine unchanged. Update this
#: deliberately, naming the change that moved it — never to make a failing run
#: pass.
SURVIVES_TODAY: frozenset[str] = frozenset(
    set(IN_SCOPE) - set(ENGINE_SPELLS_IT_TWICE) - EMITTED_BY_ANOTHER_PATH
)

#: Design kinds that never reach the engine, and why. ``reference`` left the
#: field vocabulary (DEC-932). ``derived`` and ``foreign`` are emitted by their
#: own paths. ``time`` is the declared exception REQ-502 exists for: EspoCRM has
#: ``datetime`` and ``datetimeOptional`` but nothing for a time of day alone, so
#: it will never close however much work is done.
KIND_NOT_EMITTED: frozenset[str] = frozenset(
    {"reference", "derived", "foreign", "time"}
)

# The multi-choice kind DEC-937 retired is gone from the vocabulary as of
# 2026-08-27, so it no longer needs a category here.


def _round_trip_engine(espo_type: str) -> tuple[str, str | None]:
    """Return ``(design_kind, engine_type_returned)`` for one engine type."""
    audited = _audited_field_attrs({"type": espo_type})
    return audited["field_type"], emit_type(audited)


def _round_trip_design(field_row: dict) -> tuple[str | None, str | None]:
    """Return ``(engine_type, design_kind_returned)`` for one design field."""
    engine = emit_type(field_row)
    returned = _audited_field_attrs({"type": engine})["field_type"] if engine else None
    return engine, returned


# ---------------------------------------------------------------------------
# engine → design → engine
# ---------------------------------------------------------------------------


def test_the_engine_inventory_is_complete_and_scoped():
    """46 declared, 5 outside the field vocabulary, 41 measured."""
    assert len(ESPOCRM_FIELD_TYPES) == 46
    assert len(set(ESPOCRM_FIELD_TYPES)) == 46
    assert NOT_FIELD_VOCABULARY <= set(ESPOCRM_FIELD_TYPES)
    assert len(IN_SCOPE) == 41


@pytest.mark.parametrize("espo_type", IN_SCOPE)
def test_engine_type_round_trip(espo_type: str):
    """Each in-scope engine type survives, or is a declared exception.

    Parametrized per type so a failure names the type that moved rather than
    reporting one opaque set difference.
    """
    _, returned = _round_trip_engine(espo_type)
    if espo_type in ENGINE_SPELLS_IT_TWICE:
        assert returned == ENGINE_SPELLS_IT_TWICE[espo_type], (
            f"{espo_type!r} is declared to normalise to "
            f"{ENGINE_SPELLS_IT_TWICE[espo_type]!r} but returned {returned!r}"
        )
        return
    if espo_type in EMITTED_BY_ANOTHER_PATH:
        assert returned is None
        return
    assert returned == espo_type, (
        f"{espo_type!r} returned {returned!r}. If a change moved this, update "
        f"the baseline and name the change."
    )


def test_the_survival_rate_is_recorded_not_assumed():
    """38 of 41. The number is the point; it should climb deliberately."""
    survivors = {t for t in IN_SCOPE if _round_trip_engine(t)[1] == t}
    assert survivors == SURVIVES_TODAY
    assert len(survivors) == 38


def test_a_type_the_engine_spells_twice_loses_only_its_name():
    """The two declared exceptions change type name and nothing else.

    If one of these ever lost a property as well, it would stop being a naming
    difference and become a real loss — worth failing over.
    """
    for espo_type, normalised in ENGINE_SPELLS_IT_TWICE.items():
        original = _audited_field_attrs({"type": espo_type})
        returned = _audited_field_attrs({"type": normalised})
        assert original == returned, (
            f"{espo_type!r} and {normalised!r} no longer read as the same field"
        )


# ---------------------------------------------------------------------------
# design → engine → design
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(FIELD_TYPES))
def test_design_kind_round_trip(kind: str):
    """Every design kind survives, or is accounted for in exactly one category."""
    engine, returned = _round_trip_design({"field_type": kind})
    if kind in KIND_NOT_EMITTED:
        assert engine is None, (
            f"{kind!r} now emits {engine!r} — move it out of KIND_NOT_EMITTED "
            f"and say why"
        )
        return
    assert returned == kind, (
        f"design kind {kind!r} emitted as {engine!r} and returned as {returned!r}"
    )


def test_the_categories_do_not_overlap():
    """A kind belongs to exactly one category, so its status is unambiguous."""
    assert KIND_NOT_EMITTED <= FIELD_TYPES


def test_a_time_of_day_has_no_espocrm_counterpart():
    """The declared exception, verified against the engine's own inventory.

    Pinned so it rests on EspoCRM's type list rather than on memory. If EspoCRM
    ever adds a time type, this fails and the exception should be retired.
    """
    assert "time" not in ESPOCRM_FIELD_TYPES
    assert "datetime" in ESPOCRM_FIELD_TYPES
    assert emit_type({"field_type": "time"}) is None


# ---------------------------------------------------------------------------
# The qualifying properties
# ---------------------------------------------------------------------------


def test_a_secret_is_never_built_as_an_ordinary_field():
    """REQ-515 — the one case where getting it wrong is a real-world harm.

    A design that cannot say a field is sensitive could deploy it as an ordinary
    field holding sensitive values. This is the assertion that stops that.
    """
    assert emit_type({"field_type": "text", "field_format": "secret"}) == "password"
    assert _audited_field_attrs({"type": "password"})["field_format"] == "secret"


def test_qualifying_properties_survive_in_both_directions():
    """Each property that separates types sharing a kind round-trips."""
    cases = [
        ({"field_type": "text", "field_format": "email"}, "email"),
        ({"field_type": "text", "field_display": "barcode"}, "barcode"),
        ({"field_type": "long_text", "field_display": "rich_text"}, "wysiwyg"),
        ({"field_type": "number", "field_numeric_scale": "decimal"}, "float"),
        ({"field_type": "money", "field_display": "range"}, "rangeCurrency"),
        (
            {"field_type": "enum", "field_values": "fixed", "field_holds": "several"},
            "multiEnum",
        ),
        (
            {"field_type": "enum", "field_values": "open", "field_holds": "several"},
            "array",
        ),
        ({"field_type": "file", "field_holds": "several"}, "attachmentMultiple"),
        ({"field_type": "file", "field_format": "image"}, "image"),
        (
            {"field_type": "datetime", "field_format": "time_optional"},
            "datetimeOptional",
        ),
        ({"field_type": "number", "field_supplied_by": "this_crm"}, "autoincrement"),
    ]
    for design, expected_engine in cases:
        engine = emit_type(design)
        assert engine == expected_engine, f"{design} emitted {engine!r}"
        read_back = _audited_field_attrs({"type": engine})
        for prop, value in design.items():
            assert read_back[prop] == value, (
                f"{expected_engine!r} lost {prop}={value!r} on the way back "
                f"(read {read_back[prop]!r})"
            )


def test_report(capsys):
    """Print the two-direction table. Visible under ``pytest -s``."""
    lines = ["", "engine -> design -> engine", ""]
    survivors = 0
    for espo_type in IN_SCOPE:
        kind, returned = _round_trip_engine(espo_type)
        ok = returned == espo_type
        survivors += ok
        note = ""
        if espo_type in ENGINE_SPELLS_IT_TWICE:
            note = "declared: engine spells it twice"
        elif espo_type in EMITTED_BY_ANOTHER_PATH:
            note = "declared: emitted elsewhere"
        lines.append(
            f"  {espo_type:<20} {kind:<16} {str(returned):<18} "
            f"{'ok' if ok else note}"
        )
    lines += ["", f"  {survivors} of {len(IN_SCOPE)} survive", ""]
    lines += ["design -> engine -> design", ""]
    for kind in sorted(FIELD_TYPES):
        engine, returned = _round_trip_design({"field_type": kind})
        ok = returned == kind
        if kind in KIND_NOT_EMITTED:
            state = "declared: not emitted"
        else:
            state = "ok" if ok else "LOST"
        lines.append(f"  {kind:<16} {str(engine):<18} {str(returned):<16} {state}")
    with capsys.disabled():
        print("\n".join(lines))


# ---------------------------------------------------------------------------
# What the engine cannot carry must be declared, not dropped
# ---------------------------------------------------------------------------


def test_a_percentage_is_declared_lost_rather_than_silently_dropped():
    """DEC-941 / REQ-502 — EspoCRM has no percentage of any kind.

    Not a field type, not a setting on its number fields, and nothing in its
    codebase but stylesheet maths and an icon name. So a design that says a
    number is a percentage builds a plain number, and the percentage intent has
    to be reported. Before this it vanished with nothing recording that it had —
    the silent substitution REQ-502 exists to forbid.
    """
    design = {"field_type": "number", "field_format": "percent"}
    espo_type = emit_type(design)
    assert espo_type == "int", "a percentage should still build a number"
    assert properties_not_carried(design, espo_type) == [("field_format", "percent")]


def test_the_loss_check_does_not_cry_wolf():
    """A declared property the engine *does* carry is never reported as lost.

    A check that over-reports is as useless as one that under-reports: an
    operator who learns to ignore these lines will ignore the percentage one
    too. Every combination here has a faithful EspoCRM rendering.
    """
    faithful = [
        {"field_type": "text", "field_format": "email"},
        {"field_type": "text", "field_format": "secret"},
        {"field_type": "long_text", "field_display": "rich_text"},
        {"field_type": "number", "field_numeric_scale": "decimal"},
        {"field_type": "money", "field_display": "range"},
        {"field_type": "enum", "field_values": "open", "field_holds": "several"},
        {"field_type": "file", "field_holds": "several"},
        {"field_type": "file", "field_format": "image"},
        {"field_type": "datetime", "field_format": "time_optional"},
        {"field_type": "number", "field_supplied_by": "this_crm"},
    ]
    for design in faithful:
        espo_type = emit_type(design)
        assert espo_type is not None, f"{design} built nothing"
        assert properties_not_carried(design, espo_type) == [], (
            f"{design} was wrongly reported as losing something"
        )


def test_a_property_left_unsaid_is_not_a_loss():
    """Defaults are not requests. A field that says nothing has asked for nothing.

    Holding one value, admitting only the values listed, and being filled in by a
    person are what a field means when it is silent, so their absence on the far
    side is not something to report.
    """
    for design in (
        {"field_type": "text"},
        {"field_type": "enum", "field_holds": "one", "field_values": "fixed"},
        {"field_type": "money", "field_supplied_by": "person"},
    ):
        espo_type = emit_type(design)
        assert properties_not_carried(design, espo_type) == []
