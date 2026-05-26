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

# Methodology entity `domain` lifecycle (UI v0.4 slice B, DEC-047).
# Three-status propose-verify lifecycle per ``domain.md`` section 3.4.
DOMAIN_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

# Valid status successors per ``domain.md`` section 3.4.1. A transition
# is valid when the target equals the current value (a no-op) or appears
# in the current value's successor set. The one-way propose-verify gate
# means no value lists ``candidate`` as a successor.
DOMAIN_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# Methodology entity `entity` lifecycle (UI v0.4 slice C, DEC-052).
# Mirrors ``domain``'s three-status propose-verify lifecycle exactly
# per ``entity.md`` section 3.4 — entities, like domains, are surfaced
# by the consultant and verified by the client.
ENTITY_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

# Valid status successors per ``entity.md`` section 3.4.1. Same one-way
# propose-verify gate as ``domain``: once out of ``candidate`` a record
# never regresses to it; ``confirmed`` and ``deferred`` move freely
# between each other.
ENTITY_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# Methodology entity `persona` lifecycle (v0.5+, persona.md §3.4).
# Mirrors `domain` / `entity` exactly — three-status propose-verify
# lifecycle with one-way gate out of `candidate`.
PERSONA_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

PERSONA_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# Methodology entity `crm_candidate` lifecycle (UI v0.4 slice E, DEC-062).
# Four-status lifecycle per ``crm_candidate.md`` section 3.4. ``active``
# is the starter status; ``selected``, ``declined``, ``removed`` are
# terminal — no successors permitted from any of them. The singleton-
# ``selected`` constraint (at most one live record may hold ``selected``
# per spec 3.4.3) is enforced separately at the access layer on POST,
# PATCH/PUT, and POST ``/restore``.
CRM_CANDIDATE_STATUSES: frozenset[str] = frozenset(
    {"active", "selected", "declined", "removed"}
)

# Valid status successors per ``crm_candidate.md`` section 3.4.1. The
# three terminal states (``selected``, ``declined``, ``removed``) list
# the empty set — no transitions out of a terminal state are permitted.
CRM_CANDIDATE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"selected", "declined", "removed"}),
    "selected": frozenset(),
    "declined": frozenset(),
    "removed": frozenset(),
}

# Methodology entity `process` classification (UI v0.4 slice D, DEC-057).
# Per ``process.md`` section 3.4, `process` has no `status` field — the
# four-value `process_classification` enum carries the Principle 3
# priority taxonomy in its place.
PROCESS_CLASSIFICATIONS: frozenset[str] = frozenset(
    {"unclassified", "mission_critical", "supporting", "deferred"}
)

# Valid classification successors per ``process.md`` section 3.4.2. A
# transition is valid when the target equals the current value (a
# no-op) or appears in the current value's successor set. The one-way
# ``unclassified`` gate means no value lists ``unclassified`` as a
# successor; the three classified values move freely among themselves.
PROCESS_CLASSIFICATION_TRANSITIONS: dict[str, frozenset[str]] = {
    "unclassified": frozenset(
        {"mission_critical", "supporting", "deferred"}
    ),
    "mission_critical": frozenset({"supporting", "deferred"}),
    "supporting": frozenset({"mission_critical", "deferred"}),
    "deferred": frozenset({"mission_critical", "supporting"}),
}

# ---------------------------------------------------------------------------
# Governance entity lifecycles (UI v0.7). Five workflow-shaped entities carry
# truly-terminal status machines (no transitions out of a terminal state, no
# transitions between terminals); reference_book is documentary-shaped; the
# deposit_event entity is born-terminal append-only and carries an _outcome
# enum rather than a transitioning _status. See the per-entity schema specs.
# ---------------------------------------------------------------------------

# `workstream` lifecycle (DEC-125). Five statuses; three truly terminal.
WORKSTREAM_STATUSES: frozenset[str] = frozenset(
    {"planned", "in_flight", "complete", "cancelled", "superseded"}
)
WORKSTREAM_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"in_flight", "cancelled", "superseded"}),
    "in_flight": frozenset({"complete", "cancelled", "superseded"}),
    "complete": frozenset(),
    "cancelled": frozenset(),
    "superseded": frozenset(),
}

# `conversation` lifecycle (DEC-131). Seven statuses; forward-only planning
# line (planned → kickoff_drafted → ready → in_flight) with three terminals.
CONVERSATION_STATUSES: frozenset[str] = frozenset(
    {
        "planned",
        "kickoff_drafted",
        "ready",
        "in_flight",
        "complete",
        "cancelled",
        "superseded",
    }
)
CONVERSATION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"kickoff_drafted", "cancelled", "superseded"}),
    "kickoff_drafted": frozenset({"ready", "cancelled", "superseded"}),
    "ready": frozenset({"in_flight", "cancelled", "superseded"}),
    "in_flight": frozenset({"complete", "cancelled", "superseded"}),
    "complete": frozenset(),
    "cancelled": frozenset(),
    "superseded": frozenset(),
}

# `reference_book` lifecycle (DEC-137). Documentary-shaped; three statuses,
# two truly terminal. Base timestamps only (no per-status timestamps).
REFERENCE_BOOK_STATUSES: frozenset[str] = frozenset(
    {"active", "archived", "superseded"}
)
REFERENCE_BOOK_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"archived", "superseded"}),
    "archived": frozenset(),
    "superseded": frozenset(),
}

# `reference_book_kind` closed enum (DEC-138). Eleven values: DEC-117's seven
# artifacts plus three observed types plus the `other` sentinel.
REFERENCE_BOOK_KINDS: frozenset[str] = frozenset(
    {
        "product_requirements_document",
        "implementation_plan",
        "workstream_master_plan",
        "methodology_guide",
        "architecture_document",
        "schema_specification",
        "conduct_framework",
        "investigation_report",
        "apply_script",
        "session_startup_document",
        "other",
    }
)

# `work_ticket` lifecycle (DEC-145). Five statuses; forward-only drafting line
# (drafted → ready → consumed) with three terminals.
WORK_TICKET_STATUSES: frozenset[str] = frozenset(
    {"drafted", "ready", "consumed", "cancelled", "superseded"}
)
WORK_TICKET_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "drafted": frozenset({"ready", "cancelled", "superseded"}),
    "ready": frozenset({"consumed", "cancelled", "superseded"}),
    "consumed": frozenset(),
    "cancelled": frozenset(),
    "superseded": frozenset(),
}

# `work_ticket_kind` closed enum (DEC-145).
WORK_TICKET_KINDS: frozenset[str] = frozenset(
    {"kickoff_prompt", "claude_code_prompt", "ad_hoc_prompt", "other"}
)

# `close_out_payload` lifecycle (DEC-149). Five statuses; forward-only
# (drafted → ready → applied) with three terminals.
CLOSE_OUT_PAYLOAD_STATUSES: frozenset[str] = frozenset(
    {"drafted", "ready", "applied", "cancelled", "superseded"}
)
CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "drafted": frozenset({"ready", "cancelled", "superseded"}),
    "ready": frozenset({"applied", "cancelled", "superseded"}),
    "applied": frozenset(),
    "cancelled": frozenset(),
    "superseded": frozenset(),
}

# `deposit_event_outcome` enum (DEC-156). Born-terminal append-only; both
# values are permanent facts, not transitioning workflow states.
DEPOSIT_EVENT_OUTCOMES: frozenset[str] = frozenset({"success", "failure"})


REFERENCE_RELATIONSHIPS: frozenset[str] = frozenset(
    {
        "is_about",
        "supersedes",
        "decided_in",
        "affects",
        "covers",
        "references",
        # v0.4 additions (methodology entities, UI v0.4 slice A).
        "entity_scopes_to_domain",
        "process_hands_off_to_process",
        # v0.7 additions (governance entities). Eight new kinds aggregated
        # across the six governance schema specs (workstream, conversation,
        # reference_book, work_ticket, close_out_payload, deposit_event).
        # See governance-entity-PRD-v0.1.md section 4.3.
        "conversation_belongs_to_workstream",
        "workstream_planned_in_reference_book",
        "conversation_records_session",
        "conversation_opens_against_work_ticket",
        "conversation_succeeds_conversation",
        "close_out_payload_produced_by_conversation",
        "deposit_event_applies_close_out_payload",
        "deposit_event_wrote_record",
        # v0.8 additions (Code Change Lifecycle methodology, PI-029).
        # Three new kinds plus the rename of `blocks` → `blocked_by`:
        #   - `resolves` (conversation → planning_item; methodology §3.2).
        #   - `addresses` (conversation → planning_item, work_ticket →
        #     planning_item; methodology §3.3).
        #   - `blocked_by` (planning_item → planning_item; methodology
        #     §3.4 — directional rename of the prior `blocks` kind,
        #     which is dropped from the vocabulary).
        "resolves",
        "addresses",
        "blocked_by",
        # v0.5+ persona additions (PI-003, persona.md §3.3.1):
        #   - `persona_scopes_to_domain` (persona → domain; many-to-many).
        #   - `persona_realized_as_entity` (persona → entity; conceptually
        #     optional and most often single-target, but the references
        #     mechanism permits multi-target).
        "persona_scopes_to_domain",
        "persona_realized_as_entity",
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
        # Catalog ingestion v0.1 (DEC: catalog rows as universal-reference
        # targets). Catalog rows do not naturally source references — the
        # catalog's own inter-entity relationships live in catalog_relationship
        # — but the CHECK constraint is symmetric; downstream methodology
        # workstreams will source references at ``catalog_entity`` /
        # ``catalog_attribute`` targets.
        "catalog_entity",
        "catalog_attribute",
        # Methodology entities (UI v0.4 slice A). The four new entity
        # types under the Methodology sidebar group: domain, entity,
        # process, crm_candidate.
        "domain",
        "entity",
        "process",
        "crm_candidate",
        # Governance entities (UI v0.7). The six new entity types under
        # the Governance sidebar group, in workstream order. See
        # governance-entity-PRD-v0.1.md section 4.3.
        "workstream",
        "conversation",
        "reference_book",
        "work_ticket",
        "close_out_payload",
        "deposit_event",
        # v0.8 governance entity (Code Change Lifecycle methodology,
        # PI-029). Seventh governance entity type; first under the
        # Code Change Lifecycle workstream. See
        # governance-schema-specs/commit.md v1.0.
        "commit",
        # v0.5+ methodology entity (PI-003). See persona.md.
        "persona",
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
    * ``entity_scopes_to_domain`` — source must be an entity, target must
      be a domain (v0.4, DEC-053).
    * ``process_hands_off_to_process`` — source and target must both be
      processes (v0.4, DEC-058; directional, source=producer,
      target=consumer).
    * ``resolves`` — source must be a conversation, target must be a
      planning_item (v0.8, methodology §3.2).
    * ``addresses`` — source must be a conversation or work_ticket,
      target must be a planning_item (v0.8, methodology §3.3).
    * ``blocked_by`` — source and target must both be planning_item;
      replaces the prior ``blocks`` kind (v0.8, methodology §3.4).
    * ``persona_scopes_to_domain`` — source must be a persona, target
      must be a domain (v0.5+, persona.md §3.3.1; many-to-many).
    * ``persona_realized_as_entity`` — source must be a persona, target
      must be an entity (v0.5+, persona.md §3.3.1; optional and most
      often single-target but mechanism permits multi-target).

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
    if source_type in ("charter", "status"):
        kinds.add("covers")
    # v0.4 additions per DEC-053 and DEC-058:
    if source_type == "entity" and target_type == "domain":
        kinds.add("entity_scopes_to_domain")
    if source_type == "process" and target_type == "process":
        kinds.add("process_hands_off_to_process")
    # v0.7 governance additions, grouped by source type for readability.
    # The same-type `supersedes` clause above already admits supersession
    # for every governance same-type pair (workstream/workstream, etc.);
    # the same-type `conversation_succeeds_conversation` is added alongside.
    if source_type == "conversation" and target_type == "workstream":
        kinds.add("conversation_belongs_to_workstream")
    if source_type == "conversation" and target_type == "session":
        kinds.add("conversation_records_session")
    if source_type == "conversation" and target_type == "work_ticket":
        kinds.add("conversation_opens_against_work_ticket")
    if source_type == "conversation" and target_type == "conversation":
        kinds.add("conversation_succeeds_conversation")
    if source_type == "workstream" and target_type == "reference_book":
        kinds.add("workstream_planned_in_reference_book")
    if source_type == "close_out_payload" and target_type == "conversation":
        kinds.add("close_out_payload_produced_by_conversation")
    if source_type == "deposit_event" and target_type == "close_out_payload":
        kinds.add("deposit_event_applies_close_out_payload")
    if source_type == "deposit_event" and target_type in (
        "session",
        "decision",
        "planning_item",
        "reference",
        # v0.8 additions (PI-030 slice B). The new entity types that the
        # extended close-out payload format can write. Audit chain stays
        # intact: every record the apply POSTs gets a wrote_record
        # back-edge, regardless of which entity type the record is.
        "conversation",
        "work_ticket",
        "commit",
    ):
        kinds.add("deposit_event_wrote_record")
    # v0.8 Code Change Lifecycle additions (PI-029, methodology §3.2–§3.4):
    if source_type == "conversation" and target_type == "planning_item":
        kinds.add("resolves")
        kinds.add("addresses")
    if source_type == "work_ticket" and target_type == "planning_item":
        kinds.add("addresses")
    if source_type == "planning_item" and target_type == "planning_item":
        kinds.add("blocked_by")
    # v0.5+ persona additions (PI-003, persona.md §3.3.1):
    if source_type == "persona" and target_type == "domain":
        kinds.add("persona_scopes_to_domain")
    if source_type == "persona" and target_type == "entity":
        kinds.add("persona_realized_as_entity")
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
