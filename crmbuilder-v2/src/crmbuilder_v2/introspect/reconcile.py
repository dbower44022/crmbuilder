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

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import filtered_tabs as filtered_tab_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.access.repositories import teams as team_repo
from crmbuilder_v2.access.vocab import LAYOUT_TYPES
from crmbuilder_v2.introspect.audit_utils import (
    EntityClass,
    FieldClass,
    classify_entity,
    classify_field,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)
from crmbuilder_v2.introspect.native_entity_types import get_base_type

#: A reconcile progress sink — ``(message, level)`` where ``level`` is one of
#: ``"info"`` | ``"warning"`` | ``"error"`` (PI-274 / REQ-310). Optional on every
#: reconcile function (default ``None`` = no emission, unchanged behaviour); the
#: per-area audit endpoint passes a collector so a step's otherwise-swallowed
#: sub-read failures surface in the operator's running audit log.
ProgressFn = Callable[[str, str], None]


def _note(progress: ProgressFn | None, message: str, level: str = "info") -> None:
    if progress is not None:
        progress(message, level)


class _ScopesClient(Protocol):
    """The slice of the introspection client this engine needs."""

    def get_all_scopes(self) -> tuple[int, dict | None]: ...


class _FieldsClient(_ScopesClient, Protocol):
    """Adds the per-entity field listing the field reconcile needs."""

    def get_entity_field_list(self, entity: str) -> tuple[int, dict | None]: ...


class _LinksClient(_ScopesClient, Protocol):
    """Adds the per-entity link listing the association reconcile needs."""

    def get_all_links(self, entity: str) -> tuple[int, dict | None]: ...


# EspoCRM link ``type`` -> engine-neutral cardinality (DEC-433). Only the
# "owning" side of each relationship is processed; the reciprocal
# ``belongsTo`` and the polymorphic ``belongsToParent`` / ``hasChildren`` are
# skipped (absent from this map) so each relationship reconciles once. Note the
# neutral set has no ``many_to_one`` — a ``manyToOne`` is modeled as
# ``one_to_many`` from the "one" (owning) side, which is exactly the ``hasMany``
# side we process.
_LINK_CARDINALITY: dict[str, str] = {
    "manyMany": "many_to_many",
    "hasMany": "one_to_many",
    "hasOne": "one_to_one",
}


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


def _ci(name: str | None) -> str:
    """Case-insensitive canonical match key.

    Canonical identity (DEC-431) is the neutral name, and the access layer's
    name-uniqueness is case-insensitive — so reconcile must match
    case-insensitively too, or an existing record whose name differs only in
    case (e.g. prior Phase-1 candidate data) is missed and a duplicate-create
    collides.
    """
    return (name or "").strip().lower()


class ReconcileError(RuntimeError):
    """Raised when introspection returns an unusable response."""


def _audited_entity_attrs(scope_meta: dict[str, Any]) -> dict[str, Any]:
    """Derive the neutral entity attributes the inventory compares on.

    First slice: only ``entity_track_activity`` (from the EspoCRM ``stream``
    flag). REQ-337 / PI-297 adds ``entity_tracks_activities`` from the
    EspoCRM base ``type`` (``BasePlus`` carries Activities/History/Tasks).
    Additional neutral attributes (default sort, etc.) join the comparison
    as the reconcile deepens.
    """
    return {
        "entity_track_activity": bool(scope_meta.get("stream", False)),
        "entity_tracks_activities": scope_meta.get("type") == "BasePlus",
    }


def _entity_override(canonical: dict[str, Any], audited: dict[str, Any]) -> dict:
    """Return the sparse per-attribute deviation (DEC-432), or ``{}`` if none."""
    override: dict[str, Any] = {}
    for key, audited_value in audited.items():
        if bool(canonical.get(key)) != bool(audited_value):
            override[key] = audited_value
    return override


def _has_custom_field(
    client: _FieldsClient, scope_name: str, base_type: str | None
) -> bool:
    """Whether an entity scope carries at least one custom field (PI-192).

    Used to decide if a **native** entity is "customized" — and therefore worth
    a canonical record — without creating a bare record for every native entity
    in the instance's catalog.
    """
    f_status, fields_meta = client.get_entity_field_list(scope_name)
    if f_status != 200 or not isinstance(fields_meta, dict):
        return False
    return any(
        isinstance(fm, dict)
        and classify_field(fn, fm, base_type) is FieldClass.CUSTOM
        for fn, fm in fields_meta.items()
    )


def reconcile_entities(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's entities into the canonical inventory.

    Covers **custom** entities and **native** entities that carry custom design
    (≥1 custom field — PI-192). A bare native entity (no customization) gets no
    canonical record, keeping the inventory focused on what the engagement
    actually customized. Native parents created here let the field / association
    reconcile attach to them. ``get_entity_field_list`` is used to detect a
    customized native entity, so the client must expose it.

    :returns: A summary dict ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    canonical = {
        _ci(row["entity_name"]): row for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_class = classify_entity(scope_name, scope_meta)
        if entity_class is EntityClass.CUSTOM:
            is_native = False
        elif entity_class is EntityClass.NATIVE and _has_custom_field(
            client, scope_name, get_base_type(scope_name)
        ):
            is_native = True
        else:
            continue

        summary["seen"] += 1
        neutral = strip_entity_c_prefix(scope_name)
        audited = _audited_entity_attrs(scope_meta)

        match = canonical.get(_ci(neutral))
        if match is None:
            origin = "Native EspoCRM entity" if is_native else "Discovered"
            created = entity_repo.create_entity(
                session,
                name=neutral,
                description=(
                    f"{origin} discovered by auditing instance "
                    f"{instance_identifier}."
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
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's custom fields into the canonical inventory.

    Covers custom fields on **custom** and **native** entities (PI-192) — native
    fields are classified against the parent's base type
    (``get_base_type``) so native base fields (e.g. ``website``) are skipped and
    only the custom additions reconcile. An entity with no custom fields is
    skipped (no empty native parent is created). The parent canonical entity is
    matched by neutral name (ensured if entity reconcile has not run). Same
    create → match-by-(entity, neutral name) → drift → absent → membership
    pattern as :func:`reconcile_entities`.

    :returns: A summary ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    ent_by_name = {
        _ci(row["entity_name"]): row["entity_identifier"]
        for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_class = classify_entity(scope_name, scope_meta)
        if entity_class is EntityClass.CUSTOM:
            base_type = None
        elif entity_class is EntityClass.NATIVE:
            base_type = get_base_type(scope_name)
        else:
            continue

        f_status, fields_meta = client.get_entity_field_list(scope_name)
        if f_status != 200 or not isinstance(fields_meta, dict):
            # Skip this entity's fields rather than abort the whole audit, but
            # surface it — a silently incomplete audit is the problem REQ-310
            # guards against.
            _note(
                progress,
                f"{scope_name}: could not read fields (HTTP {f_status}) — "
                f"skipped",
                "warning",
            )
            continue
        custom_fields = [
            (fn, fm)
            for fn, fm in fields_meta.items()
            if isinstance(fm, dict)
            and classify_field(fn, fm, base_type) is FieldClass.CUSTOM
        ]
        if not custom_fields:
            # Nothing to reconcile; don't create an empty (native) parent.
            continue

        neutral_entity = strip_entity_c_prefix(scope_name)
        parent_id = ent_by_name.get(_ci(neutral_entity))
        if parent_id is None:
            origin = (
                "Native EspoCRM entity"
                if entity_class is EntityClass.NATIVE
                else "Discovered"
            )
            parent = entity_repo.create_entity(
                session,
                name=neutral_entity,
                description=(
                    f"{origin} discovered by auditing instance "
                    f"{instance_identifier}."
                ),
            )
            parent_id = parent["entity_identifier"]
            ent_by_name[neutral_entity] = parent_id

        canon = {
            _ci(f["field_name"]): f
            for f in field_repo.list_fields(session, entity_identifier=parent_id)
        }

        # Only native-entity custom fields carry the platform c-prefix;
        # custom-entity fields keep their natural names (REQ-342).
        is_native = entity_class is EntityClass.NATIVE
        for field_name, field_meta in custom_fields:
            summary["seen"] += 1
            neutral_field = strip_field_c_prefix(
                field_name, entity_is_native=is_native
            )
            audited = _audited_field_attrs(field_meta)

            match = canon.get(_ci(neutral_field))
            if match is None:
                extra: dict[str, Any] = {}
                # A derived field (mapped from EspoCRM foreign/formula) requires
                # a result type (PI-197); the audit can't infer it, so default to
                # ``text`` — the override/later refinement can correct it.
                if audited["field_type"] == "derived":
                    extra["derived_result_type"] = "text"
                created = field_repo.create_field(
                    session,
                    field_belongs_to_entity_identifier=parent_id,
                    name=neutral_field,
                    description=(
                        f"Discovered by auditing instance {instance_identifier}."
                    ),
                    type=audited["field_type"],
                    required=audited["field_required"],
                    **extra,
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


def reconcile_associations(
    session: Session,
    *,
    instance_identifier: str,
    client: _LinksClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's relationships into the inventory.

    Relationships where **both** endpoints are present in the canonical
    inventory reconcile to ``association`` records (DEC-433). "Present" means
    custom, or native entities that carry custom design (PI-192) — both have
    canonical records by the time this runs. Links to uncustomized native /
    non-canonical entities are skipped (those entities have no canonical record
    to anchor the edge). Only the owning side of each relationship is processed
    (``_LINK_CARDINALITY``); ``manyMany`` is de-duplicated by its shared
    ``relationName``. Same create -> match-by-neutral-name -> drift -> absent ->
    membership pattern as the entity / field reconcile.

    :returns: A summary ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    ent_by_name = {
        _ci(row["entity_name"]): row["entity_identifier"]
        for row in entity_repo.list_entities(session)
    }
    canon = {
        _ci(a["association_name"]): a
        for a in association_repo.list_associations(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()
    seen_relation_names: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        # Read links from any canonical entity — custom or customized-native
        # (PI-192). Non-canonical scopes (uncustomized native, system) have no
        # canonical record and are skipped; endpoints likewise resolve only to
        # canonical entities.
        source_id = ent_by_name.get(_ci(strip_entity_c_prefix(scope_name)))
        if source_id is None:
            continue

        l_status, links = client.get_all_links(scope_name)
        if l_status != 200 or not isinstance(links, dict):
            _note(
                progress,
                f"{scope_name}: could not read relationships (HTTP {l_status})"
                f" — skipped",
                "warning",
            )
            continue

        for link_name, link_meta in links.items():
            if not isinstance(link_meta, dict):
                continue
            cardinality = _LINK_CARDINALITY.get(str(link_meta.get("type")))
            if cardinality is None:
                continue
            foreign_scope = link_meta.get("entity")
            if not foreign_scope:
                continue
            target_id = ent_by_name.get(_ci(strip_entity_c_prefix(foreign_scope)))
            if target_id is None:
                # Endpoint is native / not in the canonical inventory — skip.
                continue

            if cardinality == "many_to_many":
                relation_name = link_meta.get("relationName") or link_name
                if relation_name in seen_relation_names:
                    continue
                seen_relation_names.add(relation_name)
                assoc_name = relation_name
            else:
                assoc_name = link_name

            summary["seen"] += 1
            match = canon.get(_ci(assoc_name))
            if match is None:
                created = association_repo.create_association(
                    session,
                    name=assoc_name,
                    source_entity=source_id,
                    target_entity=target_id,
                    cardinality=cardinality,
                )
                canon[assoc_name] = created
                member_id = created["association_identifier"]
                summary["created"] += 1
                state, override = "present", None
            else:
                member_id = match["association_identifier"]
                override = (
                    {"association_cardinality": cardinality}
                    if match.get("association_cardinality") != cardinality
                    else {}
                )
                state = "drifted" if override else "present"
                override = override or None

            membership_repo.upsert_membership(
                session,
                instance_identifier=instance_identifier,
                member_type="association",
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
        member_type="association",
        present_member_identifiers=seen_ids,
        last_audited_at=stamp,
    )
    return summary


# Neutral LAYOUT_TYPES -> EspoCRM layout-name used by get_layout.
_LAYOUT_TYPE_TO_ESPO: dict[str, str] = {
    "detail": "detail",
    "list": "list",
    "detail_small": "detailSmall",
    "list_small": "listSmall",
    "kanban": "kanban",
    "mass_update": "massUpdate",
}


class _LayoutsClient(_ScopesClient, Protocol):
    """Adds per-(entity, type) layout fetch the layout reconcile needs."""

    def get_layout(self, entity: str, layout_type: str) -> tuple[int, Any]: ...


class _SecurityClient(Protocol):
    """The roles / teams listing the security reconcile needs."""

    def get_roles(self) -> tuple[int, dict | None]: ...
    def get_teams(self) -> tuple[int, dict | None]: ...


def reconcile_layouts(
    session: Session,
    *,
    instance_identifier: str,
    client: _LayoutsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's entity layouts into the inventory (PI-193).

    For each canonical entity (custom or customized-native), fetches each layout
    type and matches by (entity, type); content differences are recorded as a
    sparse override. Entities must already be canonical (run after
    :func:`reconcile_entities`). ``layout`` membership + absent sweep.

    :returns: A summary ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )
    ent_by_name = {
        _ci(row["entity_name"]): row["entity_identifier"]
        for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_id = ent_by_name.get(_ci(strip_entity_c_prefix(scope_name)))
        if entity_id is None:
            continue  # not a canonical entity (uncustomized native / system)
        for neutral_type in sorted(LAYOUT_TYPES):
            l_status, content = client.get_layout(
                scope_name, _LAYOUT_TYPE_TO_ESPO[neutral_type]
            )
            if l_status != 200 or content is None:
                continue
            summary["seen"] += 1
            existing = layout_repo.list_layouts(
                session, entity_identifier=entity_id, layout_type=neutral_type
            )
            match = existing[0] if existing else None
            if match is None:
                created = layout_repo.create_layout(
                    session,
                    entity_identifier=entity_id,
                    layout_type=neutral_type,
                    content=content,
                )
                member_id = created["layout_identifier"]
                summary["created"] += 1
                state, override = "present", None
            else:
                member_id = match["layout_identifier"]
                if match.get("layout_content") != content:
                    state, override = "drifted", {"layout_content": content}
                else:
                    state, override = "present", None
            membership_repo.upsert_membership(
                session, instance_identifier=instance_identifier,
                member_type="layout", member_identifier=member_id,
                state=state, override=override, last_audited_at=stamp,
            )
            seen_ids.add(member_id)
            summary[state] += 1

    summary["absent"] = membership_repo.mark_absent_missing(
        session, instance_identifier=instance_identifier, member_type="layout",
        present_member_identifiers=seen_ids, last_audited_at=stamp,
    )
    return summary


def _rows_of(body: object) -> list[dict]:
    """Extract the EspoCRM list-response rows (``{"list": [...]}``)."""
    if isinstance(body, dict) and isinstance(body.get("list"), list):
        return [r for r in body["list"] if isinstance(r, dict)]
    return []


def reconcile_roles(
    session: Session,
    *,
    instance_identifier: str,
    client: _SecurityClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's security roles into the inventory (PI-194).

    Matches by role name; scope-access matrix (EspoCRM ``data``) and system
    permissions are captured, with differences recorded as a sparse override.
    ``role`` membership + absent sweep.
    """
    status, body = client.get_roles()
    if status != 200:
        raise ReconcileError(f"get_roles returned status={status}")
    canon = {_ci(r["role_name"]): r for r in role_repo.list_roles(session)}
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for row in _rows_of(body):
        name = row.get("name")
        if not name:
            continue
        summary["seen"] += 1
        scope_access = row.get("data")
        system_permissions = {
            k: v for k, v in row.items() if "Permission" in k
        } or None
        match = canon.get(_ci(name))
        if match is None:
            created = role_repo.create_role(
                session, name=name, scope_access=scope_access,
                system_permissions=system_permissions,
            )
            canon[name] = created
            member_id = created["role_identifier"]
            summary["created"] += 1
            state, override = "present", None
        else:
            member_id = match["role_identifier"]
            override = {}
            if match.get("role_scope_access") != scope_access:
                override["role_scope_access"] = scope_access
            if match.get("role_system_permissions") != system_permissions:
                override["role_system_permissions"] = system_permissions
            state = "drifted" if override else "present"
            override = override or None
        membership_repo.upsert_membership(
            session, instance_identifier=instance_identifier, member_type="role",
            member_identifier=member_id, state=state, override=override,
            last_audited_at=stamp,
        )
        seen_ids.add(member_id)
        summary[state] += 1

    summary["absent"] = membership_repo.mark_absent_missing(
        session, instance_identifier=instance_identifier, member_type="role",
        present_member_identifiers=seen_ids, last_audited_at=stamp,
    )
    return summary


def reconcile_teams(
    session: Session,
    *,
    instance_identifier: str,
    client: _SecurityClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's security teams into the inventory (PI-194).

    Matches by team name; the description difference is recorded as a sparse
    override. ``team`` membership + absent sweep.
    """
    status, body = client.get_teams()
    if status != 200:
        raise ReconcileError(f"get_teams returned status={status}")
    canon = {_ci(t["team_name"]): t for t in team_repo.list_teams(session)}
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for row in _rows_of(body):
        name = row.get("name")
        if not name:
            continue
        summary["seen"] += 1
        description = row.get("description")
        match = canon.get(_ci(name))
        if match is None:
            created = team_repo.create_team(
                session, name=name, description=description
            )
            canon[name] = created
            member_id = created["team_identifier"]
            summary["created"] += 1
            state, override = "present", None
        else:
            member_id = match["team_identifier"]
            if (match.get("team_description") or None) != (description or None):
                state, override = "drifted", {"team_description": description}
            else:
                state, override = "present", None
        membership_repo.upsert_membership(
            session, instance_identifier=instance_identifier, member_type="team",
            member_identifier=member_id, state=state, override=override,
            last_audited_at=stamp,
        )
        seen_ids.add(member_id)
        summary[state] += 1

    summary["absent"] = membership_repo.mark_absent_missing(
        session, instance_identifier=instance_identifier, member_type="team",
        present_member_identifiers=seen_ids, last_audited_at=stamp,
    )
    return summary


class _FilteredTabsClient(_ScopesClient, Protocol):
    """Adds the per-entity report-filter listing the filtered-tab reconcile uses."""

    def list_report_filters(self, entity_type: str) -> tuple[int, dict | None]: ...


def reconcile_filtered_tabs(
    session: Session,
    *,
    instance_identifier: str,
    client: _FilteredTabsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's filtered tabs into the inventory (PI-195).

    For each canonical entity, lists its report filters (the filtered-tab
    definitions) and matches by (entity, label); filter-content differences are
    recorded as a sparse override. ``list_report_filters`` returns 404 when the
    Advanced Pack is absent — that entity is skipped, not fatal. Entities must
    already be canonical (run after :func:`reconcile_entities`). ``filtered_tab``
    membership + absent sweep.

    :returns: A summary ``{seen, created, present, drifted, absent}``.
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )
    ent_by_name = {
        _ci(row["entity_name"]): row["entity_identifier"]
        for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    seen_ids: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_id = ent_by_name.get(_ci(strip_entity_c_prefix(scope_name)))
        if entity_id is None:
            continue
        f_status, body = client.list_report_filters(scope_name)
        if f_status != 200:
            # 404 = no Advanced Pack / no filters for this entity; skip.
            continue
        for row in _rows_of(body):
            label = row.get("name")
            if not label:
                continue
            summary["seen"] += 1
            filter_content = row.get("data", row.get("filter"))
            existing = [
                ft for ft in filtered_tab_repo.list_filtered_tabs(
                    session, entity_identifier=entity_id
                )
                if _ci(ft["filtered_tab_label"]) == _ci(label)
            ]
            match = existing[0] if existing else None
            if match is None:
                created = filtered_tab_repo.create_filtered_tab(
                    session, entity_identifier=entity_id, label=label,
                    filter=filter_content,
                )
                member_id = created["filtered_tab_identifier"]
                summary["created"] += 1
                state, override = "present", None
            else:
                member_id = match["filtered_tab_identifier"]
                if match.get("filtered_tab_filter") != filter_content:
                    state, override = "drifted", {
                        "filtered_tab_filter": filter_content
                    }
                else:
                    state, override = "present", None
            membership_repo.upsert_membership(
                session, instance_identifier=instance_identifier,
                member_type="filtered_tab", member_identifier=member_id,
                state=state, override=override, last_audited_at=stamp,
            )
            seen_ids.add(member_id)
            summary[state] += 1

    summary["absent"] = membership_repo.mark_absent_missing(
        session, instance_identifier=instance_identifier,
        member_type="filtered_tab", present_member_identifiers=seen_ids,
        last_audited_at=stamp,
    )
    return summary
