"""Deposit event repository — the sixth governance entity type (UI v0.7).

Per ``governance-schema-specs/deposit_event.md``. Born-terminal append-only:
the only write operation is :func:`create_deposit_event`; there is no update,
patch, delete, or restore. The POST is atomic — in one transaction it creates
the record, its outbound ``deposit_event_applies_close_out_payload`` parent
edge, its outbound ``deposit_event_wrote_record`` back-references, and (on
``outcome='success'`` against a ``ready`` close_out_payload) transitions that
payload to ``applied`` (the first-success-transitions semantics of DEC-158).

If the target close_out_payload identifier does not yet exist, the access
layer lazy-creates a minimal ``ready`` payload row so the apply path is
forward-compatible with both routine applies and backfill (PRD section 3.5).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import next_prefixed_identifier, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import CloseOutPayload, DepositEvent
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import references as references_repo
from crmbuilder_v2.access.vocab import DEPOSIT_EVENT_OUTCOMES

_ENTITY_TYPE = "deposit_event"
_IDENTIFIER_PREFIX = "DEP"
_IDENTIFIER_RE = re.compile(r"^DEP-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_APPLY_KIND = "deposit_event_applies_close_out_payload"
_WROTE_KIND = "deposit_event_wrote_record"


def _require_outcome(outcome: object) -> str:
    return gov.require_in(
        outcome, DEPOSIT_EVENT_OUTCOMES, field="deposit_event_outcome"
    )


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_deposit_events(
    session: Session, *, outcome: str | None = None
) -> list[dict]:
    stmt = select(DepositEvent).order_by(
        DepositEvent.deposit_event_identifier.desc()
    )
    if outcome is not None:
        stmt = stmt.where(DepositEvent.deposit_event_outcome == outcome)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_deposit_event(session: Session, identifier: str) -> dict | None:
    row = session.get(DepositEvent, identifier)
    return to_dict(row) if row is not None else None


def next_deposit_event_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(DepositEvent.deposit_event_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Write (POST only — born-terminal append-only)
# ---------------------------------------------------------------------------


def _split_references(references: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """Partition the outbound edge specs into (parent edges, wrote_record edges)."""
    parents: list[dict] = []
    wrote: list[dict] = []
    for spec in references or []:
        rel = spec.get("relationship")
        if rel == _APPLY_KIND:
            parents.append(spec)
        elif rel == _WROTE_KIND:
            wrote.append(spec)
        else:
            raise UnprocessableError(
                [
                    FieldError(
                        "references",
                        "invalid_deposit_event_edge",
                        f"unexpected relationship {rel!r} on a deposit_event POST",
                    )
                ]
            )
    return parents, wrote


def _lazy_get_or_create_payload(
    session: Session, cop_identifier: str, *, target_file_path: str | None
) -> CloseOutPayload:
    """Return the target close_out_payload, lazy-creating a minimal one if absent.

    The lazy row is inserted directly (status ``ready``) rather than through
    ``close_out_payloads.create`` so the production-edge requirement does not
    block the bootstrap/backfill apply path; the payload is a minimal
    stand-in awaiting its full record.
    """
    row = session.get(CloseOutPayload, cop_identifier)
    if row is not None:
        return row
    file_path = target_file_path or (
        f"close-out-payloads/{cop_identifier.lower().replace('-', '_')}.json"
    )
    row = CloseOutPayload(
        close_out_payload_identifier=cop_identifier,
        close_out_payload_title=f"{cop_identifier} (lazy)",
        close_out_payload_description=(
            f"Lazily created on a deposit_event apply targeting {cop_identifier}."
        ),
        close_out_payload_status="ready",
        close_out_payload_file_path=file_path,
        close_out_payload_ready_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def create_deposit_event(
    session: Session,
    *,
    title: str,
    description: str,
    outcome: str,
    records_summary: dict,
    apply_context: dict,
    log_file_path: str,
    error_info: dict | None = None,
    references: list[dict] | None = None,
    identifier: str | None = None,
    target_file_path: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    title = gov.require_nonempty(title, field="deposit_event_title")
    description = gov.require_nonempty(description, field="deposit_event_description")
    outcome = _require_outcome(outcome)
    log_file_path = gov.require_repo_relative_path(
        log_file_path, field="deposit_event_log_file_path"
    )
    if not isinstance(records_summary, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "deposit_event_records_summary",
                    "invalid_value",
                    "must be a JSON object",
                )
            ]
        )
    if not isinstance(apply_context, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "deposit_event_apply_context",
                    "invalid_value",
                    "must be a JSON object",
                )
            ]
        )

    # Conditional error_info rule.
    if outcome == "success" and error_info is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "deposit_event_error_info",
                    "deposit_event_error_info_must_be_null_when_outcome_is_success",
                    "error_info must be null when outcome is success",
                )
            ]
        )
    if outcome == "failure" and not isinstance(error_info, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "deposit_event_error_info",
                    "deposit_event_error_info_required_when_outcome_is_failure",
                    "error_info must be a JSON object when outcome is failure",
                )
            ]
        )

    parents, wrote = _split_references(references)
    if len(parents) == 0:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "deposit_event_requires_applies_close_out_payload_edge",
                    "exactly one deposit_event_applies_close_out_payload edge is required",
                )
            ]
        )
    if len(parents) > 1:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "deposit_event_single_parent_violation",
                    "a deposit_event applies exactly one close_out_payload",
                )
            ]
        )

    # records_summary sum must equal the count of wrote_record edges.
    summary_sum = sum(int(v) for v in records_summary.values())
    if summary_sum != len(wrote):
        raise UnprocessableError(
            [
                FieldError(
                    "deposit_event_records_summary",
                    "records_summary_count_mismatch",
                    f"records_summary sum ({summary_sum}) must equal the number "
                    f"of wrote_record edges ({len(wrote)})",
                )
            ]
        )

    cop_identifier = parents[0]["target_id"]
    payload = _lazy_get_or_create_payload(
        session, cop_identifier, target_file_path=target_file_path
    )
    if outcome == "success" and payload.close_out_payload_status not in (
        "ready",
        "applied",
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "deposit_event_target_close_out_payload_not_ready_or_applied",
                    "a successful apply targets a ready or applied close_out_payload",
                )
            ]
        )

    # Create the deposit_event row (collision-safe identifier auto-assign).
    if identifier is None:
        candidate = next_deposit_event_identifier(session)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="deposit_event_identifier", example="DEP-001",
        )
        if session.get(DepositEvent, identifier) is not None:
            raise ConflictError(f"deposit_event {identifier!r} already exists")
        candidate = identifier

    row = None
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = DepositEvent(
            deposit_event_identifier=candidate,
            deposit_event_title=title,
            deposit_event_description=description,
            deposit_event_outcome=outcome,
            deposit_event_records_summary=records_summary,
            deposit_event_error_info=error_info,
            deposit_event_apply_context=apply_context,
            deposit_event_log_file_path=log_file_path,
        )
        if created_at is not None:
            row.deposit_event_created_at = created_at
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            if identifier is not None:
                raise ConflictError(
                    f"deposit_event {identifier!r} already exists"
                ) from exc
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        break
    else:
        raise ConflictError(
            "could not assign a unique deposit_event identifier after "
            f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
        ) from last_error

    dep_identifier = row.deposit_event_identifier

    # Outbound edges: parent + wrote_record back-references.
    references_repo.upsert(
        session,
        source_type=_ENTITY_TYPE,
        source_id=dep_identifier,
        target_type="close_out_payload",
        target_id=cop_identifier,
        relationship=_APPLY_KIND,
    )
    for spec in wrote:
        references_repo.upsert(
            session,
            source_type=_ENTITY_TYPE,
            source_id=dep_identifier,
            target_type=spec["target_type"],
            target_id=spec["target_id"],
            relationship=_WROTE_KIND,
        )

    # First-success-transition: drive ready -> applied on the first success.
    if outcome == "success" and payload.close_out_payload_status == "ready":
        payload.close_out_payload_status = "applied"
        payload.close_out_payload_applied_at = (
            row.deposit_event_created_at or datetime.now(UTC)
        )
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=dep_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after
