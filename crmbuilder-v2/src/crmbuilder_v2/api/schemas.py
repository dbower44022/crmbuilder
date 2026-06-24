"""Pydantic v2 request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Charter / Status ----------


class CharterReplaceIn(_Base):
    payload: dict


class StatusReplaceIn(_Base):
    payload: dict


# ---------- Decisions ----------


class DecisionCreateIn(_Base):
    """POST /decisions body. ``identifier`` is server-assigned when
    omitted (PI-002, option C of SES-010)."""

    identifier: str | None = None
    title: str
    decision_date: str
    status: str
    context: str = ""
    decision: str = ""
    rationale: str = ""
    alternatives_considered: str = ""
    consequences: str = ""
    supersedes: str | None = None
    superseded_by: str | None = None
    executive_summary: str  # PI-074; required since PI-075 (NOT NULL)


class DecisionUpdateIn(_Base):
    title: str | None = None
    decision_date: str | None = None
    status: str | None = None
    context: str | None = None
    decision: str | None = None
    rationale: str | None = None
    alternatives_considered: str | None = None
    consequences: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    executive_summary: str | None = None  # PI-074


# ---------- Sessions ----------


class SessionCreateIn(_Base):
    """POST /sessions body — PI-073 / DEC-314 redesign.

    Sessions are now the medium-agnostic communication container. The
    legacy fields (session_date, conversation_reference, topics_covered,
    summary, artifacts_produced, in_flight_at_end) are removed; their
    semantic content lives on the new conversation entity. ``identifier``
    is server-assigned when omitted (PI-002).
    """

    session_identifier: str | None = None
    session_title: str
    session_description: str
    session_medium: str
    session_notes: str | None = None
    session_executive_summary: str  # PI-074; required since PI-075 (NOT NULL)
    session_status: str | None = None
    session_scheduled_for: datetime | None = None
    session_started_at: datetime | None = None
    session_ended_at: datetime | None = None
    session_participants: list | None = None
    session_medium_metadata: dict | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class SessionReplaceIn(_Base):
    """PUT /sessions/{identifier} body — full replacement."""

    session_identifier: str | None = None
    session_title: str
    session_description: str
    session_medium: str
    session_notes: str | None = None
    session_executive_summary: str  # PI-074; required since PI-075 (NOT NULL)
    session_status: str
    session_scheduled_for: datetime | None = None
    session_started_at: datetime | None = None
    session_ended_at: datetime | None = None
    session_participants: list | None = None
    session_medium_metadata: dict | None = None
    references: list[GovernanceEdgeIn] | None = None


class SessionPatchIn(_Base):
    """PATCH /sessions/{identifier} body — partial update."""

    session_title: str | None = None
    session_description: str | None = None
    session_medium: str | None = None
    session_notes: str | None = None
    session_executive_summary: str | None = None  # PI-074
    session_status: str | None = None
    session_scheduled_for: datetime | None = None
    session_started_at: datetime | None = None
    session_ended_at: datetime | None = None
    session_participants: list | None = None
    session_medium_metadata: dict | None = None
    references: list[GovernanceEdgeIn] | None = None


# ---------- Risks ----------


class RiskCreateIn(_Base):
    """POST /risks body. ``identifier`` is server-assigned when omitted
    (PI-002, option C of SES-010)."""

    identifier: str | None = None
    title: str
    description: str = ""
    probability: str
    impact: str
    response_plan: str = ""
    status: str


class RiskUpdateIn(_Base):
    title: str | None = None
    description: str | None = None
    probability: str | None = None
    impact: str | None = None
    response_plan: str | None = None
    status: str | None = None


# ---------- Planning items ----------


class PlanningItemCreateIn(_Base):
    """POST /planning-items body. ``identifier`` is server-assigned when
    omitted (PI-002, option C of SES-010)."""

    identifier: str | None = None
    title: str
    item_type: str
    description: str = ""
    status: str
    resolution_reference: str | None = None
    executive_summary: str  # PI-074; required since PI-075 (NOT NULL)
    area: list[str] | None = None  # PI-076
    execution_mode: str = "ado"  # PI-183; ADO risk gate, defaults to ado


class PlanningItemUpdateIn(_Base):
    title: str | None = None
    item_type: str | None = None
    description: str | None = None
    status: str | None = None
    resolution_reference: str | None = None
    executive_summary: str | None = None  # PI-074
    area: list[str] | None = None  # PI-076
    execution_mode: str | None = None  # PI-183


class PlanningItemClaimIn(_Base):
    """POST /planning-items/{id}/claim body (PI-077). ``claimant`` is the
    conversation identifier (CONV-NNN) of the agent taking the item."""

    claimant: str


class PlanningItemReleaseIn(_Base):
    """POST /planning-items/{id}/release body (PI-077). When ``claimant``
    is supplied the release only proceeds if the item is held by it."""

    claimant: str | None = None


# ---------- Identifier reservation (PI-078) ----------


class IdentifierReserveIn(_Base):
    """POST /identifiers/reserve body. Reserves a block of ``count``
    identifiers of ``entity_type`` under the optional ``reserved_by``
    conversation claim, held for ``ttl_seconds`` (default 1 hour)."""

    entity_type: str
    count: int
    reserved_by: str | None = None
    ttl_seconds: int | None = None


# ---------- Topics ----------


class TopicCreateIn(_Base):
    """POST /topics body. ``identifier`` is server-assigned when omitted
    (PI-002, option C of SES-010)."""

    identifier: str | None = None
    name: str
    description: str = ""
    parent_topic: str | None = None


class TopicUpdateIn(_Base):
    name: str | None = None
    description: str | None = None
    parent_topic: str | None = None


# ---------- Agent Profile Registry (PI-122) ----------


class AgentProfileCreateIn(_Base):
    """POST /agent-profiles body. ``scope`` is 'system' or an engagement id."""

    identifier: str | None = None
    area: str
    tier: str
    description: str
    status: str = "active"
    scope: str | None = None
    capability_description: dict | None = None


class AgentProfileUpdateIn(_Base):
    area: str | None = None
    tier: str | None = None
    description: str | None = None
    status: str | None = None
    scope: str | None = None
    capability_description: dict | None = None


class SkillCreateIn(_Base):
    identifier: str | None = None
    name: str
    kind: str
    description: str
    io_contract: dict | None = None
    backing_callable: str | None = None
    version: int = 1
    status: str = "active"
    scope: str | None = None


class SkillUpdateIn(_Base):
    name: str | None = None
    kind: str | None = None
    description: str | None = None
    io_contract: dict | None = None
    backing_callable: str | None = None
    version: int | None = None
    status: str | None = None
    scope: str | None = None


# ---------- Terms (glossary, PI-061) ----------


class TermCreateIn(_Base):
    """POST /terms body. ``identifier`` is server-assigned when omitted; ``scope``
    defaults to ``system`` (a universal term)."""

    identifier: str | None = None
    name: str
    definition: str
    usage_scope: str | None = None
    examples: str | None = None
    distinguishing_notes: str | None = None
    related_terms: str | None = None
    version: int = 1
    status: str = "active"
    scope: str | None = None


class TermUpdateIn(_Base):
    """PATCH /terms/{identifier} body — partial update."""

    name: str | None = None
    definition: str | None = None
    usage_scope: str | None = None
    examples: str | None = None
    distinguishing_notes: str | None = None
    related_terms: str | None = None
    version: int | None = None
    status: str | None = None
    scope: str | None = None


class GovernanceRuleCreateIn(_Base):
    identifier: str | None = None
    body: str
    enforcement: str
    rule_type: str | None = None
    severity: str | None = None
    predicate: dict | None = None
    version: int = 1
    status: str = "active"
    scope: str | None = None


class GovernanceRuleUpdateIn(_Base):
    body: str | None = None
    enforcement: str | None = None
    rule_type: str | None = None
    severity: str | None = None
    predicate: dict | None = None
    version: int | None = None
    status: str | None = None
    scope: str | None = None


class LearningCreateIn(_Base):
    identifier: str | None = None
    area: str
    tier: str
    category: str
    content: str
    status: str = "active"
    confidence: int = 0
    scope: str | None = None


class LearningUpdateIn(_Base):
    area: str | None = None
    tier: str | None = None
    category: str | None = None
    content: str | None = None
    status: str | None = None
    confidence: int | None = None
    scope: str | None = None


class LearningCaptureIn(_Base):
    """POST /learnings/capture — capture at Work-Task close, optional evidence."""

    area: str
    tier: str
    category: str
    content: str
    evidence_type: str | None = None
    evidence_id: str | None = None
    scope: str | None = None


class LearningEvidenceIn(_Base):
    """POST /learnings/{id}/evidence — accumulate (or contradict) evidence."""

    target_type: str
    target_id: str
    contradicts: bool = False


class LearningPromoteSkillIn(_Base):
    """POST /learnings/{id}/promote-to-skill."""

    name: str
    kind: str
    description: str | None = None


class LearningPromoteRuleIn(_Base):
    """POST /learnings/{id}/promote-to-rule. Enforced rules require human_approved."""

    enforcement: str
    body: str | None = None
    severity: str | None = None
    rule_type: str | None = None
    human_approved: bool = False


class CurateAreaIn(_Base):
    """POST /learnings/curate — per-(release, area) curate sweep."""

    area: str
    scope: str | None = None


# ---------- Domains (methodology entity, UI v0.4 slice B) ----------


class DomainCreateIn(_Base):
    """POST /domains body. ``domain_identifier`` is server-assigned when
    omitted; ``domain_status`` defaults to ``candidate`` server-side."""

    domain_name: str
    domain_purpose: str
    domain_description: str
    domain_notes: str | None = None
    domain_status: str | None = None
    domain_identifier: str | None = None


class DomainReplaceIn(_Base):
    """PUT /domains/{identifier} body — full record replace.

    ``domain_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422)."""

    domain_identifier: str | None = None
    domain_name: str
    domain_purpose: str
    domain_description: str
    domain_notes: str | None = None
    domain_status: str


class DomainPatchIn(_Base):
    """PATCH /domains/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``domain_notes: null`` (clear the field) is distinguished
    from an omitted ``domain_notes`` (leave unchanged)."""

    domain_name: str | None = None
    domain_purpose: str | None = None
    domain_description: str | None = None
    domain_notes: str | None = None
    domain_status: str | None = None


# ---------- Entities (methodology entity, UI v0.4 slice C) ----------


class EntityCreateIn(_Base):
    """POST /entities body. ``entity_identifier`` is server-assigned when
    omitted; ``entity_status`` defaults to ``candidate`` server-side.

    Domain affiliations are NOT inlined here — per ``entity.md`` section
    3.5.4 they attach via separate ``POST /references`` calls with the
    ``entity_scopes_to_domain`` relationship kind. Entity variants
    (PI-010) attach the same way via the ``entity_variant_of_entity``
    kind. ``entity_kind`` is optional per v1.1 §3.2.3 / DEC-292 —
    operators may defer classification until Phase 3."""

    entity_name: str
    entity_description: str
    entity_notes: str | None = None
    entity_status: str | None = None
    entity_kind: str | None = None
    entity_identifier: str | None = None
    # PRJ-025 PI-182 — intrinsic engine-neutral design intent (§6).
    entity_default_sort_field: str | None = None
    entity_default_sort_direction: str | None = None
    entity_track_activity: bool | None = None
    # REQ-337 / PI-297 — neutral activity-tracking (EspoCRM BasePlus) flag.
    entity_tracks_activities: bool | None = None


class EntityReplaceIn(_Base):
    """PUT /entities/{identifier} body — full record replace.

    ``entity_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422). ``entity_kind`` is replaced
    wholesale (omitted-from-body deserialises to ``None`` and clears
    the field); operators wanting partial update should use PATCH. The
    PRJ-025 PI-182 §6 intrinsics replace wholesale under the same
    semantics."""

    entity_identifier: str | None = None
    entity_name: str
    entity_description: str
    entity_notes: str | None = None
    entity_status: str
    entity_kind: str | None = None
    entity_default_sort_field: str | None = None
    entity_default_sort_direction: str | None = None
    entity_track_activity: bool | None = None
    entity_tracks_activities: bool | None = None


class EntityPatchIn(_Base):
    """PATCH /entities/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``entity_notes: null`` (clear the field) is distinguished
    from an omitted ``entity_notes`` (leave unchanged). Same semantics
    apply to ``entity_kind`` (PI-010 / DEC-292) and the PRJ-025 PI-182
    §6 intrinsics: null clears, omitted leaves unchanged."""

    entity_name: str | None = None
    entity_description: str | None = None
    entity_notes: str | None = None
    entity_status: str | None = None
    entity_kind: str | None = None
    entity_default_sort_field: str | None = None
    entity_default_sort_direction: str | None = None
    entity_track_activity: bool | None = None
    entity_tracks_activities: bool | None = None


# ---------- Personas (methodology entity, v0.5+) ----------


class PersonaCreateIn(_Base):
    """POST /personas body. ``persona_identifier`` is server-assigned
    when omitted; ``persona_status`` defaults to ``candidate``
    server-side.

    Domain affiliations and entity realization are NOT inlined here —
    per ``persona.md`` §3.5.4 they attach via separate
    ``POST /references`` calls with the ``persona_scopes_to_domain``
    or ``persona_realized_as_entity`` relationship kinds."""

    persona_name: str
    persona_role_summary: str
    persona_responsibilities: str | None = None
    persona_notes: str | None = None
    persona_status: str | None = None
    persona_identifier: str | None = None


class PersonaReplaceIn(_Base):
    """PUT /personas/{identifier} body — full record replace.

    ``persona_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422). Per ``persona.md`` §3.5 the
    ``persona_status`` is required on a full replace."""

    persona_identifier: str | None = None
    persona_name: str
    persona_role_summary: str
    persona_responsibilities: str | None = None
    persona_notes: str | None = None
    persona_status: str


class PersonaPatchIn(_Base):
    """PATCH /personas/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``persona_notes: null`` (clear the field) is distinguished
    from an omitted ``persona_notes`` (leave unchanged)."""

    persona_name: str | None = None
    persona_role_summary: str | None = None
    persona_responsibilities: str | None = None
    persona_notes: str | None = None
    persona_status: str | None = None


# ---------- Fields (methodology entity, v0.5+ PI-004 first slice) ----------


class FieldOptionIn(_Base):
    """One enum/multi_enum option value (PRJ-025 PI-182, §8 field_option).

    ``option_order`` defaults to the list position when omitted. A
    field's ``field_options`` list, when supplied, replaces its entire
    option set; ``option_value`` is unique within the field."""

    option_value: str
    option_label: str | None = None
    option_order: int | None = None


class FieldCreateIn(_Base):
    """POST /fields body.

    ``field_identifier`` is server-assigned when omitted;
    ``field_status`` defaults to ``candidate`` server-side;
    ``field_required`` defaults to ``False`` server-side.
    ``field_belongs_to_entity_identifier`` is REQUIRED — the access
    layer creates the field row, the ``field_belongs_to_entity`` edge,
    and the change-log emit in one transaction per ``field.md`` §3.5.4.
    This is the one deviation from the cross-spec decomposed-references
    default. The PRJ-025 PI-182 §7 intrinsics + ``field_options`` are
    optional."""

    field_name: str
    field_description: str
    field_type: str
    field_belongs_to_entity_identifier: str
    field_required: bool | None = None
    field_notes: str | None = None
    field_status: str | None = None
    field_identifier: str | None = None
    # PRJ-025 PI-182 — intrinsic engine-neutral design intent (§7).
    field_tooltip: str | None = None
    field_usage_summary: str | None = None
    field_default_value: str | None = None
    field_format: str | None = None
    field_numeric_scale: str | None = None
    field_max_length: int | None = None
    field_min: str | None = None
    field_max: str | None = None
    field_read_only: bool | None = None
    field_unique: bool | None = None
    field_externally_populated: bool | None = None
    # PRJ-025 PI-197 — derived/formula intent (DEC-438).
    field_derived_result_type: str | None = None
    field_formula: dict | None = None
    field_options: list[FieldOptionIn] | None = None


class FieldReplaceIn(_Base):
    """PUT /fields/{identifier} body — full record replace.

    Does NOT accept ``field_belongs_to_entity_identifier`` — re-parenting
    requires explicit edge management per ``field.md`` §3.5.4 (DELETE
    the old edge, POST the new edge). PI-053 tracks the future
    convenience endpoint. The PRJ-025 PI-182 §7 scalar intrinsics
    replace wholesale; ``field_options`` replaces the set only when a
    list is supplied (omitted/null leaves it unchanged)."""

    field_identifier: str | None = None
    field_name: str
    field_description: str
    field_type: str
    field_required: bool
    field_notes: str | None = None
    field_status: str
    field_tooltip: str | None = None
    field_usage_summary: str | None = None
    field_default_value: str | None = None
    field_format: str | None = None
    field_numeric_scale: str | None = None
    field_max_length: int | None = None
    field_min: str | None = None
    field_max: str | None = None
    field_read_only: bool | None = None
    field_unique: bool | None = None
    field_externally_populated: bool | None = None
    # PRJ-025 PI-197 — derived/formula intent (DEC-438).
    field_derived_result_type: str | None = None
    field_formula: dict | None = None
    field_options: list[FieldOptionIn] | None = None


class FieldPatchIn(_Base):
    """PATCH /fields/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``field_notes: null`` (clear) is distinguished from an
    omitted ``field_notes`` (leave unchanged). Does NOT accept
    ``field_belongs_to_entity_identifier`` for the same reason as PUT.
    The PRJ-025 PI-182 §7 intrinsics follow the same omitted-vs-null
    semantics; ``field_options`` replaces the set when a list is
    supplied (omitted/null leaves it unchanged)."""

    field_name: str | None = None
    field_description: str | None = None
    field_type: str | None = None
    field_required: bool | None = None
    field_notes: str | None = None
    field_status: str | None = None
    field_tooltip: str | None = None
    field_usage_summary: str | None = None
    field_default_value: str | None = None
    field_format: str | None = None
    field_numeric_scale: str | None = None
    field_max_length: int | None = None
    field_min: str | None = None
    field_max: str | None = None
    field_read_only: bool | None = None
    field_unique: bool | None = None
    field_externally_populated: bool | None = None
    # PRJ-025 PI-197 — derived/formula intent (DEC-438).
    field_derived_result_type: str | None = None
    field_formula: dict | None = None
    field_options: list[FieldOptionIn] | None = None


# ---------- Requirements (methodology entity, PI-004 cohort, v0.5+) ----------


class RequirementCreateIn(_Base):
    """POST /requirements body. ``requirement_identifier`` server-assigned
    when omitted; ``requirement_priority`` defaults to ``should``;
    ``requirement_status`` defaults to ``candidate`` server-side.
    Reference attachments are NOT inlined — per ``requirement.md``
    section 3.5.5 they attach via separate ``POST /references`` calls."""

    requirement_name: str
    requirement_description: str
    requirement_acceptance_summary: str
    requirement_priority: str | None = None
    requirement_notes: str | None = None
    requirement_status: str | None = None
    requirement_identifier: str | None = None
    # Requirements-provenance Phase 5: how the requirement came to be —
    # ``human_defined`` (default when omitted) or ``ai_derived``.
    requirement_origin: str | None = None


class RequirementReplaceIn(_Base):
    """PUT /requirements/{identifier} body — full record replace.

    ``requirement_identifier`` is optional; when present it must match
    the path identifier (mismatch → 422). Per ``requirement.md`` §3.5
    ``requirement_priority`` and ``requirement_status`` are required on
    a full replace."""

    requirement_identifier: str | None = None
    requirement_name: str
    requirement_description: str
    requirement_acceptance_summary: str
    requirement_priority: str
    requirement_notes: str | None = None
    requirement_status: str


class RequirementPatchIn(_Base):
    """PATCH /requirements/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``requirement_notes: null`` (clear) is distinguished from
    an omitted ``requirement_notes`` (leave unchanged)."""

    requirement_name: str | None = None
    requirement_description: str | None = None
    requirement_acceptance_summary: str | None = None
    requirement_priority: str | None = None
    requirement_notes: str | None = None
    requirement_status: str | None = None


class ReviewSignoffCreateIn(_Base):
    """POST /review/signoffs body — record a topic review attestation.

    The server snapshots the topic's current requirement set; the body carries
    only the topic, who reviewed, and the attestation text."""

    signoff_topic_identifier: str
    signoff_reviewer: str
    signoff_attestation: str


class ReviewApprovalsCreateIn(_Base):
    """POST /review/approvals body — reviewer-driven approval of candidates (REQ-251).

    The panel passes its selection, the reviewer, and a decision date; each
    requirement is approved independently and a per-requirement result returned.
    ``note`` is an optional reviewer rationale folded into each approving decision."""

    requirement_identifiers: list[str]
    reviewer: str
    decision_date: str
    note: str | None = None


# ---------- Migration mappings (methodology entity, WTK-107) ----------


class MigrationMappingCreateIn(_Base):
    """POST /migration-mappings body (``migration-mapping-api.md`` §4.7).

    ``migration_mapping_identifier`` is server-assigned when omitted;
    ``migration_mapping_status`` defaults to ``candidate`` server-side
    (explicit ``confirmed`` permitted — the live-triage posture; explicit
    ``rejected`` refused as a starter). Both edge keys are REQUIRED — the
    access layer creates the row, the ``migrates_from_record`` edge, the
    ``migrates_to_record`` edge(s), and the change-log emit in one
    transaction (the DEC-249/250 pattern extended to a two-kind edge set).

    ``migration_mapping_transform_rules`` is deliberately structurally
    loose (``list[dict]``): authoritative rule-schema validation lives at
    the repository layer against ``vocab.MIGRATION_TRANSFORM_RULE_SCHEMAS``
    so REST, MCP, and access-layer callers enforce identically (spec §5.2).
    """

    migration_mapping_level: str
    migration_mapping_disposition: str
    migration_mapping_source_system_label: str
    migration_mapping_source_entity_name: str
    migration_mapping_migrates_from_identifier: str
    migration_mapping_migrates_to_identifiers: list[str]
    migration_mapping_source_attribute_name: str | None = None
    migration_mapping_transform_rules: list[dict] | None = None
    migration_mapping_notes: str | None = None
    migration_mapping_status: str | None = None
    migration_mapping_identifier: str | None = None


class MigrationMappingReplaceIn(_Base):
    """PUT /migration-mappings/{identifier} body — full scalar replace.

    Does NOT accept the edge keys — re-pointing is explicit reference
    management (normally soft-delete and re-create, spec §4.8).
    ``migration_mapping_level`` / ``migration_mapping_disposition`` are
    carried for the full-replace shape but are constitutive: values that
    differ from the record's current ones are refused 422."""

    migration_mapping_identifier: str | None = None
    migration_mapping_level: str
    migration_mapping_disposition: str
    migration_mapping_source_system_label: str
    migration_mapping_source_entity_name: str
    migration_mapping_source_attribute_name: str | None = None
    migration_mapping_transform_rules: list[dict] | None = None
    migration_mapping_notes: str | None = None
    migration_mapping_status: str


class MigrationMappingPatchIn(_Base):
    """PATCH /migration-mappings/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged). ``migration_mapping_level`` / ``_disposition`` and the
    edge keys are deliberately absent (constitutive / POST-only).

    ``rejected_by_decision`` (unprefixed, per the shared ``_rejection``
    contract) is the WTK-088 atomic edge-and-flip admission for a status
    change to ``rejected`` — exposed over REST for mappings (a documented
    deviation from the field cohort, which admits rejection edge-first
    only; spec §4.9)."""

    migration_mapping_source_system_label: str | None = None
    migration_mapping_source_entity_name: str | None = None
    migration_mapping_source_attribute_name: str | None = None
    migration_mapping_transform_rules: list[dict] | None = None
    migration_mapping_notes: str | None = None
    migration_mapping_status: str | None = None
    rejected_by_decision: str | None = None


# ---------- Associations (composite design record, PRJ-025 PI-189) ----------


class AssociationCreateIn(_Base):
    """POST /associations body (engine-neutral-design-model §8).

    ``association_identifier`` is server-assigned when omitted;
    ``association_status`` defaults to ``candidate`` server-side. Both
    endpoint entities (``association_source_entity`` /
    ``association_target_entity``, each an ``ENT-NNN``) are required and are
    validated to exist and be live at the access layer."""

    association_name: str
    association_source_entity: str
    association_target_entity: str
    association_cardinality: str
    association_source_role: str | None = None
    association_target_role: str | None = None
    association_description: str | None = None
    association_notes: str | None = None
    association_status: str | None = None
    association_identifier: str | None = None


class AssociationReplaceIn(_Base):
    """PUT /associations/{identifier} body — full replace."""

    association_identifier: str | None = None
    association_name: str
    association_source_entity: str
    association_target_entity: str
    association_cardinality: str
    association_source_role: str | None = None
    association_target_role: str | None = None
    association_description: str | None = None
    association_notes: str | None = None
    association_status: str


class AssociationPatchIn(_Base):
    """PATCH /associations/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    association_name: str | None = None
    association_source_entity: str | None = None
    association_target_entity: str | None = None
    association_cardinality: str | None = None
    association_source_role: str | None = None
    association_target_role: str | None = None
    association_description: str | None = None
    association_notes: str | None = None
    association_status: str | None = None


# ---------- Engine overrides (composite design record, PRJ-025 PI-189) -------


class EngineOverrideCreateIn(_Base):
    """POST /engine-overrides body (engine-neutral-design-model §9).

    ``override_identifier`` is server-assigned when omitted. The
    ``(target_engine, subject_type, subject_identifier, attribute)`` tuple is
    unique per engagement; a duplicate is refused 409. ``override_value`` is
    free JSON (scalar, list, or object) stored verbatim."""

    override_target_engine: str
    override_subject_type: str
    override_subject_identifier: str
    override_attribute: str
    override_value: object | None = None
    override_notes: str | None = None
    override_identifier: str | None = None


class EngineOverrideReplaceIn(_Base):
    """PUT /engine-overrides/{identifier} body — full replace."""

    override_identifier: str | None = None
    override_target_engine: str
    override_subject_type: str
    override_subject_identifier: str
    override_attribute: str
    override_value: object | None = None
    override_notes: str | None = None


class EngineOverridePatchIn(_Base):
    """PATCH /engine-overrides/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    override_target_engine: str | None = None
    override_subject_type: str | None = None
    override_subject_identifier: str | None = None
    override_attribute: str | None = None
    override_value: object | None = None
    override_notes: str | None = None


# ---------- Rules (condition-carrying design record, PRJ-025 PI-189) ---------


class RuleCreateIn(_Base):
    """POST /rules body (engine-neutral-design-model §8).

    ``rule_identifier`` is server-assigned when omitted; ``rule_status``
    defaults to ``candidate`` server-side. ``rule_subject_identifier`` (an
    ``FLD-NNN`` / ``ENT-NNN``) is validated live and matched against
    ``rule_subject_type`` at the access layer. ``rule_condition`` is a neutral
    condition AST validated before persistence."""

    rule_name: str
    rule_subject_type: str
    rule_subject_identifier: str
    rule_effect: str
    rule_condition: object
    rule_message: str | None = None
    rule_description: str | None = None
    rule_notes: str | None = None
    rule_status: str | None = None
    rule_identifier: str | None = None


class RuleReplaceIn(_Base):
    """PUT /rules/{identifier} body — full replace."""

    rule_identifier: str | None = None
    rule_name: str
    rule_subject_type: str
    rule_subject_identifier: str
    rule_effect: str
    rule_condition: object
    rule_message: str | None = None
    rule_description: str | None = None
    rule_notes: str | None = None
    rule_status: str


class RulePatchIn(_Base):
    """PATCH /rules/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    rule_name: str | None = None
    rule_subject_type: str | None = None
    rule_subject_identifier: str | None = None
    rule_effect: str | None = None
    rule_condition: object | None = None
    rule_message: str | None = None
    rule_description: str | None = None
    rule_notes: str | None = None
    rule_status: str | None = None


# ---------- Views (condition-carrying design record, PRJ-025 PI-189) ---------


class ViewCreateIn(_Base):
    """POST /views body (engine-neutral-design-model §8).

    ``view_identifier`` is server-assigned when omitted; ``view_status``
    defaults to ``candidate`` server-side. ``view_entity`` (an ``ENT-NNN``) is
    validated live; ``view_columns`` is a non-empty ordered list of field
    references; ``view_filter`` (when present) is a neutral condition AST."""

    view_name: str
    view_entity: str
    view_columns: list
    view_filter: object | None = None
    view_sort_field: str | None = None
    view_sort_direction: str | None = None
    view_description: str | None = None
    view_notes: str | None = None
    view_status: str | None = None
    view_identifier: str | None = None


class ViewReplaceIn(_Base):
    """PUT /views/{identifier} body — full replace."""

    view_identifier: str | None = None
    view_name: str
    view_entity: str
    view_columns: list
    view_filter: object | None = None
    view_sort_field: str | None = None
    view_sort_direction: str | None = None
    view_description: str | None = None
    view_notes: str | None = None
    view_status: str


class ViewPatchIn(_Base):
    """PATCH /views/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    view_name: str | None = None
    view_entity: str | None = None
    view_columns: list | None = None
    view_filter: object | None = None
    view_sort_field: str | None = None
    view_sort_direction: str | None = None
    view_description: str | None = None
    view_notes: str | None = None
    view_status: str | None = None


# ------- Automations (condition-carrying design record, PRJ-025 PI-189) ------


class AutomationCreateIn(_Base):
    """POST /automations body (engine-neutral-design-model §8).

    ``automation_identifier`` is server-assigned when omitted;
    ``automation_status`` defaults to ``candidate`` server-side.
    ``automation_entity`` (an ``ENT-NNN``) is validated live;
    ``automation_actions`` is a non-empty list of typed action objects;
    ``automation_condition`` (when present) is a neutral condition AST."""

    automation_name: str
    automation_entity: str
    automation_trigger: str
    automation_actions: list
    automation_condition: object | None = None
    automation_description: str | None = None
    automation_notes: str | None = None
    automation_status: str | None = None
    automation_identifier: str | None = None


class AutomationReplaceIn(_Base):
    """PUT /automations/{identifier} body — full replace."""

    automation_identifier: str | None = None
    automation_name: str
    automation_entity: str
    automation_trigger: str
    automation_actions: list
    automation_condition: object | None = None
    automation_description: str | None = None
    automation_notes: str | None = None
    automation_status: str


class AutomationPatchIn(_Base):
    """PATCH /automations/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    automation_name: str | None = None
    automation_entity: str | None = None
    automation_trigger: str | None = None
    automation_actions: list | None = None
    automation_condition: object | None = None
    automation_description: str | None = None
    automation_notes: str | None = None
    automation_status: str | None = None


# -------- Dedup rules (dedup-and-template design record, PRJ-025 PI-189) ------


class DedupRuleCreateIn(_Base):
    """POST /dedup-rules body (engine-neutral-design-model §8).

    ``dedup_rule_identifier`` is server-assigned when omitted;
    ``dedup_rule_status`` defaults to ``candidate`` server-side.
    ``dedup_rule_entity`` (an ``ENT-NNN``) is validated live;
    ``dedup_rule_match_fields`` is a non-empty list of field references;
    ``dedup_rule_normalize`` (when present) maps a field reference to a
    normalization token; ``dedup_rule_on_match`` is ``block`` / ``warn``."""

    dedup_rule_name: str
    dedup_rule_entity: str
    dedup_rule_match_fields: list
    dedup_rule_on_match: str
    dedup_rule_normalize: object | None = None
    dedup_rule_message: str | None = None
    dedup_rule_description: str | None = None
    dedup_rule_notes: str | None = None
    dedup_rule_status: str | None = None
    dedup_rule_identifier: str | None = None


class DedupRuleReplaceIn(_Base):
    """PUT /dedup-rules/{identifier} body — full replace."""

    dedup_rule_identifier: str | None = None
    dedup_rule_name: str
    dedup_rule_entity: str
    dedup_rule_match_fields: list
    dedup_rule_on_match: str
    dedup_rule_normalize: object | None = None
    dedup_rule_message: str | None = None
    dedup_rule_description: str | None = None
    dedup_rule_notes: str | None = None
    dedup_rule_status: str


class DedupRulePatchIn(_Base):
    """PATCH /dedup-rules/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    dedup_rule_name: str | None = None
    dedup_rule_entity: str | None = None
    dedup_rule_match_fields: list | None = None
    dedup_rule_on_match: str | None = None
    dedup_rule_normalize: object | None = None
    dedup_rule_message: str | None = None
    dedup_rule_description: str | None = None
    dedup_rule_notes: str | None = None
    dedup_rule_status: str | None = None


# --- Message templates (dedup-and-template design record, PRJ-025 PI-189) ---


class MessageTemplateCreateIn(_Base):
    """POST /message-templates body (engine-neutral-design-model §8).

    ``message_template_identifier`` is server-assigned when omitted;
    ``message_template_status`` defaults to ``candidate`` server-side.
    ``message_template_body`` is required (may carry merge-field placeholders);
    ``message_template_channel`` (when present) is ``email`` / ``sms`` /
    ``in_app``; ``message_template_entity`` (an optional ``ENT-NNN``) is
    validated live when present."""

    message_template_name: str
    message_template_body: str
    message_template_entity: str | None = None
    message_template_channel: str | None = None
    message_template_subject: str | None = None
    message_template_merge_fields: list | None = None
    message_template_audience: str | None = None
    message_template_description: str | None = None
    message_template_notes: str | None = None
    message_template_status: str | None = None
    message_template_identifier: str | None = None


class MessageTemplateReplaceIn(_Base):
    """PUT /message-templates/{identifier} body — full replace."""

    message_template_identifier: str | None = None
    message_template_name: str
    message_template_body: str
    message_template_entity: str | None = None
    message_template_channel: str | None = None
    message_template_subject: str | None = None
    message_template_merge_fields: list | None = None
    message_template_audience: str | None = None
    message_template_description: str | None = None
    message_template_notes: str | None = None
    message_template_status: str


class MessageTemplatePatchIn(_Base):
    """PATCH /message-templates/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit null (clear) is distinguished from an omitted key (leave
    unchanged)."""

    message_template_name: str | None = None
    message_template_body: str | None = None
    message_template_entity: str | None = None
    message_template_channel: str | None = None
    message_template_subject: str | None = None
    message_template_merge_fields: list | None = None
    message_template_audience: str | None = None
    message_template_description: str | None = None
    message_template_notes: str | None = None
    message_template_status: str | None = None


# ---------- Processes (methodology entity, UI v0.4 slice D) ----------


class ProcessCreateIn(_Base):
    """POST /processes body. ``process_identifier`` is server-assigned
    when omitted; ``process_classification`` defaults to ``unclassified``
    server-side. ``process_domain_identifier`` is a required scalar FK
    validated against live ``domain`` records.

    Handoffs are NOT inlined here — per ``process.md`` section 3.5.5
    they attach via separate ``POST /references`` calls with the
    ``process_hands_off_to_process`` relationship kind.

    The six Phase 3 content fields (``process_steps``,
    ``process_triggers``, ``process_outcomes``, ``process_edge_cases``,
    ``process_frequency``, ``process_duration_estimate``) are optional
    at create time per ``process-v2.md`` §3.6.4 — the desktop Create
    dialog omits them entirely; the REST endpoint accepts them so API
    callers may pre-populate Phase 3 content when it is already in
    hand at create time."""

    process_name: str
    process_domain_identifier: str
    process_purpose: str
    process_classification: str | None = None
    process_classification_rationale: str | None = None
    process_notes: str | None = None
    process_steps: str | None = None
    process_triggers: str | None = None
    process_outcomes: str | None = None
    process_edge_cases: str | None = None
    process_frequency: str | None = None
    process_duration_estimate: str | None = None
    process_identifier: str | None = None


class ProcessReplaceIn(_Base):
    """PUT /processes/{identifier} body — full record replace.

    ``process_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422).

    The six Phase 3 content fields follow PUT semantics per
    ``process-v2.md`` §3.5.2 — omitting any of them from the body
    clears the corresponding column to NULL. To preserve an existing
    Phase 3 value without re-supplying it, use PATCH instead."""

    process_identifier: str | None = None
    process_name: str
    process_domain_identifier: str
    process_purpose: str
    process_classification: str
    process_classification_rationale: str | None = None
    process_notes: str | None = None
    process_steps: str | None = None
    process_triggers: str | None = None
    process_outcomes: str | None = None
    process_edge_cases: str | None = None
    process_frequency: str | None = None
    process_duration_estimate: str | None = None


class ProcessPatchIn(_Base):
    """PATCH /processes/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``process_notes: null`` (clear the field) is distinguished
    from an omitted ``process_notes`` (leave unchanged).

    Per ``process-v2.md`` §3.5.2, each of the six Phase 3 content
    fields (``process_steps``, ``process_triggers``,
    ``process_outcomes``, ``process_edge_cases``, ``process_frequency``,
    ``process_duration_estimate``) is independently PATCH-able:
    explicit ``null`` clears the column; ``""`` stores empty string;
    non-empty stores the value; omitting the key leaves the column
    unchanged."""

    process_name: str | None = None
    process_domain_identifier: str | None = None
    process_purpose: str | None = None
    process_classification: str | None = None
    process_classification_rationale: str | None = None
    process_notes: str | None = None
    process_steps: str | None = None
    process_triggers: str | None = None
    process_outcomes: str | None = None
    process_edge_cases: str | None = None
    process_frequency: str | None = None
    process_duration_estimate: str | None = None


# ---------- CRM Candidates (methodology entity, UI v0.4 slice E) ----------


class CrmCandidateCreateIn(_Base):
    """POST /crm_candidates body. ``crm_candidate_identifier`` is
    server-assigned when omitted; ``crm_candidate_status`` defaults to
    ``active`` server-side. The singleton-``selected`` check fires on
    submit when the body specifies ``crm_candidate_status='selected'``
    per ``crm_candidate.md`` section 3.5.4."""

    crm_candidate_name: str
    crm_candidate_fit_reason: str
    crm_candidate_notes: str | None = None
    crm_candidate_status: str | None = None
    crm_candidate_identifier: str | None = None


class CrmCandidateReplaceIn(_Base):
    """PUT /crm_candidates/{identifier} body — full record replace.

    ``crm_candidate_identifier`` is optional; when present it must
    match the path identifier (mismatch → 422). Transitioning the
    record's status into ``selected`` triggers the singleton check."""

    crm_candidate_identifier: str | None = None
    crm_candidate_name: str
    crm_candidate_fit_reason: str
    crm_candidate_notes: str | None = None
    crm_candidate_status: str


class CrmCandidatePatchIn(_Base):
    """PATCH /crm_candidates/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``crm_candidate_notes: null`` (clear the field) is
    distinguished from an omitted ``crm_candidate_notes`` (leave
    unchanged). Transitioning ``crm_candidate_status`` into ``selected``
    triggers the singleton check."""

    crm_candidate_name: str | None = None
    crm_candidate_fit_reason: str | None = None
    crm_candidate_notes: str | None = None
    crm_candidate_status: str | None = None


# ---------- Manual Configs (methodology entity, PI-004 cohort, v0.5+) -------


class ManualConfigCreateIn(_Base):
    """POST /manual-configs body. ``manual_config_identifier`` is
    server-assigned when omitted; ``manual_config_status`` defaults to
    ``candidate`` server-side. Reference attachments are NOT inlined —
    per ``manual_config.md`` §3.5.4 they attach via separate
    ``POST /references`` calls.

    POST with ``manual_config_status='completed'`` (importing an already-
    performed config) triggers the §3.5.3 cross-field invariant: both
    ``manual_config_completed_at`` (server-defaulted to ``now()`` when
    omitted) and ``manual_config_completed_by`` (must be supplied) are
    required, or the request fails with a dedicated 422 envelope body
    identifying the missing field(s)."""

    manual_config_name: str
    manual_config_category: str
    manual_config_description: str
    manual_config_instructions: str
    manual_config_notes: str | None = None
    manual_config_status: str | None = None
    manual_config_completed_at: datetime | None = None
    manual_config_completed_by: str | None = None
    manual_config_identifier: str | None = None


class ManualConfigReplaceIn(_Base):
    """PUT /manual-configs/{identifier} body — full record replace.

    ``manual_config_identifier`` is optional; when present it must
    match the path identifier (mismatch → 422). Per ``manual_config.md``
    §3.5 ``manual_config_status`` is required on a full replace; the
    cross-field invariant of §3.5.3 fires when the post-write status
    is ``completed``."""

    manual_config_identifier: str | None = None
    manual_config_name: str
    manual_config_category: str
    manual_config_description: str
    manual_config_instructions: str
    manual_config_notes: str | None = None
    manual_config_status: str
    manual_config_completed_at: datetime | None = None
    manual_config_completed_by: str | None = None


class ManualConfigPatchIn(_Base):
    """PATCH /manual-configs/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``manual_config_notes: null`` (clear the field) is
    distinguished from an omitted ``manual_config_notes`` (leave
    unchanged). Transitioning ``manual_config_status`` into
    ``completed`` triggers the §3.5.3 cross-field invariant against
    the post-merge values."""

    manual_config_name: str | None = None
    manual_config_category: str | None = None
    manual_config_description: str | None = None
    manual_config_instructions: str | None = None
    manual_config_notes: str | None = None
    manual_config_status: str | None = None
    manual_config_completed_at: datetime | None = None
    manual_config_completed_by: str | None = None


# ---------- Test Specs (methodology entity, PI-004 cohort closer, v0.5+) ----


class TestSpecCreateIn(_Base):
    """POST /test-specs body. ``test_spec_identifier`` is server-assigned
    when omitted; ``test_spec_status`` defaults to ``candidate`` server-
    side; ``test_spec_last_run_outcome`` defaults to ``not_run``.

    Reference attachments are NOT inlined — per ``test_spec.md`` §3.5.4
    they attach via separate ``POST /references`` calls. POST with
    ``test_spec_last_run_outcome`` in ``{passing, failing, skipped}``
    triggers the §3.4.4 cross-field invariant: ``test_spec_last_run_at``
    is server-defaulted to ``now()`` if omitted, or honored if supplied
    non-null. The router consumes the body with ``exclude_unset=True``
    so an explicit ``test_spec_last_run_at: null`` (which would violate
    the invariant in a run state) can be distinguished from omission."""

    test_spec_name: str
    test_spec_description: str
    test_spec_steps: str
    test_spec_expected: str
    test_spec_setup: str | None = None
    test_spec_notes: str | None = None
    test_spec_status: str | None = None
    test_spec_last_run_outcome: str | None = None
    test_spec_last_run_at: datetime | None = None
    test_spec_last_run_notes: str | None = None
    test_spec_identifier: str | None = None


class TestSpecReplaceIn(_Base):
    """PUT /test-specs/{identifier} body — full record replace.

    ``test_spec_identifier`` is optional; when present it must match
    the path identifier (mismatch → 422). ``test_spec_status`` and
    ``test_spec_last_run_outcome`` are required on a full replace; the
    §3.4.4 cross-field invariant fires against the post-write outcome
    value."""

    test_spec_identifier: str | None = None
    test_spec_name: str
    test_spec_description: str
    test_spec_steps: str
    test_spec_expected: str
    test_spec_setup: str | None = None
    test_spec_notes: str | None = None
    test_spec_status: str
    test_spec_last_run_outcome: str
    test_spec_last_run_at: datetime | None = None
    test_spec_last_run_notes: str | None = None


class TestSpecPatchIn(_Base):
    """PATCH /test-specs/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``test_spec_last_run_at: null`` (clear the field) is
    distinguished from an omitted ``test_spec_last_run_at`` (leave
    unchanged). **Load-bearing for §3.4.4** — the cross-field invariant
    treats explicit-null and omitted differently when the outcome is a
    run state. Methodology-status transitions are restricted; outcome
    transitions are unrestricted per §3.4.2."""

    test_spec_name: str | None = None
    test_spec_description: str | None = None
    test_spec_setup: str | None = None
    test_spec_steps: str | None = None
    test_spec_expected: str | None = None
    test_spec_notes: str | None = None
    test_spec_status: str | None = None
    test_spec_last_run_outcome: str | None = None
    test_spec_last_run_at: datetime | None = None
    test_spec_last_run_notes: str | None = None


class TestSpecRecordRunIn(_Base):
    """POST /test-specs/{identifier}/record-run body — convenience endpoint.

    Per ``test_spec.md`` §3.8.1 (resolved affirmatively for v0.5+).
    Atomic update of outcome + last_run_at + last_run_notes; ``outcome``
    is required, ``notes`` and ``at`` are optional. When ``outcome`` is
    ``not_run`` the server clears ``last_run_at`` and ``last_run_notes``
    regardless of supplied values (per §3.4.4)."""

    outcome: str
    notes: str | None = None
    at: datetime | None = None


# ---------- Engagements (methodology entity, UI v0.5 slice B) ----------


class EngagementCreateIn(_Base):
    """POST /engagements body. ``engagement_identifier`` is server-assigned
    when omitted; ``engagement_status`` defaults to ``active`` server-side."""

    engagement_code: str
    engagement_name: str
    engagement_purpose: str
    engagement_status: str | None = None
    engagement_identifier: str | None = None


class EngagementReplaceIn(_Base):
    """PUT /engagements/{identifier} body — full record replace.

    ``engagement_identifier`` is optional; when present it must match
    the path (mismatch → 422). ``engagement_code`` is immutable: any
    value other than the current row's ``engagement_code`` raises 422
    with ``immutable_field``."""

    engagement_identifier: str | None = None
    engagement_code: str | None = None
    engagement_name: str
    engagement_purpose: str
    engagement_status: str


class EngagementPatchIn(_Base):
    """PATCH /engagements/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    omitted field is left unchanged. ``engagement_code`` is rejected if
    present and different from the current row."""

    engagement_name: str | None = None
    engagement_purpose: str | None = None
    engagement_status: str | None = None
    engagement_last_opened_at: str | None = None
    # Accepted but rejected by the repository if it differs from current.
    engagement_code: str | None = None


# ---------- References ----------


class ReferenceCreateIn(_Base):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str


class ReferenceDeleteIn(_Base):
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str


# ---------- Catalog: shared sub-row write shapes ----------


class CatalogSystemIn(_Base):
    """One ``catalog_entity_system`` row in an entity create/update payload."""

    system: str
    name: str
    api_name: str | None = None
    is_standard: str  # "true" / "false" / "partial"
    mechanism: str | None = None
    notes: str | None = None
    docs_url: str | None = None


class CatalogSourceIn(_Base):
    title: str
    url: str


class CatalogPresenceIn(_Base):
    system: str
    status: str  # "standard" / "custom" / "absent"
    api_name: str | None = None


class CatalogRelationshipIn(_Base):
    target: str  # catalog_id of target entity
    cardinality: str  # "one-to-one" / "one-to-many" / "many-to-one" / "many-to-many"
    role: str  # "parent" / "child" / "peer"
    description: str = ""
    presence: list[CatalogPresenceIn] = Field(default_factory=list)


class CatalogAttributeIn(_Base):
    """One attribute embedded in a CatalogEntityCreateIn payload, or the body
    for POST /catalog/entities/{cid}/attributes."""

    name: str
    display_name: str
    type: str
    required: bool = False
    max_length: int | None = None
    reference_target: str | None = None
    description: str = ""
    usage: str = ""
    notes: str | None = None
    common_synonyms: list[str] = Field(default_factory=list)
    enum_values: list[str] = Field(default_factory=list)
    presence: list[CatalogPresenceIn] = Field(default_factory=list)


# ---------- Catalog: entity-level write shapes ----------


class CatalogEntityCreateIn(_Base):
    """POST /catalog/entities body — full nested payload."""

    catalog_id: str
    name: str
    display_name: str
    tier: int
    entry_kind: Literal["universal", "subclass"]
    parent_entity: str | None = None  # catalog_id of parent (subclasses only)
    discriminator_attribute: str | None = None
    discriminator_value: str | None = None
    purpose: str = ""
    business_context: str = ""
    data_model_role: str
    typically_required: bool = False
    common_synonyms: list[str] = Field(default_factory=list)
    systems: list[CatalogSystemIn] = Field(default_factory=list)
    sources: list[CatalogSourceIn] = Field(default_factory=list)
    attributes: list[CatalogAttributeIn] = Field(default_factory=list)
    relationships: list[CatalogRelationshipIn] = Field(default_factory=list)


class CatalogEntityUpdateIn(CatalogEntityCreateIn):
    """PUT /catalog/entities/{catalog_id} body — same shape as Create.

    Full nested replace: child collections are wholly replaced by what
    the caller sends. To keep an existing child unchanged, the caller
    must send it back. To delete a child, omit it from the payload.
    """


class CatalogEntityPatchIn(_Base):
    """PATCH /catalog/entities/{catalog_id} body — entity-level fields only.

    Nested child collections (attributes, systems, sources, relationships,
    synonyms) cannot be modified via PATCH; use PUT or the per-attribute
    sub-endpoints for those.
    """

    name: str | None = None
    display_name: str | None = None
    tier: int | None = None
    entry_kind: str | None = None
    parent_entity: str | None = None
    discriminator_attribute: str | None = None
    discriminator_value: str | None = None
    purpose: str | None = None
    business_context: str | None = None
    data_model_role: str | None = None
    typically_required: bool | None = None


class CatalogAttributeCreateIn(CatalogAttributeIn):
    """POST /catalog/entities/{cid}/attributes body. Same shape as
    CatalogAttributeIn, kept as a distinct name so the API docs label
    it clearly as the entity-attribute-create body."""


class CatalogAttributeUpdateIn(CatalogAttributeIn):
    """PUT /catalog/entities/{cid}/attributes/{name} body — full replace."""


class CatalogAttributePatchIn(_Base):
    """PATCH body — partial update; nested child collections (enum_values,
    synonyms, presence) cannot be modified via PATCH."""

    display_name: str | None = None
    type: str | None = None
    required: bool | None = None
    max_length: int | None = None
    reference_target: str | None = None
    description: str | None = None
    usage: str | None = None
    notes: str | None = None


# ---------- Catalog: gap check body ----------


class CatalogGapCheckIn(_Base):
    """POST /catalog/gap-check body.

    Given a draft entity (``based_on_catalog_id``) and the attribute
    names already present in the draft, return the catalog attributes
    that are "standard" in N+ surveyed systems but absent from the
    draft.
    """

    based_on_catalog_id: str
    draft_attribute_names: list[str]
    min_systems: int = Field(default=5, ge=1, le=7)


# ---------- Envelope (response model used by /docs only) ----------


class Envelope(_Base):
    data: Any | None
    meta: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] | None


# ---------- Governance entities (UI v0.7) ----------


class GovernanceEdgeIn(_Base):
    """A fully-specified references-table edge supplied inline on a governance
    create/update body. The access layer creates these in the same
    transaction so edge-required rules see them at commit time."""

    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str


class ProjectCreateIn(_Base):
    project_name: str
    project_purpose: str
    project_description: str
    project_notes: str | None = None
    project_status: str | None = None
    project_execution_mode: str | None = None  # PI-183; ADO risk gate
    project_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class ProjectReplaceIn(_Base):
    project_identifier: str | None = None
    project_name: str
    project_purpose: str
    project_description: str
    project_notes: str | None = None
    project_status: str
    project_execution_mode: str | None = None  # PI-183
    references: list[GovernanceEdgeIn] | None = None


class ProjectPatchIn(_Base):
    project_name: str | None = None
    project_purpose: str | None = None
    project_description: str | None = None
    project_notes: str | None = None
    project_status: str | None = None
    project_execution_mode: str | None = None  # PI-183
    references: list[GovernanceEdgeIn] | None = None


# --- Release (multi-agent release pipeline keystone, PI-205 / PRJ-031) ------
class ReleaseCreateIn(_Base):
    release_title: str
    release_description: str
    release_notes: str | None = None
    release_status: str | None = None
    release_lane_order: int | None = None
    release_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class ReleasePatchIn(_Base):
    release_title: str | None = None
    release_description: str | None = None
    release_notes: str | None = None
    release_lane_order: int | None = None
    references: list[GovernanceEdgeIn] | None = None


class ReleaseTransitionIn(_Base):
    to_status: str
    actor: str | None = None


class ReleaseLaneOrderIn(_Base):
    order: int | None = None


class ReleaseCorrectionIn(_Base):
    title: str
    description: str
    notes: str | None = None


class AreaReopenIn(_Base):
    area: str
    reason: str
    approval_decision_identifier: str | None = None
    triggering_finding_identifier: str | None = None


class RevalidateIn(_Base):
    area: str


class PlanningClaimIn(_Base):
    area: str
    claimed_by: str


# --- Resource locks (PI-203 / PRJ-030) --------------------------------------
class AcquireLocksIn(_Base):
    resources: list[str]
    holder: str


class ReleaseLockIn(_Base):
    holder: str
    resource: str | None = None


class VerifyLocksIn(_Base):
    holder: str
    touched_paths: list[str]


class ReclaimLocksIn(_Base):
    holder: str


# --- Planning org (PI-209 / PRJ-033) ----------------------------------------
class PlanReleaseIn(_Base):
    delta_sets: list[dict[str, Any]]


# --- Reconciliation engine (PI-215 / PRJ-031) -------------------------------
class ReconcileIn(_Base):
    demands: list[dict[str, Any]]


class ResolveConflictIn(_Base):
    decision_identifier: str
    resolved_value: Any | None = None


# --- Agent layer: demand-set + stage drivers (PI-217/218 / PRJ-033) ----------
class DemandsIn(_Base):
    demands: list[dict[str, Any]]
    authored_by: str


class ArchitecturePlanningIn(_Base):
    delta_sets: list[dict[str, Any]] | None = None


class DecomposeIn(_Base):
    workstreams: list[dict[str, Any]]


# --- Front-half review sign-offs (PI-238 / PRJ-041, REQ-285) -----------------
class ReleaseSignoffIn(_Base):
    stage: str  # "reconciliation" | "architecture_planning"
    reviewer: str
    attestation: str
    decision_identifier: str | None = None


# --- Per-area spec (matrix back half, PI-244 / PRJ-041, REQ-295) --------------
class AreaSpecIn(_Base):
    area: str
    implementation: str
    testable: str
    change_reason: str = ""
    trigger_kind: str = "initial"  # initial|design_review|develop_gap|test_bounce|revision
    trigger_finding_identifier: str | None = None


# --- Per-area Design fan-out (matrix back half, PI-245 / REQ-295) -------------
class RunAreaDesignIn(_Base):
    # one authored design per touched area: {area, implementation, testable,
    # change_reason?, trigger_kind?}
    designs: list[dict[str, Any]]


# --- Artifact version (versioned change spine, PI-208 / PRJ-031) ------------
class ArtifactVersionSnapshotIn(_Base):
    artifact_type: str
    artifact_identifier: str
    release_identifier: str
    snapshot: dict[str, Any]


# --- Workstream (delivery phase, PI-112 Phase 4) ---------------------------
class WorkstreamCreateIn(_Base):
    workstream_phase_type: str
    workstream_title: str
    workstream_description: str | None = None
    workstream_notes: str | None = None
    workstream_status: str | None = None
    workstream_needs_attention: bool | None = None
    workstream_needs_attention_reason: str | None = None
    workstream_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class WorkstreamReplaceIn(_Base):
    workstream_identifier: str | None = None
    workstream_phase_type: str
    workstream_title: str
    workstream_description: str | None = None
    workstream_notes: str | None = None
    workstream_status: str
    workstream_needs_attention: bool | None = None
    workstream_needs_attention_reason: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class WorkstreamPatchIn(_Base):
    workstream_phase_type: str | None = None
    workstream_title: str | None = None
    workstream_description: str | None = None
    workstream_notes: str | None = None
    workstream_status: str | None = None
    workstream_needs_attention: bool | None = None
    workstream_needs_attention_reason: str | None = None
    references: list[GovernanceEdgeIn] | None = None


# --- Phase-specialist scoping (ADO §2.1 / §3.2, WTK-003) -------------------
class WorkTaskSpecIn(_Base):
    """One Work Task a phase specialist decided to create when scoping."""

    title: str
    area: str
    description: str | None = None
    notes: str | None = None
    resolved_agent_profile: str | None = None


class WorkstreamScopeIn(_Base):
    """POST /workstreams/{id}/scope body. An empty/omitted ``work_tasks`` list
    is the ``Not Applicable`` assertion (the phase was evaluated, no work)."""

    work_tasks: list[WorkTaskSpecIn] | None = None


# --- Finding (reconciliation gate, PI-134) ---------------------------------
class FindingCreateIn(_Base):
    finding_type: str
    finding_severity: str
    finding_summary: str
    finding_description: str | None = None
    finding_status: str | None = None
    finding_resolution: str | None = None
    finding_resolution_method: str | None = None
    finding_notes: str | None = None
    finding_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class FindingReplaceIn(_Base):
    finding_identifier: str | None = None
    finding_type: str
    finding_severity: str
    finding_summary: str
    finding_description: str | None = None
    finding_status: str
    finding_resolution: str | None = None
    finding_resolution_method: str | None = None
    finding_notes: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class FindingPatchIn(_Base):
    finding_type: str | None = None
    finding_severity: str | None = None
    finding_summary: str | None = None
    finding_description: str | None = None
    finding_status: str | None = None
    finding_resolution: str | None = None
    finding_resolution_method: str | None = None
    finding_notes: str | None = None
    references: list[GovernanceEdgeIn] | None = None


# --- Instance (CRM connection, PI-186 / PRJ-027) ---------------------------
# ``secret`` / ``secret_key`` are write-only plaintext inputs: the router
# stores them in the OS keyring and persists only the opaque reference
# (REQ-157). They are never echoed back. The keyring references are exposed on
# read responses as ``instance_secret_ref`` / ``instance_secret_key_ref`` (opaque).
class InstanceCreateIn(_Base):
    instance_name: str
    instance_url: str
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    instance_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class InstanceReplaceIn(_Base):
    instance_identifier: str | None = None
    instance_name: str
    instance_url: str
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class InstancePatchIn(_Base):
    instance_name: str | None = None
    instance_url: str | None = None
    instance_vendor: str | None = None
    instance_role: str | None = None
    instance_auth_method: str | None = None
    secret: str | None = None
    secret_key: str | None = None
    instance_status: str | None = None
    instance_notes: str | None = None
    references: list[GovernanceEdgeIn] | None = None


# --- Layout (engine-neutral entity layout, PI-193 / PRJ-027) ---------------
class LayoutCreateIn(_Base):
    layout_entity_identifier: str
    layout_type: str
    layout_content: dict[str, Any] | None = None
    layout_status: str | None = None
    layout_notes: str | None = None
    layout_identifier: str | None = None


class LayoutReplaceIn(_Base):
    layout_identifier: str | None = None
    layout_entity_identifier: str
    layout_type: str
    layout_content: dict[str, Any] | None = None
    layout_status: str
    layout_notes: str | None = None


class LayoutPatchIn(_Base):
    layout_entity_identifier: str | None = None
    layout_type: str | None = None
    layout_content: dict[str, Any] | None = None
    layout_status: str | None = None
    layout_notes: str | None = None


# --- Role (engine-neutral security role, PI-194 / PRJ-027) -----------------
class RoleCreateIn(_Base):
    role_name: str
    role_scope_access: dict[str, Any] | None = None
    role_system_permissions: dict[str, Any] | None = None
    role_description: str | None = None
    role_status: str | None = None
    role_notes: str | None = None
    role_identifier: str | None = None


class RoleReplaceIn(_Base):
    role_identifier: str | None = None
    role_name: str
    role_scope_access: dict[str, Any] | None = None
    role_system_permissions: dict[str, Any] | None = None
    role_description: str | None = None
    role_status: str
    role_notes: str | None = None


class RolePatchIn(_Base):
    role_name: str | None = None
    role_scope_access: dict[str, Any] | None = None
    role_system_permissions: dict[str, Any] | None = None
    role_description: str | None = None
    role_status: str | None = None
    role_notes: str | None = None


# --- Team (engine-neutral security team, PI-194 / PRJ-027) -----------------
class TeamCreateIn(_Base):
    team_name: str
    team_description: str | None = None
    team_status: str | None = None
    team_notes: str | None = None
    team_identifier: str | None = None


class TeamReplaceIn(_Base):
    team_identifier: str | None = None
    team_name: str
    team_description: str | None = None
    team_status: str
    team_notes: str | None = None


class TeamPatchIn(_Base):
    team_name: str | None = None
    team_description: str | None = None
    team_status: str | None = None
    team_notes: str | None = None


# --- Filtered tab (design family, PI-195 / PRJ-027) ------------------------
class FilteredTabCreateIn(_Base):
    filtered_tab_entity_identifier: str
    filtered_tab_label: str
    filtered_tab_filter: dict[str, Any] | None = None
    filtered_tab_status: str | None = None
    filtered_tab_notes: str | None = None
    filtered_tab_identifier: str | None = None


class FilteredTabReplaceIn(_Base):
    filtered_tab_identifier: str | None = None
    filtered_tab_entity_identifier: str
    filtered_tab_label: str
    filtered_tab_filter: dict[str, Any] | None = None
    filtered_tab_status: str | None = None
    filtered_tab_notes: str | None = None


class FilteredTabPatchIn(_Base):
    filtered_tab_entity_identifier: str | None = None
    filtered_tab_label: str | None = None
    filtered_tab_filter: dict[str, Any] | None = None
    filtered_tab_status: str | None = None
    filtered_tab_notes: str | None = None


# --- Source mapping (entity-level decision, PI-255 / PRJ-027) --------------
# Schema fields are ``source_mapping_``-prefixed (the entity prefix); the
# router strips the prefix to the repo kwargs. The ``status`` lifecycle moves
# through the gated transitions enforced in the repository (DEC-454/575/579).
class SourceMappingCreateIn(_Base):
    source_mapping_instance_identifier: str
    source_mapping_source_entity_name: str
    source_mapping_decision_type: str
    source_mapping_notes: str | None = None
    source_mapping_identifier: str | None = None


class SourceMappingReplaceIn(_Base):
    source_mapping_source_entity_name: str
    source_mapping_decision_type: str
    source_mapping_status: str
    source_mapping_notes: str | None = None
    source_mapping_stale_reason: str | None = None
    source_mapping_stale_severity: str | None = None
    source_mapping_superseded_by: str | None = None
    source_mapping_resolved_at: str | None = None


class SourceMappingPatchIn(_Base):
    source_mapping_source_entity_name: str | None = None
    source_mapping_decision_type: str | None = None
    source_mapping_notes: str | None = None


# --- Field mapping (field-level decision, PI-255 / PRJ-027) ----------------
class FieldMappingCreateIn(_Base):
    field_mapping_source_mapping_identifier: str
    field_mapping_source_field_name: str
    field_mapping_decision_type: str
    field_mapping_target_entity_identifier: str | None = None
    field_mapping_target_field_identifier: str | None = None
    field_mapping_notes: str | None = None
    field_mapping_identifier: str | None = None


class FieldMappingReplaceIn(_Base):
    field_mapping_source_field_name: str
    field_mapping_decision_type: str
    field_mapping_status: str
    field_mapping_target_entity_identifier: str | None = None
    field_mapping_target_field_identifier: str | None = None
    field_mapping_notes: str | None = None
    field_mapping_stale_reason: str | None = None
    field_mapping_stale_severity: str | None = None
    field_mapping_superseded_by: str | None = None
    field_mapping_resolved_at: str | None = None


class FieldMappingPatchIn(_Base):
    field_mapping_source_field_name: str | None = None
    field_mapping_decision_type: str | None = None
    field_mapping_target_entity_identifier: str | None = None
    field_mapping_target_field_identifier: str | None = None
    field_mapping_notes: str | None = None


# --- Mark stale (shared by source + field mappings, PI-255 / PRJ-027) ------
class MarkStaleIn(_Base):
    reason: str
    severity: str


# --- Source mapping targets (child table, PI-255 / PRJ-027) ----------------
# Integer-PK child; bodies follow the repo kwarg names directly (no prefix).
class SourceMappingTargetAddIn(_Base):
    source_mapping_identifier: str
    entity_identifier: str


class SourceMappingTargetSetIn(_Base):
    source_mapping_identifier: str
    entity_identifiers: list[str]


class SourceMappingTargetRemoveIn(_Base):
    source_mapping_identifier: str
    entity_identifier: str


# --- Value mapping (child, integer PK, PI-255 / PRJ-027) -------------------
class ValueMappingCreateIn(_Base):
    field_mapping_identifier: str
    source_value: str
    decision_type: str
    target_value: str | None = None
    notes: str | None = None


class ValueMappingUpdateIn(_Base):
    decision_type: str
    target_value: str | None = None
    notes: str | None = None
    status: str | None = None


class ValueMappingSupersedeIn(_Base):
    replacement_id: int


# --- Mapping candidate (reconciler output, integer PK, PI-255 / PRJ-027) ---
class MappingCandidateCreateIn(_Base):
    instance_identifier: str
    candidate_type: str
    source_entity_name: str
    source_field_name: str | None = None
    source_value: str | None = None
    audit_event_identifier: str | None = None
    suggested_source_mapping_identifier: str | None = None
    suggested_field_mapping_identifier: str | None = None
    suggestion_confidence: str | None = None
    suggestion_basis: str | None = None


class MappingCandidateResolveIn(_Base):
    resolved_to_source_mapping_identifier: str | None = None
    resolved_to_field_mapping_identifier: str | None = None


class MappingCandidateBulkIn(_Base):
    candidates: list[MappingCandidateCreateIn]


# --- Work Task (single-area unit, PI-112 Phase 4b) -------------------------
class WorkTaskCreateIn(_Base):
    work_task_title: str
    work_task_area: str
    work_task_description: str | None = None
    work_task_notes: str | None = None
    work_task_status: str | None = None
    work_task_resolved_agent_profile: str | None = None
    work_task_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class WorkTaskReplaceIn(_Base):
    work_task_identifier: str | None = None
    work_task_title: str
    work_task_area: str
    work_task_description: str | None = None
    work_task_notes: str | None = None
    work_task_status: str
    work_task_resolved_agent_profile: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class WorkTaskPatchIn(_Base):
    work_task_title: str | None = None
    work_task_area: str | None = None
    work_task_description: str | None = None
    work_task_notes: str | None = None
    work_task_status: str | None = None
    work_task_resolved_agent_profile: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class WorkTaskClaimIn(_Base):
    claimed_by: str


class ConversationCreateIn(_Base):
    """POST /conversations body — PI-073 / DEC-314 redesign.

    Conversations are now topical sub-units within a session. New
    identifier prefix ``CNV-NNN``. New field ``conversation_summary``
    captured at close. ``conversation_status`` six-status set (planned,
    in_flight, complete, cancelled, not_started, superseded).
    """

    conversation_title: str
    conversation_purpose: str
    conversation_description: str
    conversation_summary: str | None = None
    conversation_notes: str | None = None
    conversation_executive_summary: str | None = None  # PI-074 carry-over
    conversation_status: str | None = None
    conversation_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class ConversationReplaceIn(_Base):
    conversation_identifier: str | None = None
    conversation_title: str
    conversation_purpose: str
    conversation_description: str
    conversation_summary: str | None = None
    conversation_notes: str | None = None
    conversation_executive_summary: str | None = None  # PI-074 carry-over
    conversation_status: str
    references: list[GovernanceEdgeIn] | None = None


class ConversationPatchIn(_Base):
    conversation_title: str | None = None
    conversation_purpose: str | None = None
    conversation_description: str | None = None
    conversation_summary: str | None = None
    conversation_notes: str | None = None
    conversation_executive_summary: str | None = None  # PI-074 carry-over
    conversation_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class ReferenceBookVersionIn(_Base):
    version_label: str
    version_date: str
    version_summary: str | None = None


class ReferenceBookCreateIn(_Base):
    reference_book_title: str
    reference_book_description: str
    reference_book_kind: str
    reference_book_file_path: str
    reference_book_notes: str | None = None
    reference_book_status: str | None = None
    reference_book_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    versions: list[ReferenceBookVersionIn] | None = None


class ReferenceBookReplaceIn(_Base):
    reference_book_identifier: str | None = None
    reference_book_title: str
    reference_book_description: str
    reference_book_kind: str
    reference_book_file_path: str
    reference_book_notes: str | None = None
    reference_book_status: str
    references: list[GovernanceEdgeIn] | None = None


class ReferenceBookPatchIn(_Base):
    reference_book_title: str | None = None
    reference_book_description: str | None = None
    reference_book_kind: str | None = None
    reference_book_file_path: str | None = None
    reference_book_notes: str | None = None
    reference_book_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class WorkTicketCreateIn(_Base):
    work_ticket_title: str
    work_ticket_description: str
    work_ticket_kind: str
    work_ticket_file_path: str
    work_ticket_notes: str | None = None
    work_ticket_status: str | None = None
    work_ticket_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class WorkTicketReplaceIn(_Base):
    work_ticket_identifier: str | None = None
    work_ticket_title: str
    work_ticket_description: str
    work_ticket_kind: str
    work_ticket_file_path: str
    work_ticket_notes: str | None = None
    work_ticket_status: str
    references: list[GovernanceEdgeIn] | None = None


class WorkTicketPatchIn(_Base):
    work_ticket_title: str | None = None
    work_ticket_description: str | None = None
    work_ticket_kind: str | None = None
    work_ticket_file_path: str | None = None
    work_ticket_notes: str | None = None
    work_ticket_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class CloseOutPayloadCreateIn(_Base):
    close_out_payload_title: str
    close_out_payload_description: str
    close_out_payload_file_path: str
    close_out_payload_notes: str | None = None
    close_out_payload_status: str | None = None
    close_out_payload_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class CloseOutPayloadReplaceIn(_Base):
    close_out_payload_identifier: str | None = None
    close_out_payload_title: str
    close_out_payload_description: str
    close_out_payload_file_path: str
    close_out_payload_notes: str | None = None
    close_out_payload_status: str
    references: list[GovernanceEdgeIn] | None = None


class CloseOutPayloadPatchIn(_Base):
    close_out_payload_title: str | None = None
    close_out_payload_description: str | None = None
    close_out_payload_file_path: str | None = None
    close_out_payload_notes: str | None = None
    close_out_payload_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class CommitCreateIn(_Base):
    commit_sha: str
    commit_message_first_line: str
    commit_message_full: str
    commit_author_name: str
    commit_author_email: str
    commit_committed_at: str
    commit_repository: str
    commit_branch: str | None = "main"
    commit_parent_shas: list[str]
    commit_files_changed_count: int
    commit_session_id: str
    commit_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class CommitReplaceIn(_Base):
    commit_identifier: str | None = None
    # body may echo current; access layer rejects any change
    commit_sha: str | None = None
    commit_message_first_line: str
    commit_message_full: str
    commit_author_name: str
    commit_author_email: str
    commit_committed_at: str
    commit_repository: str
    commit_branch: str
    commit_parent_shas: list[str]
    commit_files_changed_count: int
    commit_session_id: str
    references: list[GovernanceEdgeIn] | None = None


class CommitPatchIn(_Base):
    commit_message_first_line: str | None = None
    commit_message_full: str | None = None
    commit_author_name: str | None = None
    commit_author_email: str | None = None
    commit_committed_at: str | None = None
    commit_repository: str | None = None
    commit_branch: str | None = None
    commit_parent_shas: list[str] | None = None
    commit_files_changed_count: int | None = None
    commit_session_id: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class DepositEventEdgeIn(_Base):
    """An outbound edge on a deposit_event POST (source is the new event)."""

    target_type: str
    target_id: str
    relationship: str


class DepositEventCreateIn(_Base):
    deposit_event_title: str
    deposit_event_description: str
    deposit_event_outcome: str
    deposit_event_records_summary: dict[str, Any]
    deposit_event_apply_context: dict[str, Any]
    deposit_event_log_file_path: str
    # WTK-089 kind discriminator; defaults server-side to the close-out
    # apply. The audit deposit path posts ``audit_deposit``.
    deposit_event_kind: str | None = None
    deposit_event_error_info: dict[str, Any] | None = None
    deposit_event_identifier: str | None = None
    references: list[DepositEventEdgeIn] | None = None
    # When the parent edge targets a close_out_payload that doesn't yet
    # exist, the access layer lazy-creates it; this lets the apply script
    # pass the real payload file path so the lazy COP's file_path points
    # at the right artifact (PRD §3.5).
    target_file_path: str | None = None


class UtilizationEvidenceCreateIn(_Base):
    """POST /utilization-evidence body (WTK-088 §4.5).

    Unprefixed key names — the repository kwargs and the wire shape the
    WTK-090 deposit transform posts. All metric columns are optional:
    evidence is shape-heterogeneous, and a schema-only deposit
    legitimately writes structural facts only. Datetimes travel as ISO
    strings; the access layer coerces and validates."""

    subject_type: str
    subject_identifier: str
    profiled_at: str
    source_label: str
    deposit_event_identifier: str | None = None
    catalog_class: str | None = None
    record_count: int | None = None
    last_record_created_at: str | None = None
    populated_count: int | None = None
    population_rate: float | None = None
    last_populated_at: str | None = None
    distinct_value_count: int | None = None
    declared_option_count: int | None = None
    used_option_count: int | None = None
    detail: dict[str, Any] | None = None
