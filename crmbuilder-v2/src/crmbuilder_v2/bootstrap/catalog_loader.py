"""Base entity catalog loader (catalog-ingestion-PRD-v0.1.md section 5).

Reads the YAML files under
``PRDs/product/crmbuilder-v2/research/base-entity-catalog/`` (the
top-level directory holds universals; ``subclasses/`` holds subclasses)
and populates the ten catalog tables. Idempotent — re-running against
an already-populated database produces the same final state via
upsert-by-``catalog_id`` (entities), upsert-by-``(entity_id, name)``
(attributes), and delete-and-recreate per parent for the granular
child rows (synonyms, systems, sources, enum values, presence, and
relationships).

The loader does not own a session; the caller passes one in and the
caller controls commit/rollback semantics. (PI-β slice 4 removed the
JSON-snapshot export machinery, including the per-entity catalog export;
the ``suppress_exports`` parameter below is now a no-op kept for call
compatibility.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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


@dataclass
class CatalogLoadReport:
    """Counts and validation result from a load run."""

    entities_inserted: int = 0
    entities_updated: int = 0
    attributes_inserted: int = 0
    attributes_updated: int = 0
    presence_cells_inserted: int = 0
    relationships_inserted: int = 0
    synonyms_inserted: int = 0
    sources_inserted: int = 0
    enum_values_inserted: int = 0
    entity_systems_inserted: int = 0
    relationship_presence_inserted: int = 0
    validation_failures: list[str] = field(default_factory=list)

    @property
    def total_entities(self) -> int:
        return self.entities_inserted + self.entities_updated

    @property
    def total_attributes(self) -> int:
        return self.attributes_inserted + self.attributes_updated


class CatalogLoaderError(RuntimeError):
    """Raised on validation failure or unrecoverable load error."""


def load_catalog(
    session: Session,
    yaml_dir: Path,
    *,
    suppress_exports: bool = True,
) -> CatalogLoadReport:
    """Load all catalog YAMLs from ``yaml_dir`` into the database.

    Three-pass: universals → subclasses → relationships. The caller owns
    the session and the commit; if validation fails, this function
    raises ``CatalogLoaderError`` and the caller should roll back.

    The ``suppress_exports`` parameter is reserved for the per-entity
    catalog export hook (DEC-008) that fires from the access layer's
    write methods. The loader writes through the ORM directly, not the
    access layer, so the flag is currently a no-op; it stays in the API
    so a future loader that uses the access layer can honour it.
    """
    if not yaml_dir.exists():
        raise CatalogLoaderError(f"catalog directory not found: {yaml_dir}")

    universals, subclasses = _discover_yaml_files(yaml_dir)
    if not universals:
        raise CatalogLoaderError(f"no universal YAML files in {yaml_dir}")

    report = CatalogLoadReport()
    parsed: list[tuple[Path, dict]] = []

    # Pass 1 — universals
    for path in sorted(universals):
        doc = _parse_yaml(path)
        parsed.append((path, doc))
        _upsert_entity_and_children(session, doc, parent_entity_id=None, report=report)

    # Pass 2 — subclasses (parent_entity_id resolved from Pass 1 state)
    for path in sorted(subclasses):
        doc = _parse_yaml(path)
        parsed.append((path, doc))
        parent_catalog_id = doc.get("parent_entity")
        if not parent_catalog_id:
            raise CatalogLoaderError(
                f"{path}: subclass missing parent_entity"
            )
        parent_id = _resolve_entity_id_by_catalog_id(session, parent_catalog_id)
        if parent_id is None:
            raise CatalogLoaderError(
                f"{path}: parent_entity {parent_catalog_id!r} not found "
                f"(expected to be loaded in Pass 1)"
            )
        _upsert_entity_and_children(
            session, doc, parent_entity_id=parent_id, report=report
        )

    # Pass 3 — relationships (iterate every loaded entity)
    for path, doc in parsed:
        catalog_id = doc["catalog_id"]
        source_id = _resolve_entity_id_by_catalog_id(session, catalog_id)
        # Delete existing outbound relationships so re-runs are clean.
        existing = list(
            session.scalars(
                select(CatalogRelationship).where(
                    CatalogRelationship.source_entity_id == source_id
                )
            )
        )
        for rel in existing:
            session.execute(
                delete(CatalogRelationshipPresence).where(
                    CatalogRelationshipPresence.catalog_relationship_id == rel.id
                )
            )
            session.delete(rel)
        session.flush()

        for r in doc.get("relationships", []) or []:
            target_catalog_id = r.get("target")
            target_id = _resolve_entity_id_by_catalog_id(session, target_catalog_id)
            if target_id is None:
                raise CatalogLoaderError(
                    f"{path}: relationship target {target_catalog_id!r} not found"
                )
            cardinality = r.get("cardinality")
            role = r.get("role")
            if cardinality not in CATALOG_RELATIONSHIP_CARDINALITIES:
                raise CatalogLoaderError(
                    f"{path}: invalid cardinality {cardinality!r} on relationship to {target_catalog_id}"
                )
            if role not in CATALOG_RELATIONSHIP_ROLES:
                raise CatalogLoaderError(
                    f"{path}: invalid role {role!r} on relationship to {target_catalog_id}"
                )
            rel = CatalogRelationship(
                source_entity_id=source_id,
                target_entity_id=target_id,
                cardinality=cardinality,
                role=role,
                description=_dedent(r.get("description", "")),
            )
            session.add(rel)
            session.flush()
            report.relationships_inserted += 1

            for system, status_value in (r.get("presence") or {}).items():
                if isinstance(status_value, dict):
                    status_str = status_value.get("status")
                else:
                    status_str = status_value
                if system not in CATALOG_SYSTEMS:
                    raise CatalogLoaderError(
                        f"{path}: relationship presence has unknown system {system!r}"
                    )
                if status_str not in CATALOG_PRESENCE_STATUSES:
                    raise CatalogLoaderError(
                        f"{path}: relationship presence has bad status {status_str!r} for {system}"
                    )
                session.add(
                    CatalogRelationshipPresence(
                        catalog_relationship_id=rel.id,
                        system=system,
                        status=status_str,
                    )
                )
                report.relationship_presence_inserted += 1
    session.flush()

    # Final validation across the populated tables.
    _validate_after_load(session, report)
    if report.validation_failures:
        raise CatalogLoaderError(
            "catalog load validation failed:\n  - "
            + "\n  - ".join(report.validation_failures)
        )

    return report


# ---------------------------------------------------------------------------
# YAML discovery and parsing
# ---------------------------------------------------------------------------


def _discover_yaml_files(yaml_dir: Path) -> tuple[list[Path], list[Path]]:
    """Return (universal_yaml_paths, subclass_yaml_paths).

    Universals are *.yaml at the top of ``yaml_dir`` (excluding README).
    Subclasses are *.yaml under ``yaml_dir/subclasses/`` if it exists.
    """
    universals = [
        p for p in yaml_dir.glob("*.yaml")
        if p.is_file() and p.name != "README.md"
    ]
    subclasses_dir = yaml_dir / "subclasses"
    subclasses: list[Path] = []
    if subclasses_dir.exists():
        subclasses = [p for p in subclasses_dir.glob("*.yaml") if p.is_file()]
    return universals, subclasses


def _parse_yaml(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise CatalogLoaderError(f"{path}: invalid YAML — {exc}") from exc
    if not isinstance(doc, dict):
        raise CatalogLoaderError(f"{path}: top-level YAML must be a mapping")
    for required in ("catalog_id", "name", "display_name", "tier", "entry_kind"):
        if required not in doc:
            raise CatalogLoaderError(f"{path}: missing required field {required!r}")
    if doc["entry_kind"] not in CATALOG_ENTRY_KINDS:
        raise CatalogLoaderError(
            f"{path}: entry_kind {doc['entry_kind']!r} not in {sorted(CATALOG_ENTRY_KINDS)}"
        )
    return doc


# ---------------------------------------------------------------------------
# Entity upsert + child-row replacement
# ---------------------------------------------------------------------------


def _resolve_entity_id_by_catalog_id(
    session: Session, catalog_id: str | None
) -> int | None:
    if not catalog_id:
        return None
    row = session.scalar(
        select(CatalogEntity).where(CatalogEntity.catalog_id == catalog_id)
    )
    return row.id if row else None


def _upsert_entity_and_children(
    session: Session,
    doc: dict,
    *,
    parent_entity_id: int | None,
    report: CatalogLoadReport,
) -> None:
    catalog_id = doc["catalog_id"]
    discriminator = doc.get("discriminator") or {}
    data_model_role = doc.get("data_model_role")
    if data_model_role not in CATALOG_DATA_MODEL_ROLES:
        raise CatalogLoaderError(
            f"{catalog_id}: data_model_role {data_model_role!r} not in "
            f"{sorted(CATALOG_DATA_MODEL_ROLES)}"
        )

    now = datetime.now(UTC)
    existing = session.scalar(
        select(CatalogEntity).where(CatalogEntity.catalog_id == catalog_id)
    )
    if existing is None:
        ent = CatalogEntity(
            catalog_id=catalog_id,
            name=doc["name"],
            display_name=doc.get("display_name") or doc["name"],
            tier=int(doc["tier"]),
            entry_kind=doc["entry_kind"],
            parent_entity_id=parent_entity_id,
            discriminator_attribute=discriminator.get("attribute"),
            discriminator_value=discriminator.get("value"),
            purpose=_dedent(doc.get("purpose", "")),
            business_context=_dedent(doc.get("business_context", "")),
            data_model_role=data_model_role,
            typically_required=bool(doc.get("typically_required", False)),
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        session.add(ent)
        session.flush()
        report.entities_inserted += 1
    else:
        ent = existing
        ent.name = doc["name"]
        ent.display_name = doc.get("display_name") or doc["name"]
        ent.tier = int(doc["tier"])
        ent.entry_kind = doc["entry_kind"]
        ent.parent_entity_id = parent_entity_id
        ent.discriminator_attribute = discriminator.get("attribute")
        ent.discriminator_value = discriminator.get("value")
        ent.purpose = _dedent(doc.get("purpose", ""))
        ent.business_context = _dedent(doc.get("business_context", ""))
        ent.data_model_role = data_model_role
        ent.typically_required = bool(doc.get("typically_required", False))
        ent.is_deleted = False
        ent.updated_at = now
        session.flush()
        report.entities_updated += 1

    # Replace entity-child rows.
    _replace_entity_synonyms(session, ent.id, doc.get("common_synonyms") or [], report)
    _replace_entity_systems(session, ent.id, doc.get("systems") or [], report)
    _replace_entity_sources(session, ent.id, doc.get("sources") or [], report)

    # Upsert attributes (per-attribute child rows are replaced inside the helper).
    for order, attr in enumerate(doc.get("attributes") or []):
        _upsert_attribute(session, ent.id, attr, order_index=order, report=report)


def _replace_entity_synonyms(
    session: Session,
    entity_id: int,
    synonyms: list[str],
    report: CatalogLoadReport,
) -> None:
    session.execute(
        delete(CatalogEntitySynonym).where(
            CatalogEntitySynonym.catalog_entity_id == entity_id
        )
    )
    for order, syn in enumerate(synonyms):
        session.add(
            CatalogEntitySynonym(
                catalog_entity_id=entity_id, synonym=syn, order_index=order
            )
        )
        report.synonyms_inserted += 1


def _replace_entity_systems(
    session: Session,
    entity_id: int,
    systems: list[dict],
    report: CatalogLoadReport,
) -> None:
    session.execute(
        delete(CatalogEntitySystem).where(
            CatalogEntitySystem.catalog_entity_id == entity_id
        )
    )
    for s in systems:
        system = s.get("system")
        if system not in CATALOG_SYSTEMS:
            raise CatalogLoaderError(
                f"entity_id {entity_id}: unknown system {system!r}"
            )
        is_standard = str(s.get("is_standard")).lower()
        if is_standard not in CATALOG_IS_STANDARD_VALUES:
            raise CatalogLoaderError(
                f"entity_id {entity_id}: bad is_standard {s.get('is_standard')!r}"
            )
        mechanism = s.get("mechanism")
        if mechanism is not None and mechanism not in CATALOG_MECHANISMS:
            raise CatalogLoaderError(
                f"entity_id {entity_id}: bad mechanism {mechanism!r}"
            )
        session.add(
            CatalogEntitySystem(
                catalog_entity_id=entity_id,
                system=system,
                system_name=s.get("name") or "",
                api_name=s.get("api_name"),
                is_standard=is_standard,
                mechanism=mechanism,
                notes=_dedent(s.get("notes")) if s.get("notes") else None,
                docs_url=s.get("docs_url"),
            )
        )
        report.entity_systems_inserted += 1


def _replace_entity_sources(
    session: Session,
    entity_id: int,
    sources: list[dict],
    report: CatalogLoadReport,
) -> None:
    session.execute(
        delete(CatalogSource).where(CatalogSource.catalog_entity_id == entity_id)
    )
    for order, src in enumerate(sources):
        session.add(
            CatalogSource(
                catalog_entity_id=entity_id,
                title=src.get("title", ""),
                url=src.get("url", ""),
                order_index=order,
            )
        )
        report.sources_inserted += 1


def _upsert_attribute(
    session: Session,
    entity_id: int,
    attr: dict,
    *,
    order_index: int,
    report: CatalogLoadReport,
) -> None:
    name = attr.get("name")
    if not name:
        raise CatalogLoaderError(f"entity_id {entity_id}: attribute missing 'name'")
    type_value = attr.get("type")
    if type_value not in CATALOG_ATTRIBUTE_TYPES:
        raise CatalogLoaderError(
            f"entity_id {entity_id}: attribute {name!r} has bad type {type_value!r}"
        )
    now = datetime.now(UTC)
    existing = session.scalar(
        select(CatalogAttribute).where(
            (CatalogAttribute.catalog_entity_id == entity_id)
            & (CatalogAttribute.name == name)
        )
    )
    if existing is None:
        row = CatalogAttribute(
            catalog_entity_id=entity_id,
            name=name,
            display_name=attr.get("display_name") or name,
            type=type_value,
            required=bool(attr.get("required", False)),
            max_length=attr.get("max_length"),
            reference_target=attr.get("reference_target"),
            description=_dedent(attr.get("description", "")),
            usage=_dedent(attr.get("usage", "")),
            notes=_dedent(attr.get("notes")) if attr.get("notes") else None,
            order_index=order_index,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        report.attributes_inserted += 1
    else:
        row = existing
        row.display_name = attr.get("display_name") or name
        row.type = type_value
        row.required = bool(attr.get("required", False))
        row.max_length = attr.get("max_length")
        row.reference_target = attr.get("reference_target")
        row.description = _dedent(attr.get("description", ""))
        row.usage = _dedent(attr.get("usage", ""))
        row.notes = _dedent(attr.get("notes")) if attr.get("notes") else None
        row.order_index = order_index
        row.is_deleted = False
        row.updated_at = now
        session.flush()
        report.attributes_updated += 1

    _replace_attribute_enum_values(session, row.id, attr.get("enum_values") or [])
    report.enum_values_inserted += len(attr.get("enum_values") or [])
    _replace_attribute_synonyms(session, row.id, attr.get("common_synonyms") or [])
    report.synonyms_inserted += len(attr.get("common_synonyms") or [])
    cells = _replace_attribute_presence(session, row.id, attr.get("presence") or {})
    report.presence_cells_inserted += cells


def _replace_attribute_enum_values(
    session: Session, attribute_id: int, values: list[str]
) -> None:
    session.execute(
        delete(CatalogAttributeEnumValue).where(
            CatalogAttributeEnumValue.catalog_attribute_id == attribute_id
        )
    )
    for order, v in enumerate(values):
        session.add(
            CatalogAttributeEnumValue(
                catalog_attribute_id=attribute_id,
                value=str(v),
                order_index=order,
            )
        )


def _replace_attribute_synonyms(
    session: Session, attribute_id: int, synonyms: list[str]
) -> None:
    session.execute(
        delete(CatalogAttributeSynonym).where(
            CatalogAttributeSynonym.catalog_attribute_id == attribute_id
        )
    )
    for order, syn in enumerate(synonyms):
        session.add(
            CatalogAttributeSynonym(
                catalog_attribute_id=attribute_id,
                synonym=syn,
                order_index=order,
            )
        )


def _replace_attribute_presence(
    session: Session, attribute_id: int, presence: dict[str, Any]
) -> int:
    session.execute(
        delete(CatalogAttributePresence).where(
            CatalogAttributePresence.catalog_attribute_id == attribute_id
        )
    )
    cells = 0
    for system, p_obj in presence.items():
        if system not in CATALOG_SYSTEMS:
            raise CatalogLoaderError(
                f"attribute_id {attribute_id}: presence has unknown system {system!r}"
            )
        if isinstance(p_obj, dict):
            status_str = p_obj.get("status")
            api_name = p_obj.get("api_name")
        else:
            status_str = p_obj
            api_name = None
        if status_str not in CATALOG_PRESENCE_STATUSES:
            raise CatalogLoaderError(
                f"attribute_id {attribute_id}: presence has bad status {status_str!r}"
            )
        session.add(
            CatalogAttributePresence(
                catalog_attribute_id=attribute_id,
                system=system,
                status=status_str,
                api_name=api_name,
            )
        )
        cells += 1
    return cells


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_after_load(session: Session, report: CatalogLoadReport) -> None:
    # Every subclass must have parent_entity_id resolved.
    bad_subclasses = list(
        session.scalars(
            select(CatalogEntity).where(
                (CatalogEntity.entry_kind == "subclass")
                & (CatalogEntity.parent_entity_id.is_(None))
            )
        )
    )
    if bad_subclasses:
        report.validation_failures.append(
            "subclasses missing parent_entity_id: "
            + ", ".join(e.catalog_id for e in bad_subclasses)
        )

    # catalog_id uniqueness is enforced by UNIQUE constraint, but we re-check
    # to surface a clearer error if a future loader inadvertently bypasses it.
    seen: set[str] = set()
    for cid in session.scalars(select(CatalogEntity.catalog_id)):
        if cid in seen:
            report.validation_failures.append(f"duplicate catalog_id: {cid}")
        seen.add(cid)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedent(value: str | None) -> str:
    """Normalise YAML-folded long-text blocks: strip leading/trailing whitespace."""
    if value is None:
        return ""
    return str(value).strip()
