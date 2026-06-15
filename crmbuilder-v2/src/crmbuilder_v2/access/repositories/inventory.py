"""Inventory read compositions — PI-188 (PRJ-027).

Cross-object reads over the canonical inventory + per-instance membership. These
compose the entity / field / association repositories with the
``instance_membership`` join; they are reads only (no writes, no change_log).

The headline is :func:`publish_plan` — the PRJ-025 publish handoff contract (§8
of the PRJ-027 architecture). Given a target instance, it returns every
canonical design object that is **not already correctly present** there
(absent, drifted, or never audited on that target), i.e. the set PRJ-025 would
generate + apply to bring the target in line with the canonical design. PRJ-025
owns the actual generation/apply; this is the machine-readable input it consumes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import filtered_tabs as filtered_tab_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.access.repositories import teams as team_repo

# (member_type, canonical-list callable, identifier key, display-name key).
_MEMBER_SOURCES = (
    ("entity", entity_repo.list_entities, "entity_identifier", "entity_name"),
    ("field", field_repo.list_fields, "field_identifier", "field_name"),
    (
        "association",
        association_repo.list_associations,
        "association_identifier",
        "association_name",
    ),
    ("layout", layout_repo.list_layouts, "layout_identifier", "layout_type"),
    ("role", role_repo.list_roles, "role_identifier", "role_name"),
    ("team", team_repo.list_teams, "team_identifier", "team_name"),
    (
        "filtered_tab",
        filtered_tab_repo.list_filtered_tabs,
        "filtered_tab_identifier",
        "filtered_tab_label",
    ),
)


def membership_summary(
    session: Session, *, instance_identifier: str
) -> dict[str, dict[str, int]]:
    """Count this instance's membership rows by member_type and state.

    :returns: ``{member_type: {present: n, drifted: n, absent: n}}`` (only the
        member types with at least one row appear).
    """
    out: dict[str, dict[str, int]] = {}
    for row in membership_repo.list_memberships(
        session, instance_identifier=instance_identifier
    ):
        bucket = out.setdefault(
            row["member_type"], {"present": 0, "drifted": 0, "absent": 0}
        )
        bucket[row["state"]] = bucket.get(row["state"], 0) + 1
    return out


def publish_plan(session: Session, *, instance_identifier: str) -> dict:
    """Compute the PRJ-025 publish handoff for a target instance.

    Returns every canonical design object not already ``present`` in the target
    — drifted, absent, or never audited there — as the set to publish. Each item
    carries the object's type, identifier, display name, the ``reason`` it needs
    publishing (``drifted`` / ``absent`` / ``never_audited``), and any recorded
    per-instance override.

    :returns: ``{target_instance, item_count, items: [...]}``.
    """
    membership_index = {
        (m["member_type"], m["member_identifier"]): m
        for m in membership_repo.list_memberships(
            session, instance_identifier=instance_identifier
        )
    }

    items: list[dict] = []
    for member_type, list_fn, id_key, name_key in _MEMBER_SOURCES:
        for obj in list_fn(session):
            member_id = obj[id_key]
            existing = membership_index.get((member_type, member_id))
            if existing is None:
                reason, override = "never_audited", None
            elif existing["state"] == "present":
                continue
            else:
                reason, override = existing["state"], existing.get("override")
            items.append(
                {
                    "member_type": member_type,
                    "member_identifier": member_id,
                    "name": obj.get(name_key),
                    "reason": reason,
                    "override": override,
                }
            )

    return {
        "target_instance": instance_identifier,
        "item_count": len(items),
        "items": items,
    }
