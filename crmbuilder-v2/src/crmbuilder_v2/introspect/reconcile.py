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
from crmbuilder_v2.access.repositories import (
    association_mapping as association_mapping_repo,
)
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import (
    field_mapping as field_mapping_repo,
)
from crmbuilder_v2.access.repositories import (
    field_permission_rule as field_permission_rule_repo,
)
from crmbuilder_v2.access.repositories import filtered_tabs as filtered_tab_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.repositories import mapping_candidate as candidate_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.access.repositories import source_mapping as source_mapping_repo
from crmbuilder_v2.access.repositories import (
    source_mapping_targets as source_mapping_targets_repo,
)
from crmbuilder_v2.access.repositories import teams as team_repo
from crmbuilder_v2.access.vocab import (
    DERIVED_RESULT_TYPES,
    INSTANCE_MEMBERSHIP_MEMBER_TYPES,
    LAYOUT_TYPES,
)
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

    def get_collection(self, entity: str) -> tuple[int, dict | None]: ...

    def get_i18n(self, language: str = ...) -> tuple[int, dict]: ...

    # PI-378 — resolving a foreign field's mirrored result type needs the parent
    # entity's links (link -> target entity).
    def get_all_links(self, entity: str) -> tuple[int, dict | None]: ...


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
    # A foreign field mirrors a scalar from a linked record — its own neutral
    # kind (REQ-435 / PI-374), no longer collapsed into ``derived`` (which is a
    # computed/formula value) and no longer surfacing as text.
    "foreign": "foreign",
    "formula": "derived",
}


def is_unmapped_field_type(espo_type: object) -> bool:
    """Whether the engine has no neutral mapping for this EspoCRM field type.

    Such a type is surfaced for human review rather than silently stored as text
    (REQ-437 / PI-374): the caller records it in the reconcile summary and notes
    it on the field so unmapped kinds stay visible.
    """
    return str(espo_type) not in _FIELD_TYPE_MAP


def _map_field_type(espo_type: object) -> str:
    """Map an EspoCRM concrete field type to an engine-neutral FIELD_TYPE.

    An unrecognised type falls back to ``text`` so the field is still recorded,
    but :func:`is_unmapped_field_type` lets the reconcile layer flag it for review
    rather than letting the fallback pass silently (REQ-437)."""
    return _FIELD_TYPE_MAP.get(str(espo_type), "text")


def _resolve_foreign_result_types(
    session: Session,
    client: _FieldsClient,
    pending: list[tuple[str, str, str, str]],
) -> None:
    """Derive each foreign field's mirrored result type from the linked field (REQ-436).

    ``pending`` is ``[(field_identifier, parent_entity, link, target_field)]``. For
    each, resolve the entity the ``link`` points to (from the parent's live links),
    look up the ``target_field`` on that entity, map its EspoCRM type to a neutral
    result type, and record it on the foreign field. Resolution is skipped — leaving
    the result type unset — whenever the link or the target field does not resolve,
    or the mirrored type is not a scalar result type (never guessed by name-match).
    Links and per-entity field lists are cached so each entity is read at most once.
    """
    links_by_entity: dict[str, dict] = {}
    fields_by_entity: dict[str, dict] = {}
    for member_id, parent_entity, link, target_field in pending:
        if parent_entity not in links_by_entity:
            st, lk = client.get_all_links(parent_entity)
            links_by_entity[parent_entity] = lk if st == 200 and isinstance(lk, dict) else {}
        target_entity = (links_by_entity[parent_entity].get(link) or {}).get("entity")
        if not target_entity:
            continue
        if target_entity not in fields_by_entity:
            st, fm = client.get_entity_field_list(target_entity)
            fields_by_entity[target_entity] = fm if st == 200 and isinstance(fm, dict) else {}
        target_meta = fields_by_entity[target_entity].get(target_field)
        if not isinstance(target_meta, dict):
            continue
        result_type = _map_field_type(target_meta.get("type"))
        if result_type in DERIVED_RESULT_TYPES:
            field_repo.patch_field(session, member_id, derived_result_type=result_type)


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


class _AreaMembershipWriter:
    """Per-area membership write boundary (REQ-394 §3.1 / §3.4, WTK-268).

    Binds one audit pass to exactly one ``member_type`` — its audit area — so the
    pass can only ever create, update, or sweep ``instance_membership`` rows of
    its own area, never a row another pass of the same audit owns. The
    ``member_type`` scoping that ``upsert_membership`` (keyed on
    ``(instance, member_type, member_identifier)``) and ``mark_absent_missing``
    (``WHERE member_type = ?``) already apply is the mechanism; routing every
    per-pass write through one writer that fixes the area at construction makes
    that scoping a **binding contract** rather than a literal each of the ~10
    call sites repeats and could get wrong.

    The writer also accumulates the present/drifted identifiers it upserts, so a
    pass cannot forget to register a row before the absent sweep — the sweep's
    "seen" set is exactly what this writer wrote. The inventory after an audit is
    therefore the union of disjoint per-area slices (§3.4): two passes of the
    same audit can never touch the same row, and a partial audit (some areas
    read, others not) leaves every unwritten area's slice intact.

    This writer governs **what slice** a pass may touch (§3.4) and, since
    WTK-269, carries the pass's **read-success signal** into the absent sweep
    (§3.2). A pass that did not successfully read its area — a read that failed,
    was inconclusive, or was never attempted — constructs the writer with
    ``read_succeeded=False`` (or flips it via :meth:`mark_read_failed`), and its
    :meth:`sweep_absent` becomes a hard no-op: the area's existing ``present`` /
    ``drifted`` rows are preserved unchanged rather than wiped from a
    non-observation (the REL-038 defect). Absence is therefore only ever a
    positive observation — the live area was read successfully and the object was
    confirmed missing from it (REQ-394's "set absent only when the instance was
    read successfully and the object is absent from it"). The signal threads
    through to :func:`instance_membership.mark_absent_missing`, the storage-layer
    gate WTK-267 added; a successful read that genuinely enumerated an empty area
    still sweeps (``read_succeeded=True`` with an empty seen set).
    """

    def __init__(
        self,
        session: Session,
        *,
        instance_identifier: str,
        member_type: str,
        last_audited_at: datetime,
        read_succeeded: bool = True,
    ) -> None:
        if member_type not in INSTANCE_MEMBERSHIP_MEMBER_TYPES:
            # Fail the pass at construction rather than let a typo'd area write
            # against (or sweep) the wrong slice.
            raise ReconcileError(
                f"unknown audit area member_type {member_type!r}"
            )
        self._session = session
        self._instance_identifier = instance_identifier
        self._member_type = member_type
        self._stamp = last_audited_at
        self._read_succeeded = read_succeeded
        self._seen: set[str] = set()

    def mark_read_failed(self) -> None:
        """Record that this area's live read did not succeed.

        Disarms the absent sweep (it becomes a no-op) so a failed or inconclusive
        read preserves the area's existing membership rather than inferring
        absence from it. For a pass that determines read success only mid-pass.
        """
        self._read_succeeded = False

    def upsert(
        self,
        member_identifier: str,
        state: str,
        override: dict | None = None,
    ) -> None:
        """Upsert one present/drifted row in this writer's area and mark it seen."""
        membership_repo.upsert_membership(
            self._session,
            instance_identifier=self._instance_identifier,
            member_type=self._member_type,
            member_identifier=member_identifier,
            state=state,
            override=override,
            last_audited_at=self._stamp,
        )
        self._seen.add(member_identifier)

    def sweep_absent(self) -> int:
        """Flag this area's rows not seen in this pass as ``absent``; return the count.

        No-resolution preservation (REQ-394 §3.2, WTK-269). The sweep is gated on
        this writer's read-success signal: when ``read_succeeded`` is ``False``
        (the area's live read failed, was inconclusive, or was never attempted)
        the sweep is a hard **no-op** — no row is touched and ``0`` is returned —
        so a pass that resolved nothing because it could not read the area leaves
        that area's existing ``present`` / ``drifted`` rows unchanged rather than
        wiping them from a non-observation (the REL-038 defect). A successful read
        that genuinely enumerated an empty area still sweeps (an empty "seen" set
        with ``read_succeeded=True``), so legitimate absence is recorded.

        The signal is threaded to :func:`instance_membership.mark_absent_missing`,
        the storage-layer gate (WTK-267), so absence is only ever a positive
        observation: the live area was read successfully and the row was confirmed
        missing from the resolved present set.
        """
        return membership_repo.mark_absent_missing(
            self._session,
            instance_identifier=self._instance_identifier,
            member_type=self._member_type,
            present_member_identifiers=self._seen,
            last_audited_at=self._stamp,
            read_succeeded=self._read_succeeded,
        )


# Audited entity attributes compared as booleans (the rest compare by value —
# the sort field/direction strings, the text-filter list, the FTS min length).
_ENTITY_BOOL_ATTRS = frozenset(
    {
        "entity_track_activity",
        "entity_tracks_activities",
        "entity_full_text_search",
    }
)


def _audited_entity_attrs(
    scope_meta: dict[str, Any],
    collection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive the neutral entity attributes the inventory compares on.

    ``entity_track_activity`` comes from the EspoCRM ``stream`` flag and
    ``entity_tracks_activities`` (REQ-337 / PI-297) from the base ``type``
    (``BasePlus`` carries Activities/History/Tasks). REQ-340 / PI-300 adds the
    five collection-search settings from the ``entityDefs.{Entity}.collection``
    block (``orderBy``, ``order``, ``textFilterFields``, ``fullTextSearch``,
    ``fullTextSearchMinLength``) — passed in via ``collection`` since the
    collection block is not part of ``scope_meta``.
    """
    coll = collection if isinstance(collection, dict) else {}
    order_by = coll.get("orderBy")
    order = coll.get("order")
    text_filter_fields = coll.get("textFilterFields")
    fts_min = coll.get("fullTextSearchMinLength")
    return {
        "entity_track_activity": bool(scope_meta.get("stream", False)),
        "entity_tracks_activities": scope_meta.get("type") == "BasePlus",
        "entity_default_sort_field": (
            order_by if isinstance(order_by, str) and order_by else None
        ),
        "entity_default_sort_direction": (
            order if isinstance(order, str) and order else None
        ),
        "entity_text_filter_fields": (
            text_filter_fields if isinstance(text_filter_fields, list) else None
        ),
        "entity_full_text_search": bool(coll.get("fullTextSearch", False)),
        "entity_full_text_search_min_length": (
            fts_min if isinstance(fts_min, int) and not isinstance(fts_min, bool)
            else None
        ),
    }


def _entity_override(canonical: dict[str, Any], audited: dict[str, Any]) -> dict:
    """Return the sparse per-attribute deviation (DEC-432), or ``{}`` if none.

    Boolean flags compare by truthiness; the value-carrying attributes (sort
    field/direction, text-filter list, FTS min length) compare by equality so a
    ``None`` audited value does not falsely equal a non-empty canonical one.
    """
    override: dict[str, Any] = {}
    for key, audited_value in audited.items():
        if key in _ENTITY_BOOL_ATTRS:
            if bool(canonical.get(key)) != bool(audited_value):
                override[key] = audited_value
        elif canonical.get(key) != audited_value:
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


#: Instance roles whose audit is candidate-gated. Only a purely external
#: ``source`` migrating in from a separate system is candidate-gated (DEC-648,
#: narrowed by REQ-393 / WTK-256): no design object yet corresponds to its live
#: objects. ``both`` is a deployed-to instance whose live structure maps to the
#: design by neutral name, so it takes the drift path with ``target`` — never
#: candidate-gating, which would clobber its inventory (the 06-26 CBM defect).
_SOURCE_ROLES: frozenset[str] = frozenset({"source"})


def _audit_is_source(session: Session, instance_identifier: str) -> bool:
    """Whether this instance's audit is candidate-gated (``source`` role only).

    DEC-648, narrowed by REQ-393 / WTK-256 — the instance role is the switch: a
    ``source`` audit (a purely external system migrating in) runs the
    candidate-gated mapping pass; a ``target`` **or** ``both`` audit keeps the
    present/drifted/absent drift reconcile, matching live objects to design by
    neutral name with no ``source_mapping`` required. A missing instance defaults
    to the drift path (the caller resolves the 404 separately).
    """
    rec = instances_repo.get_instance(session, instance_identifier)
    return bool(rec) and rec.get("instance_role") in _SOURCE_ROLES


def _live_decision(mappings: list[dict]) -> tuple[str, dict | None]:
    """Classify the live mapping decision for one source object's mappings.

    Given every non-deleted ``source_mapping`` / ``field_mapping`` row for a
    single source name, returns the active decision (DEC-649): ``resolved`` (a
    confirmed non-rejected decision → reconcile membership), ``rejected`` (a
    confirmed exclusion → skip), ``pending`` (an unresolved decision in flight →
    neither reconcile nor re-candidate), or ``none`` (surface a candidate). A
    ``superseded`` row is ignored; ``stale`` is treated as ``pending`` (it awaits
    human re-resolution, so it is neither reconciled nor re-surfaced).
    """
    resolved = [m for m in mappings if m["status"] == "resolved"]
    if resolved:
        m = resolved[-1]
        return ("rejected" if m["decision_type"] == "rejected" else "resolved", m)
    in_flight = [m for m in mappings if m["status"] in ("unresolved", "stale")]
    if in_flight:
        return ("pending", in_flight[-1])
    return ("none", None)


def reconcile_entities(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's entities, branching on the instance role (DEC-648).

    A ``source`` audit runs the **candidate-gated** pass
    (:func:`_reconcile_entities_candidate_gated`): no canonical object is created
    or marked present by name; every undecided source entity becomes a
    ``mapping_candidate`` and only a human-resolved ``source_mapping`` drives
    membership. A ``target`` or ``both`` audit runs the unchanged drift reconcile
    (:func:`_reconcile_entities_drift`).
    """
    if _audit_is_source(session, instance_identifier):
        return _reconcile_entities_candidate_gated(
            session,
            instance_identifier=instance_identifier,
            client=client,
            progress=progress,
        )
    return _reconcile_entities_drift(
        session,
        instance_identifier=instance_identifier,
        client=client,
        progress=progress,
    )


def _reconcile_entities_drift(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Drift reconcile (target-role audit) — the unchanged PI-185/192 path.

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

    # REL-025 / REQ-364: entity display labels live in the source's i18n (not in
    # entityDefs), keyed by the concrete scope name. Fetch once and capture the
    # singular/plural label per entity. A non-200 / missing i18n leaves labels
    # empty (the audit still reconciles structure).
    _, i18n = client.get_i18n()
    _glob = (i18n or {}).get("Global", {}) if isinstance(i18n, dict) else {}
    scope_labels = _glob.get("scopeNames") if isinstance(_glob.get("scopeNames"), dict) else {}
    scope_labels_plural = (
        _glob.get("scopeNamesPlural")
        if isinstance(_glob.get("scopeNamesPlural"), dict)
        else {}
    )

    canonical = {
        _ci(row["entity_name"]): row for row in entity_repo.list_entities(session)
    }
    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="entity",
        last_audited_at=stamp,
    )

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
        # The collection-search settings (REQ-340 / PI-300) live in the
        # ``entityDefs.{Entity}.collection`` block, not in ``scope_meta`` — fetch
        # them per entity. A non-200 or non-dict response is treated as empty.
        c_status, collection = client.get_collection(scope_name)
        if c_status != 200 or not isinstance(collection, dict):
            collection = {}
        audited = _audited_entity_attrs(scope_meta, collection)

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
                tracks_activities=audited["entity_tracks_activities"],
                default_sort_field=audited["entity_default_sort_field"],
                default_sort_direction=audited["entity_default_sort_direction"],
                text_filter_fields=audited["entity_text_filter_fields"],
                full_text_search=audited["entity_full_text_search"],
                full_text_search_min_length=(
                    audited["entity_full_text_search_min_length"]
                ),
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

        # REL-025 / REQ-364: sync the source display label onto the canonical
        # record (descriptive, not a drift attribute). Patch only when the source
        # has a label that differs from the stored value, so a label is never
        # cleared and unchanged labels are no-ops.
        current = canonical.get(_ci(neutral), {})
        label = scope_labels.get(scope_name)
        label_plural = scope_labels_plural.get(scope_name)
        label_patch: dict[str, Any] = {}
        if label and label != current.get("entity_label"):
            label_patch["label"] = label
        if label_plural and label_plural != current.get("entity_label_plural"):
            label_patch["label_plural"] = label_plural
        if label_patch:
            entity_repo.patch_entity(session, member_id, **label_patch)

        writer.upsert(member_id, state, override)
        summary[state] += 1

    summary["absent"] = writer.sweep_absent()
    return summary


def _reconcile_entities_candidate_gated(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Candidate-gated entity reconcile (source audit) — REQ-300 / DEC-649.

    No canonical entity is created or marked present by name. For each discovered
    source entity: a **resolved** ``source_mapping`` drives present/drifted
    membership against its target canonical entity(ies); a **rejected** mapping is
    skipped (a confirmed exclusion); an **in-flight** (unresolved/stale) mapping is
    left alone; an **undecided** entity becomes an idempotent
    ``mapping_candidate(entity)`` carrying a name-match suggestion. A resolved
    mapping whose source entity is gone this audit is flipped ``stale,
    source_changed`` (DEC-652).

    :returns: ``{seen, created, present, drifted, absent, candidates}`` — ``created``
        is always 0 (canonical objects are never auto-created here).
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    entities = entity_repo.list_entities(session)
    canonical_by_name = {_ci(r["entity_name"]): r for r in entities}
    canonical_by_id = {r["entity_identifier"]: r for r in entities}

    mappings_by_source: dict[str, list[dict]] = {}
    for m in source_mapping_repo.list_source_mappings(
        session, instance_identifier=instance_identifier
    ):
        mappings_by_source.setdefault(m["source_entity_name"], []).append(m)

    pending_candidate_sources = {
        c["source_entity_name"]
        for c in candidate_repo.list_candidates(
            session,
            instance_identifier=instance_identifier,
            candidate_type="entity",
            resolved=False,
        )
    }

    stamp = datetime.now(UTC)
    summary = {
        "seen": 0, "created": 0, "present": 0, "drifted": 0,
        "absent": 0, "candidates": 0,
    }
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="entity",
        last_audited_at=stamp,
    )
    seen_source_names: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_class = classify_entity(scope_name, scope_meta)
        if entity_class is EntityClass.CUSTOM:
            pass
        elif entity_class is EntityClass.NATIVE and _has_custom_field(
            client, scope_name, get_base_type(scope_name)
        ):
            pass
        else:
            continue

        summary["seen"] += 1
        source_name = scope_name  # the source's own name — what the auditor found
        seen_source_names.add(source_name)

        kind, mapping = _live_decision(mappings_by_source.get(source_name, []))
        if kind in ("rejected", "pending"):
            # rejected = confirmed exclusion; pending = decision in flight. Neither
            # writes membership nor re-surfaces a candidate.
            continue
        if kind == "resolved":
            c_status, collection = client.get_collection(scope_name)
            if c_status != 200 or not isinstance(collection, dict):
                collection = {}
            audited = _audited_entity_attrs(scope_meta, collection)
            for tgt in source_mapping_targets_repo.list_targets(
                session,
                source_mapping_identifier=mapping["source_mapping_identifier"],
            ):
                member_id = tgt["entity_identifier"]
                diff = _entity_override(canonical_by_id.get(member_id, {}), audited)
                state = "drifted" if diff else "present"
                writer.upsert(member_id, state, diff or None)
                summary[state] += 1
            continue

        # kind == "none" — undecided source entity → idempotent candidate.
        if source_name in pending_candidate_sources:
            continue
        match = canonical_by_name.get(_ci(strip_entity_c_prefix(scope_name)))
        confidence = "high" if match else None
        basis = (
            f"source entity {source_name!r} name-matches canonical entity "
            f"{match['entity_name']!r} ({match['entity_identifier']})"
            if match
            else None
        )
        candidate_repo.create_candidate(
            session,
            instance_identifier=instance_identifier,
            candidate_type="entity",
            source_entity_name=source_name,
            suggestion_confidence=confidence,
            suggestion_basis=basis,
        )
        pending_candidate_sources.add(source_name)
        summary["candidates"] += 1

    # Source-side staleness (DEC-652): a resolved entity mapping whose source
    # entity vanished this audit is flipped stale; the absent sweep then marks its
    # canonical membership absent.
    for source_name, mappings in mappings_by_source.items():
        if source_name in seen_source_names:
            continue
        kind, mapping = _live_decision(mappings)
        if kind == "resolved":
            source_mapping_repo.mark_stale(
                session,
                mapping["source_mapping_identifier"],
                reason="source_changed",
                severity="high",
            )

    summary["absent"] = writer.sweep_absent()
    return summary


# Boolean field attributes compare by truthiness (a ``None`` canonical value reads
# as False). The value-carrying attributes use forward asymmetry — see
# :func:`_field_override`.
_FIELD_BOOL_ATTRS: frozenset[str] = frozenset({"field_required", "field_read_only"})

# Value-carrying field attributes the canonical ``Field`` record can hold and the
# audit can read from EspoCRM field metadata. Each maps a neutral attribute name
# to its concrete EspoCRM ``entityDefs`` field-metadata key.
_FIELD_VALUE_ATTR_KEYS: dict[str, str] = {
    "field_max_length": "maxLength",
    "field_default_value": "default",
    "field_min": "min",
    "field_max": "max",
}


def _audited_field_attrs(field_meta: dict[str, Any]) -> dict[str, Any]:
    """Derive the neutral field attributes the inventory compares on (PI-314).

    Covers neutral ``field_type`` (mapped from the concrete type), the boolean
    flags ``field_required`` and ``field_read_only``, and the value-carrying
    settings the canonical ``Field`` record stores — ``field_max_length``,
    ``field_default_value``, ``field_min``, ``field_max`` — read from the concrete
    EspoCRM field metadata. This is the value-level substrate the three-way
    reconciliation diff reads (REQ-357).
    """
    attrs: dict[str, Any] = {
        "field_type": _map_field_type(field_meta.get("type")),
        "field_required": bool(field_meta.get("required", False)),
        "field_read_only": bool(field_meta.get("readOnly", False)),
    }
    for neutral, espo_key in _FIELD_VALUE_ATTR_KEYS.items():
        attrs[neutral] = field_meta.get(espo_key)
    return attrs


def _field_override(canonical: dict[str, Any], audited: dict[str, Any]) -> dict:
    """Return the sparse per-attribute field deviation (DEC-432), or ``{}``.

    ``field_type`` always compares (the canonical record always carries one) and
    the boolean flags compare by truthiness. The value-carrying attributes use
    **forward asymmetry**: a deviation is recorded only when the canonical design
    declares a non-``None`` value that the instance contradicts. This mirrors the
    field-comparator rule used elsewhere and keeps platform defaults the design
    never set (e.g. a varchar's implicit ``maxLength``) from producing false
    drift on every field.
    """
    override: dict[str, Any] = {}
    if canonical.get("field_type") != audited["field_type"]:
        override["field_type"] = audited["field_type"]
    for key in _FIELD_BOOL_ATTRS:
        if bool(canonical.get(key)) != bool(audited.get(key)):
            override[key] = audited.get(key)
    for key in _FIELD_VALUE_ATTR_KEYS:
        canonical_value = canonical.get(key)
        if canonical_value is not None and canonical_value != audited.get(key):
            override[key] = audited.get(key)
    return override


def reconcile_fields(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's custom fields, branching on the instance role.

    A ``source`` audit runs the **candidate-gated** pass
    (:func:`_reconcile_fields_candidate_gated`); a ``target`` or ``both`` audit runs the
    unchanged drift reconcile (:func:`_reconcile_fields_drift`). See DEC-648.
    """
    if _audit_is_source(session, instance_identifier):
        return _reconcile_fields_candidate_gated(
            session,
            instance_identifier=instance_identifier,
            client=client,
            progress=progress,
        )
    return _reconcile_fields_drift(
        session,
        instance_identifier=instance_identifier,
        client=client,
        progress=progress,
    )


def _reconcile_fields_drift(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Drift reconcile (target-role audit) — the unchanged PI-185/192 field path.

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
    # REL-025 / REQ-366: field display labels live in i18n under
    # ``<Entity>.fields.<field>`` (per-entity), falling back to
    # ``Global.fields.<field>``. Fetch once; look up by concrete scope + field.
    _, _i18n = client.get_i18n()
    _i18n = _i18n if isinstance(_i18n, dict) else {}
    _global_field_labels = (_i18n.get("Global") or {}).get("fields") or {}

    def _field_label(scope: str, field: str) -> str | None:
        per_entity = (_i18n.get(scope) or {}).get("fields")
        if isinstance(per_entity, dict) and per_entity.get(field):
            return per_entity[field]
        return _global_field_labels.get(field) if isinstance(_global_field_labels, dict) else None

    stamp = datetime.now(UTC)
    summary = {"seen": 0, "created": 0, "present": 0, "drifted": 0, "absent": 0}
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="field",
        last_audited_at=stamp,
    )
    # PI-378 (REQ-436): foreign fields whose mirrored result type is resolved in a
    # post-pass — (field_identifier, parent EspoCRM entity, link, target field).
    foreign_pending: list[tuple[str, str, str, str]] = []

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
            # REQ-437: a source field kind the engine cannot map falls back to
            # ``text`` but is surfaced for review, not silently misrepresented.
            if is_unmapped_field_type(field_meta.get("type")):
                summary.setdefault("unmapped_field_types", []).append(
                    {"field": neutral_field, "source_type": str(field_meta.get("type"))}
                )

            match = canon.get(_ci(neutral_field))
            if match is None:
                extra: dict[str, Any] = {}
                # A ``derived`` (formula) field requires a result type the audit
                # cannot infer (PI-197) — default to ``text``, correctable later.
                # A ``foreign`` field is NOT defaulted to text (REQ-436): its
                # mirrored value-type stays unset until known, never assumed.
                if audited["field_type"] == "derived":
                    extra["derived_result_type"] = "text"
                description = f"Discovered by auditing instance {instance_identifier}."
                if is_unmapped_field_type(field_meta.get("type")):
                    description += (
                        f" Source field kind {field_meta.get('type')!r} is not "
                        f"recognised by the engine and was recorded as text — review."
                    )
                created = field_repo.create_field(
                    session,
                    field_belongs_to_entity_identifier=parent_id,
                    name=neutral_field,
                    description=description,
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

            # REL-025 / REQ-366: sync the source display label onto the canonical
            # field (descriptive, not a drift attribute); patch only when present
            # and changed, so a label is never cleared and unchanged is a no-op.
            cur = canon.get(_ci(neutral_field), {})
            label = _field_label(scope_name, field_name)
            if label and label != cur.get("field_label"):
                field_repo.patch_field(session, member_id, label=label)

            # PI-374 (REQ-435): record/refresh a foreign field's mirror coordinates
            # — the link and the field on the linked entity — whether it was just
            # created or already existed, so it round-trips to deploy. Patch only on
            # change so an unchanged re-audit is a no-op.
            if audited["field_type"] == "foreign":
                link = field_meta.get("link")
                target = field_meta.get("field")
                if link and link != cur.get("field_foreign_link"):
                    field_repo.patch_field(session, member_id, foreign_link=link)
                if target and target != cur.get("field_foreign_target"):
                    field_repo.patch_field(session, member_id, foreign_target=target)
                # PI-378 (REQ-436): resolve the mirrored result type after the scan
                # (the target may live on an entity not yet seen).
                if link and target:
                    foreign_pending.append((member_id, scope_name, link, target))

            writer.upsert(member_id, state, override)
            summary[state] += 1

    _resolve_foreign_result_types(session, client, foreign_pending)
    summary["absent"] = writer.sweep_absent()
    return summary


def _reconcile_fields_candidate_gated(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Candidate-gated field reconcile (source audit) — REQ-300 / DEC-651.

    Fields surface only for a source entity that is **mapped** (a resolved
    ``source_mapping``); fields of an undecided / rejected / in-flight entity are
    **deferred** (fractal multi-pass — a field candidate waits until its parent
    entity is mapped). For a mapped entity, a source custom field matched by
    neutral name against the mapping's target canonical entity(ies) drives
    present/drifted field membership; an unmatched source field becomes an
    idempotent ``mapping_candidate(field)``. A resolved ``field_mapping`` whose
    source field is gone this audit is flipped ``stale, source_changed`` (DEC-652).

    :returns: ``{seen, created, present, drifted, absent, candidates}`` — ``created``
        is always 0 (canonical objects are never auto-created here).
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    mappings_by_source: dict[str, list[dict]] = {}
    for m in source_mapping_repo.list_source_mappings(
        session, instance_identifier=instance_identifier
    ):
        mappings_by_source.setdefault(m["source_entity_name"], []).append(m)

    pending_field_candidates = {
        (c["source_entity_name"], c["source_field_name"])
        for c in candidate_repo.list_candidates(
            session,
            instance_identifier=instance_identifier,
            candidate_type="field",
            resolved=False,
        )
    }

    stamp = datetime.now(UTC)
    summary = {
        "seen": 0, "created": 0, "present": 0, "drifted": 0,
        "absent": 0, "candidates": 0,
    }
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="field",
        last_audited_at=stamp,
    )

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_class = classify_entity(scope_name, scope_meta)
        if entity_class is EntityClass.CUSTOM:
            base_type, is_native = None, False
        elif entity_class is EntityClass.NATIVE:
            base_type, is_native = get_base_type(scope_name), True
        else:
            continue

        kind, mapping = _live_decision(mappings_by_source.get(scope_name, []))
        if kind != "resolved":
            continue  # defer fields until the parent entity is mapped (DEC-651)

        f_status, fields_meta = client.get_entity_field_list(scope_name)
        if f_status != 200 or not isinstance(fields_meta, dict):
            _note(
                progress,
                f"{scope_name}: could not read fields (HTTP {f_status}) — skipped",
                "warning",
            )
            continue
        custom_fields = [
            (fn, fm)
            for fn, fm in fields_meta.items()
            if isinstance(fm, dict)
            and classify_field(fn, fm, base_type) is FieldClass.CUSTOM
        ]

        # Canonical fields across the mapping's target entities, by neutral name.
        canon_fields: dict[str, dict] = {}
        for tgt in source_mapping_targets_repo.list_targets(
            session, source_mapping_identifier=mapping["source_mapping_identifier"]
        ):
            for f in field_repo.list_fields(
                session, entity_identifier=tgt["entity_identifier"]
            ):
                canon_fields.setdefault(_ci(f["field_name"]), f)

        seen_source_fields: set[str] = set()
        for field_name, field_meta in custom_fields:
            summary["seen"] += 1
            seen_source_fields.add(field_name)
            neutral_field = strip_field_c_prefix(
                field_name, entity_is_native=is_native
            )
            match = canon_fields.get(_ci(neutral_field))
            if match is not None:
                member_id = match["field_identifier"]
                diff = _field_override(match, _audited_field_attrs(field_meta))
                state = "drifted" if diff else "present"
                writer.upsert(member_id, state, diff or None)
                summary[state] += 1
            else:
                key = (scope_name, field_name)
                if key in pending_field_candidates:
                    continue
                candidate_repo.create_candidate(
                    session,
                    instance_identifier=instance_identifier,
                    candidate_type="field",
                    source_entity_name=scope_name,
                    source_field_name=field_name,
                )
                pending_field_candidates.add(key)
                summary["candidates"] += 1

        # Field source-side staleness (DEC-652): a resolved field_mapping under
        # this entity mapping whose source field vanished this audit is flipped
        # stale, surfacing it for human re-resolution.
        for fm in field_mapping_repo.list_field_mappings(
            session,
            source_mapping_identifier=mapping["source_mapping_identifier"],
            status="resolved",
        ):
            if fm["source_field_name"] not in seen_source_fields:
                field_mapping_repo.mark_stale(
                    session,
                    fm["field_mapping_identifier"],
                    reason="source_changed",
                    severity="high",
                )

    summary["absent"] = writer.sweep_absent()
    return summary


def reconcile_associations(
    session: Session,
    *,
    instance_identifier: str,
    client: _LinksClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile an instance's relationships, branching on the instance role.

    A ``source`` audit runs the **candidate-gated** pass
    (:func:`_reconcile_associations_candidate_gated`); a ``target`` or ``both`` audit runs the
    unchanged drift reconcile (:func:`_reconcile_associations_drift`). See DEC-648.
    """
    if _audit_is_source(session, instance_identifier):
        return _reconcile_associations_candidate_gated(
            session,
            instance_identifier=instance_identifier,
            client=client,
            progress=progress,
        )
    return _reconcile_associations_drift(
        session,
        instance_identifier=instance_identifier,
        client=client,
        progress=progress,
    )


def _reconcile_associations_candidate_gated(
    session: Session,
    *,
    instance_identifier: str,
    client: _LinksClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Candidate-gated relationship reconcile (source) — REQ-319 / DEC-654.

    A source relationship surfaces only once **both** endpoint entities are mapped
    (a resolved ``source_mapping`` each — DEC-651). For such a relationship: a
    resolved ``association_mapping`` drives present/drifted membership against its
    target canonical association; a rejected mapping is skipped; an undecided
    relationship becomes an idempotent ``mapping_candidate(association)`` (the
    source link name in ``source_field_name``). A resolved association mapping whose
    source relationship is gone this audit is flipped ``stale, source_changed``.

    :returns: ``{seen, created, present, drifted, absent, candidates}`` — ``created``
        is always 0 (canonical objects are never auto-created here).
    :raises ReconcileError: If the scopes call fails or returns a non-dict body.
    """
    status, scopes = client.get_all_scopes()
    if status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={status}; expected 200 + dict body"
        )

    # Source entities with a resolved (non-rejected) mapping are "mapped".
    mapped_sources: set[str] = set()
    for m in source_mapping_repo.list_source_mappings(
        session, instance_identifier=instance_identifier
    ):
        if m["status"] == "resolved" and m["decision_type"] != "rejected":
            mapped_sources.add(m["source_entity_name"])

    assoc_mappings_by_name: dict[str, list[dict]] = {}
    for am in association_mapping_repo.list_association_mappings(
        session, instance_identifier=instance_identifier
    ):
        assoc_mappings_by_name.setdefault(
            am["source_association_name"], []
        ).append(am)

    pending_assoc_candidates = {
        c["source_field_name"]
        for c in candidate_repo.list_candidates(
            session,
            instance_identifier=instance_identifier,
            candidate_type="association",
            resolved=False,
        )
    }
    canon_assoc_by_id = {
        a["association_identifier"]: a
        for a in association_repo.list_associations(session)
    }

    stamp = datetime.now(UTC)
    summary = {
        "seen": 0, "created": 0, "present": 0, "drifted": 0,
        "absent": 0, "candidates": 0,
    }
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="association",
        last_audited_at=stamp,
    )
    seen_assoc_names: set[str] = set()
    seen_relation_names: set[str] = set()

    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        if scope_name not in mapped_sources:
            continue  # owning endpoint not mapped → defer

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
            if not foreign_scope or foreign_scope not in mapped_sources:
                continue  # far endpoint not mapped → defer (both must be mapped)

            if cardinality == "many_to_many":
                relation_name = link_meta.get("relationName") or link_name
                if relation_name in seen_relation_names:
                    continue
                seen_relation_names.add(relation_name)
                assoc_name = relation_name
            else:
                assoc_name = link_name  # the source's own link name (its identity)

            seen_assoc_names.add(assoc_name)
            summary["seen"] += 1
            kind, am = _live_decision(assoc_mappings_by_name.get(assoc_name, []))
            if kind in ("rejected", "pending"):
                continue
            if kind == "resolved":
                member_id = am["target_association_identifier"]
                if member_id is None:
                    continue
                canon = canon_assoc_by_id.get(member_id, {})
                diff = (
                    {"association_cardinality": cardinality}
                    if canon.get("association_cardinality") != cardinality
                    else {}
                )
                state = "drifted" if diff else "present"
                writer.upsert(member_id, state, diff or None)
                summary[state] += 1
                continue

            # kind == "none" — undecided relationship → idempotent candidate.
            if assoc_name in pending_assoc_candidates:
                continue
            candidate_repo.create_candidate(
                session,
                instance_identifier=instance_identifier,
                candidate_type="association",
                source_entity_name=scope_name,
                source_field_name=assoc_name,
            )
            pending_assoc_candidates.add(assoc_name)
            summary["candidates"] += 1

    # Source-side staleness (DEC-652): a resolved association mapping whose source
    # relationship is gone this audit is flipped stale.
    for assoc_name, ams in assoc_mappings_by_name.items():
        if assoc_name in seen_assoc_names:
            continue
        kind, am = _live_decision(ams)
        if kind == "resolved":
            association_mapping_repo.mark_stale(
                session,
                am["association_mapping_identifier"],
                reason="source_changed",
                severity="high",
            )

    summary["absent"] = writer.sweep_absent()
    return summary


def _reconcile_associations_drift(
    session: Session,
    *,
    instance_identifier: str,
    client: _LinksClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Drift reconcile (target-role audit) — the unchanged PI-185/192 path.

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
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="association",
        last_audited_at=stamp,
    )
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
                # Strip the platform c-prefix EspoCRM applies to custom links
                # on native entities, so the association name is natural and a
                # later YAML export/deploy does not double-prefix it (REQ-344).
                assoc_name = strip_field_c_prefix(
                    link_name,
                    entity_is_native=(scope_name in NATIVE_ENTITIES),
                )

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

            writer.upsert(member_id, state, override)
            summary[state] += 1

    summary["absent"] = writer.sweep_absent()
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


class _FieldPermissionsClient(_ScopesClient, Protocol):
    """Adds the role listing the field-permission reconcile needs.

    Field-permission reconcile reads each Role's ``fieldData`` (``get_roles``)
    and resolves its ``(entity, field)`` cells against the design model, which
    needs the scope metadata (``get_all_scopes``) to classify native vs custom
    entities for the c-prefix strip — exactly as :func:`reconcile_fields` does.
    """

    def get_roles(self) -> tuple[int, dict | None]: ...


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
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="layout",
        last_audited_at=stamp,
    )

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
            writer.upsert(member_id, state, override)
            summary[state] += 1

    summary["absent"] = writer.sweep_absent()
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
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="role",
        last_audited_at=stamp,
    )

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
        writer.upsert(member_id, state, override)
        summary[state] += 1

    summary["absent"] = writer.sweep_absent()
    return summary


#: EspoCRM Role ``fieldData`` cell ``{"read","edit"}`` → neutral permission
#: level — the exact reverse of ``security_rule_manager._LEVEL_TO_CELL``. Any
#: cell that is not one of these three (an empty/default cell, or the
#: nonsensical read=no/edit=yes) is not a field-permission *rule* and is skipped.
_CELL_TO_LEVEL: dict[tuple[str, str], str] = {
    ("yes", "yes"): "read_write",
    ("yes", "no"): "read_only",
    ("no", "no"): "no_access",
}


def _cell_to_level(cell: dict) -> str | None:
    """Reverse-map an EspoCRM ``fieldData`` cell to a neutral permission level.

    Returns ``None`` for a cell that does not encode one of the three rule
    levels (e.g. an empty/inherit cell, or read=no/edit=yes) so the caller can
    skip it — only an explicit restriction is a field-permission rule.
    """
    return _CELL_TO_LEVEL.get((cell.get("read"), cell.get("edit")))


def reconcile_field_permissions(
    session: Session,
    *,
    instance_identifier: str,
    client: _FieldPermissionsClient,
    progress: ProgressFn | None = None,
) -> dict:
    """Reconcile a live instance's field-level permissions into rule records.

    The audit-IN half of REQ-129 (PI-051): each EspoCRM Role carries a
    ``fieldData`` matrix ``{entity: {field: {"read","edit"}}}`` — the field-level
    permissions the deploy side writes. This routine reads that matrix and
    materialises it as ``field_permission_rule`` design records, then verifies
    the round-trip:

    * A ``(role, field, level)`` cell with **no** matching design rule is
      captured as a new ``candidate`` rule (``deployment_status=pending``) —
      live state proposed as design intent, awaiting human confirmation.
    * A cell matching an existing **confirmed** rule whose level agrees flips
      the rule to ``deployment_status=deployed`` (verified active).
    * A confirmed rule whose live level **diverges**, or whose cell is **absent**
      from live state, flips to ``deployment_status=drift``. The design's
      ``permission_level`` is never overwritten by the audit — drift is recorded
      on the deploy axis, not by mutating intent.
    * Non-confirmed (candidate/deferred) rules are left untouched — the
      confirmed-before-deploy gate forbids a non-pending deploy status on them.

    A live cell whose entity or field has no design record, or whose cell does
    not encode a rule level, is **skipped and logged** (DEC: orphan cells stay
    out of the design model, mirroring the deploy side which only emits rules
    for design fields). Resolution mirrors :func:`reconcile_fields`: the entity
    is matched by neutral name, the field by neutral name after the
    native/custom c-prefix strip.

    :returns: A summary ``{seen, created, deployed, drifted, present, skipped,
        absent}``.
    :raises ReconcileError: If the scopes or roles call fails.
    """
    s_status, scopes = client.get_all_scopes()
    if s_status != 200 or not isinstance(scopes, dict):
        raise ReconcileError(
            f"get_all_scopes returned status={s_status}; expected 200 + dict"
        )
    r_status, roles_body = client.get_roles()
    if r_status != 200:
        raise ReconcileError(f"get_roles returned status={r_status}")

    # Resolve EspoCRM (scope, field) → design records, the same way
    # reconcile_fields matches: entity by neutral name, field by neutral name
    # after the native/custom c-prefix strip.
    ent_by_name = {
        _ci(e["entity_name"]): e["entity_identifier"]
        for e in entity_repo.list_entities(session)
    }
    entity_id_by_scope: dict[str, str] = {}
    is_native_by_scope: dict[str, bool] = {}
    field_id_by_cell: dict[tuple[str, str], str] = {}
    for scope_name, scope_meta in scopes.items():
        if not isinstance(scope_meta, dict):
            continue
        entity_class = classify_entity(scope_name, scope_meta)
        if entity_class is EntityClass.CUSTOM:
            is_native = False
        elif entity_class is EntityClass.NATIVE:
            is_native = True
        else:
            continue
        eid = ent_by_name.get(_ci(strip_entity_c_prefix(scope_name)))
        if eid is None:
            continue
        entity_id_by_scope[scope_name] = eid
        is_native_by_scope[scope_name] = is_native
        for f in field_repo.list_fields(session, entity_identifier=eid):
            field_id_by_cell[(scope_name, _ci(f["field_name"]))] = f[
                "field_identifier"
            ]

    role_id_by_name = {
        _ci(r["role_name"]): r["role_identifier"]
        for r in role_repo.list_roles(session)
    }
    rule_by_pair = {
        (
            r["field_permission_rule_role"],
            r["field_permission_rule_target_field"],
        ): r
        for r in field_permission_rule_repo.list_field_permission_rules(session)
    }

    summary = {
        "seen": 0, "created": 0, "deployed": 0, "drifted": 0,
        "present": 0, "skipped": 0, "absent": 0,
    }
    seen_pairs: set[tuple[str, str]] = set()

    for row in _rows_of(roles_body):
        role_name = row.get("name")
        if not role_name:
            continue
        role_id = role_id_by_name.get(_ci(role_name))
        if role_id is None:
            _note(
                progress,
                f"role {role_name!r} not in inventory (run the Roles audit "
                f"first) — its field permissions were skipped",
                "warning",
            )
            continue
        field_data = row.get("fieldData") or {}
        if not isinstance(field_data, dict):
            continue
        for scope_name, cells in field_data.items():
            if not isinstance(cells, dict):
                continue
            eid = entity_id_by_scope.get(scope_name)
            is_native = is_native_by_scope.get(scope_name, False)
            for espo_field, cell in cells.items():
                if not isinstance(cell, dict):
                    continue
                level = _cell_to_level(cell)
                if level is None:
                    continue  # empty/inherit cell — not a restriction rule
                summary["seen"] += 1
                neutral_field = strip_field_c_prefix(
                    espo_field, entity_is_native=is_native
                )
                fid = (
                    field_id_by_cell.get((scope_name, _ci(neutral_field)))
                    if eid is not None
                    else None
                )
                if fid is None:
                    summary["skipped"] += 1
                    _note(
                        progress,
                        f"{role_name}: field permission on "
                        f"{scope_name}.{espo_field} has no design field — "
                        f"skipped",
                        "warning",
                    )
                    continue
                pair = (role_id, fid)
                seen_pairs.add(pair)
                existing = rule_by_pair.get(pair)
                if existing is None:
                    field_permission_rule_repo.create_field_permission_rule(
                        session,
                        name=f"{role_name}: {neutral_field} {level}",
                        role=role_id,
                        target_field=fid,
                        permission_level=level,
                        description=(
                            "Captured by auditing instance "
                            f"{instance_identifier}."
                        ),
                    )
                    summary["created"] += 1
                    continue
                if existing["field_permission_rule_status"] != "confirmed":
                    # Non-confirmed rules can't carry a non-pending deploy
                    # status (confirmed-before-deploy gate) — leave untouched.
                    summary["present"] += 1
                    continue
                matches = (
                    existing["field_permission_rule_permission_level"] == level
                )
                new_deploy = "deployed" if matches else "drift"
                _set_field_permission_deploy_status(
                    session, existing, new_deploy
                )
                summary["deployed" if matches else "drifted"] += 1

    # Absent sweep: a confirmed rule previously verified ``deployed`` whose cell
    # is no longer present live has drifted (the live CRM dropped it).
    for (role_id, fid), rule in rule_by_pair.items():
        if (role_id, fid) in seen_pairs:
            continue
        if (
            rule["field_permission_rule_status"] == "confirmed"
            and rule["field_permission_rule_deployment_status"] == "deployed"
        ):
            _set_field_permission_deploy_status(session, rule, "drift")
            summary["absent"] += 1

    return summary


def _set_field_permission_deploy_status(
    session: Session, rule: dict, deployment_status: str
) -> None:
    """Flip a confirmed rule's ``deployment_status`` without touching intent.

    A full-replace PUT that passes every current value through unchanged except
    ``deployment_status`` — the design ``permission_level`` and lifecycle
    ``status`` are preserved (drift is a deploy-axis fact, not an intent edit).
    No-op when already at the requested status.
    """
    if rule["field_permission_rule_deployment_status"] == deployment_status:
        return
    field_permission_rule_repo.update_field_permission_rule(
        session,
        rule["field_permission_rule_identifier"],
        name=rule["field_permission_rule_name"],
        role=rule["field_permission_rule_role"],
        target_field=rule["field_permission_rule_target_field"],
        permission_level=rule["field_permission_rule_permission_level"],
        status=rule["field_permission_rule_status"],
        deployment_status=deployment_status,
        description=rule.get("field_permission_rule_description"),
        notes=rule.get("field_permission_rule_notes"),
    )


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
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="team",
        last_audited_at=stamp,
    )

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
        writer.upsert(member_id, state, override)
        summary[state] += 1

    summary["absent"] = writer.sweep_absent()
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
    writer = _AreaMembershipWriter(
        session,
        instance_identifier=instance_identifier,
        member_type="filtered_tab",
        last_audited_at=stamp,
    )

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
            writer.upsert(member_id, state, override)
            summary[state] += 1

    summary["absent"] = writer.sweep_absent()
    return summary


# --------------------------------------------------------------------------
# Truthful audit completion (REQ-395 / PI-354 / DEC-862)
# --------------------------------------------------------------------------

#: Per-area summary count keys that represent *populated inventory* — a run that
#: produced any of these reconciled real structure into the inventory.
_INVENTORY_KEYS = ("seen", "created", "present", "drifted", "absent")


def classify_audit_completion(area_summaries: dict[str, object]) -> dict[str, object]:
    """Classify an audit run's outcome truthfully (REQ-395).

    An audit that reads the instance successfully but populates **no** inventory
    must report that plainly, rather than looking like a successful, complete
    audit — the failure mode behind the 06-26 CBM incident, where an audit that
    resolved nothing still read as success.

    ``area_summaries`` is the ``{area_key: summary}`` map the all-in-one audit
    endpoint returns; each ``summary`` is a per-area count dict
    (``{seen, created, present, drifted, absent[, candidates]}``) or a
    ``{"skipped": True, ...}`` marker. A read *failure* is not seen here at all —
    it raises ``ReconcileError`` upstream (a 422), so it is already
    distinguishable from any outcome classified below.

    Returns ``{"status", "message", "totals", "areas_ran"}`` where ``status`` is:

    * ``complete`` — the audit populated real inventory.
    * ``candidates_only`` — the audit produced only unresolved candidates needing
      human review and populated no confirmed inventory.
    * ``empty`` — the audit completed but found nothing: no inventory, no
      candidates. This is **not** a populated audit.
    * ``no_areas`` — no area actually ran (every area skipped).
    """
    totals = dict.fromkeys((*_INVENTORY_KEYS, "candidates"), 0)
    areas_ran = 0
    for summary in area_summaries.values():
        if not isinstance(summary, dict) or summary.get("skipped"):
            continue
        areas_ran += 1
        for key in totals:
            value = summary.get(key, 0)
            if isinstance(value, int):
                totals[key] += value

    inventory = sum(totals[k] for k in _INVENTORY_KEYS)
    candidates = totals["candidates"]

    if areas_ran == 0:
        status = "no_areas"
        message = "No audit areas ran for this instance — nothing was reconciled."
    elif inventory > 0:
        status = "complete"
        message = (
            f"Audit populated inventory across {areas_ran} area(s): "
            f"{totals['present']} present, {totals['drifted']} drifted, "
            f"{totals['created']} created, {totals['absent']} absent."
        )
    elif candidates > 0:
        status = "candidates_only"
        message = (
            f"Audit produced {candidates} unresolved candidate(s) needing human "
            "review and populated no confirmed inventory — this is not a "
            "completed inventory."
        )
    else:
        status = "empty"
        message = (
            "Audit completed but found no objects in this instance: no inventory "
            "was populated and no candidates were produced. This is an empty "
            "result, not a successful populated audit."
        )

    return {
        "status": status,
        "message": message,
        "totals": totals,
        "areas_ran": areas_ran,
    }
