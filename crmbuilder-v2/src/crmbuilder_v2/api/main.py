"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    StatusTransitionError,
)
from crmbuilder_v2.api.errors import (
    access_layer_handler,
    request_validation_handler,
    status_transition_handler,
)
from crmbuilder_v2.api.routers import (
    catalog,
    charter,
    decisions,
    domains,
    entities,
    health,
    orientation,
    planning_items,
    references,
    risks,
    sessions,
    status,
    topics,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="CRMBuilder v2 — Storage System",
        version="0.1.0",
        description=(
            "REST API over the v0.1 storage system. Provides CRUD for "
            "project-management entities (charter, status, decisions, "
            "sessions, risks, planning items, topics) and the universal "
            "references table per DEC-006."
        ),
    )

    # StatusTransitionError must register before the AccessLayerError
    # base so Starlette routes it to the dedicated handler by exact
    # class match rather than falling through to the envelope handler.
    app.add_exception_handler(
        StatusTransitionError, status_transition_handler
    )
    app.add_exception_handler(AccessLayerError, access_layer_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)

    app.include_router(health.router)
    app.include_router(charter.router)
    app.include_router(status.router)
    app.include_router(decisions.router)
    app.include_router(sessions.router)
    app.include_router(risks.router)
    app.include_router(planning_items.router)
    app.include_router(topics.router)
    app.include_router(domains.router)
    app.include_router(entities.router)
    app.include_router(references.router)
    app.include_router(orientation.router)
    app.include_router(catalog.router)

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root():
        return {
            "name": "crmbuilder-v2",
            "version": "0.1.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app
