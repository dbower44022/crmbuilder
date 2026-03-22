"""YAML program file loading and validation."""

import logging
from pathlib import Path

import yaml

from espo_impl.core.models import (
    EntityDefinition,
    FieldDefinition,
    ProgramFile,
)

logger = logging.getLogger(__name__)

SUPPORTED_FIELD_TYPES: set[str] = {
    "varchar",
    "text",
    "enum",
    "multiEnum",
    "bool",
    "int",
    "float",
    "date",
    "datetime",
    "currency",
    "url",
    "email",
    "phone",
}

ENUM_TYPES: set[str] = {"enum", "multiEnum"}


class ConfigLoader:
    """Loads and validates YAML program files.

    :param path: Path to the YAML program file.
    """

    def load_program(self, path: Path) -> ProgramFile:
        """Parse a YAML program file into a ProgramFile.

        :param path: Path to the YAML file.
        :returns: Parsed ProgramFile.
        :raises ValueError: If the file cannot be parsed as YAML.
        """
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError("YAML file must contain a mapping at the top level")

        entities: list[EntityDefinition] = []
        raw_entities = raw.get("entities", {})
        if isinstance(raw_entities, dict):
            for entity_name, entity_data in raw_entities.items():
                fields: list[FieldDefinition] = []
                raw_fields = entity_data.get("fields", []) if isinstance(entity_data, dict) else []
                for field_data in raw_fields:
                    if not isinstance(field_data, dict):
                        continue
                    fields.append(self._parse_field(field_data))
                entities.append(EntityDefinition(name=entity_name, fields=fields))

        return ProgramFile(
            version=str(raw.get("version", "")),
            description=str(raw.get("description", "")),
            entities=entities,
            source_path=path,
        )

    def validate_program(self, program: ProgramFile) -> list[str]:
        """Validate a parsed program file.

        :param program: Parsed program file to validate.
        :returns: List of error messages. Empty list means valid.
        """
        errors: list[str] = []

        if not program.version:
            errors.append("Missing required top-level key: 'version'")
        if not program.description:
            errors.append("Missing required top-level key: 'description'")
        if not program.entities:
            errors.append("Missing or empty 'entities' section")
            return errors

        for entity in program.entities:
            seen_names: set[str] = set()
            for field_def in entity.fields:
                errors.extend(
                    self._validate_field(entity.name, field_def, seen_names)
                )

        return errors

    def _parse_field(self, data: dict) -> FieldDefinition:
        """Convert a raw dict to a FieldDefinition.

        :param data: Raw field data from YAML.
        :returns: FieldDefinition instance.
        """
        return FieldDefinition(
            name=data.get("name", ""),
            type=data.get("type", ""),
            label=data.get("label", ""),
            required=data.get("required", False),
            default=data.get("default"),
            readOnly=data.get("readOnly", False),
            audited=data.get("audited", False),
            options=data.get("options"),
            translatedOptions=data.get("translatedOptions"),
            style=data.get("style"),
            isSorted=data.get("isSorted", False),
            displayAsLabel=data.get("displayAsLabel", False),
        )

    def _validate_field(
        self,
        entity_name: str,
        field_def: FieldDefinition,
        seen_names: set[str],
    ) -> list[str]:
        """Validate a single field definition.

        :param entity_name: Name of the containing entity.
        :param field_def: Field definition to validate.
        :param seen_names: Set of field names already encountered (for dupe detection).
        :returns: List of error messages.
        """
        errors: list[str] = []
        prefix = f"{entity_name}.{field_def.name or '(unnamed)'}"

        if not field_def.name:
            errors.append(f"{prefix}: missing required property 'name'")
        if not field_def.type:
            errors.append(f"{prefix}: missing required property 'type'")
        elif field_def.type not in SUPPORTED_FIELD_TYPES:
            errors.append(
                f"{prefix}: unsupported field type '{field_def.type}'"
            )
        if not field_def.label:
            errors.append(f"{prefix}: missing required property 'label'")

        if field_def.type in ENUM_TYPES:
            if not field_def.options:
                errors.append(
                    f"{prefix}: enum/multiEnum fields must have a non-empty 'options' list"
                )

        if field_def.name:
            if field_def.name in seen_names:
                errors.append(
                    f"{prefix}: duplicate field name in entity '{entity_name}'"
                )
            seen_names.add(field_def.name)

        return errors
