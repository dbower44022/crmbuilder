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


class PlanningItemUpdateIn(_Base):
    title: str | None = None
    item_type: str | None = None
    description: str | None = None
    status: str | None = None
    resolution_reference: str | None = None
    executive_summary: str | None = None  # PI-074
    area: list[str] | None = None  # PI-076


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


class EntityReplaceIn(_Base):
    """PUT /entities/{identifier} body — full record replace.

    ``entity_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422). ``entity_kind`` is replaced
    wholesale (omitted-from-body deserialises to ``None`` and clears
    the field); operators wanting partial update should use PATCH."""

    entity_identifier: str | None = None
    entity_name: str
    entity_description: str
    entity_notes: str | None = None
    entity_status: str
    entity_kind: str | None = None


class EntityPatchIn(_Base):
    """PATCH /entities/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``entity_notes: null`` (clear the field) is distinguished
    from an omitted ``entity_notes`` (leave unchanged). Same semantics
    apply to ``entity_kind`` (PI-010 / DEC-292): null clears, omitted
    leaves unchanged."""

    entity_name: str | None = None
    entity_description: str | None = None
    entity_notes: str | None = None
    entity_status: str | None = None
    entity_kind: str | None = None


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


class FieldCreateIn(_Base):
    """POST /fields body.

    ``field_identifier`` is server-assigned when omitted;
    ``field_status`` defaults to ``candidate`` server-side;
    ``field_required`` defaults to ``False`` server-side.
    ``field_belongs_to_entity_identifier`` is REQUIRED — the access
    layer creates the field row, the ``field_belongs_to_entity`` edge,
    and the change-log emit in one transaction per ``field.md`` §3.5.4.
    This is the one deviation from the cross-spec decomposed-references
    default."""

    field_name: str
    field_description: str
    field_type: str
    field_belongs_to_entity_identifier: str
    field_required: bool | None = None
    field_notes: str | None = None
    field_status: str | None = None
    field_identifier: str | None = None


class FieldReplaceIn(_Base):
    """PUT /fields/{identifier} body — full record replace.

    Does NOT accept ``field_belongs_to_entity_identifier`` — re-parenting
    requires explicit edge management per ``field.md`` §3.5.4 (DELETE
    the old edge, POST the new edge). PI-053 tracks the future
    convenience endpoint."""

    field_identifier: str | None = None
    field_name: str
    field_description: str
    field_type: str
    field_required: bool
    field_notes: str | None = None
    field_status: str


class FieldPatchIn(_Base):
    """PATCH /fields/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``field_notes: null`` (clear) is distinguished from an
    omitted ``field_notes`` (leave unchanged). Does NOT accept
    ``field_belongs_to_entity_identifier`` for the same reason as PUT."""

    field_name: str | None = None
    field_description: str | None = None
    field_type: str | None = None
    field_required: bool | None = None
    field_notes: str | None = None
    field_status: str | None = None


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


class ProjectCreateIn(_Base):
    project_name: str
    project_purpose: str
    project_description: str
    project_notes: str | None = None
    project_status: str | None = None
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
    references: list[GovernanceEdgeIn] | None = None


class ProjectPatchIn(_Base):
    project_name: str | None = None
    project_purpose: str | None = None
    project_description: str | None = None
    project_notes: str | None = None
    project_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


# --- Workstream (delivery phase, PI-112 Phase 4) ---------------------------
class WorkstreamCreateIn(_Base):
    workstream_phase_type: str
    workstream_title: str
    workstream_description: str | None = None
    workstream_notes: str | None = None
    workstream_status: str | None = None
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
    references: list[GovernanceEdgeIn] | None = None


class WorkstreamPatchIn(_Base):
    workstream_phase_type: str | None = None
    workstream_title: str | None = None
    workstream_description: str | None = None
    workstream_notes: str | None = None
    workstream_status: str | None = None
    references: list[GovernanceEdgeIn] | None = None


# --- Work Task (single-area unit, PI-112 Phase 4b) -------------------------
class WorkTaskCreateIn(_Base):
    work_task_title: str
    work_task_area: str
    work_task_description: str | None = None
    work_task_notes: str | None = None
    work_task_status: str | None = None
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
    references: list[GovernanceEdgeIn] | None = None


class WorkTaskPatchIn(_Base):
    work_task_title: str | None = None
    work_task_area: str | None = None
    work_task_description: str | None = None
    work_task_notes: str | None = None
    work_task_status: str | None = None
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
    deposit_event_error_info: dict[str, Any] | None = None
    deposit_event_identifier: str | None = None
    references: list[DepositEventEdgeIn] | None = None
    # When the parent edge targets a close_out_payload that doesn't yet
    # exist, the access layer lazy-creates it; this lets the apply script
    # pass the real payload file path so the lazy COP's file_path points
    # at the right artifact (PRD §3.5).
    target_file_path: str | None = None
