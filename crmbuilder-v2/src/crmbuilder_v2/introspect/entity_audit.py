"""Fast entity-only re-audit — PI-351 (REL-037 / REQ-392).

A targeted refresh of a single entity's stored audit data against one live
instance, so an operator can re-read just one entity before reconciling without
the cost of a full-instance audit. It updates the membership of the entity and
its **existing canonical members** — settings (on the entity row), fields,
relationships, layouts — to ``present`` / ``drifted`` / ``absent`` against the
live state.

This is a **refresh, not discovery**: unlike the full per-area audit
(:mod:`crmbuilder_v2.introspect.reconcile`), it never creates new canonical
records and never touches any other entity's rows — every write is keyed to one
of *this* entity's members, so it cannot mark unrelated objects absent (the
failure mode a whole-instance ``mark_absent_missing`` sweep risks). Discovering
brand-new entities/fields/relationships still requires a full audit.

The reconcilers it mirrors (drift semantics) live in ``reconcile.py``; this module
reuses their factored helpers rather than duplicating the comparison logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.introspect.audit_utils import (
    NATIVE_ENTITIES,
    EntityClass,
    FieldClass,
    classify_entity,
    classify_field,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)
from crmbuilder_v2.introspect.native_entity_types import get_base_type
from crmbuilder_v2.introspect.reconcile import (
    _LAYOUT_TYPE_TO_ESPO,
    _LINK_CARDINALITY,
    ProgressFn,
    ReconcileError,
    _audited_entity_attrs,
    _audited_field_attrs,
    _ci,
    _entity_override,
    _field_override,
    _note,
)


def _empty() -> dict[str, int]:
    return {"present": 0, "drifted": 0, "absent": 0}


def reconcile_entity_slice(
    session: Session,
    *,
    instance_identifier: str,
    entity_identifier: str,
    client: Any,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Re-audit one entity's full slice on a live instance (REQ-392).

    Refreshes membership for the entity (presence + settings) and its existing
    canonical fields, relationships, and layouts, scoped entirely to this entity.

    :returns: ``{entity, present, entity_state, fields, layouts, relationships}``
        where each member section is a ``{present, drifted, absent}`` count.
    :raises ReconcileError: if the entity is unknown or the live scopes are
        unreadable.
    """
    ent = entity_repo.get_entity(session, entity_identifier)
    if ent is None:
        raise ReconcileError(f"entity {entity_identifier} not found")
    entity_name = ent["entity_name"]
    stamp = datetime.now(UTC)

    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    # Find this entity's live scope by neutral name (live scopes are c-prefixed
    # for custom entities, natural for native).
    scope_name: str | None = None
    scope_meta: dict[str, Any] | None = None
    for name, meta in scopes.items():
        if isinstance(meta, dict) and _ci(strip_entity_c_prefix(name)) == _ci(entity_name):
            scope_name, scope_meta = name, meta
            break
    present_here = scope_name is not None
    is_native = present_here and classify_entity(scope_name, scope_meta) is EntityClass.NATIVE
    base_type = get_base_type(scope_name) if is_native else None

    out: dict[str, Any] = {"entity": entity_name, "present": present_here}

    # 1. Entity presence + collection settings (REQ-375 settings drift).
    if present_here:
        c_status, collection = client.get_collection(scope_name)
        collection = collection if (c_status == 200 and isinstance(collection, dict)) else {}
        audited = _audited_entity_attrs(scope_meta, collection)
        diff = _entity_override(ent, audited)
        entity_state = "drifted" if diff else "present"
        entity_override = diff or None
    else:
        _note(progress, f"{entity_name}: not present on this instance", "warning")
        entity_state, entity_override = "absent", None
    membership_repo.upsert_membership(
        session, instance_identifier=instance_identifier, member_type="entity",
        member_identifier=entity_identifier, state=entity_state,
        override=entity_override, last_audited_at=stamp,
    )
    out["entity_state"] = entity_state

    # 2. Fields — refresh every existing canonical field of this entity.
    live_fields: dict[str, dict[str, Any]] = {}
    if present_here:
        f_status, fields_meta = client.get_entity_field_list(scope_name)
        if f_status == 200 and isinstance(fields_meta, dict):
            for fn, fm in fields_meta.items():
                if isinstance(fm, dict) and classify_field(fn, fm, base_type) is FieldClass.CUSTOM:
                    key = _ci(strip_field_c_prefix(fn, entity_is_native=is_native))
                    live_fields[key] = fm
        else:
            _note(progress, f"{entity_name}: could not read fields (HTTP {f_status})", "warning")
    f_summary = _empty()
    for canon_f in field_repo.list_fields(session, entity_identifier=entity_identifier):
        fid = canon_f["field_identifier"]
        fm = live_fields.get(_ci(canon_f["field_name"]))
        if fm is None:
            state, override = "absent", None
        else:
            diff = _field_override(canon_f, _audited_field_attrs(fm))
            state, override = ("drifted" if diff else "present"), (diff or None)
        membership_repo.upsert_membership(
            session, instance_identifier=instance_identifier, member_type="field",
            member_identifier=fid, state=state, override=override, last_audited_at=stamp,
        )
        f_summary[state] += 1
    out["fields"] = f_summary

    # 3. Layouts — refresh every existing canonical layout of this entity.
    l_summary = _empty()
    for lay in layout_repo.list_layouts(session, entity_identifier=entity_identifier):
        lid = lay["layout_identifier"]
        ltype = lay["layout_type"]
        content = None
        if present_here and ltype in _LAYOUT_TYPE_TO_ESPO:
            l_status, body = client.get_layout(scope_name, _LAYOUT_TYPE_TO_ESPO[ltype])
            if l_status == 200 and body is not None:
                content = body
        if content is None:
            state, override = "absent", None
        elif lay.get("layout_content") != content:
            state, override = "drifted", {"layout_content": content}
        else:
            state, override = "present", None
        membership_repo.upsert_membership(
            session, instance_identifier=instance_identifier, member_type="layout",
            member_identifier=lid, state=state, override=override, last_audited_at=stamp,
        )
        l_summary[state] += 1
    out["layouts"] = l_summary

    # 4. Relationships — refresh associations this entity owns (the source side;
    # associations it is only the target of are refreshed with the owning entity).
    live_links: dict[str, dict[str, Any]] = {}
    if present_here:
        lk_status, links = client.get_all_links(scope_name)
        if lk_status == 200 and isinstance(links, dict):
            for link_name, link_meta in links.items():
                if not isinstance(link_meta, dict):
                    continue
                cardinality = _LINK_CARDINALITY.get(str(link_meta.get("type")))
                if cardinality is None:
                    continue
                if cardinality == "many_to_many":
                    assoc_name = link_meta.get("relationName") or link_name
                else:
                    assoc_name = strip_field_c_prefix(
                        link_name, entity_is_native=(scope_name in NATIVE_ENTITIES)
                    )
                live_links[_ci(assoc_name)] = {**link_meta, "_cardinality": cardinality}
        else:
            _note(progress, f"{entity_name}: could not read relationships (HTTP {lk_status})", "warning")
    a_summary = _empty()
    for assoc in association_repo.list_associations(session):
        if assoc.get("association_source_entity") != entity_identifier:
            continue
        aid = assoc["association_identifier"]
        lm = live_links.get(_ci(assoc["association_name"]))
        if lm is None:
            state, override = "absent", None
        else:
            override = (
                {"association_cardinality": lm["_cardinality"]}
                if assoc.get("association_cardinality") != lm["_cardinality"]
                else None
            )
            state = "drifted" if override else "present"
        membership_repo.upsert_membership(
            session, instance_identifier=instance_identifier, member_type="association",
            member_identifier=aid, state=state, override=override, last_audited_at=stamp,
        )
        a_summary[state] += 1
    out["relationships"] = a_summary

    return out
