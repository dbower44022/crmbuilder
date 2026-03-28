"""YAML program file loading and validation."""

import logging
from pathlib import Path
from typing import Any

import yaml

from espo_impl.core.models import (
    SUPPORTED_ENTITY_TYPES,
    ColumnSpec,
    EntityAction,
    EntityDefinition,
    FieldDefinition,
    LayoutSpec,
    PanelSpec,
    ProgramFile,
    RelationshipDefinition,
    TabSpec,
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

VALID_LAYOUT_TYPES: set[str] = {"detail", "edit", "list"}

VALID_LINK_TYPES: set[str] = {"oneToMany", "manyToOne", "manyToMany"}


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

                # Parse fields (list or dict format)
                fields: list[FieldDefinition] = []
                raw_fields = entity_data.get("fields", [])
                if isinstance(raw_fields, list):
                    for field_data in raw_fields:
                        if isinstance(field_data, dict):
                            fields.append(self._parse_field(field_data))
                elif isinstance(raw_fields, dict):
                    for field_name, field_data in raw_fields.items():
                        if isinstance(field_data, dict):
                            field_data.setdefault("name", field_name)
                            fields.append(self._parse_field(field_data))

                # Parse layouts
                layouts: dict[str, LayoutSpec] = {}
                raw_layout = entity_data.get("layout", {})
                if isinstance(raw_layout, dict):
                    for layout_type, layout_data in raw_layout.items():
                        if isinstance(layout_data, dict):
                            layouts[layout_type] = self._parse_layout(
                                layout_type, layout_data
                            )

                entities.append(EntityDefinition(
                    name=entity_name,
                    fields=fields,
                    action=action,
                    type=entity_data.get("type"),
                    labelSingular=entity_data.get("labelSingular"),
                    labelPlural=entity_data.get("labelPlural"),
                    stream=entity_data.get("stream", False),
                    disabled=entity_data.get("disabled", False),
                    layouts=layouts,
                    description=entity_data.get("description"),
                ))

        # Parse relationships
        relationships: list[RelationshipDefinition] = []
        raw_rels = raw.get("relationships", [])
        if isinstance(raw_rels, list):
            for rel_data in raw_rels:
                if isinstance(rel_data, dict):
                    relationships.append(self._parse_relationship(rel_data))

        return ProgramFile(
            version=str(raw.get("version", "")),
            description=str(raw.get("description", "")),
            content_version=str(raw.get("content_version", "1.0.0")),
            entities=entities,
            source_path=path,
            relationships=relationships,
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
        if not program.entities and not program.relationships:
            errors.append("Missing or empty 'entities' and 'relationships' sections")
            return errors

        for entity in program.entities:
            errors.extend(self._validate_entity(entity))

        for rel in program.relationships:
            errors.extend(self._validate_relationship(rel))

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

        # Validate layouts
        for layout_type, layout_spec in entity.layouts.items():
            errors.extend(
                self._validate_layout(entity, layout_type, layout_spec)
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
            copyToClipboard=data.get("copyToClipboard"),
            options=data.get("options"),
            optionDescriptions=data.get("optionDescriptions"),
            translatedOptions=data.get("translatedOptions"),
            style=data.get("style"),
            isSorted=data.get("isSorted"),
            displayAsLabel=data.get("displayAsLabel"),
            min=data.get("min"),
            max=data.get("max"),
            maxLength=data.get("maxLength"),
            category=data.get("category"),
            description=data.get("description"),
            tooltip=data.get("tooltip"),
        )

    def _parse_layout(
        self, layout_type: str, data: dict[str, Any]
    ) -> LayoutSpec:
        """Parse a layout definition from YAML.

        :param layout_type: Layout type (detail, edit, list).
        :param data: Raw layout data.
        :returns: LayoutSpec instance.
        """
        if layout_type == "list":
            columns: list[ColumnSpec] = []
            for col_data in data.get("columns", []):
                columns.append(self._parse_column(col_data))
            return LayoutSpec(
                layout_type=layout_type, columns=columns
            )

        # detail or edit layout
        panels: list[PanelSpec] = []
        for panel_data in data.get("panels", []):
            if isinstance(panel_data, dict):
                panels.append(self._parse_panel(panel_data))
        return LayoutSpec(layout_type=layout_type, panels=panels)

    def _parse_panel(self, data: dict[str, Any]) -> PanelSpec:
        """Parse a panel definition from YAML.

        :param data: Raw panel data.
        :returns: PanelSpec instance.
        """
        tabs: list[TabSpec] | None = None
        raw_tabs = data.get("tabs")
        if isinstance(raw_tabs, list):
            tabs = [self._parse_tab(t) for t in raw_tabs if isinstance(t, dict)]

        return PanelSpec(
            label=data.get("label", ""),
            tabBreak=data.get("tabBreak", False),
            tabLabel=data.get("tabLabel"),
            style=data.get("style", "default"),
            hidden=data.get("hidden", False),
            dynamicLogicVisible=data.get("dynamicLogicVisible"),
            rows=data.get("rows"),
            tabs=tabs,
            description=data.get("description"),
        )

    def _parse_tab(self, data: dict[str, Any]) -> TabSpec:
        """Parse a tab definition from YAML.

        :param data: Raw tab data.
        :returns: TabSpec instance.
        """
        return TabSpec(
            label=data.get("label", ""),
            category=data.get("category", ""),
            rows=data.get("rows"),
        )

    def _parse_column(self, data: dict | str) -> ColumnSpec:
        """Parse a column definition from YAML.

        :param data: Raw column data (dict or string shorthand).
        :returns: ColumnSpec instance.
        """
        if isinstance(data, str):
            return ColumnSpec(field=data)
        return ColumnSpec(
            field=data.get("field", ""),
            width=data.get("width"),
        )

    def _validate_layout(
        self,
        entity: EntityDefinition,
        layout_type: str,
        layout_spec: LayoutSpec,
    ) -> list[str]:
        """Validate a layout definition.

        :param entity: The containing entity definition.
        :param layout_type: Layout type string.
        :param layout_spec: Layout specification to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        prefix = f"{entity.name}.layout.{layout_type}"

        if layout_type not in VALID_LAYOUT_TYPES:
            errors.append(f"{prefix}: unsupported layout type '{layout_type}'")
            return errors

        if layout_type == "list":
            if not layout_spec.columns:
                errors.append(f"{prefix}: list layout must have 'columns'")
            if layout_spec.panels:
                errors.append(
                    f"{prefix}: list layout must not have 'panels'"
                )
            return errors

        # detail / edit layout
        if not layout_spec.panels:
            errors.append(f"{prefix}: detail/edit layout must have 'panels'")
            return errors

        field_names = {f.name for f in entity.fields}
        field_categories = {
            f.category for f in entity.fields if f.category
        }
        seen_labels: set[str] = set()

        for panel in layout_spec.panels:
            panel_prefix = f"{prefix}.panel[{panel.label}]"

            if panel.label in seen_labels:
                errors.append(
                    f"{panel_prefix}: duplicate panel label"
                )
            seen_labels.add(panel.label)

            if panel.rows is not None and panel.tabs is not None:
                errors.append(
                    f"{panel_prefix}: panel cannot have both 'rows' and 'tabs'"
                )

            if panel.tabBreak and not panel.tabLabel:
                errors.append(
                    f"{panel_prefix}: 'tabLabel' is required when "
                    f"'tabBreak' is true"
                )

            if panel.tabs:
                for tab in panel.tabs:
                    if tab.category and tab.category not in field_categories:
                        errors.append(
                            f"{panel_prefix}.tab[{tab.label}]: "
                            f"category '{tab.category}' not found in "
                            f"any field definition"
                        )

            if panel.rows:
                for row in panel.rows:
                    if isinstance(row, list):
                        for cell in row:
                            if isinstance(cell, str) and cell not in field_names:
                                # Allow native field names (not in YAML fields)
                                pass

        return errors

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

        if field_def.optionDescriptions is not None:
            if field_def.type not in ENUM_TYPES:
                errors.append(
                    f"{prefix}: 'optionDescriptions' is only valid on "
                    f"enum/multiEnum fields"
                )
            elif field_def.options:
                option_set = set(field_def.options)
                for key in field_def.optionDescriptions:
                    if key not in option_set:
                        errors.append(
                            f"{prefix}: optionDescriptions key '{key}' "
                            f"does not match any value in 'options'"
                        )
            else:
                logger.warning(
                    "%s: optionDescriptions present but 'options' is empty "
                    "or absent — descriptions cannot be cross-referenced",
                    prefix,
                )

        if field_def.name:
            if field_def.name in seen_names:
                errors.append(
                    f"{prefix}: duplicate field name in entity '{entity_name}'"
                )
            seen_names.add(field_def.name)

        return errors

    def _parse_relationship(self, data: dict) -> RelationshipDefinition:
        """Parse a relationship definition from YAML.

        :param data: Raw relationship data.
        :returns: RelationshipDefinition instance.
        """
        return RelationshipDefinition(
            name=data.get("name", ""),
            description=data.get("description"),
            entity=data.get("entity", ""),
            entity_foreign=data.get("entityForeign", ""),
            link_type=data.get("linkType", ""),
            link=data.get("link", ""),
            link_foreign=data.get("linkForeign", ""),
            label=data.get("label", ""),
            label_foreign=data.get("labelForeign", ""),
            relation_name=data.get("relationName"),
            audited=data.get("audited", False),
            audited_foreign=data.get("auditedForeign", False),
            action=data.get("action"),
        )

    def _validate_relationship(
        self, rel: RelationshipDefinition
    ) -> list[str]:
        """Validate a relationship definition.

        :param rel: Relationship definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        prefix = f"relationship[{rel.name or '(unnamed)'}]"

        required_fields = {
            "name": rel.name,
            "entity": rel.entity,
            "entityForeign": rel.entity_foreign,
            "link": rel.link,
            "linkForeign": rel.link_foreign,
            "label": rel.label,
            "labelForeign": rel.label_foreign,
        }
        for field_name, value in required_fields.items():
            if not value:
                errors.append(
                    f"{prefix}: missing required property '{field_name}'"
                )

        if rel.link_type and rel.link_type not in VALID_LINK_TYPES:
            errors.append(
                f"{prefix}: invalid linkType '{rel.link_type}' "
                f"(must be one of: {', '.join(sorted(VALID_LINK_TYPES))})"
            )
        elif not rel.link_type:
            errors.append(f"{prefix}: missing required property 'linkType'")

        if rel.link_type == "manyToMany" and not rel.relation_name:
            errors.append(
                f"{prefix}: 'relationName' is required for "
                f"manyToMany relationships"
            )

        if rel.action is not None and rel.action != "skip":
            errors.append(
                f"{prefix}: invalid action '{rel.action}' "
                f"(must be 'skip' or omitted)"
            )

        return errors
