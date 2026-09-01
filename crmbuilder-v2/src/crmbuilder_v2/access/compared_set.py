"""The compared set — what conformance compares, declared (PI-409).

REQ-490: the design declares, for each attribute of each construct, whether
conformance compares it and by what rule two values are judged equal; the
evaluation applies those declarations mechanically and exercises no judgement
of its own. This module is the binding form of that declaration (DEC-989): the
document ``PRDs/product/crmbuilder-v2/compared-set-declaration.md`` (approved
as DEC-928) is the human source; conformance reads THIS, and the API serves it
verbatim (``GET /reconcile/compared-set``) so every surface reports against
exactly what the engine enforces.

**Provenance discipline.** Every row below is one of:

* a DEC-928 row, carried verbatim from the approved table; or
* a post-DEC-928 construct — an attribute a later governed planning item put
  into the audited inventory (PI-414's qualifying properties, PI-420 message
  templates, PI-421 field rules, PI-422/PI-424 entity options, PI-425
  built-in fields, PI-406 governed settings). Each cites its source. DEC-928
  anticipated exactly this: "three constructs are not yet in the table and
  join it as their planning items land."

One DEC-928 ruling deliberately changes current behaviour: ``team_description``
was being audited into drift, and the ruling excludes it — a team's definition
is its name; its description is design-record prose.

**Null policy (global, DEC-928):** absent and empty are DIFFERENT. A rule that
needs the opposite says so in its own note.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Dispositions
# ---------------------------------------------------------------------------

#: The attribute is compared; any difference under its rule is drift (REQ-490).
COMPARED = "compared"
#: The attribute is the identity used to match design to instance (join-key).
#: Not a compared value: it can never produce drift, only presence/absence.
IDENTITY = "identity"
#: The attribute is never examined and can never produce drift (REQ-490).
EXCLUDED = "excluded"

# ---------------------------------------------------------------------------
# Equality rules (DEC-928's vocabulary, verbatim)
# ---------------------------------------------------------------------------

EXACT = "exact"          #: Python ``==``, no normalization.
BOOL = "bool"            #: boolean equality.
INT = "int"              #: numeric equality; absent != 0.
STR_EXACT = "str-exact"  #: exact string; whitespace and case significant.
STR_TRIM = "str-trim"    #: trim leading/trailing whitespace, then exact.
SET = "set"              #: order-insensitive collection equality.
SEQ = "seq"              #: order-SENSITIVE sequence equality.
MAP = "map"              #: key-wise comparison; key order irrelevant.
CANONICAL = "canonical"  #: normalize to canonical form, then compare.
MAPPED = "mapped"        #: translate neutral value to engine form, then compare.
JOIN_KEY = "join-key"    #: not a comparison — the identity match key.

EQUALITY_RULES: frozenset[str] = frozenset(
    {EXACT, BOOL, INT, STR_EXACT, STR_TRIM, SET, SEQ, MAP, CANONICAL, MAPPED}
)


@dataclass(frozen=True)
class AttributeDeclaration:
    """One attribute's declared disposition, and its rule when compared."""

    disposition: str
    rule: str | None = None
    note: str | None = None


def _c(rule: str, note: str | None = None) -> AttributeDeclaration:
    return AttributeDeclaration(COMPARED, rule, note)


def _i(note: str | None = None) -> AttributeDeclaration:
    return AttributeDeclaration(IDENTITY, JOIN_KEY, note)


def _x(note: str | None = None) -> AttributeDeclaration:
    return AttributeDeclaration(EXCLUDED, None, note)


# ---------------------------------------------------------------------------
# The declaration (DEC-928 rows verbatim; post-DEC-928 rows cite their source)
# ---------------------------------------------------------------------------

COMPARED_SET: dict[str, dict[str, AttributeDeclaration]] = {
    "entity": {
        "entity_identifier": _x("design's own ID"),
        "entity_name": _i("the match key"),
        "entity_status": _x("design lifecycle"),
        "entity_kind": _x("design classification"),
        "entity_description": _x("design-record prose"),
        "entity_notes": _x("authoring notes"),
        "entity_label": _c(STR_TRIM, "user-visible (DEC-928 ruling)"),
        "entity_label_plural": _c(STR_TRIM, "user-visible (DEC-928 ruling)"),
        "entity_default_sort_field": _c(EXACT),
        "entity_default_sort_direction": _c(EXACT),
        "entity_track_activity": _c(BOOL),
        "entity_tracks_activities": _c(BOOL),
        "entity_text_filter_fields": _c(SET, "order contested; ruled a set"),
        "entity_full_text_search": _c(BOOL),
        "entity_full_text_search_min_length": _c(INT, "absent != 0"),
        # Post-DEC-928: PI-424 / REQ-346 entity options, audited since.
        "entity_base_type": _c(
            EXACT, "PI-424; learned on first audit when undeclared"
        ),
        "entity_icon": _c(EXACT, "PI-424"),
        "entity_color": _c(EXACT, "PI-424"),
        "entity_status_field": _c(EXACT, "PI-424"),
        "entity_kanban_view": _c(BOOL, "PI-424"),
        "entity_count_disabled": _c(BOOL, "PI-424"),
        "entity_optimistic_concurrency": _c(BOOL, "PI-424"),
        "entity_multiple_assigned_users": _c(BOOL, "PI-424"),
        # Post-DEC-928: PI-422 / REQ-122 / DEC-947 — verbatim, capture-only.
        "entity_formula_scripts": _c(MAP, "PI-422; scripts verbatim per stage"),
    },
    "field": {
        "field_identifier": _x("design's own ID"),
        "field_name": _i(),
        "field_type": _c(
            MAPPED,
            "neutral-to-engine mapping first (DEC-928); at the store layer "
            "both sides are already neutral, so mapped compares exact here "
            "and the mapping burden sits on the engine-facing reader",
        ),
        "field_required": _c(BOOL),
        "field_read_only": _c(BOOL),
        "field_unique": _c(BOOL),
        "field_max_length": _c(INT, "absent != 0"),
        "field_min": _c(EXACT, "stored as string; absent != '0'"),
        "field_max": _c(EXACT),
        "field_numeric_scale": _c(EXACT),
        "field_default_value": _c(EXACT, "absent != ''"),
        "field_format": _c(EXACT),
        "field_formula": _c(CANONICAL, "semantic, not textual (DEC-928 ruling)"),
        "field_foreign_link": _c(EXACT, "structural"),
        "field_foreign_target": _c(EXACT, "structural"),
        "field_label": _c(STR_TRIM, "user-visible (DEC-928 ruling)"),
        "field_tooltip": _x("DEC-928 ruling: noise, no behaviour"),
        "field_description": _x("design-record prose"),
        "field_notes": _x("authoring notes"),
        "field_status": _x("design lifecycle"),
        "field_usage_summary": _x("design-record prose"),
        # DEC-928 excluded ``field_externally_populated`` pending verification;
        # the column was since retired outright (PI-414 subtractive, 0130) —
        # ``field_supplied_by`` below is its successor.
        "field_derived_result_type": _x("design-side derivation metadata"),
        "field_previous_parent_entity_identifier": _x("design bookkeeping"),
        # DEC-928's child-collection note: enum options compare as a set over
        # (value, effective label) — REQ-442's order-insensitive rule.
        "field_options": _c(SET, "over (value, effective-label) per REQ-442"),
        # Post-DEC-928: the PI-414 qualifying properties (REQ-508/510/512/514),
        # audited as qualifiers since — deployed function, like field_format.
        "field_display": _c(EXACT, "PI-414"),
        "field_values": _c(EXACT, "PI-414"),
        "field_holds": _c(EXACT, "PI-414"),
        "field_supplied_by": _c(EXACT, "PI-414"),
        # Post-DEC-928: PI-425 / REQ-523 — platform-shipped field flag.
        "field_built_in": _c(BOOL, "PI-425"),
    },
    "association": {
        "association_identifier": _x(),
        "association_name": _i(),
        "association_source_entity": _c(EXACT, "structural"),
        "association_target_entity": _c(EXACT, "structural"),
        "association_cardinality": _c(EXACT, "structural"),
        "association_source_role": _c(EXACT, "link name on the instance"),
        "association_target_role": _c(EXACT),
        "association_description": _x("design-record prose"),
        "association_notes": _x(),
        "association_status": _x("design lifecycle"),
    },
    "layout": {
        "layout_identifier": _x(),
        "layout_entity_identifier": _i("with layout_type"),
        "layout_type": _i(),
        "layout_content": _c(
            SEQ, "order IS the visible arrangement (DEC-928 ruling)"
        ),
        "layout_status": _x("design lifecycle"),
        "layout_notes": _x(),
    },
    "role": {
        "role_identifier": _x(),
        "role_name": _i(),
        "role_scope_access": _c(MAP, "the security boundary"),
        "role_system_permissions": _c(MAP),
        "role_description": _x("design-record prose"),
        "role_status": _x("design lifecycle"),
        "role_notes": _x(),
    },
    "team": {
        "team_identifier": _x(),
        "team_name": _i(),
        "team_description": _x(
            "DEC-928: definitions compared, prose not — this row deliberately "
            "retires the drift the audit had been recording"
        ),
        "team_status": _x("design lifecycle"),
        "team_notes": _x(),
    },
    "filtered_tab": {
        "filtered_tab_identifier": _x(),
        "filtered_tab_entity_identifier": _i(),
        "filtered_tab_label": _c(STR_TRIM, "user-visible (DEC-928 ruling)"),
        "filtered_tab_filter": _c(
            CANONICAL, "condition AST — semantic, not textual"
        ),
        "filtered_tab_status": _x("design lifecycle"),
        "filtered_tab_notes": _x(),
    },
    # Post-DEC-928 constructs, joining as their planning items landed
    # (anticipated by DEC-928's consequences).
    "message_template": {
        "message_template_identifier": _x("PI-420"),
        "message_template_name": _i("PI-420"),
        "message_template_subject": _c(STR_EXACT, "PI-420 / REQ-124"),
        "message_template_body": _c(STR_EXACT, "PI-420 / REQ-124"),
        "message_template_merge_fields": _c(SET, "PI-420 / REQ-124"),
        "message_template_channel": _x("PI-420; capture bookkeeping"),
        "message_template_description": _x("design-record prose"),
        "message_template_status": _x("design lifecycle"),
        "message_template_notes": _x(),
    },
    "rule": {
        "rule_identifier": _x("PI-421"),
        "rule_name": _i("PI-421"),
        "rule_condition": _c(CANONICAL, "PI-421 / REQ-123; condition AST"),
        "rule_effect": _c(EXACT, "PI-421"),
        "rule_subject_type": _x("identity context"),
        "rule_subject_identifier": _x("identity context"),
        "rule_message": _x("authoring prose"),
        "rule_status": _x("design lifecycle"),
    },
    # PI-406 / REQ-485: a governed setting's canonical value is per instance;
    # each side compares against ITS OWN declared value, and a setting with no
    # declared value for an instance is not captured — never conformant.
    "system_setting": {
        "system_setting_identifier": _x(),
        "system_setting_key": _i("the name the CRM itself uses"),
        "system_setting_name": _x("design-record prose"),
        "system_setting_value_type": _x("declaration shape, not instance state"),
        "system_setting_description": _x("design-record prose"),
        "system_setting_notes": _x(),
        "system_setting_status": _x("design lifecycle"),
        "value": _c(EXACT, "per-instance: against the instance's own declaration"),
    },
}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def declaration_for(member_type: str, attribute: str) -> AttributeDeclaration | None:
    """The declared disposition of one attribute, or ``None`` if undeclared.

    An undeclared attribute is not silently excluded: the caller decides what
    an undeclared attribute means in its context (the comparison reports it
    as unknown naming the design — DEC-938 — rather than examining it).
    """
    return COMPARED_SET.get(member_type, {}).get(attribute)


def compared_attributes(member_type: str) -> tuple[str, ...]:
    """The attributes conformance compares for one member type, in order."""
    return tuple(
        attribute
        for attribute, declaration in COMPARED_SET.get(member_type, {}).items()
        if declaration.disposition == COMPARED
    )


def is_compared(member_type: str, attribute: str) -> bool:
    declaration = declaration_for(member_type, attribute)
    return declaration is not None and declaration.disposition == COMPARED


def serialized() -> dict[str, list[dict[str, Any]]]:
    """The declaration exactly as the engine sees it (DEC-989's API form)."""
    return {
        member_type: [
            {
                "attribute": attribute,
                "disposition": declaration.disposition,
                "rule": declaration.rule,
                "note": declaration.note,
            }
            for attribute, declaration in attributes.items()
        ]
        for member_type, attributes in COMPARED_SET.items()
    }


# ---------------------------------------------------------------------------
# The rule engine (REQ-490: applied mechanically, no judgement)
# ---------------------------------------------------------------------------


def _canonical_form(value: Any) -> str | None:
    """Canonical rendering of a structured value (formulas, condition ASTs).

    Key order and whitespace never matter; a changed calculation always does.
    ``None`` stays ``None`` (absent is not an empty structure).
    """
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _set_form(value: Any) -> frozenset | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, set, frozenset)):
        return None
    return frozenset(_canonical_form(v) if isinstance(v, (dict, list)) else v
                     for v in value)


def values_equal(rule: str, a: Any, b: Any) -> bool:
    """Whether two values are equal under one declared rule.

    The global null policy applies first: two absents are equal; an absent
    never equals a present value (DEC-928) — a rule needing the opposite
    encodes it here, none currently does.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if rule == BOOL:
        return bool(a) == bool(b)
    if rule == INT:
        try:
            return int(a) == int(b)
        except (TypeError, ValueError):
            return a == b
    if rule == STR_TRIM:
        return str(a).strip() == str(b).strip()
    if rule == STR_EXACT:
        return str(a) == str(b)
    if rule == SET:
        sa, sb = _set_form(a), _set_form(b)
        if sa is None or sb is None:
            return a == b
        return sa == sb
    if rule == SEQ:
        return list(a) == list(b) if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) else a == b
    if rule == MAP:
        return a == b  # dict equality is key-wise; key order never matters
    if rule == CANONICAL:
        return _canonical_form(a) == _canonical_form(b)
    # EXACT and MAPPED (both sides neutral at this layer) fall through.
    return a == b


def attr_equal(member_type: str, attribute: str, a: Any, b: Any) -> bool:
    """Whether two values of one declared-compared attribute are equal.

    Applies the attribute's declared rule mechanically. For an attribute with
    no declaration the conservative ``exact`` comparison applies — the caller
    is expected to have routed undeclared attributes to the unknown outcome
    already (DEC-938), so this is a backstop, not a policy.
    """
    declaration = declaration_for(member_type, attribute)
    rule = declaration.rule if declaration and declaration.rule else EXACT
    if rule == JOIN_KEY:
        return a == b
    return values_equal(rule, a, b)
