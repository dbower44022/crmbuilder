"""Reconcile transaction-log repository — PI-318 (REL-024).

The append-only trail behind trust-but-log governance (DEC-722): every reconcile
action records a row here; rollback flips ``status`` to ``rolled_back`` and stamps
who/when rather than deleting it (DEC-723). A lightweight engagement-scoped child
table (integer PK, no ``change_log`` / ``refs``), mirroring
``instance_membership``: scoping is applied by the session read-filter /
write-stamp.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.models import ReconcileTransaction
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    RECONCILE_TRANSACTION_DIRECTIONS,
)


def record(
    session: Session,
    *,
    direction: str,
    source_ref: str,
    target_ref: str,
    member_type: str,
    member_identifier: str,
    actor: str,
    attribute: str | None = None,
    before_value: Any = None,
    after_value: Any = None,
    batch_id: str | None = None,
    note: str | None = None,
) -> dict:
    """Append one applied reconcile transaction and return it."""
    direction = gov.require_in(
        direction, RECONCILE_TRANSACTION_DIRECTIONS, field="direction"
    )
    actor = gov.require_nonempty(actor, field="actor")
    row = ReconcileTransaction(
        direction=direction,
        source_ref=gov.require_nonempty(source_ref, field="source_ref"),
        target_ref=gov.require_nonempty(target_ref, field="target_ref"),
        member_type=gov.require_nonempty(member_type, field="member_type"),
        member_identifier=gov.require_nonempty(
            member_identifier, field="member_identifier"
        ),
        attribute=attribute,
        before_value=before_value,
        after_value=after_value,
        actor=actor,
        status="applied",
        batch_id=batch_id,
        note=note,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def get(session: Session, transaction_id: int) -> dict:
    """Return one transaction by id, or raise ``NotFoundError``."""
    row = session.get(ReconcileTransaction, transaction_id)
    if row is None:
        raise NotFoundError("reconcile_transaction", str(transaction_id))
    return to_dict(row)


def list_transactions(
    session: Session,
    *,
    batch_id: str | None = None,
    member_type: str | None = None,
    member_identifier: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """List transactions, newest first, with optional filters."""
    stmt = select(ReconcileTransaction).order_by(ReconcileTransaction.id.desc())
    if batch_id is not None:
        stmt = stmt.where(ReconcileTransaction.batch_id == batch_id)
    if member_type is not None:
        stmt = stmt.where(ReconcileTransaction.member_type == member_type)
    if member_identifier is not None:
        stmt = stmt.where(
            ReconcileTransaction.member_identifier == member_identifier
        )
    if status is not None:
        stmt = stmt.where(ReconcileTransaction.status == status)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def mark_rolled_back(
    session: Session, transaction_id: int, *, actor: str
) -> dict:
    """Flip a transaction to ``rolled_back`` (idempotency: re-rollback is a 409).

    This records the rollback event only; reversing the actual data change is the
    caller's job (it records its own compensating transaction). Returns the row.
    """
    actor = gov.require_nonempty(actor, field="actor")
    row = session.get(ReconcileTransaction, transaction_id)
    if row is None:
        raise NotFoundError("reconcile_transaction", str(transaction_id))
    if row.status == "rolled_back":
        raise ConflictError(
            f"reconcile_transaction {transaction_id} is already rolled back"
        )
    row.status = "rolled_back"
    row.rolled_back_at = datetime.now(UTC)
    row.rolled_back_by = actor
    session.flush()
    return to_dict(row)
