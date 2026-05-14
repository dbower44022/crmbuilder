"""Catalog write methods (catalog-ingestion-PRD-v0.1.md section 6).

Entity is the unit of write — nested sub-row data (attributes, systems,
sources, synonyms, relationships) flows through the parent entity's
payload on create/PUT. PATCH updates entity-level scalar fields only.
Soft-delete (``is_deleted=True``) is used for both entity and attribute
deletion to preserve referential integrity for inbound references.

These methods do NOT emit ``change_log`` entries at v0.1: the existing
emit() machinery is per-entity flat, and catalog rows are nested. A
later workstream can add catalog-aware audit emission once the
methodology entity schema (which has the same shape) lands.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import (
    ConflictError,
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
)
from crmbuilder_v2.access.repositories.catalog.exports import export_entity
from crmbuilder_v2.access.repositories.catalog.read import (
    _attribute_full,
    _entity_full,
    _require_entity,
    _resolve_entity_id,
)
from crmbuilder_v2.access.vocab import (
    CATALOG_ATTRIBUTE_TYPES,
    CATALOG_DATA_MODEL_ROLES,
    CATALOG_ENTRY_KINDS,
    CATALOG_IS_STANDARD_VALUES,
    CATALOG_MECHANISMS,
    CATALOG_PRESENCE_STATUSES,
    CATALOG_RELATIONSHIP_CARDINALITIES,
    CATALOG_RELATIONSHIP_ROLES,
    CATALOG_SYSTEMS,
)

_ENTITY_TYPE = "catalog_entity"
_ATTRIBUTE_TYPE = "catalog_attribute"


# ---------------------------------------------------------------------------
# Public write API
# ---------------------------------------------------------------------------


def create_entity(session: Session, *, payload: dict) -> dict:
    """POST /catalog/entities — create a new entity with all nested data."""
    _validate_entity_scalars(payload)
    catalog_id = payload["catalog_id"]
    existing = session.scalar(
        select(CatalogEntity).where(CatalogEntity.catalog_id == catalog_id)
    )
    if existing is not None:
        raise ConflictError(f"catalog_entity {catalog_id!r} already exists")

    parent_id = _resolve_parent_id(session, payload)
    now = datetime.now(UTC)
    row = CatalogEntity(
        catalog_id=catalog_id,
        name=payload["name"],
        display_name=payload.get("display_name") or payload["name"],
        tier=int(payload["tier"]),
        entry_kind=payload["entry_kind"],
        parent_entity_id=parent_id,
        discriminator_attribute=payload.get("discriminator_attribute"),
        discriminator_value=payload.get("discriminator_value"),
        purpose=payload.get("purpose", "") or "",
        business_context=payload.get("business_context", "") or "",
        data_model_role=payload["data_model_role"],
        typically_required=bool(payload.get("typically_required", False)),
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()

    _replace_entity_children(session, row.id, payload)
    _replace_entity_attributes(session, row.id, payload.get("attributes") or [])
    _replace_outbound_relationships(session, row.id, payload.get("relationships") or [])
    session.flush()
    export_entity(session, row.catalog_id)
    return _entity_full(session, row)


def update_entity(session: Session, catalog_id: str, *, payload: dict) -> dict:
    """PUT /catalog/entities/{catalog_id} — full nested replace.

    The catalog_id in the payload (if present) must equal the URL path
    catalog_id; this endpoint does not allow renaming.
    """
    row = _require_entity(session, catalog_id)
    if "catalog_id" in payload and payload["catalog_id"] != catalog_id:
        raise ValidationError(
            [
                FieldError(
                    "catalog_id",
                    "immutable",
                    "catalog_id cannot be changed via update; delete and re-create",
                )
            ]
        )
    payload_with_id = {**payload, "catalog_id": catalog_id}
    _validate_entity_scalars(payload_with_id)
    parent_id = _resolve_parent_id(session, payload_with_id)

    row.name = payload_with_id["name"]
    row.display_name = payload_with_id.get("display_name") or payload_with_id["name"]
    row.tier = int(payload_with_id["tier"])
    row.entry_kind = payload_with_id["entry_kind"]
    row.parent_entity_id = parent_id
    row.discriminator_attribute = payload_with_id.get("discriminator_attribute")
    row.discriminator_value = payload_with_id.get("discriminator_value")
    row.purpose = payload_with_id.get("purpose", "") or ""
    row.business_context = payload_with_id.get("business_context", "") or ""
    row.data_model_role = payload_with_id["data_model_role"]
    row.typically_required = bool(payload_with_id.get("typically_required", False))
    row.is_deleted = False
    row.updated_at = datetime.now(UTC)
    session.flush()

    _replace_entity_children(session, row.id, payload_with_id)
    _replace_entity_attributes(
        session, row.id, payload_with_id.get("attributes") or []
    )
    _replace_outbound_relationships(
        session, row.id, payload_with_id.get("relationships") or []
    )
    session.flush()
    export_entity(session, row.catalog_id)
    return _entity_full(session, row)


_PATCHABLE_ENTITY_FIELDS = frozenset(
    {
        "name",
        "display_name",
        "tier",
        "entry_kind",
        "parent_entity",
        "discriminator_attribute",
        "discriminator_value",
        "purpose",
        "business_context",
        "data_model_role",
        "typically_required",
    }
)


def patch_entity(session: Session, catalog_id: str, **fields: Any) -> dict:
    """PATCH /catalog/entities/{catalog_id} — partial update of scalar fields.

    Nested child collections are untouched by PATCH; use PUT for those.
    Passing an unknown field name is a 400-class validation error.
    """
    row = _require_entity(session, catalog_id)
    unknown = set(fields) - _PATCHABLE_ENTITY_FIELDS
    if unknown:
        raise ValidationError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown updatable fields: {sorted(unknown)}",
                )
            ]
        )
    if "entry_kind" in fields and fields["entry_kind"] not in CATALOG_ENTRY_KINDS:
        raise ValidationError(
            [
                FieldError(
                    "entry_kind",
                    "invalid_value",
                    f"must be one of {sorted(CATALOG_ENTRY_KINDS)}",
                )
            ]
        )
    if (
        "data_model_role" in fields
        and fields["data_model_role"] not in CATALOG_DATA_MODEL_ROLES
    ):
        raise ValidationError(
            [
                FieldError(
                    "data_model_role",
                    "invalid_value",
                    f"must be one of {sorted(CATALOG_DATA_MODEL_ROLES)}",
                )
            ]
        )
    if "tier" in fields:
        tier = fields["tier"]
        if not isinstance(tier, int) or not 1 <= tier <= 5:
            raise ValidationError(
                [
                    FieldError(
                        "tier",
                        "out_of_range",
                        "tier must be int 1-5",
                    )
                ]
            )

    if "parent_entity" in fields:
        parent_catalog_id = fields.pop("parent_entity")
        if parent_catalog_id is None or parent_catalog_id == "":
            row.parent_entity_id = None
        else:
            pid = _resolve_entity_id(session, parent_catalog_id)
            if pid is None:
                raise ValidationError(
                    [
                        FieldError(
                            "parent_entity",
                            "not_found",
                            f"parent_entity {parent_catalog_id!r} does not exist",
                        )
                    ]
                )
            row.parent_entity_id = pid

    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    session.flush()
    export_entity(session, row.catalog_id)
    return _entity_full(session, row)


def delete_entity(session: Session, catalog_id: str) -> dict:
    """Soft-delete: set is_deleted=True, leave the row in place.

    Inbound references continue to resolve via get_entity; the row is
    excluded from list_entities by default.
    """
    row = _require_entity(session, catalog_id)
    row.is_deleted = True
    row.updated_at = datetime.now(UTC)
    session.flush()
    export_entity(session, row.catalog_id)  # removes the JSON file
    return _entity_full(session, row)


# ---------------------------------------------------------------------------
# Attribute writes
# ---------------------------------------------------------------------------


def create_attribute(
    session: Session, catalog_id: str, *, payload: dict
) -> dict:
    entity = _require_entity(session, catalog_id)
    _validate_attribute_scalars(payload)
    name = payload["name"]
    existing = session.scalar(
        select(CatalogAttribute).where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.name == name)
        )
    )
    if existing is not None:
        raise ConflictError(
            f"catalog_attribute {catalog_id}.{name} already exists"
        )
    max_order = session.scalar(
        select(CatalogAttribute.order_index)
        .where(CatalogAttribute.catalog_entity_id == entity.id)
        .order_by(CatalogAttribute.order_index.desc())
        .limit(1)
    )
    now = datetime.now(UTC)
    row = CatalogAttribute(
        catalog_entity_id=entity.id,
        name=name,
        display_name=payload.get("display_name") or name,
        type=payload["type"],
        required=bool(payload.get("required", False)),
        max_length=payload.get("max_length"),
        reference_target=payload.get("reference_target"),
        description=payload.get("description", "") or "",
        usage=payload.get("usage", "") or "",
        notes=payload.get("notes"),
        order_index=(max_order or -1) + 1,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    _replace_attribute_children(session, row.id, payload)
    session.flush()
    export_entity(session, entity.catalog_id)
    return _attribute_full(session, row)


def update_attribute(
    session: Session, catalog_id: str, attribute_name: str, *, payload: dict
) -> dict:
    """PUT /catalog/entities/{cid}/attributes/{name} — full nested replace."""
    entity = _require_entity(session, catalog_id)
    row = session.scalar(
        select(CatalogAttribute).where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.name == attribute_name)
        )
    )
    if row is None or row.is_deleted:
        raise NotFoundError(_ATTRIBUTE_TYPE, f"{catalog_id}.{attribute_name}")
    if "name" in payload and payload["name"] != attribute_name:
        raise ValidationError(
            [
                FieldError(
                    "name",
                    "immutable",
                    "attribute name cannot be changed via update",
                )
            ]
        )
    payload_with_name = {**payload, "name": attribute_name}
    _validate_attribute_scalars(payload_with_name)
    row.display_name = payload_with_name.get("display_name") or attribute_name
    row.type = payload_with_name["type"]
    row.required = bool(payload_with_name.get("required", False))
    row.max_length = payload_with_name.get("max_length")
    row.reference_target = payload_with_name.get("reference_target")
    row.description = payload_with_name.get("description", "") or ""
    row.usage = payload_with_name.get("usage", "") or ""
    row.notes = payload_with_name.get("notes")
    row.is_deleted = False
    row.updated_at = datetime.now(UTC)
    session.flush()
    _replace_attribute_children(session, row.id, payload_with_name)
    session.flush()
    export_entity(session, entity.catalog_id)
    return _attribute_full(session, row)


_PATCHABLE_ATTRIBUTE_FIELDS = frozenset(
    {
        "display_name",
        "type",
        "required",
        "max_length",
        "reference_target",
        "description",
        "usage",
        "notes",
    }
)


def patch_attribute(
    session: Session, catalog_id: str, attribute_name: str, **fields: Any
) -> dict:
    entity = _require_entity(session, catalog_id)
    row = session.scalar(
        select(CatalogAttribute).where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.name == attribute_name)
        )
    )
    if row is None or row.is_deleted:
        raise NotFoundError(_ATTRIBUTE_TYPE, f"{catalog_id}.{attribute_name}")
    unknown = set(fields) - _PATCHABLE_ATTRIBUTE_FIELDS
    if unknown:
        raise ValidationError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown updatable fields: {sorted(unknown)}",
                )
            ]
        )
    if "type" in fields and fields["type"] not in CATALOG_ATTRIBUTE_TYPES:
        raise ValidationError(
            [
                FieldError(
                    "type",
                    "invalid_value",
                    f"must be one of {sorted(CATALOG_ATTRIBUTE_TYPES)}",
                )
            ]
        )
    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    session.flush()
    export_entity(session, entity.catalog_id)
    return _attribute_full(session, row)


def delete_attribute(
    session: Session, catalog_id: str, attribute_name: str
) -> dict:
    entity = _require_entity(session, catalog_id)
    row = session.scalar(
        select(CatalogAttribute).where(
            (CatalogAttribute.catalog_entity_id == entity.id)
            & (CatalogAttribute.name == attribute_name)
        )
    )
    if row is None or row.is_deleted:
        raise NotFoundError(_ATTRIBUTE_TYPE, f"{catalog_id}.{attribute_name}")
    row.is_deleted = True
    row.updated_at = datetime.now(UTC)
    session.flush()
    export_entity(session, entity.catalog_id)
    return _attribute_full(session, row)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _validate_entity_scalars(payload: dict) -> None:
    errors: list[FieldError] = []
    for required in ("catalog_id", "name", "display_name", "tier", "entry_kind", "data_model_role"):
        if payload.get(required) in (None, ""):
            errors.append(FieldError(required, "missing", f"required field {required}"))
    if payload.get("entry_kind") and payload["entry_kind"] not in CATALOG_ENTRY_KINDS:
        errors.append(
            FieldError(
                "entry_kind",
                "invalid_value",
                f"must be one of {sorted(CATALOG_ENTRY_KINDS)}",
            )
        )
    if (
        payload.get("data_model_role")
        and payload["data_model_role"] not in CATALOG_DATA_MODEL_ROLES
    ):
        errors.append(
            FieldError(
                "data_model_role",
                "invalid_value",
                f"must be one of {sorted(CATALOG_DATA_MODEL_ROLES)}",
            )
        )
    tier = payload.get("tier")
    if tier is not None and (not isinstance(tier, int) or not 1 <= tier <= 5):
        errors.append(FieldError("tier", "out_of_range", "tier must be int 1-5"))
    if errors:
        raise ValidationError(errors)


def _validate_attribute_scalars(payload: dict) -> None:
    errors: list[FieldError] = []
    for required in ("name", "type"):
        if payload.get(required) in (None, ""):
            errors.append(FieldError(required, "missing", f"required field {required}"))
    if payload.get("type") and payload["type"] not in CATALOG_ATTRIBUTE_TYPES:
        errors.append(
            FieldError(
                "type",
                "invalid_value",
                f"must be one of {sorted(CATALOG_ATTRIBUTE_TYPES)}",
            )
        )
    if errors:
        raise ValidationError(errors)


def _resolve_parent_id(session: Session, payload: dict) -> int | None:
    parent_catalog_id = payload.get("parent_entity")
    if not parent_catalog_id:
        return None
    parent_id = _resolve_entity_id(session, parent_catalog_id)
    if parent_id is None:
        raise ValidationError(
            [
                FieldError(
                    "parent_entity",
                    "not_found",
                    f"parent_entity {parent_catalog_id!r} does not exist",
                )
            ]
        )
    return parent_id


# ---------------------------------------------------------------------------
# Child-row replacement
# ---------------------------------------------------------------------------


def _replace_entity_children(
    session: Session, entity_id: int, payload: dict
) -> None:
    # Synonyms
    session.execute(
        delete(CatalogEntitySynonym).where(
            CatalogEntitySynonym.catalog_entity_id == entity_id
        )
    )
    for order, syn in enumerate(payload.get("common_synonyms") or []):
        session.add(
            CatalogEntitySynonym(
                catalog_entity_id=entity_id, synonym=syn, order_index=order
            )
        )

    # Systems
    session.execute(
        delete(CatalogEntitySystem).where(
            CatalogEntitySystem.catalog_entity_id == entity_id
        )
    )
    for s in payload.get("systems") or []:
        system = s.get("system")
        if system not in CATALOG_SYSTEMS:
            raise ValidationError(
                [
                    FieldError(
                        "systems[].system",
                        "invalid_value",
                        f"unknown system {system!r}",
                    )
                ]
            )
        is_standard = str(s.get("is_standard", "false")).lower()
        if is_standard not in CATALOG_IS_STANDARD_VALUES:
            raise ValidationError(
                [
                    FieldError(
                        "systems[].is_standard",
                        "invalid_value",
                        f"must be one of {sorted(CATALOG_IS_STANDARD_VALUES)}",
                    )
                ]
            )
        mechanism = s.get("mechanism")
        if mechanism is not None and mechanism not in CATALOG_MECHANISMS:
            raise ValidationError(
                [
                    FieldError(
                        "systems[].mechanism",
                        "invalid_value",
                        f"must be one of {sorted(CATALOG_MECHANISMS)}",
                    )
                ]
            )
        session.add(
            CatalogEntitySystem(
                catalog_entity_id=entity_id,
                system=system,
                system_name=s.get("name", "") or "",
                api_name=s.get("api_name"),
                is_standard=is_standard,
                mechanism=mechanism,
                notes=s.get("notes"),
                docs_url=s.get("docs_url"),
            )
        )

    # Sources
    session.execute(
        delete(CatalogSource).where(CatalogSource.catalog_entity_id == entity_id)
    )
    for order, src in enumerate(payload.get("sources") or []):
        session.add(
            CatalogSource(
                catalog_entity_id=entity_id,
                title=src.get("title", "") or "",
                url=src.get("url", "") or "",
                order_index=order,
            )
        )


def _replace_entity_attributes(
    session: Session, entity_id: int, attrs: list[dict]
) -> None:
    """Replace the attribute set for an entity: delete existing, insert new.

    Used by PUT (full nested replace). Preserves order via order_index.
    """
    existing = list(
        session.scalars(
            select(CatalogAttribute).where(
                CatalogAttribute.catalog_entity_id == entity_id
            )
        )
    )
    for old in existing:
        session.execute(
            delete(CatalogAttributeEnumValue).where(
                CatalogAttributeEnumValue.catalog_attribute_id == old.id
            )
        )
        session.execute(
            delete(CatalogAttributeSynonym).where(
                CatalogAttributeSynonym.catalog_attribute_id == old.id
            )
        )
        session.execute(
            delete(CatalogAttributePresence).where(
                CatalogAttributePresence.catalog_attribute_id == old.id
            )
        )
        session.delete(old)
    session.flush()

    now = datetime.now(UTC)
    for order, a in enumerate(attrs):
        _validate_attribute_scalars(a)
        row = CatalogAttribute(
            catalog_entity_id=entity_id,
            name=a["name"],
            display_name=a.get("display_name") or a["name"],
            type=a["type"],
            required=bool(a.get("required", False)),
            max_length=a.get("max_length"),
            reference_target=a.get("reference_target"),
            description=a.get("description", "") or "",
            usage=a.get("usage", "") or "",
            notes=a.get("notes"),
            order_index=order,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        _replace_attribute_children(session, row.id, a)


def _replace_attribute_children(
    session: Session, attribute_id: int, payload: dict
) -> None:
    # Enum values
    session.execute(
        delete(CatalogAttributeEnumValue).where(
            CatalogAttributeEnumValue.catalog_attribute_id == attribute_id
        )
    )
    for order, v in enumerate(payload.get("enum_values") or []):
        session.add(
            CatalogAttributeEnumValue(
                catalog_attribute_id=attribute_id,
                value=str(v),
                order_index=order,
            )
        )
    # Synonyms
    session.execute(
        delete(CatalogAttributeSynonym).where(
            CatalogAttributeSynonym.catalog_attribute_id == attribute_id
        )
    )
    for order, syn in enumerate(payload.get("common_synonyms") or []):
        session.add(
            CatalogAttributeSynonym(
                catalog_attribute_id=attribute_id,
                synonym=syn,
                order_index=order,
            )
        )
    # Presence
    session.execute(
        delete(CatalogAttributePresence).where(
            CatalogAttributePresence.catalog_attribute_id == attribute_id
        )
    )
    for p in payload.get("presence") or []:
        system = p.get("system")
        if system not in CATALOG_SYSTEMS:
            raise ValidationError(
                [
                    FieldError(
                        "presence[].system",
                        "invalid_value",
                        f"unknown system {system!r}",
                    )
                ]
            )
        status = p.get("status")
        if status not in CATALOG_PRESENCE_STATUSES:
            raise ValidationError(
                [
                    FieldError(
                        "presence[].status",
                        "invalid_value",
                        f"must be one of {sorted(CATALOG_PRESENCE_STATUSES)}",
                    )
                ]
            )
        session.add(
            CatalogAttributePresence(
                catalog_attribute_id=attribute_id,
                system=system,
                status=status,
                api_name=p.get("api_name"),
            )
        )


def _replace_outbound_relationships(
    session: Session, source_entity_id: int, rels: list[dict]
) -> None:
    existing = list(
        session.scalars(
            select(CatalogRelationship).where(
                CatalogRelationship.source_entity_id == source_entity_id
            )
        )
    )
    for old in existing:
        session.execute(
            delete(CatalogRelationshipPresence).where(
                CatalogRelationshipPresence.catalog_relationship_id == old.id
            )
        )
        session.delete(old)
    session.flush()

    for r in rels:
        target_catalog_id = r.get("target")
        target_id = _resolve_entity_id(session, target_catalog_id)
        if target_id is None:
            raise ValidationError(
                [
                    FieldError(
                        "relationships[].target",
                        "not_found",
                        f"target {target_catalog_id!r} does not exist",
                    )
                ]
            )
        cardinality = r.get("cardinality")
        role = r.get("role")
        if cardinality not in CATALOG_RELATIONSHIP_CARDINALITIES:
            raise ValidationError(
                [
                    FieldError(
                        "relationships[].cardinality",
                        "invalid_value",
                        f"must be one of {sorted(CATALOG_RELATIONSHIP_CARDINALITIES)}",
                    )
                ]
            )
        if role not in CATALOG_RELATIONSHIP_ROLES:
            raise ValidationError(
                [
                    FieldError(
                        "relationships[].role",
                        "invalid_value",
                        f"must be one of {sorted(CATALOG_RELATIONSHIP_ROLES)}",
                    )
                ]
            )
        rel = CatalogRelationship(
            source_entity_id=source_entity_id,
            target_entity_id=target_id,
            cardinality=cardinality,
            role=role,
            description=r.get("description", "") or "",
        )
        session.add(rel)
        session.flush()
        for p in r.get("presence") or []:
            system = p.get("system")
            if system not in CATALOG_SYSTEMS:
                raise ValidationError(
                    [
                        FieldError(
                            "relationships[].presence[].system",
                            "invalid_value",
                            f"unknown system {system!r}",
                        )
                    ]
                )
            status = p.get("status")
            if status not in CATALOG_PRESENCE_STATUSES:
                raise ValidationError(
                    [
                        FieldError(
                            "relationships[].presence[].status",
                            "invalid_value",
                            f"must be one of {sorted(CATALOG_PRESENCE_STATUSES)}",
                        )
                    ]
                )
            session.add(
                CatalogRelationshipPresence(
                    catalog_relationship_id=rel.id,
                    system=system,
                    status=status,
                )
            )
