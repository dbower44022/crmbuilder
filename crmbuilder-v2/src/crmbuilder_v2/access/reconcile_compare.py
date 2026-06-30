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

from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import filtered_tabs as filtered_tab_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.access.repositories import teams as team_repo

#: A source carries the member on the instance (its value participates in diffs).
PRESENT = "present"
#: The instance was audited and the member is confirmed missing there.
ABSENT = "absent"
#: The member has never been audited on the instance — presence unknown.
UNKNOWN = "unknown"

#: Membership states that mean the member is carried on the instance.
_PRESENT_STATES = frozenset({"present", "drifted"})

#: Entity-level collection settings that can be reconciled in either direction
#: (REQ-375). An entity attribute row is actionable when its attribute is one of
#: these — the apply engine captures them into the design and publishes them out.
RECONCILABLE_ENTITY_SETTINGS = frozenset({
    "entity_default_sort_field",
    "entity_default_sort_direction",
    "entity_full_text_search",
    "entity_full_text_search_min_length",
    "entity_text_filter_fields",
})


def _attribute_actionable(member_type: str, attribute: str | None) -> bool:
    """Whether the apply engine can reconcile this attribute row.

    Field attributes are reconcilable (capture into the design, publish out);
    entity-level rows are reconcilable only for the collection settings the apply
    engine supports (REQ-375). Everything else is shown for visibility but not
    offered an action (REQ-358 / view-only handling).
    """
    if member_type == "field":
        return True
    if member_type == "entity":
        return attribute in RECONCILABLE_ENTITY_SETTINGS
    return False


def _presence(membership: dict[str, Any] | None) -> str:
    """Map a membership row (or its absence) to a presence token."""
    if membership is None:
        return UNKNOWN
    return PRESENT if membership["state"] in _PRESENT_STATES else ABSENT


#: The field attribute whose value is an enum/multi_enum option set (REQ-442). Its
#: value is the canonical ``field_options`` shape — a list of
#: ``{"option_value": str, "option_label": str|None, "option_order": int?}`` — and
#: it is compared order-insensitively by ``(value, effective-label)`` rather than
#: by list identity (Decision 2): option identity is the value, and a label that
#: merely echoes its value is not drift.
FIELD_OPTIONS_ATTR = "field_options"


def normalize_option_set(options: Any) -> frozenset[tuple[str, str]]:
    """Reduce an option list to the order-insensitive set used for comparison.

    Each option contributes a ``(value, effective_label)`` pair where the effective
    label defaults to the value when no explicit label is set, so a label that
    merely echoes its value is never reported as relabel drift (Decision 2). A
    non-list (``None``, a presence token, …) yields the empty set.
    """
    if not isinstance(options, (list, tuple)):
        return frozenset()
    out: set[tuple[str, str]] = set()
    for opt in options:
        if not isinstance(opt, dict):
            continue
        value = opt.get("option_value")
        if value is None:
            continue
        value = str(value)
        label = opt.get("option_label")
        effective = str(label) if label not in (None, "") else value
        out.add((value, effective))
    return frozenset(out)


def option_sets_equal(a: Any, b: Any) -> bool:
    """Whether two option lists carry the same ``(value, effective-label)`` set."""
    return normalize_option_set(a) == normalize_option_set(b)


def summarize_option_diff(design: Any, instance: Any) -> dict[str, list]:
    """Added / removed / relabeled options of ``instance`` measured against ``design``.

    Identity is the option value (Decision 2). ``added`` and ``removed`` are value
    lists (in the instance but not the design, and vice versa); ``relabeled`` is
    ``[(value, design_label, instance_label)]`` for values on both sides whose
    effective label differs.
    """
    d = dict(normalize_option_set(design))
    i = dict(normalize_option_set(instance))
    added = sorted(v for v in i if v not in d)
    removed = sorted(v for v in d if v not in i)
    relabeled = sorted((v, d[v], i[v]) for v in d.keys() & i.keys() if d[v] != i[v])
    return {"added": added, "removed": removed, "relabeled": relabeled}


def _attr_equal(attribute: str | None, a: Any, b: Any) -> bool:
    """Value equality for one attribute — option-aware for ``field_options``.

    Every attribute compares by ``==`` except the enum option set, which compares
    by its order-insensitive ``(value, effective-label)`` set (REQ-442).
    """
    if attribute == FIELD_OPTIONS_ATTR:
        return option_sets_equal(a, b)
    return a == b


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
    include_unchanged: bool = False,
) -> list[dict[str, Any]]:
    """Pure three-way comparison for one design member.

    Emits at most one **presence** row (when an instance does not carry the
    member the design defines) followed by one **attribute** row per attribute
    whose effective value differs across the design and the *present* instances.
    Returns ``[]`` when the member is present everywhere with no attribute drift.

    With ``include_unchanged`` (REQ-432), a member that is in sync everywhere
    instead yields a single **present-everywhere confirmation row**
    (``differs: False``) so the operator can verify the field exists in each
    instance, not just inspect the ones that differ. A member that *does* differ
    is unaffected — its existing presence/attribute rows already show it.

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
            "actionable": False,
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
        if all(_attr_equal(attr, v, present_values[0]) for v in present_values):
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
            "actionable": _attribute_actionable(member_type, attr),
        })

    # Show-all-values verification (REQ-432): a member present everywhere with no
    # attribute drift produced no rows above. When asked, surface it as a single
    # in-sync presence row so the operator can confirm the field exists in each
    # instance. A member that already produced diff rows is left as-is.
    if include_unchanged and not rows:
        rows.append({
            "member_type": member_type,
            "member_identifier": member_identifier,
            "member_name": member_name,
            "kind": "presence",
            "attribute": None,
            "design": PRESENT,
            "instance_a": pres_a,
            "instance_b": pres_b,
            "differs": False,
            "actionable": False,
        })

    return rows


def _override_attrs(*memberships: dict[str, Any] | None) -> list[str]:
    """Union of the override keys across the given memberships, sorted stably."""
    keys: set[str] = set()
    for m in memberships:
        if m and m.get("override"):
            keys.update(m["override"].keys())
    return sorted(keys)


#: Keys on a design member dict that are identity / bookkeeping, not comparable
#: configuration properties — excluded from the per-field property view (REQ-433).
_NON_PROPERTY_KEYS = frozenset({"id", "engagement_id"})


def _is_property_key(key: str) -> bool:
    """Whether ``key`` is a comparable property rather than identity/bookkeeping."""
    if key in _NON_PROPERTY_KEYS:
        return False
    return not key.endswith(("_identifier", "_at"))


def compute_member_properties(
    *,
    member_type: str,
    member_identifier: str,
    member_name: str | None,
    design_obj: dict[str, Any],
    membership_a: dict[str, Any] | None,
    membership_b: dict[str, Any] | None,
) -> dict[str, Any]:
    """Full property comparison for ONE member across design + two instances (REQ-433).

    Unlike :func:`compute_member_rows` — which emits only the rows that differ —
    this returns **one row per property**, so an operator can click a field and
    inspect its complete configuration side by side. The property set is the union
    of the design's keys and each instance's override keys, minus identity /
    bookkeeping keys. Each row carries the design value and each instance's
    effective value (the override when present, else the design value); an instance
    that does not carry the member shows its presence token in place of a value.
    ``differs`` flags a property whose value disagrees across the design and the
    instances that carry the member.

    :returns: ``{member_type, member_identifier, member_name, presence: {design,
        instance_a, instance_b}, rows: [...]}``.
    """
    pres_a = _presence(membership_a)
    pres_b = _presence(membership_b)
    a_carries = pres_a == PRESENT
    b_carries = pres_b == PRESENT
    override_a = (membership_a or {}).get("override") or {}
    override_b = (membership_b or {}).get("override") or {}

    keys = {k for k in design_obj if _is_property_key(k)}
    keys |= {k for k in override_a if _is_property_key(k)}
    keys |= {k for k in override_b if _is_property_key(k)}

    rows: list[dict[str, Any]] = []
    for attr in sorted(keys):
        design_value = design_obj.get(attr)
        a_eff = _effective_value(membership_a, attr, design_value) if a_carries else None
        b_eff = _effective_value(membership_b, attr, design_value) if b_carries else None
        carrying_values = [design_value]
        if a_carries:
            carrying_values.append(a_eff)
        if b_carries:
            carrying_values.append(b_eff)
        differs = not all(
            _attr_equal(attr, v, carrying_values[0]) for v in carrying_values
        )
        rows.append({
            "member_type": member_type,
            "member_identifier": member_identifier,
            "member_name": member_name,
            "kind": "attribute",
            "attribute": attr,
            "design": design_value,
            "instance_a": a_eff if a_carries else pres_a,
            "instance_b": b_eff if b_carries else pres_b,
            "differs": differs,
            "actionable": _attribute_actionable(member_type, attr),
        })

    return {
        "member_type": member_type,
        "member_identifier": member_identifier,
        "member_name": member_name,
        "presence": {"design": PRESENT, "instance_a": pres_a, "instance_b": pres_b},
        "rows": rows,
    }


#: Synthetic group for members not scoped to a single entity (roles, teams,
#: filtered tabs).
GLOBAL_GROUP = "(global)"

#: The six object-type buckets a drill groups its rows into (REQ-370). The order
#: is the display order in the entity-detail tree. "other" catches every member
#: type without a dedicated bucket — today roles/teams/filtered tabs, and the
#: view-only types (saved views, duplicate checks, workflows) when they are added.
OBJECT_TYPE_ORDER: tuple[str, ...] = (
    "fields",
    "layouts",
    "relations",
    "formulas",
    "settings",
    "other",
)

#: Field attributes that are really a derived/formula definition, bucketed under
#: "formulas" rather than "fields" (DEC-438 — ``field_formula`` is the neutral AST).
_FORMULA_FIELD_ATTRS = frozenset({"field_formula", "field_derived_result_type"})


def object_type_for(member_type: str, attribute: str | None) -> str:
    """The object-type bucket a difference row belongs under (REQ-370).

    A field's formula/derived attributes go under "formulas"; its other
    attributes (and its presence) under "fields". Associations are "relations",
    layouts "layouts", entity-level rows "settings". Everything else — roles,
    teams, filtered tabs, and any later view-only type — falls under "other".
    """
    if member_type == "field":
        return "formulas" if attribute in _FORMULA_FIELD_ATTRS else "fields"
    if member_type == "association":
        return "relations"
    if member_type == "layout":
        return "layouts"
    if member_type == "entity":
        return "settings"
    return "other"

# (member_type, canonical-list callable, identifier key, display-name key) —
# every member type the inventory tracks (mirrors inventory._MEMBER_SOURCES).
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


def _membership_index(
    session: Session, instance: str
) -> dict[tuple[str, str], dict[str, Any]]:
    """``{(member_type, member_identifier): membership_row}`` for one instance."""
    return {
        (m["member_type"], m["member_identifier"]): m
        for m in membership_repo.list_memberships(
            session, instance_identifier=instance
        )
    }


def _field_parent_map(session: Session) -> dict[str, str]:
    """``{field_identifier: parent entity_identifier}`` for entity grouping."""
    out: dict[str, str] = {}
    for ent in entity_repo.list_entities(session):
        eid = ent["entity_identifier"]
        for fld in field_repo.list_fields(session, entity_identifier=eid):
            out[fld["field_identifier"]] = eid
    return out


def _group_ids(member_type: str, obj: dict[str, Any], field_parent: dict[str, str]) -> list[str]:
    """The entity group(s) a member belongs under.

    A relationship is dual-listed under both endpoint entities (REQ-355); a field
    under its parent entity; a layout under its entity; entity members under
    themselves; roles/teams/filtered tabs under the synthetic global group.
    """
    if member_type == "entity":
        return [obj["entity_identifier"]]
    if member_type == "field":
        return [field_parent.get(obj["field_identifier"], GLOBAL_GROUP)]
    if member_type == "association":
        ids = [obj.get("association_source_entity"), obj.get("association_target_entity")]
        deduped = [i for i in dict.fromkeys(ids) if i]
        return deduped or [GLOBAL_GROUP]
    if member_type == "layout":
        return [obj.get("layout_entity_identifier") or GLOBAL_GROUP]
    return [GLOBAL_GROUP]


def _object_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Partition a group's rows into the six object-type buckets (REQ-370).

    Returns one entry per bucket that has at least one row, in
    :data:`OBJECT_TYPE_ORDER`, each carrying its rows and how many of them differ
    so the detail tree can render a collapsible section with a count.
    """
    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        bucket = object_type_for(r["member_type"], r.get("attribute"))
        by_type.setdefault(bucket, []).append(r)
    out: list[dict[str, Any]] = []
    for bucket in OBJECT_TYPE_ORDER:
        bucket_rows = by_type.get(bucket)
        if not bucket_rows:
            continue
        out.append({
            "object_type": bucket,
            "differing_count": sum(1 for r in bucket_rows if r.get("differs")),
            "rows": bucket_rows,
        })
    return out


def _existence_rollup(
    session: Session,
    *,
    idx_a: dict[tuple[str, str], dict[str, Any]],
    idx_b: dict[tuple[str, str], dict[str, Any]],
    entity_identifier: str | None,
) -> list[dict[str, Any]]:
    """One existence row per entity for the landing grid (REQ-368).

    The canonical design defines every entity, so its location is always
    :data:`PRESENT`; each instance's is derived from the stored entity-membership
    snapshot — :data:`PRESENT` (carried), :data:`ABSENT` (audited, missing), or
    :data:`UNKNOWN` (never audited). Scoped to one entity when ``entity_identifier``
    is given (the drill), else every entity, ordered by name.
    """
    out: list[dict[str, Any]] = []
    entities = entity_repo.list_entities(session)
    for ent in sorted(entities, key=lambda e: str(e.get("entity_name") or "")):
        eid = ent["entity_identifier"]
        if entity_identifier is not None and eid != entity_identifier:
            continue
        out.append({
            "entity_identifier": eid,
            "entity": ent.get("entity_name"),
            "entity_label": ent.get("entity_label"),
            "design": PRESENT,
            "instance_a": _presence(idx_a.get(("entity", eid))),
            "instance_b": _presence(idx_b.get(("entity", eid))),
        })
    return out


def three_way_compare(
    session: Session,
    *,
    instance_a: str,
    instance_b: str,
    entity_identifier: str | None = None,
    include_unchanged: bool = False,
) -> dict[str, Any]:
    """Compute the three-way diff across the design and two instances (PI-316).

    Reads every canonical member type (entities, fields, relationships, layouts,
    roles, teams, filtered tabs) plus each instance's membership snapshot and
    returns the differing rows grouped by entity. A relationship is dual-listed
    under both endpoint entities (REQ-355); roles/teams/filtered tabs fall under a
    synthetic global group. When ``entity_identifier`` is given the comparison is
    scoped to that one entity — the per-entity drill (REQ-353); otherwise it spans
    everything (the full scan). Only groups with at least one differing row appear.

    Two redesign-era additions (REL-027): ``existence`` is one row per entity with
    its presence in the design and each instance — the landing-grid source (REQ-368)
    — and each group additionally carries ``object_groups``, its rows partitioned
    into the six object-type buckets for the collapsible detail tree (REQ-370).

    :returns: ``{instance_a, instance_b, scope, existence: [...], groups: [{entity,
        entity_identifier, entity_label, rows: [...], object_groups: [...]}],
        row_count}``.
    """
    idx_a = _membership_index(session, instance_a)
    idx_b = _membership_index(session, instance_b)
    field_parent = _field_parent_map(session)
    _entities = entity_repo.list_entities(session)
    entity_name = {e["entity_identifier"]: e.get("entity_name") for e in _entities}
    # REL-025 / REQ-365: the source display label, surfaced on each group so the
    # UI can show an entity by the friendly name users see in the CRM.
    entity_label = {
        e["entity_identifier"]: e.get("entity_label") for e in _entities
    }

    grouped: dict[str, list[dict[str, Any]]] = {}
    for member_type, list_fn, id_key, name_key in _MEMBER_SOURCES:
        for obj in list_fn(session):
            mid = obj[id_key]
            ma, mb = idx_a.get((member_type, mid)), idx_b.get((member_type, mid))
            group_ids = _group_ids(member_type, obj, field_parent)
            if entity_identifier is not None:
                if entity_identifier not in group_ids:
                    continue
                group_ids = [entity_identifier]  # drill shows it under this entity
            rows = compute_member_rows(
                member_type=member_type,
                member_identifier=mid,
                member_name=obj.get(name_key),
                design_obj=obj,
                attributes=_override_attrs(ma, mb),
                membership_a=ma,
                membership_b=mb,
                include_unchanged=include_unchanged,
            )
            if not rows:
                continue
            for gid in group_ids:
                grouped.setdefault(gid, []).extend(rows)

    def _order(gid: str) -> tuple[bool, str]:
        # Entities first (alphabetical by name), the global group last.
        return (gid == GLOBAL_GROUP, str(entity_name.get(gid, gid) or gid))

    groups: list[dict[str, Any]] = []
    row_count = 0
    for gid in sorted(grouped, key=_order):
        rows = grouped[gid]
        groups.append({
            "entity": GLOBAL_GROUP if gid == GLOBAL_GROUP else entity_name.get(gid, gid),
            "entity_identifier": None if gid == GLOBAL_GROUP else gid,
            "entity_label": None if gid == GLOBAL_GROUP else entity_label.get(gid),
            "rows": rows,
            "object_groups": _object_groups(rows),
        })
        row_count += len(rows)

    return {
        "instance_a": instance_a,
        "instance_b": instance_b,
        "scope": entity_identifier or "all",
        "existence": _existence_rollup(
            session, idx_a=idx_a, idx_b=idx_b, entity_identifier=entity_identifier
        ),
        "groups": groups,
        "row_count": row_count,
    }


def member_property_compare(
    session: Session,
    *,
    instance_a: str,
    instance_b: str,
    member_type: str,
    member_identifier: str,
) -> dict[str, Any] | None:
    """Full property comparison for one member across design + two instances (REQ-433).

    Resolves the canonical design object for ``(member_type, member_identifier)``
    and each instance's membership snapshot, then delegates to
    :func:`compute_member_properties`. Returns ``None`` when the member type is
    unknown or no canonical member with that identifier exists, so the endpoint can
    answer 404.
    """
    source = next((s for s in _MEMBER_SOURCES if s[0] == member_type), None)
    if source is None:
        return None
    _, list_fn, id_key, name_key = source
    design_obj = next(
        (o for o in list_fn(session) if o.get(id_key) == member_identifier), None
    )
    if design_obj is None:
        return None
    idx_a = _membership_index(session, instance_a)
    idx_b = _membership_index(session, instance_b)
    return compute_member_properties(
        member_type=member_type,
        member_identifier=member_identifier,
        member_name=design_obj.get(name_key),
        design_obj=design_obj,
        membership_a=idx_a.get((member_type, member_identifier)),
        membership_b=idx_b.get((member_type, member_identifier)),
    )
