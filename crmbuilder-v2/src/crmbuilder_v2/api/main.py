"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

import crmbuilder_v2
from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    ClassificationTransitionError,
    CompletedStatusRequiresCompletionFieldsError,
    DuplicateMappingForCandidateError,
    InvalidDomainReferenceError,
    SelectedCandidateConflictError,
    StatusTransitionError,
)
from crmbuilder_v2.access.rbac import PermissionDenied
from crmbuilder_v2.api.errors import (
    access_layer_handler,
    classification_transition_handler,
    completed_status_requires_completion_fields_handler,
    duplicate_mapping_for_candidate_handler,
    invalid_domain_reference_handler,
    permission_denied_handler,
    request_validation_handler,
    selected_candidate_conflict_handler,
    status_transition_handler,
)
from crmbuilder_v2.api.principal_middleware import PrincipalMiddleware
from crmbuilder_v2.api.routers import (
    admin,
    artifact_versions,
    association_mappings,
    associations,
    automations,
    catalog,
    charter,
    close_out_payloads,
    commits,
    conversations,
    cost,
    coverage,
    crm_candidates,
    decisions,
    dedup_rules,
    deposit_events,
    domains,
    engagements,
    engine_overrides,
    entities,
    field,
    field_mappings,
    field_permission_rules,
    field_visibility_rules,
    filtered_tabs,
    findings,
    health,
    identifiers,
    instances,
    layouts,
    locks,
    manual_configs,
    mapping_candidates,
    message_templates,
    migration_mappings,
    orchestration,
    orientation,
    participant,
    persona,
    planning_items,
    principals,
    processes,
    projects,
    publish_runs,
    reconcile,
    reconciliation_conflicts,
    reference_books,
    references,
    registry,
    release_runs,
    releases,
    requirements,
    review,
    risks,
    roles,
    rules,
    sessions,
    source_mapping_targets,
    source_mappings,
    status,
    teams,
    terms,
    test_specs,
    topics,
    utilization_evidence,
    value_mappings,
    views,
    work_tasks,
    work_tickets,
    workstreams,
)
from crmbuilder_v2.api.scope_middleware import EngagementScopeMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="CRMBuilder v2 — Storage System",
        version=crmbuilder_v2.__version__,
        description=(
            "REST API over the v0.1 storage system. Provides CRUD for "
            "project-management entities (charter, status, decisions, "
            "sessions, risks, planning items, topics) and the universal "
            "references table per DEC-006."
        ),
    )

    # PI-123 Slice 2c / PI-β D5: resolve the active engagement per request from
    # the ``X-Engagement`` header and set it on the engagement-scope ContextVar
    # so the row-level filter/stamp scope every query and insert. Gated
    # internally by Settings.engagement_scoping_enabled. A pure-ASGI middleware
    # so the ContextVar set here reaches the sync route handler's threadpool
    # copy deterministically.
    app.add_middleware(EngagementScopeMiddleware)

    # PI-γ: resolve the authenticated principal per request from the
    # ``Authorization: Bearer`` header and set it on the principal-scope
    # ContextVar. Added AFTER the engagement middleware so it wraps it (the
    # last-added middleware is outermost), making the principal available when
    # the engagement selection is validated against it. Gated internally by
    # Settings.principal_auth_enabled — off ⇒ a synthetic default-owner, so the
    # localhost flow is unchanged.
    app.add_middleware(PrincipalMiddleware)

    # The three dedicated-body access-layer errors must register before
    # the AccessLayerError base so Starlette routes each to its own
    # handler by exact class match rather than falling through to the
    # envelope handler.
    app.add_exception_handler(
        StatusTransitionError, status_transition_handler
    )
    app.add_exception_handler(
        ClassificationTransitionError, classification_transition_handler
    )
    app.add_exception_handler(
        InvalidDomainReferenceError, invalid_domain_reference_handler
    )
    app.add_exception_handler(
        SelectedCandidateConflictError,
        selected_candidate_conflict_handler,
    )
    app.add_exception_handler(
        CompletedStatusRequiresCompletionFieldsError,
        completed_status_requires_completion_fields_handler,
    )
    app.add_exception_handler(
        DuplicateMappingForCandidateError,
        duplicate_mapping_for_candidate_handler,
    )
    app.add_exception_handler(AccessLayerError, access_layer_handler)
    app.add_exception_handler(PermissionDenied, permission_denied_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)

    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(principals.router)
    app.include_router(engagements.router)
    app.include_router(charter.router)
    app.include_router(status.router)
    app.include_router(decisions.router)
    app.include_router(sessions.router)
    app.include_router(risks.router)
    app.include_router(planning_items.router)
    app.include_router(orchestration.router)
    app.include_router(identifiers.router)
    app.include_router(topics.router)
    app.include_router(domains.router)
    app.include_router(entities.router)
    app.include_router(processes.router)
    app.include_router(crm_candidates.router)
    app.include_router(persona.router)
    app.include_router(participant.router)
    app.include_router(field.router)
    # PI-004 methodology cohort (v0.5+).
    app.include_router(requirements.router)
    app.include_router(manual_configs.router)
    app.include_router(test_specs.router)
    app.include_router(references.router)
    # Requirements-provenance Phase 3 — no-orphan-capability coverage report.
    app.include_router(coverage.router)
    app.include_router(cost.router)
    # Requirements-provenance Phase 6 — review surface data layer.
    app.include_router(review.router)
    app.include_router(orientation.router)
    app.include_router(catalog.router)
    # Governance entities (UI v0.7), in project order.
    app.include_router(projects.router)
    app.include_router(releases.router)
    app.include_router(release_runs.router)
    app.include_router(release_runs.release_scoped_router)
    app.include_router(artifact_versions.router)
    app.include_router(reconcile.router)
    app.include_router(reconciliation_conflicts.router)
    app.include_router(locks.router)
    app.include_router(workstreams.router)
    app.include_router(work_tasks.router)
    app.include_router(findings.router)
    app.include_router(conversations.router)
    app.include_router(reference_books.router)
    app.include_router(work_tickets.router)
    app.include_router(close_out_payloads.router)
    app.include_router(deposit_events.router)
    app.include_router(utilization_evidence.router)
    app.include_router(migration_mappings.router)
    app.include_router(associations.router)
    app.include_router(engine_overrides.router)
    app.include_router(rules.router)
    app.include_router(field_permission_rules.router)
    app.include_router(field_visibility_rules.router)
    app.include_router(views.router)
    app.include_router(automations.router)
    app.include_router(dedup_rules.router)
    app.include_router(message_templates.router)
    app.include_router(commits.router)
    app.include_router(instances.router)
    app.include_router(publish_runs.router)
    app.include_router(layouts.router)
    app.include_router(filtered_tabs.router)
    app.include_router(roles.router)
    app.include_router(teams.router)
    # Source-mapping model (PI-255).
    app.include_router(source_mappings.router)
    app.include_router(field_mappings.router)
    app.include_router(association_mappings.router)
    app.include_router(source_mapping_targets.router)
    app.include_router(value_mappings.router)
    app.include_router(mapping_candidates.router)
    # Agent Profile Registry (PI-122).
    app.include_router(registry.agent_profiles_router)
    app.include_router(registry.skills_router)
    app.include_router(registry.governance_rules_router)
    app.include_router(registry.learnings_router)
    # Glossary terms (PI-061).
    app.include_router(terms.router)

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root():
        return {
            "name": "crmbuilder-v2",
            "version": crmbuilder_v2.__version__,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app
