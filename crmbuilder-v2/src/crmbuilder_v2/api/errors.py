"""Map access-layer exceptions to HTTP responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    ClassificationTransitionError,
    InvalidDomainReferenceError,
    SelectedCandidateConflictError,
    StatusTransitionError,
    ValidationError,
)
from crmbuilder_v2.api.envelope import err
from crmbuilder_v2.runtime.exceptions import (
    EngagementExportDirError,
    EngagementExportDirMissing,
    EngagementExportDirNotConfigured,
)


def _status_for(exc: AccessLayerError) -> int:
    """HTTP status for an access-layer exception.

    Every :class:`AccessLayerError` subclass carries an ``http_status``
    class attribute (404 for not-found, 409 for conflict, 400 for
    validation, 422 for the methodology-entity ``Unprocessable`` /
    ``StatusTransition`` variants, 500 for the bare base). Honouring it
    directly keeps this mapping single-sourced.
    """
    return exc.http_status


def access_layer_handler(_request: Request, exc: AccessLayerError) -> JSONResponse:
    status = _status_for(exc)
    if isinstance(exc, ValidationError):
        body = err(
            [{"code": e.code, "field": e.field, "message": e.message} for e in exc.errors]
        )
    else:
        body = err([exc.to_dict()])
    return JSONResponse(status_code=status, content=body)


def status_transition_handler(
    _request: Request, exc: StatusTransitionError
) -> JSONResponse:
    """Render a disallowed status transition.

    Uses the dedicated body shape from ``domain.md`` section 3.5.3 —
    ``{"error": "invalid_status_transition", "from": ..., "to": ...}`` —
    rather than the standard ``{data, meta, errors}`` envelope. Registered
    as a more-specific handler than :func:`access_layer_handler`, so
    Starlette routes ``StatusTransitionError`` here by exact class match.
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": "invalid_status_transition",
            "from": exc.from_status,
            "to": exc.to_status,
        },
    )


def classification_transition_handler(
    _request: Request, exc: ClassificationTransitionError
) -> JSONResponse:
    """Render a disallowed ``process_classification`` transition.

    Uses the dedicated body shape from ``process.md`` section 3.5.3 —
    ``{"error": "invalid_classification_transition", "from": ..., "to": ...}``
    — rather than the standard ``{data, meta, errors}`` envelope.
    Registered as a more-specific handler than
    :func:`access_layer_handler` so Starlette routes
    ``ClassificationTransitionError`` here by exact class match.
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": "invalid_classification_transition",
            "from": exc.from_classification,
            "to": exc.to_classification,
        },
    )


def invalid_domain_reference_handler(
    _request: Request, exc: InvalidDomainReferenceError
) -> JSONResponse:
    """Render a ``process_domain_identifier`` FK that does not resolve.

    Uses the dedicated body shape from ``process.md`` section 3.5.4 —
    ``{"error": "invalid_domain_reference", "domain_identifier": ...}`` —
    rather than the standard ``{data, meta, errors}`` envelope.
    Registered as a more-specific handler than
    :func:`access_layer_handler` so Starlette routes
    ``InvalidDomainReferenceError`` here by exact class match.
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": "invalid_domain_reference",
            "domain_identifier": exc.domain_identifier,
        },
    )


def selected_candidate_conflict_handler(
    _request: Request, exc: SelectedCandidateConflictError
) -> JSONResponse:
    """Render a singleton-``selected`` violation on ``crm_candidate``.

    Uses the dedicated body shape from ``crm_candidate.md`` section
    3.4.3 — ``{"error": "selected_candidate_already_exists",
    "existing": "CRM-NNN"}`` — rather than the standard
    ``{data, meta, errors}`` envelope. Registered as a more-specific
    handler than :func:`access_layer_handler` so Starlette routes
    ``SelectedCandidateConflictError`` here by exact class match.
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": "selected_candidate_already_exists",
            "existing": exc.existing_identifier,
        },
    )


#: Stable envelope error codes for the export-dir write-gate failures, so
#: the desktop UI can recognise them and offer the "Edit engagement…"
#: remediation rather than rendering a raw server error.
EXPORT_DIR_NOT_CONFIGURED_CODE = "engagement_export_dir_not_configured"
EXPORT_DIR_MISSING_CODE = "engagement_export_dir_missing"
EXPORT_DIR_ERROR_CODE = "engagement_export_dir_error"


def engagement_export_dir_handler(
    _request: Request, exc: EngagementExportDirError
) -> JSONResponse:
    """Render an export-dir write-gate failure as a 500 envelope.

    Multi-tenancy routing fix (slice A raises these from ``session_scope``
    / ``force_export`` / the catalog exporter; slice B registers this
    handler so the response carries the standard ``{data, meta, errors}``
    envelope with a stable code instead of FastAPI's bare 500). The DB
    write has already rolled back inside ``session_scope`` by the time the
    exception reaches here, and the export directory was not touched.
    """
    if isinstance(exc, EngagementExportDirNotConfigured):
        code = EXPORT_DIR_NOT_CONFIGURED_CODE
    elif isinstance(exc, EngagementExportDirMissing):
        code = EXPORT_DIR_MISSING_CODE
    else:
        code = EXPORT_DIR_ERROR_CODE
    body = err([{"code": code, "message": str(exc)}])
    return JSONResponse(status_code=500, content=body)


def request_validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = err(
        [
            {
                "code": "request_validation_error",
                "field": ".".join(str(p) for p in (e.get("loc") or [])),
                "message": e.get("msg", ""),
            }
            for e in exc.errors()
        ]
    )
    return JSONResponse(status_code=422, content=body)
