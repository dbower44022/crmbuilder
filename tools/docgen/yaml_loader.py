"""Load and index all YAML program files."""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ENTITY_ORDER: list[str] = [
    "Account",
    "Contact",
    "Engagement",
    "Session",
    "NpsSurveyResponse",
    "Workshop",
    "WorkshopAttendance",
    "Dues",
    "PartnerAgreement",
    "ClientPartnerAssociation",
    "PartnerActivity",
]

ENTITY_DISPLAY_NAMES: dict[str, str] = {
    "Account": "Company",
    "NpsSurveyResponse": "NPS Survey Response",
    "WorkshopAttendance": "Workshop Attendance",
    "ClientPartnerAssociation": "Client-Partner Association",
    "PartnerAgreement": "Partner Agreement",
    "PartnerActivity": "Partner Activity",
}


def get_display_name(entity_name: str) -> str:
    """Get the friendly display name for an entity.

    :param entity_name: YAML entity name.
    :returns: Display name.
    """
    return ENTITY_DISPLAY_NAMES.get(entity_name, entity_name)


def load_programs(programs_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all YAML files and build an entity index.

    :param programs_dir: Directory containing YAML program files.
    :returns: Dict mapping entity name to entity data dict.
    """
    entities: dict[str, dict[str, Any]] = {}

    for path in sorted(programs_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse %s: %s", path, exc)
            continue

        if not isinstance(raw, dict):
            continue

        raw_entities = raw.get("entities", {})
        if not isinstance(raw_entities, dict):
            continue

        for entity_name, entity_data in raw_entities.items():
            if not isinstance(entity_data, dict):
                entity_data = {}

            if entity_name in entities:
                # Merge fields from multiple files
                existing_fields = entities[entity_name].get("fields", [])
                new_fields = entity_data.get("fields", [])
                if new_fields:
                    existing_names = {
                        f.get("name") for f in existing_fields
                        if isinstance(f, dict)
                    }
                    for f in new_fields:
                        if isinstance(f, dict):
                            fname = f.get("name")
                            if fname in existing_names:
                                logger.warning(
                                    "Entity '%s': duplicate field '%s' "
                                    "in %s (already defined)",
                                    entity_name,
                                    fname,
                                    path.name,
                                )
                            else:
                                existing_fields.append(f)
                                existing_names.add(fname)
                    entities[entity_name]["fields"] = existing_fields
                # Merge non-field keys (later file wins for scalar values)
                for key, val in entity_data.items():
                    if key != "fields":
                        entities[entity_name][key] = val
                entities[entity_name]["_source_file"] = path.name
            else:
                entities[entity_name] = {
                    **entity_data,
                    "_source_file": path.name,
                    "_entity_name": entity_name,
                }

    for path in sorted(programs_dir.glob("*.yml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(raw, dict):
            continue
        raw_entities = raw.get("entities", {})
        if isinstance(raw_entities, dict):
            for entity_name, entity_data in raw_entities.items():
                if entity_name not in entities and isinstance(entity_data, dict):
                    entities[entity_name] = {
                        **entity_data,
                        "_source_file": path.name,
                        "_entity_name": entity_name,
                    }

    return entities


def get_version(programs_dir: Path) -> str:
    """Get the version string from the first YAML file.

    :param programs_dir: Directory containing YAML program files.
    :returns: Version string.
    """
    for path in sorted(programs_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "version" in raw:
                return str(raw["version"])
        except yaml.YAMLError:
            continue
    return "1.0"


def ordered_entities(
    entities: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Return entities in canonical order.

    :param entities: Entity index dict.
    :returns: List of (entity_name, entity_data) in order.
    """
    result: list[tuple[str, dict[str, Any]]] = []

    for name in ENTITY_ORDER:
        if name in entities:
            result.append((name, entities[name]))

    for name in sorted(entities.keys()):
        if name not in ENTITY_ORDER:
            result.append((name, entities[name]))

    return result
