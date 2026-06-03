"""Map access-layer exceptions to HTTP responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    ClassificationTransitionError,
    CompletedStatusRequiresCompletionFieldsError,
    InvalidDomainReferenceError,
    SelectedCandidateConflictError,
    StatusTransitionError,
    ValidationError,
)
from crmbuilder_v2.api.envelope import err


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


def completed_status_requires_completion_fields_handler(
    _request: Request, exc: CompletedStatusRequiresCompletionFieldsError
) -> JSONResponse:
    """Render a ``manual_config`` cross-field invariant violation.

    Uses the v2 envelope shape (``{"data": null, "meta": {}, "errors":
    [...]}``) per ``manual_config.md`` §3.5.3 with the dedicated
    ``completed_status_requires_completion_fields`` error code and the
    ``missing`` list. Registered as a more-specific handler than
    :func:`access_layer_handler` so Starlette routes
    ``CompletedStatusRequiresCompletionFieldsError`` here by exact
    class match.
    """
    body = err(
        [
            {
                "error": "completed_status_requires_completion_fields",
                "missing": exc.missing,
            }
        ]
    )
    return JSONResponse(status_code=exc.http_status, content=body)


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
