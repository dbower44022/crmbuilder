"""Structured access-layer exceptions.

The API layer maps these to HTTP responses (see ``api/errors.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldError:
    field: str
    code: str
    message: str


class AccessLayerError(Exception):
    """Base class for access-layer exceptions."""

    http_status: int = 500
    code: str = "internal_error"

    def to_dict(self) -> dict:
        return {"code": self.code, "message": str(self)}


class ValidationError(AccessLayerError):
    """One or more inputs failed validation."""

    http_status = 400
    code = "validation_error"

    def __init__(self, errors: list[FieldError]):
        self.errors = errors
        super().__init__(
            "; ".join(f"{e.field}: {e.message}" for e in errors) or "validation failed"
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": str(self),
            "errors": [e.__dict__ for e in self.errors],
        }


class UnprocessableError(ValidationError):
    """Validation failure that maps to HTTP 422 rather than 400.

    Used by the methodology entity types (UI v0.4) for input-validation
    failures the spec assigns to 422: identifier-format violations,
    case-insensitive name-uniqueness collisions, status-enum
    violations, PUT identifier/path mismatches, and restore-on-a-live
    record. ``isinstance(exc, ValidationError)`` still holds, so the
    API error handler renders it with the same per-field envelope as a
    400; only the HTTP status differs.
    """

    http_status = 422


class StatusTransitionError(AccessLayerError):
    """A status change that the entity's lifecycle map disallows.

    Carries the offending ``from``/``to`` pair. The API layer renders
    this as HTTP 422 with the dedicated body shape
    ``{"error": "invalid_status_transition", "from": ..., "to": ...}``
    (``domain.md`` section 3.5.3) — not the standard v2 envelope.
    """

    http_status = 422
    code = "invalid_status_transition"

    def __init__(self, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"invalid status transition: {from_status!r} -> {to_status!r}"
        )


class NotFoundError(AccessLayerError):
    """Requested entity does not exist."""

    http_status = 404
    code = "not_found"

    def __init__(self, entity_type: str, identifier: str):
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} '{identifier}' not found")


class ConflictError(AccessLayerError):
    """Identifier collision or other state conflict."""

    http_status = 409
    code = "conflict"


@dataclass
class Operation:
    """Result of an access-layer mutation, returned to callers."""

    entity_type: str
    identifier: str
    operation: str  # insert | update | delete
    record: dict | None = None
    metadata: dict = field(default_factory=dict)
