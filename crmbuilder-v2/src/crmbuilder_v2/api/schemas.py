"""Pydantic v2 request and response schemas."""

from __future__ import annotations

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


# ---------- Sessions ----------


class SessionCreateIn(_Base):
    """POST /sessions body. ``identifier`` is server-assigned when
    omitted (PI-002, option C of SES-010)."""

    identifier: str | None = None
    title: str
    session_date: str
    status: str
    conversation_reference: str = ""
    topics_covered: str = ""
    summary: str = ""
    artifacts_produced: str = ""
    in_flight_at_end: str = ""


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


class PlanningItemUpdateIn(_Base):
    title: str | None = None
    item_type: str | None = None
    description: str | None = None
    status: str | None = None
    resolution_reference: str | None = None


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
    ``entity_scopes_to_domain`` relationship kind."""

    entity_name: str
    entity_description: str
    entity_notes: str | None = None
    entity_status: str | None = None
    entity_identifier: str | None = None


class EntityReplaceIn(_Base):
    """PUT /entities/{identifier} body — full record replace.

    ``entity_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422)."""

    entity_identifier: str | None = None
    entity_name: str
    entity_description: str
    entity_notes: str | None = None
    entity_status: str


class EntityPatchIn(_Base):
    """PATCH /entities/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``entity_notes: null`` (clear the field) is distinguished
    from an omitted ``entity_notes`` (leave unchanged)."""

    entity_name: str | None = None
    entity_description: str | None = None
    entity_notes: str | None = None
    entity_status: str | None = None


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


# ---------- Processes (methodology entity, UI v0.4 slice D) ----------


class ProcessCreateIn(_Base):
    """POST /processes body. ``process_identifier`` is server-assigned
    when omitted; ``process_classification`` defaults to ``unclassified``
    server-side. ``process_domain_identifier`` is a required scalar FK
    validated against live ``domain`` records.

    Handoffs are NOT inlined here — per ``process.md`` section 3.5.5
    they attach via separate ``POST /references`` calls with the
    ``process_hands_off_to_process`` relationship kind."""

    process_name: str
    process_domain_identifier: str
    process_purpose: str
    process_classification: str | None = None
    process_classification_rationale: str | None = None
    process_notes: str | None = None
    process_identifier: str | None = None


class ProcessReplaceIn(_Base):
    """PUT /processes/{identifier} body — full record replace.

    ``process_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422)."""

    process_identifier: str | None = None
    process_name: str
    process_domain_identifier: str
    process_purpose: str
    process_classification: str
    process_classification_rationale: str | None = None
    process_notes: str | None = None


class ProcessPatchIn(_Base):
    """PATCH /processes/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``process_notes: null`` (clear the field) is distinguished
    from an omitted ``process_notes`` (leave unchanged)."""

    process_name: str | None = None
    process_domain_identifier: str | None = None
    process_purpose: str | None = None
    process_classification: str | None = None
    process_classification_rationale: str | None = None
    process_notes: str | None = None


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


# ---------- Engagements (methodology entity, UI v0.5 slice B) ----------


class EngagementCreateIn(_Base):
    """POST /engagements body. ``engagement_identifier`` is server-assigned
    when omitted; ``engagement_status`` defaults to ``active`` server-side.
    ``engagement_export_dir`` is optional and validated as an existing
    writable absolute directory when provided."""

    engagement_code: str
    engagement_name: str
    engagement_purpose: str
    engagement_status: str | None = None
    engagement_export_dir: str | None = None
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
    engagement_export_dir: str | None = None


class EngagementPatchIn(_Base):
    """PATCH /engagements/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``engagement_export_dir: null`` (clear the field) is
    distinguished from an omitted ``engagement_export_dir`` (leave
    unchanged). ``engagement_code`` is rejected if present and
    different from the current row."""

    engagement_name: str | None = None
    engagement_purpose: str | None = None
    engagement_status: str | None = None
    engagement_export_dir: str | None = None
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


class WorkstreamCreateIn(_Base):
    workstream_name: str
    workstream_purpose: str
    workstream_description: str
    workstream_notes: str | None = None
    workstream_status: str | None = None
    workstream_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class WorkstreamReplaceIn(_Base):
    workstream_identifier: str | None = None
    workstream_name: str
    workstream_purpose: str
    workstream_description: str
    workstream_notes: str | None = None
    workstream_status: str
    references: list[GovernanceEdgeIn] | None = None


class WorkstreamPatchIn(_Base):
    workstream_name: str | None = None
    workstream_purpose: str | None = None
    workstream_description: str | None = None
    workstream_notes: str | None = None
    workstream_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


class ConversationCreateIn(_Base):
    conversation_title: str
    conversation_purpose: str
    conversation_description: str
    conversation_notes: str | None = None
    conversation_status: str | None = None
    conversation_identifier: str | None = None
    references: list[GovernanceEdgeIn] | None = None
    timestamps: dict[str, Any] | None = None


class ConversationReplaceIn(_Base):
    conversation_identifier: str | None = None
    conversation_title: str
    conversation_purpose: str
    conversation_description: str
    conversation_notes: str | None = None
    conversation_status: str
    references: list[GovernanceEdgeIn] | None = None


class ConversationPatchIn(_Base):
    conversation_title: str | None = None
    conversation_purpose: str | None = None
    conversation_description: str | None = None
    conversation_notes: str | None = None
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
    commit_conversation_id: str
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
    commit_conversation_id: str
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
    commit_conversation_id: str | None = None
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
    deposit_event_error_info: dict[str, Any] | None = None
    deposit_event_identifier: str | None = None
    references: list[DepositEventEdgeIn] | None = None
    # When the parent edge targets a close_out_payload that doesn't yet
    # exist, the access layer lazy-creates it; this lets the apply script
    # pass the real payload file path so the lazy COP's file_path points
    # at the right artifact (PRD §3.5).
    target_file_path: str | None = None
