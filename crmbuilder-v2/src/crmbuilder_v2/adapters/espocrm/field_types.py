"""What each EspoCRM field type means in engine-neutral terms — PI-414 (REQ-501).

One table, owned by the engine adapter and used in both directions: the audit
reads an instance through it, and the emitter is its inverse. It lives here
rather than with the audit because it is EspoCRM knowledge — a second engine
brings its own table, not an edit to this one.

Keeping a single table is the point. Two independently-maintained maps are what
let the design describe a field more coarsely than the CRM it describes, so that
9 of EspoCRM's 46 field types could survive a round trip out and back.
"""

from __future__ import annotations

# EspoCRM concrete field type -> the full engine-neutral shape of the field
# (PI-414 / REQ-501; supersedes the kind-only table this replaces). A kind alone
# cannot describe a field: ``varchar`` and ``email`` are both neutral ``text``
# and are told apart only by the format, ``multiEnum`` and ``checklist`` are both
# a choice holding several and are told apart by the display, and ``int`` and
# ``float`` are both a number told apart by the scale. Reading only the kind is
# what made 33 of EspoCRM's 46 types unable to survive a round trip.
#
# Each value is the neutral field this engine type reads as. Omitted properties
# are None — a field that carries no format reads as carrying none, not as
# unread. The emitter in ``adapters/espocrm/model.py`` is the inverse and the
# round-trip check in ``tests/crmbuilder_v2/test_field_vocabulary_round_trip.py``
# holds the two honest.
#
# Deliberately absent: ``link``, ``linkOne``, ``linkParent`` and ``linkMultiple``.
# A link between records is described once, as a relationship, never as a field
# (DEC-932 / REQ-505), so they are not field-vocabulary concerns at all. ``base``
# is the shared definition the other types extend, not a type an administrator
# picks.
ESPO_FIELD_SHAPE: dict[str, dict[str, str]] = {
    # Text-shaped. The format says what sort of value beyond the kind; the
    # display says how it is shown (DEC-933).
    "varchar": {"field_type": "text"},
    "email": {"field_type": "text", "field_format": "email"},
    "phone": {"field_type": "text", "field_format": "phone"},
    "url": {"field_type": "text", "field_format": "url"},
    "urlMultiple": {
        "field_type": "text", "field_format": "url", "field_holds": "several",
    },
    "password": {"field_type": "text", "field_format": "secret"},
    "colorpicker": {"field_type": "text", "field_format": "colour"},
    "barcode": {"field_type": "text", "field_display": "barcode"},
    "text": {"field_type": "long_text"},
    "wysiwyg": {"field_type": "long_text", "field_display": "rich_text"},
    # Number-shaped. Scale separates whole from decimal; a range is the same
    # kind shown as a range (DEC-934); a duration is a number in that format.
    "int": {"field_type": "number", "field_numeric_scale": "integer"},
    "float": {"field_type": "number", "field_numeric_scale": "decimal"},
    "decimal": {"field_type": "number", "field_numeric_scale": "decimal"},
    "duration": {"field_type": "number", "field_format": "duration"},
    "rangeInt": {
        "field_type": "number", "field_numeric_scale": "integer",
        "field_display": "range",
    },
    "rangeFloat": {
        "field_type": "number", "field_numeric_scale": "decimal",
        "field_display": "range",
    },
    "rangeCurrency": {"field_type": "money", "field_display": "range"},
    "currency": {"field_type": "money"},
    # The CRM computes the converted amount; nobody types it (DEC-939).
    "currencyConverted": {"field_type": "money", "field_supplied_by": "this_crm"},
    # A number the CRM assigns rather than a person entering it.
    "autoincrement": {"field_type": "number", "field_supplied_by": "this_crm"},
    "number": {"field_type": "number", "field_supplied_by": "this_crm"},
    # Dates. ``datetimeOptional`` is a datetime whose time part may be absent.
    "date": {"field_type": "date"},
    "datetime": {"field_type": "datetime"},
    "datetimeOptional": {"field_type": "datetime", "field_format": "time_optional"},
    # Choices. How many are held and how they are shown are separate from the
    # kind (DEC-935, DEC-937); an open list carries no option set at all.
    "enum": {"field_type": "enum", "field_values": "fixed", "field_holds": "one"},
    "multiEnum": {
        "field_type": "enum", "field_values": "fixed", "field_holds": "several",
    },
    "checklist": {
        "field_type": "enum", "field_values": "fixed", "field_holds": "several",
        "field_display": "tick_list",
    },
    "array": {"field_type": "enum", "field_values": "open", "field_holds": "several"},
    # A choice whose stored values are numbers is the number kind with fixed
    # values — no kind of its own (DEC-935).
    "enumInt": {
        "field_type": "number", "field_numeric_scale": "integer",
        "field_values": "fixed", "field_holds": "one",
    },
    "enumFloat": {
        "field_type": "number", "field_numeric_scale": "decimal",
        "field_values": "fixed", "field_holds": "one",
    },
    "arrayInt": {
        "field_type": "number", "field_numeric_scale": "integer",
        "field_values": "open", "field_holds": "several",
    },
    "bool": {"field_type": "boolean"},
    # Files. An image is a file in that format; several attachments is a file
    # that holds several (DEC-936, DEC-937).
    "file": {"field_type": "file"},
    "image": {"field_type": "file", "field_format": "image"},
    "attachmentMultiple": {"field_type": "file", "field_holds": "several"},
    # Values made of several fixed parts, described as one field (DEC-934).
    "address": {"field_type": "postal_address"},
    "personName": {"field_type": "person_name"},
    "map": {"field_type": "place"},
    # Structured data; an array of them holds several.
    "jsonObject": {"field_type": "structured_data"},
    "jsonArray": {"field_type": "structured_data", "field_holds": "several"},
    # A field mirroring a scalar from a linked record, and a computed value.
    "foreign": {"field_type": "foreign"},
    "formula": {"field_type": "derived"},
}



#: Property values that need no engine representation because they are what a
#: field means when it says nothing. A design declaring one of these has not
#: asked the engine for anything, so its absence on the far side is not a loss.
DEFAULT_PROPERTY_VALUES: dict[str, str] = {
    "field_holds": "one",
    "field_values": "fixed",
    "field_supplied_by": "person",
}

#: The qualifying properties that can be lost in translation.
QUALIFYING_PROPERTIES: tuple[str, ...] = (
    "field_format",
    "field_numeric_scale",
    "field_display",
    "field_values",
    "field_holds",
    "field_supplied_by",
)


def properties_not_carried(field_row: dict, espo_type: str) -> list[tuple[str, str]]:
    """Which declared properties the chosen EspoCRM type cannot carry.

    Returns ``[(property, requested_value)]``. The check is the round trip
    applied at publish time: read back what the emitted type means, and report
    anything the design asked for that did not survive. REQ-502 requires the
    translation to say what a target CRM cannot hold rather than substitute a
    near equivalent silently — this is how it knows.

    Deriving it from the table rather than listing known losses means a property
    added later is covered without anyone remembering to update a list. It is
    also why a percentage stopped vanishing: EspoCRM has no percentage field of
    any kind, so a number carrying that format emits as a plain number, and this
    is what notices.
    """
    carried = ESPO_FIELD_SHAPE.get(espo_type, {})
    lost: list[tuple[str, str]] = []
    for prop in QUALIFYING_PROPERTIES:
        requested = field_row.get(prop)
        if requested is None or requested == DEFAULT_PROPERTY_VALUES.get(prop):
            continue
        if carried.get(prop) != requested:
            lost.append((prop, str(requested)))
    return lost
