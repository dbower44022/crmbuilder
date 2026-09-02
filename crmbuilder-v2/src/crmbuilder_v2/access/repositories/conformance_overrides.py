"""One-deploy conformance overrides — PI-410 (REQ-494).

An operator authorization for one deploy to proceed past a blocking
conformance result. Recorded with who, when and why; consumed exactly once;
never altering the verdict a check produces. Plain engagement-scoped rows —
no prefixed identifier, no change-log participation: this is an operational
authorization, not a design record.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.models import ConformanceOverride
from crmbuilder_v2.access.repositories import _governance as gov


def create_override(
    session: Session,
    *,
    instance_identifier: str,
    authorized_by: str,
    reason: str,
) -> dict:
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    authorized_by = gov.require_nonempty(authorized_by, field="authorized_by")
    reason = gov.require_nonempty(reason, field="reason")
    row = ConformanceOverride(
        instance_identifier=instance_identifier,
        authorized_by=authorized_by,
        reason=reason,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def list_overrides(
    session: Session, *, instance_identifier: str | None = None
) -> list[dict]:
    stmt = select(ConformanceOverride).order_by(ConformanceOverride.id)
    if instance_identifier is not None:
        stmt = stmt.where(
            ConformanceOverride.instance_identifier == instance_identifier
        )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def consume_override(
    session: Session, *, instance_identifier: str
) -> dict | None:
    """Spend the oldest unconsumed override for this instance, or ``None``.

    Single-deploy semantics (REQ-494): the first blocking check that consumes
    it stamps ``consumed_at``; a subsequent run finds nothing and reports the
    same outcome as if no override had been granted.
    """
    row = session.scalars(
        select(ConformanceOverride)
        .where(
            ConformanceOverride.instance_identifier == instance_identifier,
            ConformanceOverride.consumed_at.is_(None),
        )
        .order_by(ConformanceOverride.id)
    ).first()
    if row is None:
        return None
    row.consumed_at = datetime.now(UTC)
    session.flush()
    return to_dict(row)
