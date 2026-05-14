"""Controlled vocabularies enforced by the access layer.

Both the SQLAlchemy CHECK constraints (database boundary, belt-and-braces)
and the access-layer validators consume the values defined here. New
allowed values are added by editing this module — that deliberate gate is
the point, per DEC-006.
"""

from __future__ import annotations

DECISION_STATUSES: frozenset[str] = frozenset(
    {"Active", "Superseded", "Withdrawn", "Deleted"}
)

SESSION_STATUSES: frozenset[str] = frozenset({"Complete", "In Progress"})

RISK_PROBABILITIES: frozenset[str] = frozenset({"Low", "Medium", "High"})
RISK_IMPACTS: frozenset[str] = frozenset({"Low", "Medium", "High"})
RISK_STATUSES: frozenset[str] = frozenset({"Open", "Mitigated", "Accepted", "Closed"})

PLANNING_ITEM_TYPES: frozenset[str] = frozenset(
    {"planning_dimension", "open_question", "pending_work"}
)
PLANNING_ITEM_STATUSES: frozenset[str] = frozenset({"Open", "Resolved", "Deferred"})

REFERENCE_RELATIONSHIPS: frozenset[str] = frozenset(
    {
        "is_about",
        "supersedes",
        "decided_in",
        "affects",
        "covers",
        "blocks",
        "references",
    }
)

# Entity types that can appear as source_type or target_type in references.
# The set grows as methodology entities are added in Step 0 follow-on.
ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "charter",
        "status",
        "decision",
        "session",
        "risk",
        "planning_item",
        "topic",
    }
)


def _kinds_for_pair(source_type: str, target_type: str) -> frozenset[str]:
    """Return the valid relationship kinds for a (source, target) pair.

    Used to populate :data:`RELATIONSHIP_RULES` and the cascading
    `ReferenceCreateDialog` (v0.3 slice C, DEC-033). The semantic rules:

    * ``is_about`` and ``references`` — generic, valid for any pair.
    * ``decided_in`` — target must be a session.
    * ``supersedes`` — source and target types must match.
    * ``affects`` — source must be a risk.
    * ``covers`` — source must be charter or status.
    * ``blocks`` — source must be a risk or planning_item.

    The ruleset is permissive by design: every pair has at least the
    two generic kinds, so the dialog never produces an empty kind list
    for a valid (source, target) combination. Specific kinds (e.g.
    ``decided_in``) constrain only their target side. Future iterations
    may tighten the rules; the dict-shape lookup pattern is unchanged.
    """
    kinds = {"is_about", "references"}
    if target_type == "session":
        kinds.add("decided_in")
    if source_type == target_type:
        kinds.add("supersedes")
    if source_type == "risk":
        kinds.add("affects")
        kinds.add("blocks")
    if source_type == "planning_item":
        kinds.add("blocks")
    if source_type in ("charter", "status"):
        kinds.add("covers")
    return frozenset(kinds)


# Tuple-keyed dict mapping ``(source_type, target_type)`` to the set of
# relationship kinds valid for that pair. Computed at module load from
# :func:`_kinds_for_pair`. Read by the v0.3 cascading
# `ReferenceCreateDialog` to enforce strict vocab compliance: dropdowns
# show only valid choices for the partially-filled state, so invalid
# combinations are unrepresentable in the dialog (per DEC-033).
RELATIONSHIP_RULES: dict[tuple[str, str], frozenset[str]] = {
    (s, t): _kinds_for_pair(s, t)
    for s in sorted(ENTITY_TYPES)
    for t in sorted(ENTITY_TYPES)
}


def kinds_for_source(source_type: str) -> frozenset[str]:
    """Union of relationship kinds valid for any pair where source_type matches."""
    out: set[str] = set()
    for (s, _t), kinds in RELATIONSHIP_RULES.items():
        if s == source_type:
            out.update(kinds)
    return frozenset(out)


def target_types_for(source_type: str, kind: str) -> frozenset[str]:
    """Return the target types valid for ``(source_type, kind)``.

    Used by the cascading dialog after the user picks source type and
    relationship kind to filter the target type combo.
    """
    out: set[str] = set()
    for (s, t), kinds in RELATIONSHIP_RULES.items():
        if s == source_type and kind in kinds:
            out.add(t)
    return frozenset(out)


def source_types_with_relationships() -> frozenset[str]:
    """Return the set of source types that have at least one valid relationship.

    Used by the cascading dialog to populate the source-type combo.
    Every entity type currently has valid relationships (the two generic
    kinds always apply), so this returns ``ENTITY_TYPES`` today, but the
    helper is exposed so future restrictive rule changes don't require
    UI changes.
    """
    out: set[str] = set()
    for (s, _t), kinds in RELATIONSHIP_RULES.items():
        if kinds:
            out.add(s)
    return frozenset(out)

CHANGE_LOG_OPERATIONS: frozenset[str] = frozenset({"insert", "update", "delete"})

CHANGE_LOG_ACTORS: frozenset[str] = frozenset(
    {"claude_session", "migration", "manual"}
)


# Base entity catalog vocabularies (catalog-ingestion-PRD-v0.1.md section 4).
#
# The seven systems surveyed in the catalog. Catalog rows in
# ``catalog_entity_system``, ``catalog_attribute_presence``, and
# ``catalog_relationship_presence`` carry a ``system`` column constrained
# to this set.

CATALOG_SYSTEMS: frozenset[str] = frozenset(
    {
        "salesforce",
        "hubspot",
        "attio",
        "espocrm",
        "civicrm",
        "salesforce_npsp",
        "bloomerang",
    }
)

CATALOG_ENTRY_KINDS: frozenset[str] = frozenset({"universal", "subclass"})

CATALOG_DATA_MODEL_ROLES: frozenset[str] = frozenset(
    {"anchor", "event", "classifier", "junction", "log", "document"}
)

# Attribute-type vocabulary documented in
# ``research/base-entity-catalog/README.md`` (section "attributes[] schema").
# Wider than what the v0.10 dataset actually uses; admitting the full
# documented set keeps future authored entries unblocked.
CATALOG_ATTRIBUTE_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "text",
        "richtext",
        "integer",
        "decimal",
        "currency",
        "boolean",
        "date",
        "datetime",
        "time",
        "enum",
        "multienum",
        "reference",
        "multireference",
        "email",
        "phone",
        "url",
        "address",
        "attachment",
        "autonumber",
        "formula",
    }
)

# ``is_standard`` on ``catalog_entity_system`` is stored as TEXT (not BOOLEAN)
# because the catalog admits a ``partial`` value for the edge case where an
# entity is partly built-in and partly custom in a system.
CATALOG_IS_STANDARD_VALUES: frozenset[str] = frozenset({"true", "false", "partial"})

# Subclass-realisation mechanisms on ``catalog_entity_system`` (subclasses
# only — universals leave this NULL). Vocabulary per PRD section 4.3.
CATALOG_MECHANISMS: frozenset[str] = frozenset(
    {
        "record_type",
        "contact_subtype",
        "type_discriminator",
        "custom_property",
        "separate_object",
        "entity_inheritance",
    }
)

# Per-system presence on attributes and relationships.
CATALOG_PRESENCE_STATUSES: frozenset[str] = frozenset(
    {"standard", "custom", "absent"}
)

CATALOG_RELATIONSHIP_CARDINALITIES: frozenset[str] = frozenset(
    {"one-to-one", "one-to-many", "many-to-one", "many-to-many"}
)

CATALOG_RELATIONSHIP_ROLES: frozenset[str] = frozenset({"parent", "child", "peer"})


def _check_in(name: str, allowed: frozenset[str]) -> str:
    """Build a SQLite CHECK constraint expression for an enumerated column."""
    quoted = ", ".join(f"'{v}'" for v in sorted(allowed))
    return f"{name} IN ({quoted})"
