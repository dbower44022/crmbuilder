"""Utilization-evidence endpoints (WTK-088 §4.5 / WTK-097 §6).

Append-only surface: POST and GET only — no PUT, PATCH, DELETE, or
restore is registered (invariant I8, the born-terminal posture the
``deposit_event`` router also follows). The POST is the deposit path's
evidence write; the list GET with
``subject_type=field&max_population_rate=0.05&latest=true`` is the
headline triage query over REST (WTK-088 §5.1 Q1).

Request bodies use the repository's unprefixed key names (the wire
shape the WTK-090 transform posts); responses carry the stored
``evidence_*`` column names. This module also hosts
:func:`embed_inline_evidence`, the shared ``include_evidence``
query-parameter handler the five candidate endpoint families delegate
to (WTK-097 §6.1).
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import utilization_evidence
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import UtilizationEvidenceCreateIn

router = APIRouter(prefix="/utilization-evidence", tags=["utilization-evidence"])


def embed_inline_evidence(
    session: Session,
    records: list[dict],
    *,
    subject_type: str,
    identifier_key: str,
    include_evidence: str | None,
    is_list: bool,
) -> list[dict]:
    """Apply the ``include_evidence`` projection for a candidate router.

    ``None`` (parameter omitted) returns the records untouched — the
    projection is strictly additive and costs nothing when not
    requested. ``latest`` embeds one §3 object per source; ``all``
    embeds full history on single-record GETs and is refused with 422
    on list GETs to bound payloads (WTK-097 §6.1). Any other value is
    422.
    """
    if include_evidence is None:
        return records
    if include_evidence not in utilization_evidence.EVIDENCE_INCLUDE_MODES:
        raise UnprocessableError(
            [
                FieldError(
                    "include_evidence",
                    "invalid_value",
                    "must be 'latest' or 'all'",
                )
            ]
        )
    if include_evidence == "all" and is_list:
        raise UnprocessableError(
            [
                FieldError(
                    "include_evidence",
                    "invalid_value",
                    "'all' is refused on list endpoints to bound payloads; "
                    "use the single-record GET, or 'latest'",
                )
            ]
        )
    return utilization_evidence.attach_inline_evidence(
        session,
        records,
        subject_type=subject_type,
        identifier_key=identifier_key,
        mode=include_evidence,
    )


@router.get("")
def list_all(
    subject_type: str | None = None,
    subject_identifier: str | None = None,
    deposit_event: str | None = None,
    max_population_rate: float | None = None,
    latest: bool = False,
):
    with readonly_session() as s:
        return ok(
            utilization_evidence.list_utilization_evidence(
                s,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                deposit_event_identifier=deposit_event,
                max_population_rate=max_population_rate,
                latest=latest,
            )
        )


@router.get("/{evidence_id}")
def get(evidence_id: int):
    with readonly_session() as s:
        record = utilization_evidence.get_utilization_evidence(s, evidence_id)
        if record is None:
            raise NotFoundError("utilization_evidence", str(evidence_id))
        return ok(record)


@router.post("", status_code=201)
def create(body: UtilizationEvidenceCreateIn):
    with writable_session() as s:
        return ok(
            utilization_evidence.create_utilization_evidence(
                s,
                subject_type=body.subject_type,
                subject_identifier=body.subject_identifier,
                profiled_at=body.profiled_at,
                source_label=body.source_label,
                deposit_event_identifier=body.deposit_event_identifier,
                catalog_class=body.catalog_class,
                record_count=body.record_count,
                last_record_created_at=body.last_record_created_at,
                populated_count=body.populated_count,
                population_rate=body.population_rate,
                last_populated_at=body.last_populated_at,
                distinct_value_count=body.distinct_value_count,
                declared_option_count=body.declared_option_count,
                used_option_count=body.used_option_count,
                detail=body.detail,
            )
        )
