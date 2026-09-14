"""Reference integrity — both records of a reference exist (PI-502).

Implements REQ-596 to REQ-598 (approved by DEC-1083, ruling DEC-1081). A
reference says one record relates to another; a reference whose source or
target record does not exist says nothing true, and some references change
another record the moment they are written (a ``resolves`` reference marks its
planning item resolved). So:

* :func:`require_both_ends` runs inside :func:`references.create` before the row
  is written or any such change is made, and refuses a reference to a missing
  record with a reason naming the missing end (``source_not_found`` /
  ``target_not_found``). Record types on
  :data:`~crmbuilder_v2.access.vocab.REFERENCE_EXISTENCE_EXEMPT_TYPES` are not
  looked up.
* :func:`dangling_references` is the read-only census: every stored reference
  in the active engagement whose source or target record does not exist, with
  the missing end. It changes nothing.

A record counts as existing when its row is present, soft-deleted or not: a
decision about a retired record, or a withdrawal of a deleted one, still names
a real record. Engagement scoping applies as it does to every read, so a record
held in another engagement does not exist from this one.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.entity_summary import _SPECS
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import Reference
from crmbuilder_v2.access.vocab import REFERENCE_EXISTENCE_EXEMPT_TYPES


def record_exists(session: Session, entity_type: str, identifier: str) -> bool | None:
    """Whether a record of ``entity_type`` with ``identifier`` exists.

    Returns ``None`` for a type the store does not look up — an exempt type, or
    one with no identifier table registered.
    """
    if entity_type in REFERENCE_EXISTENCE_EXEMPT_TYPES:
        return None
    spec = _SPECS.get(entity_type)
    if spec is None:
        return None
    column = getattr(spec.model, spec.id_col)
    return session.scalar(select(column).where(column == identifier)) is not None


def require_both_ends(
    session: Session,
    *,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
) -> None:
    """Refuse a reference whose source or target record does not exist (REQ-596).

    Both ends are checked and both failures reported together, so a caller
    fixing one does not meet the other on the next attempt.
    """
    errors: list[FieldError] = []
    if record_exists(session, source_type, source_id) is False:
        errors.append(
            FieldError(
                "source_id",
                "source_not_found",
                f"the source {source_type} {source_id!r} does not exist",
            )
        )
    if record_exists(session, target_type, target_id) is False:
        errors.append(
            FieldError(
                "target_id",
                "target_not_found",
                f"the target {target_type} {target_id!r} does not exist",
            )
        )
    if errors:
        raise UnprocessableError(errors)


def dangling_references(session: Session) -> list[dict]:
    """Every stored reference whose source or target record is missing (REQ-598).

    One entry per reference, in identifier order, naming the reference, its
    relationship, both ends and which of them is missing. Read-only. Existence
    is resolved one type at a time, so the census reads each identifier table
    once rather than once per reference.
    """
    known: dict[str, set[str] | None] = {}

    def exists(entity_type: str, identifier: str) -> bool | None:
        if entity_type not in known:
            if entity_type in REFERENCE_EXISTENCE_EXEMPT_TYPES or entity_type not in _SPECS:
                known[entity_type] = None
            else:
                spec = _SPECS[entity_type]
                known[entity_type] = set(
                    session.scalars(select(getattr(spec.model, spec.id_col))).all()
                )
        ids = known[entity_type]
        return None if ids is None else identifier in ids

    report: list[dict] = []
    rows = session.scalars(select(Reference).order_by(Reference.id)).all()
    for row in rows:
        missing = []
        if exists(row.source_type, row.source_id) is False:
            missing.append("source")
        if exists(row.target_type, row.target_id) is False:
            missing.append("target")
        if not missing:
            continue
        report.append(
            {
                "id": row.id,
                "reference_identifier": row.reference_identifier,
                "relationship": row.relationship_kind,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "missing": missing,
                "engagement_id": row.engagement_id,
            }
        )
    return report
