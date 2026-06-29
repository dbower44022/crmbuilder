"""instance_membership repository — PI-185 (PRJ-027).

The per-(canonical design object, instance) join is a lightweight
engagement-scoped child table, so this repository is deliberately small: an
idempotent ``upsert`` keyed on (instance, member_type, member_identifier), a
read ``list``, and a ``mark_absent_missing`` sweep the reconcile engine uses to
flag canonical objects not seen in an instance's latest audit. There is no
prefixed identifier, no ``change_log`` emit, and no ``refs`` participation
(mirroring ``field_options``); engagement scoping is applied by the session
read-filter / write-stamp.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.models import InstanceMembership
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    INSTANCE_MEMBERSHIP_MEMBER_TYPES,
    INSTANCE_MEMBERSHIP_STATES,
)


def _require_member_type(value: object) -> str:
    return gov.require_in(
        value, INSTANCE_MEMBERSHIP_MEMBER_TYPES, field="member_type"
    )


def _require_state(value: object) -> str:
    return gov.require_in(value, INSTANCE_MEMBERSHIP_STATES, field="state")


def _find(
    session: Session,
    instance_identifier: str,
    member_type: str,
    member_identifier: str,
) -> InstanceMembership | None:
    stmt = select(InstanceMembership).where(
        InstanceMembership.instance_identifier == instance_identifier,
        InstanceMembership.member_type == member_type,
        InstanceMembership.member_identifier == member_identifier,
    )
    return session.scalars(stmt).first()


def upsert_membership(
    session: Session,
    *,
    instance_identifier: str,
    member_type: str,
    member_identifier: str,
    state: str,
    override: dict | None = None,
    last_audited_at: datetime | None = None,
) -> dict:
    """Create or update one membership row idempotently.

    Keyed on (instance, member_type, member_identifier) within the active
    engagement. ``override`` is the sparse per-attribute deviation (DEC-432);
    it is replaced wholesale on each call (and cleared when ``None``).
    """
    member_type = _require_member_type(member_type)
    state = _require_state(state)
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    member_identifier = gov.require_nonempty(
        member_identifier, field="member_identifier"
    )
    stamp = last_audited_at or datetime.now(UTC)

    row = _find(session, instance_identifier, member_type, member_identifier)
    if row is None:
        row = InstanceMembership(
            instance_identifier=instance_identifier,
            member_type=member_type,
            member_identifier=member_identifier,
            state=state,
            override=override,
            last_audited_at=stamp,
        )
        session.add(row)
    else:
        row.state = state
        row.override = override
        row.last_audited_at = stamp
    session.flush()
    return to_dict(row)


def list_memberships(
    session: Session,
    *,
    instance_identifier: str | None = None,
    member_type: str | None = None,
    member_identifier: str | None = None,
    state: str | None = None,
) -> list[dict]:
    stmt = select(InstanceMembership).order_by(
        InstanceMembership.member_type,
        InstanceMembership.member_identifier,
        InstanceMembership.instance_identifier,
    )
    if instance_identifier is not None:
        stmt = stmt.where(
            InstanceMembership.instance_identifier == instance_identifier
        )
    if member_type is not None:
        stmt = stmt.where(InstanceMembership.member_type == member_type)
    if member_identifier is not None:
        stmt = stmt.where(
            InstanceMembership.member_identifier == member_identifier
        )
    if state is not None:
        stmt = stmt.where(InstanceMembership.state == state)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def mark_absent_missing(
    session: Session,
    *,
    instance_identifier: str,
    member_type: str,
    present_member_identifiers: set[str],
    last_audited_at: datetime | None = None,
) -> int:
    """Flag canonical objects of ``member_type`` not seen in this audit.

    Every existing membership row for (instance, member_type) whose
    ``member_identifier`` is not in ``present_member_identifiers`` and is not
    already ``absent`` is set to ``absent`` with its override cleared. Returns
    the number of rows transitioned. Reconcile calls this after upserting the
    present/drifted rows so absence reflects the latest audit.

    No-resolution preservation contract (REQ-394, REL-038). This sweep is the
    mechanism behind the absent transition documented on
    ``InstanceMembership`` and ``INSTANCE_MEMBERSHIP_STATES``; honoring the
    rule is the **caller's** responsibility, not this function's. A pass that
    resolves no objects for an area — a read that failed, was candidate-gated,
    or was never attempted — must leave that area's existing ``present`` and
    ``drifted`` membership unchanged: it is a no-op for membership, and the
    caller MUST NOT invoke this sweep for it. An empty
    ``present_member_identifiers`` is therefore meaningful only when it is the
    result of a SUCCESSFUL read that confirmed the area genuinely holds no live
    objects (every canonical row legitimately swept to ``absent``); it must
    never stand in for "the pass resolved nothing". Because this function
    cannot tell the two apart from the set it is handed, it sweeps
    unconditionally against that set — the introspect/reconcile layer enforces
    the rule by computing ``present_member_identifiers`` (and thus reaching
    this call) only once the area's instance read returned successfully, and by
    skipping the call entirely for an area its own pass did not resolve.
    """
    member_type = _require_member_type(member_type)
    stamp = last_audited_at or datetime.now(UTC)
    stmt = select(InstanceMembership).where(
        InstanceMembership.instance_identifier == instance_identifier,
        InstanceMembership.member_type == member_type,
    )
    transitioned = 0
    for row in session.scalars(stmt).all():
        if row.member_identifier in present_member_identifiers:
            continue
        if row.state == "absent":
            continue
        row.state = "absent"
        row.override = None
        row.last_audited_at = stamp
        transitioned += 1
    session.flush()
    return transitioned
