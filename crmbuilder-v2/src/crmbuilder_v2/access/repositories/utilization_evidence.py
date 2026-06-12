"""Utilization-evidence repository (PI-153 / WTK-088 design spec §4, D2).

Append-only mechanical table: the only write operation is
:func:`create_utilization_evidence`; there is no update, patch, delete,
or restore (invariant I8 — the born-terminal ``deposit_event`` posture).
One row = one profiling measurement of one Phase 1.5 capture record at
one source snapshot, written by the audit deposit path or a standalone
re-profile.

Subject linkage is the polymorphic soft pair
(``evidence_subject_type``, ``evidence_subject_identifier``) per the
``change_log`` precedent — not a refs edge. The access layer validates
at insert that the subject exists, is live, and matches the declared
type (invariant I9); after that the reference is soft by design
(evidence outlives nothing — a later soft-delete or rejection of the
subject leaves its evidence rows intact and queryable, invariant I10).

Reads support the WTK-088 §4.5 filter surface, including the
latest-snapshot rule (``latest=True``): the current evidence for a
subject is the row with the greatest ``evidence_profiled_at`` per
``(subject_type, subject_identifier, source_label)``.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import get_by_identifier, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import (
    Entity,
    Field,
    ManualConfig,
    Persona,
    Process,
    UtilizationEvidence,
)
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import EVIDENCE_SUBJECT_TYPES

_ENTITY_TYPE = "utilization_evidence"
_DEP_IDENTIFIER_RE = re.compile(r"^DEP-\d{3}$")
_CATALOG_CLASSES = frozenset({"standard", "custom"})

# The five Phase 1.5 capture types (WTK-088 §4.3), mapped to
# (model, identifier attribute, deleted_at attribute) for the I9
# subject existence/liveness/type-match validation.
_SUBJECT_MODELS: dict[str, tuple[type, str, str]] = {
    "entity": (Entity, "entity_identifier", "entity_deleted_at"),
    "field": (Field, "field_identifier", "field_deleted_at"),
    "persona": (Persona, "persona_identifier", "persona_deleted_at"),
    "process": (Process, "process_identifier", "process_deleted_at"),
    "manual_config": (
        ManualConfig,
        "manual_config_identifier",
        "manual_config_deleted_at",
    ),
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_subject(
    session: Session, subject_type: object, subject_identifier: object
) -> tuple[str, str]:
    """Validate the polymorphic subject pair per invariant I9.

    The subject must be a capture type, exist in that type's table, and
    be live (not soft-deleted). Type mismatch surfaces as ``not_found``
    by construction — the identifier is looked up in the declared
    type's table only.
    """
    if subject_type not in EVIDENCE_SUBJECT_TYPES:
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_subject_type",
                    "invalid_value",
                    f"must be one of {sorted(EVIDENCE_SUBJECT_TYPES)}",
                )
            ]
        )
    if not isinstance(subject_identifier, str) or not subject_identifier.strip():
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_subject_identifier",
                    "missing_or_empty",
                    "must be a non-empty string",
                )
            ]
        )
    subject_identifier = subject_identifier.strip()
    model, identifier_attr, deleted_attr = _SUBJECT_MODELS[subject_type]
    row = get_by_identifier(
        session, model, getattr(model, identifier_attr), subject_identifier
    )
    if row is None:
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_subject_identifier",
                    "subject_not_found",
                    f"{subject_type} {subject_identifier!r} not found",
                )
            ]
        )
    if getattr(row, deleted_attr) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_subject_identifier",
                    "subject_soft_deleted",
                    f"{subject_type} {subject_identifier!r} is soft-deleted",
                )
            ]
        )
    return subject_type, subject_identifier  # type: ignore[return-value]


def _require_nonneg_int(value: object, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnprocessableError(
            [FieldError(field, "invalid_value", "must be a non-negative integer")]
        )
    return value


def _require_rate(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnprocessableError(
            [FieldError(field, "invalid_value", "must be a number in [0.0, 1.0]")]
        )
    rate = float(value)
    if not 0.0 <= rate <= 1.0:
        raise UnprocessableError(
            [FieldError(field, "invalid_value", "must be a number in [0.0, 1.0]")]
        )
    return rate


def _optional_datetime(value: object, *, field: str) -> datetime | None:
    if value is None:
        return None
    return gov.coerce_datetime(value, field=field)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_utilization_evidence(session: Session, evidence_id: int) -> dict | None:
    """Return one evidence row by integer primary key, or ``None``."""
    row = session.get(UtilizationEvidence, evidence_id)
    return to_dict(row) if row is not None else None


def list_utilization_evidence(
    session: Session,
    *,
    subject_type: str | None = None,
    subject_identifier: str | None = None,
    deposit_event_identifier: str | None = None,
    max_population_rate: float | None = None,
    latest: bool = False,
) -> list[dict]:
    """Return evidence rows, optionally filtered (WTK-088 §4.5).

    Filters compose by exact match except ``max_population_rate``
    (``evidence_population_rate <= value``, NULL rates excluded by SQL
    semantics) and ``latest`` (the §4.4 latest-snapshot rule: keep only
    the greatest ``evidence_profiled_at`` per ``(subject_type,
    subject_identifier, source_label)``; ``id`` breaks exact ties so a
    re-appended duplicate row wins deterministically). Ordered by
    subject, then newest snapshot first — the nested per-subject reads
    are this function with the two subject filters supplied.
    """
    stmt = select(UtilizationEvidence)
    if latest:
        ranked = select(
            UtilizationEvidence.id,
            func.row_number()
            .over(
                partition_by=(
                    UtilizationEvidence.evidence_subject_type,
                    UtilizationEvidence.evidence_subject_identifier,
                    UtilizationEvidence.evidence_source_label,
                ),
                order_by=(
                    UtilizationEvidence.evidence_profiled_at.desc(),
                    UtilizationEvidence.id.desc(),
                ),
            )
            .label("rn"),
        ).subquery()
        latest_ids = select(ranked.c.id).where(ranked.c.rn == 1)
        stmt = stmt.where(UtilizationEvidence.id.in_(latest_ids))
    if subject_type is not None:
        stmt = stmt.where(
            UtilizationEvidence.evidence_subject_type == subject_type
        )
    if subject_identifier is not None:
        stmt = stmt.where(
            UtilizationEvidence.evidence_subject_identifier == subject_identifier
        )
    if deposit_event_identifier is not None:
        stmt = stmt.where(
            UtilizationEvidence.evidence_deposit_event_identifier
            == deposit_event_identifier
        )
    if max_population_rate is not None:
        stmt = stmt.where(
            UtilizationEvidence.evidence_population_rate <= max_population_rate
        )
    stmt = stmt.order_by(
        UtilizationEvidence.evidence_subject_type,
        UtilizationEvidence.evidence_subject_identifier,
        UtilizationEvidence.evidence_profiled_at.desc(),
        UtilizationEvidence.id.desc(),
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


# ---------------------------------------------------------------------------
# Write (POST only — append-only, invariant I8)
# ---------------------------------------------------------------------------


def create_utilization_evidence(
    session: Session,
    *,
    subject_type: str,
    subject_identifier: str,
    profiled_at: datetime | str,
    source_label: str,
    deposit_event_identifier: str | None = None,
    catalog_class: str | None = None,
    record_count: int | None = None,
    last_record_created_at: datetime | str | None = None,
    populated_count: int | None = None,
    population_rate: float | None = None,
    last_populated_at: datetime | str | None = None,
    distinct_value_count: int | None = None,
    declared_option_count: int | None = None,
    used_option_count: int | None = None,
    detail: dict | None = None,
) -> dict:
    """Insert one evidence snapshot row.

    Validates the subject per invariant I9 and the enum/range
    constraints per WTK-088 §4.3. ``deposit_event_identifier`` is a
    soft reference — format-validated only (a standalone re-profile may
    run outside a deposit, and the depositing event is not re-resolved
    here). All metric columns are nullable: evidence is
    shape-heterogeneous, and a schema-only deposit (no utilization
    profile) legitimately writes structural facts only.
    """
    subject_type, subject_identifier = _require_subject(
        session, subject_type, subject_identifier
    )
    profiled_at_dt = gov.coerce_datetime(profiled_at, field="evidence_profiled_at")
    source_label = gov.require_nonempty(
        source_label, field="evidence_source_label"
    )
    if deposit_event_identifier is not None and not (
        isinstance(deposit_event_identifier, str)
        and _DEP_IDENTIFIER_RE.match(deposit_event_identifier)
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_deposit_event_identifier",
                    "invalid_format",
                    r"must match ^DEP-\d{3}$ (e.g. DEP-001) when set",
                )
            ]
        )
    if catalog_class is not None and catalog_class not in _CATALOG_CLASSES:
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_catalog_class",
                    "invalid_value",
                    f"must be one of {sorted(_CATALOG_CLASSES)} or null",
                )
            ]
        )
    if detail is not None and not isinstance(detail, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "evidence_detail",
                    "invalid_value",
                    "must be a JSON object when set",
                )
            ]
        )

    row = UtilizationEvidence(
        evidence_subject_type=subject_type,
        evidence_subject_identifier=subject_identifier,
        evidence_profiled_at=profiled_at_dt,
        evidence_source_label=source_label,
        evidence_deposit_event_identifier=deposit_event_identifier,
        evidence_catalog_class=catalog_class,
        evidence_record_count=_require_nonneg_int(
            record_count, field="evidence_record_count"
        ),
        evidence_last_record_created_at=_optional_datetime(
            last_record_created_at, field="evidence_last_record_created_at"
        ),
        evidence_populated_count=_require_nonneg_int(
            populated_count, field="evidence_populated_count"
        ),
        evidence_population_rate=_require_rate(
            population_rate, field="evidence_population_rate"
        ),
        evidence_last_populated_at=_optional_datetime(
            last_populated_at, field="evidence_last_populated_at"
        ),
        evidence_distinct_value_count=_require_nonneg_int(
            distinct_value_count, field="evidence_distinct_value_count"
        ),
        evidence_declared_option_count=_require_nonneg_int(
            declared_option_count, field="evidence_declared_option_count"
        ),
        evidence_used_option_count=_require_nonneg_int(
            used_option_count, field="evidence_used_option_count"
        ),
        evidence_detail=detail,
    )
    session.add(row)
    session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=str(row.id),
        operation="insert",
        before=None,
        after=after,
    )
    return after
