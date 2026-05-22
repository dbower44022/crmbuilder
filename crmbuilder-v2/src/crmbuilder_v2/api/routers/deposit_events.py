"""Deposit events endpoints — the sixth governance entity type (UI v0.7).

Reduced API surface per ``deposit_event.md`` §3.5: POST and GET only. PUT,
PATCH, DELETE, and restore are intentionally NOT registered — the framework
returns HTTP 405 for those methods on the registered paths. The POST is the
only write operation; the access layer makes it atomic (record + parent edge
+ wrote_record edges + first-success ready->applied transition).
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import deposit_events
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import DepositEventCreateIn

router = APIRouter(prefix="/deposit-events", tags=["deposit-events"])


@router.get("")
def list_all(outcome: str | None = None):
    with readonly_session() as s:
        return ok(deposit_events.list_deposit_events(s, outcome=outcome))


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": deposit_events.next_deposit_event_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        record = deposit_events.get_deposit_event(s, identifier)
        if record is None:
            raise NotFoundError("deposit_event", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: DepositEventCreateIn):
    references = (
        [e.model_dump() for e in body.references] if body.references else None
    )
    with writable_session() as s:
        return ok(
            deposit_events.create_deposit_event(
                s,
                title=body.deposit_event_title,
                description=body.deposit_event_description,
                outcome=body.deposit_event_outcome,
                records_summary=body.deposit_event_records_summary,
                apply_context=body.deposit_event_apply_context,
                log_file_path=body.deposit_event_log_file_path,
                error_info=body.deposit_event_error_info,
                identifier=body.deposit_event_identifier,
                references=references,
            )
        )
