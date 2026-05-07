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
