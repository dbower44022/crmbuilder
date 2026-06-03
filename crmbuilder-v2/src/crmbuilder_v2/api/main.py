"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

import crmbuilder_v2
from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    ClassificationTransitionError,
    CompletedStatusRequiresCompletionFieldsError,
    InvalidDomainReferenceError,
    SelectedCandidateConflictError,
    StatusTransitionError,
)
from crmbuilder_v2.api.errors import (
    access_layer_handler,
    classification_transition_handler,
    completed_status_requires_completion_fields_handler,
    invalid_domain_reference_handler,
    request_validation_handler,
    selected_candidate_conflict_handler,
    status_transition_handler,
)
from crmbuilder_v2.api.routers import (
    admin,
    catalog,
    charter,
    close_out_payloads,
    commits,
    conversations,
    crm_candidates,
    decisions,
    deposit_events,
    domains,
    engagements,
    entities,
    field,
    health,
    identifiers,
    manual_configs,
    orchestration,
    orientation,
    persona,
    planning_items,
    processes,
    projects,
    reference_books,
    references,
    requirements,
    risks,
    sessions,
    status,
    test_specs,
    topics,
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
    app.add_exception_handler(AccessLayerError, access_layer_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)

    app.include_router(health.router)
    app.include_router(admin.router)
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
    app.include_router(field.router)
    # PI-004 methodology cohort (v0.5+).
    app.include_router(requirements.router)
    app.include_router(manual_configs.router)
    app.include_router(test_specs.router)
    app.include_router(references.router)
    app.include_router(orientation.router)
    app.include_router(catalog.router)
    # Governance entities (UI v0.7), in project order.
    app.include_router(projects.router)
    app.include_router(workstreams.router)
    app.include_router(work_tasks.router)
    app.include_router(conversations.router)
    app.include_router(reference_books.router)
    app.include_router(work_tickets.router)
    app.include_router(close_out_payloads.router)
    app.include_router(deposit_events.router)
    app.include_router(commits.router)

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root():
        return {
            "name": "crmbuilder-v2",
            "version": crmbuilder_v2.__version__,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app
