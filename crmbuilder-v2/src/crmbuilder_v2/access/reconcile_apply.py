"""Reconcile apply engine — PI-317 / PI-318 (REL-024).

The write side of three-way reconciliation. **Capture** promotes an instance's
value into the canonical design (instance -> design); **rollback** reverses a
prior design change, restoring the previous value (DEC-723, the always-safe
blueprint undo). Every action records a :class:`ReconcileTransaction` so the
design never changes without a reversible, attributable trail (DEC-722).

This slice covers **field** attributes — the dominant drift case. Publish
(design -> instance) reuses the existing PRJ-042 publish path and the guarded
live-instance revert is built alongside it; capture for the other member types
extends the same shape.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import reconcile_transactions as txn_repo

#: Canonical design literal used as a transaction source/target ref.
DESIGN = "design"


def _field_patch_kwarg(attribute: str) -> str:
    """Map a neutral field attribute (``field_max_length``) to its ``patch_field``
    keyword (``max_length``)."""
    return attribute.removeprefix("field_")


def _membership_for(
    session: Session, instance: str, member_type: str, member_identifier: str
) -> dict[str, Any] | None:
    rows = membership_repo.list_memberships(
        session,
        instance_identifier=instance,
        member_type=member_type,
        member_identifier=member_identifier,
    )
    return rows[0] if rows else None


def capture_field_attribute(
    session: Session,
    *,
    instance: str,
    field_identifier: str,
    attribute: str,
    actor: str,
    batch_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Capture an instance's value for one field attribute into the design.

    Reads the instance's recorded override value for ``attribute``, writes it onto
    the canonical field, records the transaction, and updates the instance's
    membership so the now-matching attribute no longer reads as drift. Raises
    ``ConflictError`` when the instance records no deviation for ``attribute``
    (nothing to capture).

    :returns: ``{transaction, field}``.
    """
    membership = _membership_for(session, instance, "field", field_identifier)
    override = (membership or {}).get("override") or {}
    if attribute not in override:
        raise ConflictError(
            f"instance {instance} records no deviation for {field_identifier}."
            f"{attribute}; nothing to capture"
        )
    new_value = override[attribute]

    current = field_repo.get_field(session, field_identifier)
    if current is None:
        raise NotFoundError("field", field_identifier)
    before_value = current.get(attribute)

    field_repo.patch_field(
        session, field_identifier, **{_field_patch_kwarg(attribute): new_value}
    )

    transaction = txn_repo.record(
        session,
        direction="capture",
        source_ref=instance,
        target_ref=DESIGN,
        member_type="field",
        member_identifier=field_identifier,
        attribute=attribute,
        before_value=before_value,
        after_value=new_value,
        actor=actor,
        batch_id=batch_id,
        note=note,
    )

    # The captured attribute now matches the design; drop it from this instance's
    # override and recompute its membership state.
    remaining = {k: v for k, v in override.items() if k != attribute}
    membership_repo.upsert_membership(
        session,
        instance_identifier=instance,
        member_type="field",
        member_identifier=field_identifier,
        state="drifted" if remaining else "present",
        override=remaining or None,
    )
    return {"transaction": transaction, "field": field_repo.get_field(session, field_identifier)}


def rollback(session: Session, transaction_id: int, *, actor: str) -> dict[str, Any]:
    """Reverse a prior design change, restoring the previous value (DEC-723).

    Only design-targeting transactions (``capture``) are reversible this way — the
    always-safe blueprint undo. Restores the canonical value to the transaction's
    ``before_value``, marks the transaction ``rolled_back``, and records a
    compensating transaction. A live-instance (``publish``) revert is the guarded,
    data-loss-analysed path handled with the publish engine, not here.

    :returns: ``{rolled_back, compensating}``.
    """
    txn = txn_repo.get(session, transaction_id)
    if txn["status"] == "rolled_back":
        raise ConflictError(f"transaction {transaction_id} is already rolled back")
    if txn["target_ref"] != DESIGN:
        raise ConflictError(
            f"transaction {transaction_id} targets {txn['target_ref']}, not the "
            f"design; use the guarded live-instance revert instead"
        )
    if txn["member_type"] != "field" or not txn["attribute"]:
        raise ConflictError(
            f"transaction {transaction_id} is not a reversible field-attribute "
            f"capture in this slice"
        )

    field_repo.patch_field(
        session,
        txn["member_identifier"],
        **{_field_patch_kwarg(txn["attribute"]): txn["before_value"]},
    )
    rolled = txn_repo.mark_rolled_back(session, transaction_id, actor=actor)
    compensating = txn_repo.record(
        session,
        direction="capture",
        source_ref=DESIGN,
        target_ref=DESIGN,
        member_type="field",
        member_identifier=txn["member_identifier"],
        attribute=txn["attribute"],
        before_value=txn["after_value"],
        after_value=txn["before_value"],
        actor=actor,
        note=f"rollback of transaction {transaction_id}",
    )
    return {"rolled_back": rolled, "compensating": compensating}
