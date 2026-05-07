"""Map access-layer exceptions to HTTP responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from crmbuilder_v2.access.exceptions import (
    AccessLayerError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.api.envelope import err


def _status_for(exc: AccessLayerError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, ValidationError):
        return 400
    return 500


def access_layer_handler(_request: Request, exc: AccessLayerError) -> JSONResponse:
    status = _status_for(exc)
    if isinstance(exc, ValidationError):
        body = err(
            [{"code": e.code, "field": e.field, "message": e.message} for e in exc.errors]
        )
    else:
        body = err([exc.to_dict()])
    return JSONResponse(status_code=status, content=body)


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
