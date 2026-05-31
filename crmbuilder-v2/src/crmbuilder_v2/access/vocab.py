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

# `session` lifecycle (DEC-314, PI-073 redesign). Six statuses; forward-only
# (planned → in_flight) with four terminals (complete, cancelled,
# not_started, superseded). Sessions are now schedulable and stateful per
# the DEC-013 supersession.
SESSION_STATUSES: frozenset[str] = frozenset(
    {
        "planned",
        "in_flight",
        "complete",
        "cancelled",
        "not_started",
        "superseded",
    }
)
SESSION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"in_flight", "cancelled", "not_started", "superseded"}),
    "in_flight": frozenset({"complete", "cancelled", "superseded"}),
    "complete": frozenset(),
    "cancelled": frozenset(),
    "not_started": frozenset(),
    "superseded": frozenset(),
}

# `session_medium` enum (DEC-314, PI-073). Seven mediums plus 'other' for
# extensibility — chat, email, phone, zoom, in_person, slack, other.
SESSION_MEDIUMS: frozenset[str] = frozenset(
    {"chat", "email", "phone", "zoom", "in_person", "slack", "other"}
)

RISK_PROBABILITIES: frozenset[str] = frozenset({"Low", "Medium", "High"})
RISK_IMPACTS: frozenset[str] = frozenset({"Low", "Medium", "High"})
RISK_STATUSES: frozenset[str] = frozenset({"Open", "Mitigated", "Accepted", "Closed"})

PLANNING_ITEM_TYPES: frozenset[str] = frozenset(
    {"planning_dimension", "open_question", "pending_work"}
)
PLANNING_ITEM_STATUSES: frozenset[str] = frozenset({"Open", "Resolved", "Deferred"})

# `area` vocabulary (PI-076, DEC-246/DEC-247). The set of work areas a
# planning_item may declare so the parallel-agent orchestrator (WS-012)
# can partition the open backlog into file-disjoint clusters. An item's
# ``area`` field is a *set* (JSON array) — a cross-cutting item declares
# every area it touches, and two items conflict iff their area sets
# intersect (DEC-247). Each label maps to a region of filesystem
# topology. New areas are added by editing this frozenset — the
# deliberate gate per DEC-006, mirroring every other vocabulary here.
#
# Source of truth: orchestrator-planning.md §2.1. (That section and the
# PI-076 prose both say "seventeen" but enumerate eighteen names; the
# enumerated names are authoritative — all eighteen are registered.)
AREAS: frozenset[str] = frozenset(
    {
        "v2-storage",
        "v2-access",
        "v2-api",
        "v2-mcp",
        "v2-ui",
        "cbm-mn",
        "cbm-mr",
        "cbm-cr",
        "cbm-fu",
        "cbm-services",
        "methodology-interviews",
        "methodology-process",
        "methodology-templates",
        "methodology-product",
        "infrastructure",
        "v1-automation",
        "v1-espo",
        "v1-programs",
    }
)

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

# `entity_kind` base-type classification enum (v0.5+, PI-010 / DEC-292).
# Five-value vocabulary per ``entity.md`` v1.1 §3.2.3 informing Phase 3
# field-shape defaults and Phase 5 CRM-engine evaluation scoring.
# Nullable on the column — operators may defer classification when
# Phase 1 surfaces an entity before its kind is settled.
ENTITY_KINDS: frozenset[str] = frozenset(
    {"person", "organization", "event", "transaction", "other"}
)

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

# Methodology entity `field` lifecycle (v0.5+, PI-004 first slice).
# Mirrors `domain` / `entity` exactly — three-status propose-verify
# lifecycle with one-way gate out of `candidate` per ``field.md`` §3.4.
FIELD_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

FIELD_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# `field_type` enum (v0.5+, PI-004 first slice). 11-value vocabulary
# per ``field.md`` §3.2.3. Richer types (`formula`, `link`, `address`,
# `phone`, `url`) deferred to v0.6+ per PI-054.
FIELD_TYPES: frozenset[str] = frozenset(
    {
        "text",
        "long_text",
        "enum",
        "multi_enum",
        "date",
        "datetime",
        "money",
        "boolean",
        "number",
        "reference",
        "derived",
    }
)

# Methodology entity `requirement` lifecycle (PI-004 cohort, v0.5+).
# Three-status propose-verify mirroring ``domain`` / ``entity`` per
# ``requirement.md`` section 3.4.
REQUIREMENT_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

# Same one-way propose-verify gate as ``domain`` / ``entity``: once out
# of ``candidate``, never regress; ``confirmed`` / ``deferred`` move
# freely between each other.
REQUIREMENT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# MoSCoW priority enum per ``requirement.md`` section 3.2.3. Default
# starter value is ``should`` — consultants must affirmatively escalate
# to ``must``. ``wont`` (priority) is distinct from ``deferred``
# (status): see spec §3.2.3 and §3.4.3 for the distinction. Priority
# transitions are unconstrained — any-to-any movement permitted.
REQUIREMENT_PRIORITIES: frozenset[str] = frozenset(
    {"must", "should", "could", "wont"}
)

# Methodology entity `manual_config` lifecycle (PI-004 cohort, v0.5+).
# **Four-status lifecycle** per ``manual_config.md`` §3.4 — explicit
# deviation from the cross-spec three-status default. Adds a terminal
# ``completed`` reachable only from ``confirmed``; once completed,
# soft-delete-and-restore-and-redo is the only path back. The
# additional cross-field invariant (both ``manual_config_completed_at``
# and ``manual_config_completed_by`` populated on transition into
# ``completed``) is enforced at the repository layer per §3.5.3, not by
# this map.
MANUAL_CONFIG_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred", "completed"}
)

MANUAL_CONFIG_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred", "completed"}),
    "deferred": frozenset({"confirmed"}),
    "completed": frozenset(),
}

# Seven-value ``manual_config_category`` enum per ``manual_config.md``
# §3.2.3. Aligned with the historical deploy-pipeline NOT_SUPPORTED
# categories and the v1.1 YAML schema's ``optionsDeferred`` flag.
# ``other`` is a generic bucket — free-text sub-classification is
# deferred to a v0.6+ planning item per §3.8.3.
MANUAL_CONFIG_CATEGORIES: frozenset[str] = frozenset(
    {
        "saved_view",
        "duplicate_check",
        "workflow",
        "deferred_options_enum",
        "role_permission",
        "dynamic_logic",
        "other",
    }
)

# Methodology entity `test_spec` lifecycle (PI-004 cohort closer, v0.5+).
# Three-status methodology lifecycle mirroring ``domain`` / ``entity``
# exactly per ``test_spec.md`` §3.4.1 — propose-verify one-way gate out
# of ``candidate``. The execution-outcome axis (TEST_SPEC_RUN_OUTCOMES
# below) is a SEPARATE field with unrestricted transitions per
# §3.4.2-3.4.3 — see the dual-axis rationale in the spec.
TEST_SPEC_STATUSES: frozenset[str] = frozenset(
    {"candidate", "confirmed", "deferred"}
)

TEST_SPEC_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "deferred"}),
    "confirmed": frozenset({"deferred"}),
    "deferred": frozenset({"confirmed"}),
}

# Execution-outcome enum for ``test_spec`` — the snapshot of the most
# recent verification run's result per ``test_spec.md`` §3.4.2.
# **Intentionally NO ``TEST_SPEC_RUN_OUTCOME_TRANSITIONS`` map.**
# Outcomes are observational (records what happened on the last run),
# not decisional, so any value may move to any other value freely. This
# is the principal asymmetry that justifies the dual-axis state pattern
# per §3.4.3: methodology lifecycle benefits from a propose-verify gate;
# execution outcome benefits from frictionless update. The §3.4.4
# cross-field invariant (``last_run_at`` populated whenever outcome is
# a run state; cleared on move back to ``not_run``) lives at the
# repository layer in ``repositories/test_spec.py``, not in this map.
TEST_SPEC_RUN_OUTCOMES: frozenset[str] = frozenset(
    {"not_run", "passing", "failing", "skipped"}
)

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
PROJECT_STATUSES: frozenset[str] = frozenset(
    {"planned", "in_flight", "complete", "cancelled", "superseded"}
)
PROJECT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"in_flight", "cancelled", "superseded"}),
    "in_flight": frozenset({"complete", "cancelled", "superseded"}),
    "complete": frozenset(),
    "cancelled": frozenset(),
    "superseded": frozenset(),
}

# `conversation` lifecycle (DEC-314, PI-073 redesign — supersedes DEC-131).
# Six statuses; forward-only (planned → in_flight) with four terminals
# (complete, cancelled, not_started, superseded). Conversations are now
# topical sub-units within a session per the redesign; the not_started
# terminal captures conversations planned within a session that never
# opened (Q2 resolution).
CONVERSATION_STATUSES: frozenset[str] = frozenset(
    {
        "planned",
        "in_flight",
        "complete",
        "cancelled",
        "not_started",
        "superseded",
    }
)
CONVERSATION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"in_flight", "cancelled", "not_started", "superseded"}),
    "in_flight": frozenset({"complete", "cancelled", "superseded"}),
    "complete": frozenset(),
    "cancelled": frozenset(),
    "not_started": frozenset(),
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
        "project_master_plan",
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
        # v0.5+ entity-schema growth (PI-010, entity.md v1.1 §3.3.1):
        #   - `entity_variant_of_entity` (entity → entity; many-to-one
        #     at source side per DEC-291). First entity-to-entity edge
        #     kind in the vocabulary. Cardinality (an entity has at
        #     most one outbound variant edge) enforced at the access
        #     layer per references.py, not the schema layer.
        "entity_variant_of_entity",
        # v0.7 additions (governance entities). Eight new kinds aggregated
        # across the six governance schema specs (workstream, conversation,
        # reference_book, work_ticket, close_out_payload, deposit_event).
        # See governance-entity-PRD-v0.1.md section 4.3.
        "conversation_belongs_to_project",
        "project_planned_in_reference_book",
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
        # v0.5+ field additions (PI-004 first slice, field.md §3.3.1):
        #   - `field_belongs_to_entity` (field → entity; mandatory 1:1
        #     at the source side per DEC-249). Cardinality enforced at
        #     the access layer, not the schema layer.
        "field_belongs_to_entity",
        # v0.5+ requirement additions (PI-004 cohort, requirement.md
        # §3.3.1). Five outbound kinds declared by ``requirement``.
        # Three target live entity types (``domain``, ``entity``,
        # ``process``, and now ``field`` post PI-004 first slice); one
        # targets a sibling cohort entity type not yet live
        # (``test_spec``) whose CHECK admittance lands here proactively
        # per requirement.md §3.3.1. The ``_kinds_for_pair`` clause for
        # ``(requirement, test_spec)`` is left as a TODO until that
        # sibling lands.
        "requirement_scopes_to_domain",
        "requirement_touches_entity",
        "requirement_touches_field",
        "requirement_realized_by_process",
        "requirement_verified_by_test_spec",
        # v0.5+ manual_config additions (PI-004 cohort, manual_config.md
        # §3.3.1). Four outbound kinds. All four target entity types are
        # live (``domain`` v0.4, ``entity`` v0.4, ``field`` PI-004 first
        # slice, ``requirement`` PI-004 cohort) so every clause in
        # ``_kinds_for_pair`` activates unconditionally.
        "manual_config_scopes_to_domain",
        "manual_config_touches_entity",
        "manual_config_touches_field",
        "manual_config_realizes_requirement",
        # v0.5+ test_spec additions (PI-004 cohort closer, test_spec.md
        # §3.3.1). Three outbound kinds registered here. The inbound
        # ``requirement_verified_by_test_spec`` kind is registered above
        # in the requirement block (per CLAUDE.md line 48's once-per-kind
        # rule); this build only activates its previously-dormant
        # ``_kinds_for_pair`` clause. All three target entity types
        # (``entity`` v0.4, ``field`` PI-004 first slice, ``process``
        # v0.4) are live, so every ``test_spec_*`` clause in
        # ``_kinds_for_pair`` activates unconditionally.
        "test_spec_exercises_process",
        "test_spec_touches_entity",
        "test_spec_touches_field",
        # v0.8 process v2 schema growth (PI-005, process-v2.md §3.3.2).
        # Three new outgoing kinds from ``process`` to other methodology
        # entity types. All three target types are live in ENTITY_TYPES
        # by the time this build lands (``persona`` PI-003, ``field``
        # PI-004 first slice, ``entity`` v0.4) so every clause in
        # ``_kinds_for_pair`` activates unconditionally. The
        # ``process_touches_entity`` kind promotes the v0.4-anticipated
        # relationship from ``process.md`` §3.3.2 to a live registration.
        "process_performed_by_persona",
        "process_touches_field",
        "process_touches_entity",
        # PI-073 / DEC-314 additions (session-conversation redesign).
        # Six new kinds aggregated across session-v2.md §3.3.4 and
        # conversation-v2.md §3.3.4. The v0.7-era kinds
        # (`conversation_records_session`, `conversation_opens_against_work_ticket`,
        # `conversation_succeeds_conversation`, `close_out_payload_produced_by_conversation`)
        # remain admitted during transition; Phase F retires them after
        # the data migration retargets the edges.
        #
        # session outbound:
        #   - `session_belongs_to_project` (session → workstream;
        #     exactly-one membership per session-v2.md §3.3.1).
        #   - `session_opens_against_work_ticket` (session → work_ticket;
        #     successor to `conversation_opens_against_work_ticket`).
        #   - `session_follows_from` (session → session; medium-driven
        #     session-level sequencing per Q1 resolution).
        # conversation outbound (new topical sub-unit shape):
        #   - `conversation_belongs_to_session` (conversation → session;
        #     mandatory parent linkage, replaces 1:0..1 with 1:N).
        #   - `conversation_follows_from` (conversation → conversation;
        #     direct cross-session topical continuity per Q2).
        #   - `conversation_relates_to` (conversation → conversation;
        #     loose cross-session topical relation).
        "session_belongs_to_project",
        "session_opens_against_work_ticket",
        "session_follows_from",
        "conversation_belongs_to_session",
        "conversation_follows_from",
        "conversation_relates_to",
        # PI-080 addition: orchestrator → child conversation edge. Allows
        # the governance timeline to express the parent–child structure
        # of a parallel run (an orchestrator conversation supervising
        # one or more child agents' conversations). Joins the other two
        # conversation→conversation kinds (`conversation_follows_from`,
        # `conversation_relates_to`) in _kinds_for_pair below.
        "conversation_orchestrates_conversation",
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
        "project",
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
        # v0.5+ methodology entity (PI-004 first slice). See field.md.
        "field",
        # v0.5+ methodology entity (PI-004 cohort). See requirement.md.
        "requirement",
        # v0.5+ methodology entity (PI-004 cohort). See manual_config.md.
        "manual_config",
        # v0.5+ methodology entity (PI-004 cohort closer; resolves
        # PI-004). See test_spec.md.
        "test_spec",
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
    * ``entity_variant_of_entity`` — source and target must both be
      entities (v0.5+, PI-010 / DEC-291; many-to-one at source —
      cardinality enforced at the access layer, not by this map).
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
    * ``field_belongs_to_entity`` — source must be a field, target must
      be an entity (v0.5+, field.md §3.3.1; mandatory 1:1 at source,
      access-layer cardinality enforcement per DEC-249).
    * ``requirement_scopes_to_domain`` — source must be a requirement,
      target must be a domain (v0.5+, requirement.md §3.3.1; many-to-many).
    * ``requirement_touches_entity`` — source must be a requirement,
      target must be an entity (v0.5+, requirement.md §3.3.1).
    * ``requirement_touches_field`` — source must be a requirement,
      target must be a field (v0.5+, requirement.md §3.3.1).
    * ``requirement_realized_by_process`` — source must be a requirement,
      target must be a process (v0.5+, requirement.md §3.3.1).
    * ``requirement_verified_by_test_spec`` — held as a TODO; activates
      when the ``test_spec`` sibling entity type lands. CHECK admits
      the kind already; the ``_kinds_for_pair`` clause uncomments at
      sibling-build time.
    * ``manual_config_scopes_to_domain`` — source must be a manual_config,
      target must be a domain (v0.5+, manual_config.md §3.3.1;
      many-to-many; zero-affiliation permitted).
    * ``manual_config_touches_entity`` — source must be a manual_config,
      target must be an entity (v0.5+, manual_config.md §3.3.1).
    * ``manual_config_touches_field`` — source must be a manual_config,
      target must be a field (v0.5+, manual_config.md §3.3.1; clause
      active because ``field`` is live as of PI-004 first slice).
    * ``manual_config_realizes_requirement`` — source must be a
      manual_config, target must be a requirement (v0.5+,
      manual_config.md §3.3.1; clause active because ``requirement`` is
      live as of PI-004 cohort).
    * ``test_spec_touches_entity`` — source must be a test_spec, target
      must be an entity (v0.5+, test_spec.md §3.3.1; many-to-many).
    * ``test_spec_touches_field`` — source must be a test_spec, target
      must be a field (v0.5+, test_spec.md §3.3.1; many-to-many).
    * ``test_spec_exercises_process`` — source must be a test_spec,
      target must be a process (v0.5+, test_spec.md §3.3.1; many-to-
      many).
    * ``process_performed_by_persona`` — source must be a process,
      target must be a persona (v0.8, PI-005, process-v2.md §3.3.2;
      many-to-many).
    * ``process_touches_field`` — source must be a process, target
      must be a field (v0.8, PI-005, process-v2.md §3.3.2; many-to-
      many).
    * ``process_touches_entity`` — source must be a process, target
      must be an entity (v0.8, PI-005, process-v2.md §3.3.2; promotes
      the v0.5+ anticipation from process.md §3.3.2 to a live
      registration; many-to-many).

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
    # v0.5+ PI-010 / DEC-291: entity variants. First entity-to-entity
    # edge kind in the vocabulary. Note the `supersedes` clause above
    # already admits same-type supersession for (entity, entity), so
    # this pair surfaces both kinds in the cascading dialog.
    if source_type == "entity" and target_type == "entity":
        kinds.add("entity_variant_of_entity")
    # v0.7 governance additions, grouped by source type for readability.
    # The same-type `supersedes` clause above already admits supersession
    # for every governance same-type pair (workstream/workstream, etc.);
    # the same-type `conversation_succeeds_conversation` is added alongside.
    if source_type == "conversation" and target_type == "project":
        kinds.add("conversation_belongs_to_project")
    if source_type == "conversation" and target_type == "session":
        kinds.add("conversation_records_session")
    if source_type == "conversation" and target_type == "work_ticket":
        kinds.add("conversation_opens_against_work_ticket")
    if source_type == "conversation" and target_type == "conversation":
        kinds.add("conversation_succeeds_conversation")
    if source_type == "project" and target_type == "reference_book":
        kinds.add("project_planned_in_reference_book")
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
    # v0.5+ field additions (PI-004 first slice, field.md §3.3.1):
    if source_type == "field" and target_type == "entity":
        kinds.add("field_belongs_to_entity")
    # v0.5+ requirement additions (PI-004 cohort, requirement.md
    # §3.3.1). Four pairs are active because their target entity types
    # are live in ENTITY_TYPES; the fifth pair targets ``test_spec``,
    # which is a PI-004 sibling not yet built — its clause is held as
    # a TODO. The refs.relationship_kind CHECK admits all five kinds
    # proactively (migration 0015); these clauses gate the cascading
    # ReferenceCreateDialog + RELATIONSHIP_RULES precomputation. A
    # clause for an unregistered target_type would be skipped by the
    # outer ``ENTITY_TYPES × ENTITY_TYPES`` comprehension anyway, but
    # leaving an active clause for a missing type is a tripping hazard
    # if the sibling later lands and its build forgets to revisit this
    # file — keep the TODO comment explicit.
    if source_type == "requirement" and target_type == "domain":
        kinds.add("requirement_scopes_to_domain")
    if source_type == "requirement" and target_type == "entity":
        kinds.add("requirement_touches_entity")
    if source_type == "requirement" and target_type == "field":
        kinds.add("requirement_touches_field")
    if source_type == "requirement" and target_type == "process":
        kinds.add("requirement_realized_by_process")
    # Activated by the test_spec PI-004 cohort closer build — now that
    # ``test_spec`` is live in ENTITY_TYPES this clause is no longer
    # dormant. The kind itself is still registered above in the
    # requirement block (once-per-kind rule).
    if source_type == "requirement" and target_type == "test_spec":
        kinds.add("requirement_verified_by_test_spec")
    # v0.5+ manual_config additions (PI-004 cohort, manual_config.md
    # §3.3.1). Four outbound kinds. All four target types
    # (``domain`` / ``entity`` / ``field`` / ``requirement``) are live
    # as of the PI-004 first slice and cohort builds, so every clause
    # activates unconditionally — no TODOs needed.
    if source_type == "manual_config" and target_type == "domain":
        kinds.add("manual_config_scopes_to_domain")
    if source_type == "manual_config" and target_type == "entity":
        kinds.add("manual_config_touches_entity")
    if source_type == "manual_config" and target_type == "field":
        kinds.add("manual_config_touches_field")
    if source_type == "manual_config" and target_type == "requirement":
        kinds.add("manual_config_realizes_requirement")
    # v0.5+ test_spec additions (PI-004 cohort closer, test_spec.md
    # §3.3.1). Three outbound kinds. All three target types
    # (``entity`` / ``field`` / ``process``) are live in ENTITY_TYPES,
    # so every clause activates unconditionally.
    if source_type == "test_spec" and target_type == "entity":
        kinds.add("test_spec_touches_entity")
    if source_type == "test_spec" and target_type == "field":
        kinds.add("test_spec_touches_field")
    if source_type == "test_spec" and target_type == "process":
        kinds.add("test_spec_exercises_process")
    # v0.8 process v2 schema growth additions (PI-005, process-v2.md
    # §3.3.2). Three new outgoing kinds from ``process``. All three
    # target types are live in ENTITY_TYPES (``persona`` PI-003,
    # ``field`` PI-004 first slice, ``entity`` v0.4), so every clause
    # activates unconditionally.
    if source_type == "process" and target_type == "persona":
        kinds.add("process_performed_by_persona")
    if source_type == "process" and target_type == "field":
        kinds.add("process_touches_field")
    if source_type == "process" and target_type == "entity":
        kinds.add("process_touches_entity")
    # PI-073 / DEC-314 additions (session-conversation redesign). The
    # legacy `conversation_records_session`, `conversation_opens_against_work_ticket`,
    # `conversation_succeeds_conversation`, `close_out_payload_produced_by_conversation`
    # clauses remain present above during transition; Phase F retires them
    # after the data migration retargets edges to the new kinds.
    if source_type == "session" and target_type == "project":
        kinds.add("session_belongs_to_project")
    if source_type == "session" and target_type == "work_ticket":
        kinds.add("session_opens_against_work_ticket")
    if source_type == "session" and target_type == "session":
        kinds.add("session_follows_from")
    if source_type == "conversation" and target_type == "session":
        kinds.add("conversation_belongs_to_session")
    if source_type == "conversation" and target_type == "conversation":
        kinds.add("conversation_follows_from")
        kinds.add("conversation_relates_to")
        # PI-080: orchestrator → child conversation. Joins the other two
        # conversation→conversation kinds; the same-type ``supersedes``
        # clause earlier already admits supersession for this pair too.
        kinds.add("conversation_orchestrates_conversation")
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
