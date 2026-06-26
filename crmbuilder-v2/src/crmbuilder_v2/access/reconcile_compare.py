"""Three-way reconciliation comparison engine — PI-316 (REL-024 / REQ-352).

Computes value-level differences across the canonical **design** and **two live
instances**, grouped by entity, from already-stored audit data — the canonical
records plus each instance's ``instance_membership`` snapshot. No live re-audit
is needed to display: the per-instance ``override`` already encodes each
instance's sparse deviation from the design (DEC-432), so a member's effective
value on an instance is the canonical value *unless* its override says otherwise,
and the member is ABSENT when the instance does not carry it.

The headline is :func:`three_way_compare`, which reads the design + two
memberships and returns the differing rows grouped by entity. The comparison
itself is the pure :func:`compute_member_rows`, so it is fully testable offline
without a session. This slice covers **entities and fields**; the remaining
member types (associations with dual-listing, layouts, roles, teams, filtered
tabs) extend the same shape in the next slice.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo

#: A source carries the member on the instance (its value participates in diffs).
PRESENT = "present"
#: The instance was audited and the member is confirmed missing there.
ABSENT = "absent"
#: The member has never been audited on the instance — presence unknown.
UNKNOWN = "unknown"

#: Membership states that mean the member is carried on the instance.
_PRESENT_STATES = frozenset({"present", "drifted"})


def _presence(membership: dict[str, Any] | None) -> str:
    """Map a membership row (or its absence) to a presence token."""
    if membership is None:
        return UNKNOWN
    return PRESENT if membership["state"] in _PRESENT_STATES else ABSENT


def _effective_value(
    membership: dict[str, Any] | None, attr: str, design_value: Any
) -> Any:
    """The instance's effective value for ``attr``.

    The override holds only attributes that deviate from the canonical design, so
    a present instance's value is the override's value when present, else the
    design value. A not-present instance has no value (caller handles that via
    :func:`_presence`).
    """
    override = (membership or {}).get("override") or {}
    return override[attr] if attr in override else design_value


def compute_member_rows(
    *,
    member_type: str,
    member_identifier: str,
    member_name: str | None,
    design_obj: dict[str, Any],
    attributes: list[str],
    membership_a: dict[str, Any] | None,
    membership_b: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Pure three-way comparison for one design member.

    Emits at most one **presence** row (when an instance does not carry the
    member the design defines) followed by one **attribute** row per attribute
    whose effective value differs across the design and the *present* instances.
    Returns ``[]`` when the member is present everywhere with no attribute drift.

    :param attributes: candidate attribute names to compare — typically the union
        of the two memberships' override keys. The design value of each is read
        from ``design_obj``.
    """
    pres_a = _presence(membership_a)
    pres_b = _presence(membership_b)
    rows: list[dict[str, Any]] = []

    # Presence: the design always carries the member; flag any instance that does
    # not (absent or never audited).
    if pres_a != PRESENT or pres_b != PRESENT:
        rows.append({
            "member_type": member_type,
            "member_identifier": member_identifier,
            "member_name": member_name,
            "kind": "presence",
            "attribute": None,
            "design": PRESENT,
            "instance_a": pres_a,
            "instance_b": pres_b,
            "differs": True,
        })

    # Attributes: compare effective values across the design and the instances
    # that actually carry the member. An instance that does not carry it shows its
    # presence token in the cell but does not drive the difference (the presence
    # row already covers that).
    for attr in attributes:
        design_value = design_obj.get(attr)
        a_carries = pres_a == PRESENT
        b_carries = pres_b == PRESENT
        a_value = _effective_value(membership_a, attr, design_value) if a_carries else None
        b_value = _effective_value(membership_b, attr, design_value) if b_carries else None

        present_values = [design_value]
        if a_carries:
            present_values.append(a_value)
        if b_carries:
            present_values.append(b_value)
        if all(v == present_values[0] for v in present_values):
            continue  # design and every carrying instance agree: no drift

        rows.append({
            "member_type": member_type,
            "member_identifier": member_identifier,
            "member_name": member_name,
            "kind": "attribute",
            "attribute": attr,
            "design": design_value,
            "instance_a": a_value if a_carries else pres_a,
            "instance_b": b_value if b_carries else pres_b,
            "differs": True,
        })

    return rows


def _override_attrs(*memberships: dict[str, Any] | None) -> list[str]:
    """Union of the override keys across the given memberships, sorted stably."""
    keys: set[str] = set()
    for m in memberships:
        if m and m.get("override"):
            keys.update(m["override"].keys())
    return sorted(keys)


def three_way_compare(
    session: Session,
    *,
    instance_a: str,
    instance_b: str,
    entity_identifier: str | None = None,
) -> dict[str, Any]:
    """Compute the three-way diff across the design and two instances (PI-316).

    Reads the canonical entities and fields plus each instance's membership
    snapshot and returns the differing rows grouped by entity. When
    ``entity_identifier`` is given, the comparison is scoped to that one entity
    and its fields — the per-entity drill (REQ-353); otherwise it spans every
    entity (the full scan). Only entities with at least one differing row appear.

    :returns: ``{instance_a, instance_b, scope, groups: [{entity,
        entity_identifier, rows: [...]}], row_count}``.
    """
    def index(instance: str) -> dict[tuple[str, str], dict[str, Any]]:
        return {
            (m["member_type"], m["member_identifier"]): m
            for m in membership_repo.list_memberships(
                session, instance_identifier=instance
            )
        }

    idx_a, idx_b = index(instance_a), index(instance_b)

    entities = entity_repo.list_entities(session)
    if entity_identifier is not None:
        entities = [e for e in entities if e["entity_identifier"] == entity_identifier]

    groups: list[dict[str, Any]] = []
    row_count = 0
    for ent in entities:
        eid = ent["entity_identifier"]
        rows: list[dict[str, Any]] = []

        # The entity member itself.
        rows.extend(compute_member_rows(
            member_type="entity",
            member_identifier=eid,
            member_name=ent.get("entity_name"),
            design_obj=ent,
            attributes=_override_attrs(idx_a.get(("entity", eid)), idx_b.get(("entity", eid))),
            membership_a=idx_a.get(("entity", eid)),
            membership_b=idx_b.get(("entity", eid)),
        ))

        # Its fields.
        for fld in field_repo.list_fields(session, entity_identifier=eid):
            fid = fld["field_identifier"]
            ma, mb = idx_a.get(("field", fid)), idx_b.get(("field", fid))
            rows.extend(compute_member_rows(
                member_type="field",
                member_identifier=fid,
                member_name=fld.get("field_name"),
                design_obj=fld,
                attributes=_override_attrs(ma, mb),
                membership_a=ma,
                membership_b=mb,
            ))

        if rows:
            groups.append({
                "entity": ent.get("entity_name"),
                "entity_identifier": eid,
                "rows": rows,
            })
            row_count += len(rows)

    return {
        "instance_a": instance_a,
        "instance_b": instance_b,
        "scope": entity_identifier or "all",
        "groups": groups,
        "row_count": row_count,
    }
