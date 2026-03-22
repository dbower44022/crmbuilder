"""YAML program file loading and validation."""

import logging
from pathlib import Path

import yaml

from espo_impl.core.models import (
    SUPPORTED_ENTITY_TYPES,
    EntityAction,
    EntityDefinition,
    FieldDefinition,
    ProgramFile,
)

logger = logging.getLogger(__name__)

SUPPORTED_FIELD_TYPES: set[str] = {
    "varchar",
    "text",
    "wysiwyg",
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

VALID_ACTIONS: set[str] = {"create", "delete", "delete_and_create"}


class ConfigLoader:
    """Loads and validates YAML program files."""

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
                if not isinstance(entity_data, dict):
                    entity_data = {}

                # Parse entity action
                raw_action = entity_data.get("action")
                if raw_action is None:
                    action = EntityAction.NONE
                elif raw_action in VALID_ACTIONS:
                    action = EntityAction(raw_action)
                else:
                    action = EntityAction.NONE

                # Parse fields
                fields: list[FieldDefinition] = []
                raw_fields = entity_data.get("fields", [])
                if isinstance(raw_fields, list):
                    for field_data in raw_fields:
                        if isinstance(field_data, dict):
                            fields.append(self._parse_field(field_data))

                entities.append(EntityDefinition(
                    name=entity_name,
                    fields=fields,
                    action=action,
                    type=entity_data.get("type"),
                    labelSingular=entity_data.get("labelSingular"),
                    labelPlural=entity_data.get("labelPlural"),
                    stream=entity_data.get("stream", False),
                    disabled=entity_data.get("disabled", False),
                ))

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
            errors.extend(self._validate_entity(entity))

        return errors

    def _validate_entity(self, entity: EntityDefinition) -> list[str]:
        """Validate an entity definition.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []

        if entity.action in (EntityAction.CREATE, EntityAction.DELETE_AND_CREATE):
            if not entity.type:
                errors.append(
                    f"{entity.name}: 'type' is required for "
                    f"action '{entity.action.value}'"
                )
            elif entity.type not in SUPPORTED_ENTITY_TYPES:
                errors.append(
                    f"{entity.name}: unsupported entity type '{entity.type}'"
                )
            if not entity.labelSingular:
                errors.append(
                    f"{entity.name}: 'labelSingular' is required for "
                    f"action '{entity.action.value}'"
                )
            if not entity.labelPlural:
                errors.append(
                    f"{entity.name}: 'labelPlural' is required for "
                    f"action '{entity.action.value}'"
                )

        if entity.action == EntityAction.DELETE and entity.fields:
            errors.append(
                f"{entity.name}: 'action: delete' must not contain 'fields' "
                f"(fields on a deleted entity make no sense)"
            )

        # Validate fields
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
            required=data.get("required"),
            default=data.get("default"),
            readOnly=data.get("readOnly"),
            audited=data.get("audited"),
            options=data.get("options"),
            translatedOptions=data.get("translatedOptions"),
            style=data.get("style"),
            isSorted=data.get("isSorted"),
            displayAsLabel=data.get("displayAsLabel"),
            min=data.get("min"),
            max=data.get("max"),
            maxLength=data.get("maxLength"),
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
