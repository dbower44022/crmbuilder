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


class ClassificationTransitionError(AccessLayerError):
    """A classification change that the lifecycle map disallows.

    The ``process`` equivalent of :class:`StatusTransitionError` —
    ``process`` has no status field, so its lifecycle gate lives on
    ``process_classification`` instead. Carries the offending
    ``from``/``to`` pair. The API layer renders this as HTTP 422 with
    the dedicated body shape
    ``{"error": "invalid_classification_transition", "from": ..., "to": ...}``
    (``process.md`` section 3.5.3) — not the standard v2 envelope.
    """

    http_status = 422
    code = "invalid_classification_transition"

    def __init__(self, from_classification: str, to_classification: str):
        self.from_classification = from_classification
        self.to_classification = to_classification
        super().__init__(
            "invalid classification transition: "
            f"{from_classification!r} -> {to_classification!r}"
        )


class InvalidDomainReferenceError(AccessLayerError):
    """A ``process_domain_identifier`` FK that does not resolve to a live domain.

    Raised by the ``process`` repository when a create or update
    references a ``DOM-NNN`` that does not exist or is soft-deleted. The
    API layer renders this as HTTP 422 with the dedicated body shape
    ``{"error": "invalid_domain_reference", "domain_identifier": ...}``
    (``process.md`` section 3.5.4) — not the standard v2 envelope.
    """

    http_status = 422
    code = "invalid_domain_reference"

    def __init__(self, domain_identifier: str):
        self.domain_identifier = domain_identifier
        super().__init__(
            f"invalid domain reference: {domain_identifier!r}"
        )


class SelectedCandidateConflictError(AccessLayerError):
    """A second live ``crm_candidate`` record cannot hold ``selected``.

    Raised by the ``crm_candidate`` repository on POST, PATCH/PUT, or
    POST ``/restore`` operations that would result in two live (non
    soft-deleted) records holding ``crm_candidate_status = 'selected'``.
    Carries the identifier of the already-selected record. The API
    layer renders this as HTTP 422 with the dedicated body shape
    ``{"error": "selected_candidate_already_exists", "existing": "CRM-NNN"}``
    (``crm_candidate.md`` section 3.4.3) — not the standard v2 envelope.
    """

    http_status = 422
    code = "selected_candidate_already_exists"

    def __init__(self, existing_identifier: str):
        self.existing_identifier = existing_identifier
        super().__init__(
            "another crm_candidate is already selected: "
            f"{existing_identifier!r}"
        )


class CompletedStatusRequiresCompletionFieldsError(AccessLayerError):
    """A ``manual_config`` transition into ``completed`` is missing one
    or both completion fields.

    Raised by the ``manual_config`` repository on POST, PATCH/PUT
    operations that would result in ``manual_config_status =
    'completed'`` without both ``manual_config_completed_at`` and
    ``manual_config_completed_by`` populated in the same write. Carries
    the list of missing field names. The API layer renders this as HTTP
    422 with the dedicated body shape per ``manual_config.md`` §3.5.3 —
    ``{"data": null, "meta": {}, "errors": [{"error":
    "completed_status_requires_completion_fields", "missing": [...]}]}``
    — keeping the v2 envelope so clients can introspect a uniform error
    shape across endpoints.

    ``completed_at`` is server-defaultable to ``now()`` when omitted on
    transition into ``completed``; only ``completed_by`` (the operator
    identity) is rejected when missing.
    """

    http_status = 422
    code = "completed_status_requires_completion_fields"

    def __init__(self, missing: list[str]):
        self.missing = list(missing)
        super().__init__(
            "manual_config status 'completed' requires completion "
            f"fields: missing={self.missing}"
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
