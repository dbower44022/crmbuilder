"""Catalog read methods (catalog-ingestion-PRD-v0.1.md section 6).

Every method takes a session and returns plain Python dicts that the
FastAPI layer wraps in the standard envelope. The shapes mirror what
the PRD documents in section 6; UUIDs are excluded from outputs (the
``catalog_id`` text identifier is the stable handle).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.models import (
    CatalogAttribute,
    CatalogAttributeEnumValue,
    CatalogAttributePresence,
    CatalogAttributeSynonym,
    CatalogEntity,
    CatalogEntitySynonym,
    CatalogEntitySystem,
    CatalogRelationship,
    CatalogRelationshipPresence,
    CatalogSource,
    Reference,
)
from crmbuilder_v2.access.vocab import CATALOG_SYSTEMS

_ENTITY_TYPE = "catalog_entity"
_ATTRIBUTE_TYPE = "catalog_attribute"


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------


def list_entities(
    session: Session,
    *,
    tier: int | None = None,
    entry_kind: str | None = None,
    parent_catalog_id: str | None = None,
    system: str | None = None,
    data_model_role: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return lightweight entity summaries matching the filters.

    Filters are AND-combined; ``system`` filters to entities that have a
    ``catalog_entity_system`` row for that system (any is_standard
    value). ``parent_catalog_id`` filters to subclasses of that parent.
    """
    stmt = select(CatalogEntity).order_by(CatalogEntity.catalog_id)
    if not include_deleted:
        stmt = stmt.where(CatalogEntity.is_deleted.is_(False))
    if tier is not None:
        stmt = stmt.where(CatalogEntity.tier == tier)
    if entry_kind is not None:
        stmt = stmt.where(CatalogEntity.entry_kind == entry_kind)
    if data_model_role is not None:
        stmt = stmt.where(CatalogEntity.data_model_role == data_model_role)
    if parent_catalog_id is not None:
        parent_id = _resolve_entity_id(session, parent_catalog_id)
        if parent_id is None:
            return []
        stmt = stmt.where(CatalogEntity.parent_entity_id == parent_id)
    if system is not None:
        if system not in CATALOG_SYSTEMS:
            raise ValidationError(
                [FieldError("system", "invalid_value", f"unknown system {system!r}")]
            )
        sub = select(CatalogEntitySystem.catalog_entity_id).where(
            CatalogEntitySystem.system == system
        )
        stmt = stmt.where(CatalogEntity.id.in_(sub))
    rows = session.scalars(stmt).all()
    return [_entity_summary(row) for row in rows]


def get_entity(session: Session, catalog_id: str) -> dict:
    """Return one entity with all nested data."""
    row = _require_entity(session, catalog_id)
    return _entity_full(session, row)


def get_attribute(
    session: Session, catalog_id: str, attribute_name: str
) -> dict:
    """Return one attribute with all nested data."""
    entity = _require_entity(session, catalog_id)
    attr = session.scalar(
        select(CatalogAttribute).where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.name == attribute_name)
        )
    )
    if attr is None or attr.is_deleted:
        raise NotFoundError(_ATTRIBUTE_TYPE, f"{catalog_id}.{attribute_name}")
    return _attribute_full(session, attr)


def search(
    session: Session,
    query: str,
    *,
    limit: int = 10,
    include_attributes: bool = True,
    include_synonyms: bool = True,
) -> list[dict]:
    """Text search across entity names, attribute names, and synonyms.

    Returns a ranked list of hits. Each hit carries ``kind``
    (``"entity"`` or ``"attribute"``), the catalog_id/name, the
    display_name, a rank score (lower is better), and a brief context.
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    hits: list[tuple[int, dict]] = []

    # Entity-name matches
    for ent in session.scalars(
        select(CatalogEntity).where(CatalogEntity.is_deleted.is_(False))
    ):
        rank = _match_rank(q, ent.catalog_id, ent.name, ent.display_name)
        if rank is not None:
            hits.append(
                (
                    rank,
                    {
                        "kind": "entity",
                        "catalog_id": ent.catalog_id,
                        "name": ent.name,
                        "display_name": ent.display_name,
                        "tier": ent.tier,
                        "entry_kind": ent.entry_kind,
                        "context": _truncate(ent.purpose, 160),
                        "rank": rank,
                    },
                )
            )

    if include_synonyms:
        for ent_syn, ent in session.execute(
            select(CatalogEntitySynonym, CatalogEntity)
            .join(CatalogEntity, CatalogEntity.id == CatalogEntitySynonym.catalog_entity_id)
            .where(CatalogEntity.is_deleted.is_(False))
        ):
            rank = _match_rank(q, ent_syn.synonym)
            if rank is not None:
                hits.append(
                    (
                        rank + 1,  # synonyms rank slightly worse than direct hits
                        {
                            "kind": "entity_synonym",
                            "catalog_id": ent.catalog_id,
                            "name": ent.name,
                            "display_name": ent.display_name,
                            "matched_synonym": ent_syn.synonym,
                            "context": _truncate(ent.purpose, 160),
                            "rank": rank + 1,
                        },
                    )
                )

    if include_attributes:
        for attr, ent in session.execute(
            select(CatalogAttribute, CatalogEntity)
            .join(CatalogEntity, CatalogEntity.id == CatalogAttribute.catalog_entity_id)
            .where(
                (CatalogAttribute.is_deleted.is_(False))
                & (CatalogEntity.is_deleted.is_(False))
            )
        ):
            rank = _match_rank(q, attr.name, attr.display_name)
            if rank is not None:
                hits.append(
                    (
                        rank,
                        {
                            "kind": "attribute",
                            "catalog_id": ent.catalog_id,
                            "entity_name": ent.name,
                            "attribute_name": attr.name,
                            "display_name": attr.display_name,
                            "type": attr.type,
                            "context": _truncate(attr.description, 160),
                            "rank": rank,
                        },
                    )
                )

    if include_synonyms and include_attributes:
        for attr_syn, attr, ent in session.execute(
            select(CatalogAttributeSynonym, CatalogAttribute, CatalogEntity)
            .join(
                CatalogAttribute,
                CatalogAttribute.id == CatalogAttributeSynonym.catalog_attribute_id,
            )
            .join(CatalogEntity, CatalogEntity.id == CatalogAttribute.catalog_entity_id)
            .where(
                (CatalogAttribute.is_deleted.is_(False))
                & (CatalogEntity.is_deleted.is_(False))
            )
        ):
            rank = _match_rank(q, attr_syn.synonym)
            if rank is not None:
                hits.append(
                    (
                        rank + 1,
                        {
                            "kind": "attribute_synonym",
                            "catalog_id": ent.catalog_id,
                            "entity_name": ent.name,
                            "attribute_name": attr.name,
                            "display_name": attr.display_name,
                            "matched_synonym": attr_syn.synonym,
                            "context": _truncate(attr.description, 160),
                            "rank": rank + 1,
                        },
                    )
                )

    hits.sort(key=lambda x: (x[0], x[1].get("catalog_id", ""), x[1].get("attribute_name", "")))
    return [hit for _, hit in hits[:limit]]


def cross_system_map(
    session: Session,
    catalog_id: str,
    *,
    system: str | None = None,
) -> dict:
    """Return the catalog entity + its attributes mapped per system.

    ``system=None`` returns all seven surveyed systems; otherwise only
    that one.
    """
    if system is not None and system not in CATALOG_SYSTEMS:
        raise ValidationError(
            [FieldError("system", "invalid_value", f"unknown system {system!r}")]
        )
    entity = _require_entity(session, catalog_id)

    target_systems = [system] if system else sorted(CATALOG_SYSTEMS)

    # Entity-level system mappings
    ent_systems_rows = session.scalars(
        select(CatalogEntitySystem).where(
            CatalogEntitySystem.catalog_entity_id == entity.id
        )
    ).all()
    ent_systems_by_name = {r.system: r for r in ent_systems_rows}

    # Attributes ordered, plus their per-system presence
    attrs = session.scalars(
        select(CatalogAttribute)
        .where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.is_deleted.is_(False))
        )
        .order_by(CatalogAttribute.order_index, CatalogAttribute.name)
    ).all()
    pres_rows = session.scalars(
        select(CatalogAttributePresence).where(
            CatalogAttributePresence.catalog_attribute_id.in_([a.id for a in attrs])
            if attrs
            else CatalogAttributePresence.id.is_(None)
        )
    ).all()
    pres_by_attr_system: dict[tuple[int, str], CatalogAttributePresence] = {
        (p.catalog_attribute_id, p.system): p for p in pres_rows
    }

    systems_out: dict[str, dict] = {}
    for sys_name in target_systems:
        ent_sys = ent_systems_by_name.get(sys_name)
        attrs_out: list[dict] = []
        for a in attrs:
            p = pres_by_attr_system.get((a.id, sys_name))
            attrs_out.append(
                {
                    "catalog_name": a.name,
                    "display_name": a.display_name,
                    "type": a.type,
                    "status": p.status if p else "absent",
                    "api_name": (p.api_name if p else None),
                }
            )
        systems_out[sys_name] = {
            "entity_name": ent_sys.system_name if ent_sys else None,
            "api_name": ent_sys.api_name if ent_sys else None,
            "is_standard": ent_sys.is_standard if ent_sys else None,
            "mechanism": ent_sys.mechanism if ent_sys else None,
            "notes": ent_sys.notes if ent_sys else None,
            "docs_url": ent_sys.docs_url if ent_sys else None,
            "attributes": attrs_out,
        }

    return {
        "entity": _entity_summary(entity),
        "systems": systems_out,
    }


def gap_check(
    session: Session,
    *,
    based_on_catalog_id: str,
    draft_attribute_names: list[str],
    min_systems: int = 5,
) -> dict:
    """Compare a draft attribute list against a catalog entity.

    Returns the catalog attributes that are "standard" in at least
    ``min_systems`` surveyed systems but absent from the draft. Useful
    during entity-PRD drafting to surface common attributes the
    operator may have forgotten.
    """
    if not 1 <= min_systems <= 7:
        raise ValidationError(
            [
                FieldError(
                    "min_systems",
                    "out_of_range",
                    "must be between 1 and 7",
                )
            ]
        )
    entity = _require_entity(session, based_on_catalog_id)
    draft = {n.strip() for n in draft_attribute_names if n and n.strip()}

    attrs = session.scalars(
        select(CatalogAttribute)
        .where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.is_deleted.is_(False))
        )
        .order_by(CatalogAttribute.order_index, CatalogAttribute.name)
    ).all()
    if not attrs:
        return {
            "based_on": _entity_summary(entity),
            "min_systems": min_systems,
            "missing": [],
        }

    pres_rows = session.scalars(
        select(CatalogAttributePresence).where(
            CatalogAttributePresence.catalog_attribute_id.in_([a.id for a in attrs])
        )
    ).all()
    standard_by_attr: dict[int, int] = {}
    for p in pres_rows:
        if p.status == "standard":
            standard_by_attr[p.catalog_attribute_id] = (
                standard_by_attr.get(p.catalog_attribute_id, 0) + 1
            )

    missing: list[dict] = []
    for a in attrs:
        if a.name in draft:
            continue
        count = standard_by_attr.get(a.id, 0)
        if count >= min_systems:
            missing.append(
                {
                    "name": a.name,
                    "display_name": a.display_name,
                    "type": a.type,
                    "standard_system_count": count,
                    "description": a.description,
                }
            )
    missing.sort(key=lambda d: (-d["standard_system_count"], d["name"]))
    return {
        "based_on": _entity_summary(entity),
        "min_systems": min_systems,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Internal helpers (used by both read and write)
# ---------------------------------------------------------------------------


def _resolve_entity_id(session: Session, catalog_id: str) -> int | None:
    row = session.scalar(
        select(CatalogEntity).where(CatalogEntity.catalog_id == catalog_id)
    )
    return row.id if row else None


def _require_entity(session: Session, catalog_id: str) -> CatalogEntity:
    row = session.scalar(
        select(CatalogEntity).where(CatalogEntity.catalog_id == catalog_id)
    )
    if row is None or row.is_deleted:
        raise NotFoundError(_ENTITY_TYPE, catalog_id)
    return row


def _entity_summary(row: CatalogEntity) -> dict:
    """Lightweight entity shape used in list responses, search hits, etc."""
    return {
        "catalog_id": row.catalog_id,
        "name": row.name,
        "display_name": row.display_name,
        "tier": row.tier,
        "entry_kind": row.entry_kind,
        "data_model_role": row.data_model_role,
        "typically_required": row.typically_required,
        "parent_catalog_id": (
            _parent_catalog_id(row) if row.entry_kind == "subclass" else None
        ),
    }


def _parent_catalog_id(row: CatalogEntity) -> str | None:
    """Return the parent's catalog_id text identifier, or None."""
    if row.parent is None:
        return None
    return row.parent.catalog_id


def _entity_full(session: Session, row: CatalogEntity) -> dict:
    """Full nested entity dict."""
    summary = _entity_summary(row)

    # Synonyms (ordered)
    synonyms = list(
        session.scalars(
            select(CatalogEntitySynonym.synonym)
            .where(CatalogEntitySynonym.catalog_entity_id == row.id)
            .order_by(CatalogEntitySynonym.order_index)
        )
    )

    # Per-system entity mappings
    systems_rows = session.scalars(
        select(CatalogEntitySystem)
        .where(CatalogEntitySystem.catalog_entity_id == row.id)
        .order_by(CatalogEntitySystem.system)
    ).all()
    systems = [
        {
            "system": s.system,
            "name": s.system_name,
            "api_name": s.api_name,
            "is_standard": s.is_standard,
            "mechanism": s.mechanism,
            "notes": s.notes,
            "docs_url": s.docs_url,
        }
        for s in systems_rows
    ]

    # Sources (ordered)
    sources_rows = session.scalars(
        select(CatalogSource)
        .where(CatalogSource.catalog_entity_id == row.id)
        .order_by(CatalogSource.order_index)
    ).all()
    sources = [{"title": s.title, "url": s.url} for s in sources_rows]

    # Attributes with their child rows
    attrs_rows = session.scalars(
        select(CatalogAttribute)
        .where(
            (CatalogAttribute.catalog_entity_id == row.id)
            & (CatalogAttribute.is_deleted.is_(False))
        )
        .order_by(CatalogAttribute.order_index, CatalogAttribute.name)
    ).all()
    attributes = [_attribute_full(session, a) for a in attrs_rows]

    # Relationships (source side only)
    rels_rows = session.scalars(
        select(CatalogRelationship).where(
            CatalogRelationship.source_entity_id == row.id
        )
    ).all()
    relationships: list[dict] = []
    for rel in rels_rows:
        target = session.get(CatalogEntity, rel.target_entity_id)
        rp_rows = session.scalars(
            select(CatalogRelationshipPresence).where(
                CatalogRelationshipPresence.catalog_relationship_id == rel.id
            )
        ).all()
        relationships.append(
            {
                "target": target.catalog_id if target else None,
                "target_name": target.name if target else None,
                "cardinality": rel.cardinality,
                "role": rel.role,
                "description": rel.description,
                "presence": [
                    {"system": p.system, "status": p.status} for p in rp_rows
                ],
            }
        )

    inbound = _inbound_references(
        session, target_type="catalog_entity", target_id=row.catalog_id
    )

    full = {
        **summary,
        "discriminator_attribute": row.discriminator_attribute,
        "discriminator_value": row.discriminator_value,
        "purpose": row.purpose,
        "business_context": row.business_context,
        "is_deleted": row.is_deleted,
        "common_synonyms": synonyms,
        "systems": systems,
        "sources": sources,
        "attributes": attributes,
        "relationships": relationships,
        "inbound_references": inbound,
    }
    return full


def _attribute_full(session: Session, attr: CatalogAttribute) -> dict:
    """Full attribute dict with enum_values, synonyms, presence."""
    # Resolve parent entity for the attribute identifier ``{catalog_id}.{name}``.
    parent = session.get(CatalogEntity, attr.catalog_entity_id)
    parent_catalog_id = parent.catalog_id if parent else None
    inbound = (
        _inbound_references(
            session,
            target_type="catalog_attribute",
            target_id=f"{parent_catalog_id}.{attr.name}",
        )
        if parent_catalog_id
        else []
    )
    enum_values = list(
        session.scalars(
            select(CatalogAttributeEnumValue.value)
            .where(CatalogAttributeEnumValue.catalog_attribute_id == attr.id)
            .order_by(CatalogAttributeEnumValue.order_index)
        )
    )
    synonyms = list(
        session.scalars(
            select(CatalogAttributeSynonym.synonym)
            .where(CatalogAttributeSynonym.catalog_attribute_id == attr.id)
            .order_by(CatalogAttributeSynonym.order_index)
        )
    )
    pres_rows = session.scalars(
        select(CatalogAttributePresence)
        .where(CatalogAttributePresence.catalog_attribute_id == attr.id)
        .order_by(CatalogAttributePresence.system)
    ).all()
    presence = [
        {
            "system": p.system,
            "status": p.status,
            "api_name": p.api_name,
        }
        for p in pres_rows
    ]
    return {
        "name": attr.name,
        "display_name": attr.display_name,
        "type": attr.type,
        "required": attr.required,
        "max_length": attr.max_length,
        "reference_target": attr.reference_target,
        "description": attr.description,
        "usage": attr.usage,
        "notes": attr.notes,
        "is_deleted": attr.is_deleted,
        "common_synonyms": synonyms,
        "enum_values": enum_values,
        "presence": presence,
        "inbound_references": inbound,
    }


def _inbound_references(
    session: Session, *, target_type: str, target_id: str
) -> list[dict]:
    """Return cross-entity references that target the given catalog row.

    Catalog rows do not source references; this surfaces the inbound
    direction (e.g. a decision that references a catalog entity, a
    planning item that ``is_about`` an attribute) on the catalog
    detail responses.
    """
    rows = session.scalars(
        select(Reference)
        .where(
            (Reference.target_type == target_type)
            & (Reference.target_id == target_id)
        )
        .order_by(
            Reference.source_type, Reference.source_id, Reference.relationship_kind
        )
    ).all()
    return [
        {
            "source_type": r.source_type,
            "source_id": r.source_id,
            "relationship": r.relationship_kind,
        }
        for r in rows
    ]


def _match_rank(q: str, *fields: str | None) -> int | None:
    """Return the best rank across fields, or None if no field matches."""
    best: int | None = None
    for f in fields:
        if f is None:
            continue
        text = f.lower()
        if text == q:
            r = 0
        elif text.startswith(q):
            r = 1
        elif q in text:
            r = 2
        else:
            continue
        if best is None or r < best:
            best = r
    return best


def _truncate(text: str | None, length: int) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) <= length:
        return t
    return t[: length - 1].rstrip() + "…"
