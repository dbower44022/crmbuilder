"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError

import crmbuilder_v2
from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    ClassificationTransitionError,
    InvalidDomainReferenceError,
    SelectedCandidateConflictError,
    StatusTransitionError,
)
from crmbuilder_v2.access.meta_db import bootstrap_meta_db, init_meta_db_pool
from crmbuilder_v2.api.errors import (
    access_layer_handler,
    classification_transition_handler,
    engagement_export_dir_handler,
    invalid_domain_reference_handler,
    request_validation_handler,
    selected_candidate_conflict_handler,
    status_transition_handler,
)
from crmbuilder_v2.api.routers import (
    admin,
    catalog,
    charter,
    crm_candidates,
    decisions,
    domains,
    engagements,
    entities,
    health,
    orientation,
    planning_items,
    processes,
    references,
    risks,
    sessions,
    status,
    topics,
)
from crmbuilder_v2.migration.meta_alembic import run_meta_migrations
from crmbuilder_v2.runtime.exceptions import EngagementExportDirError


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
    app.add_exception_handler(AccessLayerError, access_layer_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    # Export-dir write-gate failures (multi-tenancy routing fix). Distinct
    # exception hierarchy from AccessLayerError, so registration order
    # relative to the handlers above does not matter.
    app.add_exception_handler(
        EngagementExportDirError, engagement_export_dir_handler
    )

    # v0.5 slice A: apply meta-DB Alembic chain (idempotent; no-op if
    # already at head) and initialise the meta-DB connection pool
    # alongside the per-engagement pool. The two pools are independent;
    # routing is by FastAPI dependency.
    try:
        run_meta_migrations()
    except Exception:  # pragma: no cover - logged inside helper
        # Surface the failure but do not prevent app construction; the
        # meta DB may be created later (e.g., dogfood migration runs
        # at first launch from the desktop side).
        pass
    # v0.5 slice A follow-up: ensure the meta-DB file exists with the
    # current ``MetaBase`` schema before any request routes against it.
    # Belt-and-braces with ``run_meta_migrations()`` above: Alembic
    # applies the chain on a present-or-newly-created file, and this
    # ``create_all()`` covers the fresh-install case where Alembic
    # silently fails or the file is materialised lazily by the engine.
    # ``create_all(checkfirst=True)`` is not atomic on SQLite, so the
    # narrow ``OperationalError`` catch absorbs the benign "table
    # engagements already exists" raised when concurrent ``create_app``
    # calls (the per-thread ``TestClient`` fixtures in the concurrent
    # POST tests, eight at a time) race past each other's ``has_table``
    # check — the loser observes a schema the winner just created.
    try:
        bootstrap_meta_db()
    except OperationalError:
        pass
    init_meta_db_pool()

    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(engagements.router)
    app.include_router(charter.router)
    app.include_router(status.router)
    app.include_router(decisions.router)
    app.include_router(sessions.router)
    app.include_router(risks.router)
    app.include_router(planning_items.router)
    app.include_router(topics.router)
    app.include_router(domains.router)
    app.include_router(entities.router)
    app.include_router(processes.router)
    app.include_router(crm_candidates.router)
    app.include_router(references.router)
    app.include_router(orientation.router)
    app.include_router(catalog.router)

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root():
        return {
            "name": "crmbuilder-v2",
            "version": crmbuilder_v2.__version__,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app
