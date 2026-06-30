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

import re
from typing import Any

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.repositories import reconcile_transactions as txn_repo

#: Canonical design literal used as a transaction source/target ref.
DESIGN = "design"


def _field_patch_kwarg(attribute: str) -> str:
    """Map a neutral field attribute (``field_max_length``) to its ``patch_field``
    keyword (``max_length``)."""
    return attribute.removeprefix("field_")


def _entity_patch_kwarg(attribute: str) -> str:
    """Map a neutral entity-settings attribute (``entity_default_sort_field``) to
    its ``patch_entity`` keyword (``default_sort_field``)."""
    return attribute.removeprefix("entity_")


def _association_patch_kwarg(attribute: str) -> str:
    """Map a neutral association attribute (``association_cardinality``) to its
    ``patch_association`` keyword (``cardinality``)."""
    return attribute.removeprefix("association_")


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


def capture_entity_setting(
    session: Session,
    *,
    instance: str,
    entity_identifier: str,
    attribute: str,
    actor: str,
    batch_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Capture an instance's value for one entity-collection setting into the
    design (REQ-375) — the entity-level twin of :func:`capture_field_attribute`.

    Settings covered are sort field/direction, full-text search (+ its minimum
    length), and the text-filter field list. Reads the instance's recorded
    override for ``attribute``, writes it onto the canonical entity, logs the
    transaction, and clears that attribute's drift on the source instance. Raises
    ``ConflictError`` when the instance records no deviation for ``attribute``.

    :returns: ``{transaction, entity}``.
    """
    membership = _membership_for(session, instance, "entity", entity_identifier)
    override = (membership or {}).get("override") or {}
    if attribute not in override:
        raise ConflictError(
            f"instance {instance} records no deviation for {entity_identifier}."
            f"{attribute}; nothing to capture"
        )
    new_value = override[attribute]

    current = entity_repo.get_entity(session, entity_identifier)
    if current is None:
        raise NotFoundError("entity", entity_identifier)
    before_value = current.get(attribute)

    entity_repo.patch_entity(
        session, entity_identifier, **{_entity_patch_kwarg(attribute): new_value}
    )

    transaction = txn_repo.record(
        session,
        direction="capture",
        source_ref=instance,
        target_ref=DESIGN,
        member_type="entity",
        member_identifier=entity_identifier,
        attribute=attribute,
        before_value=before_value,
        after_value=new_value,
        actor=actor,
        batch_id=batch_id,
        note=note,
    )

    remaining = {k: v for k, v in override.items() if k != attribute}
    membership_repo.upsert_membership(
        session,
        instance_identifier=instance,
        member_type="entity",
        member_identifier=entity_identifier,
        state="drifted" if remaining else "present",
        override=remaining or None,
    )
    return {
        "transaction": transaction,
        "entity": entity_repo.get_entity(session, entity_identifier),
    }


def capture_association_attribute(
    session: Session,
    *,
    instance: str,
    association_identifier: str,
    attribute: str,
    actor: str,
    batch_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Capture an instance's value for one association attribute into the design (REQ-443).

    The relationship twin of :func:`capture_field_attribute` — today the only
    audited (and so reconcilable) attribute is ``association_cardinality``. Reads
    the instance's recorded override value, writes it onto the canonical
    association, records the transaction, and clears that attribute's drift on the
    source instance. Raises ``ConflictError`` when the instance records no
    deviation for ``attribute``.

    Note this is **capture only** (instance → design): the deploy engine cannot
    alter an existing link's cardinality in place, so publishing a cardinality
    change is view-only (routed there by ``plan_apply``), not handled here.

    :returns: ``{transaction, association}``.
    """
    membership = _membership_for(session, instance, "association", association_identifier)
    override = (membership or {}).get("override") or {}
    if attribute not in override:
        raise ConflictError(
            f"instance {instance} records no deviation for {association_identifier}."
            f"{attribute}; nothing to capture"
        )
    new_value = override[attribute]

    current = association_repo.get_association(session, association_identifier)
    if current is None:
        raise NotFoundError("association", association_identifier)
    before_value = current.get(attribute)

    association_repo.patch_association(
        session, association_identifier,
        **{_association_patch_kwarg(attribute): new_value},
    )

    transaction = txn_repo.record(
        session,
        direction="capture",
        source_ref=instance,
        target_ref=DESIGN,
        member_type="association",
        member_identifier=association_identifier,
        attribute=attribute,
        before_value=before_value,
        after_value=new_value,
        actor=actor,
        batch_id=batch_id,
        note=note,
    )

    remaining = {k: v for k, v in override.items() if k != attribute}
    membership_repo.upsert_membership(
        session,
        instance_identifier=instance,
        member_type="association",
        member_identifier=association_identifier,
        state="drifted" if remaining else "present",
        override=remaining or None,
    )
    return {
        "transaction": transaction,
        "association": association_repo.get_association(session, association_identifier),
    }


def entity_for_member(
    session: Session, member_type: str, member_identifier: str
) -> dict[str, Any]:
    """Resolve the design entity a member is published with (REQ-369/376).

    Publish granularity is a whole entity (one generated program = one entity),
    so pushing any single object to an instance pushes its parent entity: a field
    maps to its parent entity, a layout to its entity, an association to its
    source entity, and an entity to itself. Returns the entity record. Raises
    ``NotFoundError`` when the member or its entity cannot be resolved.
    """
    if member_type == "entity":
        ent = entity_repo.get_entity(session, member_identifier)
        if ent is None:
            raise NotFoundError("entity", member_identifier)
        return ent
    if member_type == "field":
        if field_repo.get_field(session, member_identifier) is None:
            raise NotFoundError("field", member_identifier)
        edges = gov.outbound_edges(
            session,
            source_type="field",
            source_id=member_identifier,
            relationship="field_belongs_to_entity",
            target_type="entity",
        )
        eid = edges[0].target_id if edges else None
    elif member_type == "layout":
        lay = layout_repo.get_layout(session, member_identifier)
        if lay is None:
            raise NotFoundError("layout", member_identifier)
        eid = lay.get("layout_entity_identifier")
    elif member_type == "association":
        assoc = association_repo.get_association(session, member_identifier)
        if assoc is None:
            raise NotFoundError("association", member_identifier)
        eid = assoc.get("association_source_entity")
    else:
        raise ConflictError(
            f"member type {member_type!r} cannot be published to an instance"
        )
    if not eid:
        raise NotFoundError("entity", f"parent of {member_identifier}")
    ent = entity_repo.get_entity(session, eid)
    if ent is None:
        raise NotFoundError("entity", eid)
    return ent


def _filename_slug(entity_name: str, entity_identifier: str) -> str:
    """The generated program filename for an entity, matching the EspoCRM
    adapter's ``_filename_for`` convention (a word-slug of the name + ``.yaml``).

    The no-collision form is ``{slug}.yaml``; only two entities slugging
    identically would diverge (the adapter then suffixes the identifier), which
    the publish scope tolerates as a safe no-match. Kept here as a tiny mirror so
    the access layer does not import the adapter.
    """
    words = [w for w in re.split(r"[^A-Za-z0-9]+", entity_name or "") if w]
    slug = "-".join(words) or entity_identifier
    return f"{slug}.yaml"


def publish_scope_for_member(
    session: Session, member_type: str, member_identifier: str
) -> dict[str, Any]:
    """The entity + generated-program filename to scope a publish to (REQ-376).

    :returns: ``{entity_identifier, entity_name, filename}`` — pass ``filename``
        as the publish ``scope`` to push just this object's parent entity.
    """
    ent = entity_for_member(session, member_type, member_identifier)
    eid = ent["entity_identifier"]
    name = ent.get("entity_name") or eid
    return {
        "entity_identifier": eid,
        "entity_name": name,
        "filename": _filename_slug(name, eid),
    }


def record_publish(
    session: Session,
    *,
    instance: str,
    member_type: str,
    member_identifier: str,
    actor: str,
    attribute: str | None = None,
    before_value: Any = None,
    after_value: Any = None,
    batch_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Log a design→instance publish and reconcile the instance snapshot (REQ-376).

    Called after a successful live publish of the object's parent entity to the
    target. Records a ``publish`` transaction (design → instance) and brings the
    stored membership back in line with the design: a specific ``attribute`` is
    dropped from the instance's override (it now matches the design); with no
    ``attribute`` the whole member is marked present with its override cleared (a
    whole-object/entity promote, REQ-369). The membership row is left untouched
    when the instance never carried the member.

    :returns: ``{transaction}``.
    """
    transaction = txn_repo.record(
        session,
        direction="publish",
        source_ref=DESIGN,
        target_ref=instance,
        member_type=member_type,
        member_identifier=member_identifier,
        attribute=attribute,
        before_value=before_value,
        after_value=after_value,
        actor=actor,
        batch_id=batch_id,
        note=note,
    )

    membership = _membership_for(session, instance, member_type, member_identifier)
    if membership is not None:
        override = membership.get("override") or {}
        if attribute is not None:
            remaining = {k: v for k, v in override.items() if k != attribute}
        else:
            remaining = {}
        membership_repo.upsert_membership(
            session,
            instance_identifier=instance,
            member_type=member_type,
            member_identifier=member_identifier,
            state="drifted" if remaining else "present",
            override=remaining or None,
        )
    return {"transaction": transaction}


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
    member_type = txn["member_type"]
    attribute = txn["attribute"]
    if member_type not in ("field", "association") or not attribute:
        raise ConflictError(
            f"transaction {transaction_id} is not a reversible field- or "
            f"relationship-attribute capture in this slice"
        )

    # Restore the canonical value via the member type's patch helper (REQ-443
    # adds the relationship arm to the original field-only undo).
    if member_type == "field":
        field_repo.patch_field(
            session,
            txn["member_identifier"],
            **{_field_patch_kwarg(attribute): txn["before_value"]},
        )
    else:
        association_repo.patch_association(
            session,
            txn["member_identifier"],
            **{_association_patch_kwarg(attribute): txn["before_value"]},
        )
    rolled = txn_repo.mark_rolled_back(session, transaction_id, actor=actor)
    compensating = txn_repo.record(
        session,
        direction="capture",
        source_ref=DESIGN,
        target_ref=DESIGN,
        member_type=member_type,
        member_identifier=txn["member_identifier"],
        attribute=attribute,
        before_value=txn["after_value"],
        after_value=txn["before_value"],
        actor=actor,
        note=f"rollback of transaction {transaction_id}",
    )
    return {"rolled_back": rolled, "compensating": compensating}
