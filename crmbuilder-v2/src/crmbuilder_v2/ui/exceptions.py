"""Typed exceptions for the storage HTTP client.

Wired in slice C. See PRD section 4.11 for the HTTP-status to exception
mapping. The connection-failure class is named
``StorageConnectionError`` (not ``ConnectionError``) to avoid shadowing
the built-in.

Hierarchy:

* ``StorageClientError`` (abstract base)
    * ``StorageConnectionError`` — network-level failure
    * ``ServerError`` — 5xx (and unexpected 4xx)
    * ``RequestShapeError`` — 422
    * ``NotFoundError`` — 404
    * ``ConflictError`` — 409
    * ``ValidationError`` — 400
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class StorageClientError(Exception):
    """Abstract base for all storage-client errors."""

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class StorageConnectionError(StorageClientError):
    """Network-level failure reaching the storage API.

    Wraps ``httpx.ConnectError``, ``httpx.ConnectTimeout``,
    ``httpx.ReadTimeout``, ``httpx.NetworkError``, etc. The original
    exception (if any) is attached as ``original``.
    """

    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.original = original


class ServerError(StorageClientError):
    """5xx response, or unexpected non-2xx status outside the documented matrix."""

    def __init__(
        self,
        status_code: int,
        errors: list[dict[str, Any]],
        message: str,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors


class RequestShapeError(StorageClientError):
    """422 — FastAPI request-validation error (programmer error in the client)."""

    def __init__(
        self,
        errors: list[dict[str, Any]],
        message: str,
    ):
        super().__init__(message)
        self.errors = errors


class NotFoundError(StorageClientError):
    """404 — requested entity does not exist."""

    def __init__(
        self,
        errors: list[dict[str, Any]],
        message: str,
    ):
        super().__init__(message)
        self.errors = errors


class ConflictError(StorageClientError):
    """409 — identifier collision or state conflict."""

    def __init__(
        self,
        errors: list[dict[str, Any]],
        message: str,
    ):
        super().__init__(message)
        self.errors = errors


class ValidationError(StorageClientError):
    """400 — domain validation failure with per-field error details."""

    def __init__(
        self,
        errors: list[dict[str, Any]],
        message: str,
    ):
        super().__init__(message)
        self.errors = errors

    def field_errors(self) -> dict[str, str]:
        """Return ``{field_name: first_message}`` for inline-on-field display.

        Errors without a ``field`` key are omitted; only the first message
        encountered for each field is kept.
        """
        out: dict[str, str] = {}
        for err in self.errors:
            field = err.get("field")
            if not field:
                continue
            if field not in out:
                out[field] = err.get("message", "")
        return out


def _parse_envelope_errors(resp: httpx.Response) -> list[dict[str, Any]]:
    """Best-effort parse of the ``errors`` array from a response envelope.

    Returns an empty list if the body is unparseable or doesn't have an
    ``errors`` array.
    """
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(body, dict):
        return []
    errors = body.get("errors")
    if not isinstance(errors, list):
        return []
    return [e for e in errors if isinstance(e, dict)]


def _first_message(errors: list[dict[str, Any]], fallback: str) -> str:
    for err in errors:
        msg = err.get("message")
        if msg:
            return str(msg)
    return fallback


def from_response(resp: httpx.Response) -> StorageClientError:
    """Map a non-2xx httpx response to the appropriate typed exception.

    Mirrors ``crmbuilder_v2.api.errors``. Falls back to ``ServerError``
    for unrecognized statuses or unparseable bodies.
    """
    status = resp.status_code
    errors = _parse_envelope_errors(resp)

    if status == 400:
        return ValidationError(
            errors=errors,
            message=_first_message(errors, "Validation failed"),
        )
    if status == 404:
        return NotFoundError(
            errors=errors,
            message=_first_message(errors, "Not found"),
        )
    if status == 409:
        return ConflictError(
            errors=errors,
            message=_first_message(errors, "Conflict"),
        )
    if status == 422:
        return RequestShapeError(
            errors=errors,
            message=_first_message(errors, "Request validation error"),
        )
    if 500 <= status < 600:
        return ServerError(
            status_code=status,
            errors=errors,
            message=_first_message(errors, f"Server error (status {status})"),
        )
    # Catchall for unexpected non-2xx (e.g., 401, 403, 418).
    return ServerError(
        status_code=status,
        errors=errors,
        message=_first_message(errors, f"Unexpected response (status {status})"),
    )
