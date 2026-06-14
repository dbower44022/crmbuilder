"""Audit/pull reconcile engine — PI-185 (PRJ-027).

Re-homes the V1 ``audit_manager`` discovery pipeline as a
*reconcile-into-inventory* routine (§6 of the PRJ-027 architecture): introspect a
source instance, normalize its concrete CRM structure to engine-neutral form,
match it against the canonical inventory by neutral identity (DEC-431), create
canonical records that are missing, and upsert per-(object, instance) membership
rows recording present / drifted / absent with a sparse per-attribute override
(DEC-427/432). Output is DB records + membership — never YAML (YAML is a PRJ-025
publish render).

This slice covers **entities**. Fields and relationships (associations, DEC-433)
reuse this same create → match-by-neutral-name → drift → absent → membership
pattern in a later slice; they add field-type mapping + parent linking and
link-pair matching respectively.

The routine takes an injected introspection client (the
``EspoIntrospectionClient`` interface from :mod:`crmbuilder_v2.introspect`) so it
is testable with a fake and engine-agnostic at the call boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.introspect.audit_utils import (
    EntityClass,
    classify_entity,
    strip_entity_c_prefix,
)


class _ScopesClient(Protocol):
    """The slice of the introspection client this engine needs."""

    def get_all_scopes(self) -> tuple[int, dict | None]: ...


class ReconcileError(RuntimeError):
    """Raised when introspection returns an unusable response."""


def _audited_entity_attrs(scope_meta: dict[str, Any]) -> dict[str, Any]:
    """Derive the neutral entity attributes the inventory compares on.

    First slice: only ``entity_track_activity`` (from the EspoCRM ``stream``
    flag). Additional neutral attributes (default sort, etc.) join the
    comparison as the reconcile deepens.
    """
    return {"entity_track_activity": bool(scope_meta.get("stream", False))}


def _entity_override(canonical: dict[str, Any], audited: dict[str, Any]) -> dict:
    """Return the sparse per-attribute deviation (DEC-432), or ``{}`` if none."""
    override: dict[str, Any] = {}
    for key, audited_value in audited.items():
        if bool(canonical.get(key)) != bool(audited_value):
            override[key] = audited_value
    return override


def reconcile_entities(
    session: Session,
    *,
    instance_identifier: str,
    client: _ScopesClient,
) -> dict:
    """Reconcile an instance's custom entities into the canonical inventory.

    :param session: An active writable session (engagement scope set).
    :param instance_identifier: The ``INST-NNN`` being audited.
    :param client: An introspection client exposing ``get_all_scopes``.
    :returns: A summary dict ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    canonical = {
        row["entity_name"]: row for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        if classify_entity(scope_name, scope_meta) is not EntityClass.CUSTOM:
            continue
        summary["seen"] += 1
        neutral = strip_entity_c_prefix(scope_name)
        audited = _audited_entity_attrs(scope_meta)

        match = canonical.get(neutral)
        if match is None:
            created = entity_repo.create_entity(
                session,
                name=neutral,
                description=(
                    f"Discovered by auditing instance {instance_identifier}."
                ),
                track_activity=audited["entity_track_activity"],
            )
            canonical[neutral] = created
            member_id = created["entity_identifier"]
            summary["created"] += 1
            state, override = "present", None
        else:
            member_id = match["entity_identifier"]
            diff = _entity_override(match, audited)
            state = "drifted" if diff else "present"
            override = diff or None

        membership_repo.upsert_membership(
            session,
            instance_identifier=instance_identifier,
            member_type="entity",
            member_identifier=member_id,
            state=state,
            override=override,
            last_audited_at=stamp,
        )
        seen_ids.add(member_id)
        summary[state] += 1

    summary["absent"] = membership_repo.mark_absent_missing(
        session,
        instance_identifier=instance_identifier,
        member_type="entity",
        present_member_identifiers=seen_ids,
        last_audited_at=stamp,
    )
    return summary
