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
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.introspect.audit_utils import (
    EntityClass,
    FieldClass,
    classify_entity,
    classify_field,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)


class _ScopesClient(Protocol):
    """The slice of the introspection client this engine needs."""

    def get_all_scopes(self) -> tuple[int, dict | None]: ...


class _FieldsClient(_ScopesClient, Protocol):
    """Adds the per-entity field listing the field reconcile needs."""

    def get_entity_field_list(self, entity: str) -> tuple[int, dict | None]: ...


# EspoCRM concrete field type -> engine-neutral FIELD_TYPE (DEC-431 normalize
# step). Unmapped types fall back to ``text`` — the safest lossless default for
# a first reconcile; the per-attribute override still records the audited
# specifics that matter. Kept here (not in audit_utils) because the target
# vocabulary is a V2 design concept, not a V1 audit concept.
_FIELD_TYPE_MAP: dict[str, str] = {
    "varchar": "text",
    "text": "long_text",
    "wysiwyg": "long_text",
    "bool": "boolean",
    "int": "number",
    "float": "number",
    "currency": "money",
    "date": "date",
    "datetime": "datetime",
    "datetimeOptional": "datetime",
    "enum": "enum",
    "multiEnum": "multi_enum",
    "checklist": "multi_enum",
    "array": "multi_enum",
    "url": "text",
    "phone": "text",
    "email": "text",
    "link": "reference",
    "linkOne": "reference",
    "linkParent": "reference",
    "foreign": "derived",
    "formula": "derived",
}


def _map_field_type(espo_type: object) -> str:
    """Map an EspoCRM concrete field type to an engine-neutral FIELD_TYPE."""
    return _FIELD_TYPE_MAP.get(str(espo_type), "text")


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


def _audited_field_attrs(field_meta: dict[str, Any]) -> dict[str, Any]:
    """Derive the neutral field attributes the inventory compares on.

    First field slice: neutral ``field_type`` (mapped from the concrete type)
    and ``field_required``. More neutral attributes (max length, default, …)
    join the comparison as the reconcile deepens.
    """
    return {
        "field_type": _map_field_type(field_meta.get("type")),
        "field_required": bool(field_meta.get("required", False)),
    }


def _field_override(canonical: dict[str, Any], audited: dict[str, Any]) -> dict:
    """Return the sparse per-attribute field deviation (DEC-432), or ``{}``."""
    override: dict[str, Any] = {}
    if canonical.get("field_type") != audited["field_type"]:
        override["field_type"] = audited["field_type"]
    if bool(canonical.get("field_required")) != audited["field_required"]:
        override["field_required"] = audited["field_required"]
    return override


def reconcile_fields(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
) -> dict:
    """Reconcile an instance's custom fields (on custom entities) into the inventory.

    Slice 2a: custom fields on **custom** entities. The parent canonical entity
    is matched by neutral name (ensured if entity reconcile has not run). Custom
    fields on native entities are a later slice (they need native parent
    entity records). Same create → match-by-(entity, neutral name) → drift →
    absent → membership pattern as :func:`reconcile_entities`.

    :returns: A summary ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    ent_by_name = {
        row["entity_name"]: row["entity_identifier"]
        for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        if classify_entity(scope_name, scope_meta) is not EntityClass.CUSTOM:
            continue
        neutral_entity = strip_entity_c_prefix(scope_name)
        parent_id = ent_by_name.get(neutral_entity)
        if parent_id is None:
            parent = entity_repo.create_entity(
                session,
                name=neutral_entity,
                description=(
                    f"Discovered by auditing instance {instance_identifier}."
                ),
            )
            parent_id = parent["entity_identifier"]
            ent_by_name[neutral_entity] = parent_id

        canon = {
            f["field_name"]: f
            for f in field_repo.list_fields(session, entity_identifier=parent_id)
        }

        f_status, fields_meta = client.get_entity_field_list(scope_name)
        if f_status != 200 or not isinstance(fields_meta, dict):
            # Skip this entity's fields rather than abort the whole audit.
            continue

        for field_name, field_meta in fields_meta.items():
            if not isinstance(field_meta, dict):
                continue
            if classify_field(field_name, field_meta) is not FieldClass.CUSTOM:
                continue
            summary["seen"] += 1
            neutral_field = strip_field_c_prefix(field_name)
            audited = _audited_field_attrs(field_meta)

            match = canon.get(neutral_field)
            if match is None:
                created = field_repo.create_field(
                    session,
                    field_belongs_to_entity_identifier=parent_id,
                    name=neutral_field,
                    description=(
                        f"Discovered by auditing instance {instance_identifier}."
                    ),
                    type=audited["field_type"],
                    required=audited["field_required"],
                )
                canon[neutral_field] = created
                member_id = created["field_identifier"]
                summary["created"] += 1
                state, override = "present", None
            else:
                member_id = match["field_identifier"]
                diff = _field_override(match, audited)
                state = "drifted" if diff else "present"
                override = diff or None

            membership_repo.upsert_membership(
                session,
                instance_identifier=instance_identifier,
                member_type="field",
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
        member_type="field",
        present_member_identifiers=seen_ids,
        last_audited_at=stamp,
    )
    return summary
