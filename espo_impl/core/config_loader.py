"""YAML program file loading and validation."""

import logging
from pathlib import Path
from typing import Any

import yaml

from espo_impl.core.condition_expression import parse_condition, validate_condition
from espo_impl.core.models import (
    SUPPORTED_ENTITY_TYPES,
    VALID_NORMALIZE_VALUES,
    VALID_ON_MATCH_VALUES,
    VALID_SETTINGS_KEYS,
    ColumnSpec,
    DuplicateCheck,
    EntityAction,
    EntityDefinition,
    EntitySettings,
    FieldDefinition,
    LayoutSpec,
    OrderByClause,
    PanelSpec,
    ProgramFile,
    RelationshipDefinition,
    SavedView,
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

        deprecation_warnings: list[str] = []

        # Keys that moved from entity top-level to settings: in v1.1
        _DEPRECATED_ENTITY_KEYS = {
            "labelSingular", "labelPlural", "stream", "disabled",
        }

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

                # Deprecation warnings for v1.0 top-level entity keys
                for dep_key in _DEPRECATED_ENTITY_KEYS:
                    if dep_key in entity_data:
                        msg = (
                            f"{entity_name}: '{dep_key}' at entity top level "
                            f"is deprecated in v1.1; use 'settings.{dep_key}' "
                            f"instead"
                        )
                        logger.warning(msg)
                        deprecation_warnings.append(msg)

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
                                layout_type, layout_data,
                                entity_name=entity_name,
                                deprecation_warnings=deprecation_warnings,
                            )

                # Pass-through entity-level v1.1 keys (raw, unparsed)
                settings_raw = entity_data.get("settings")
                duplicate_checks_raw = entity_data.get("duplicateChecks")
                saved_views_raw = entity_data.get("savedViews")
                email_templates_raw = entity_data.get("emailTemplates")
                workflows_raw = entity_data.get("workflows")

                # Parse settings block into typed model
                settings = self._parse_settings(settings_raw)

                # Deprecation merge: top-level keys → settings when
                # the settings block doesn't already carry the value
                settings = self._deprecation_merge(
                    entity_name, entity_data, settings,
                    deprecation_warnings,
                )

                # Sync settings back to top-level fields for backward
                # compatibility (entity_manager.py reads these directly)
                label_singular = entity_data.get("labelSingular")
                label_plural = entity_data.get("labelPlural")
                stream_val = entity_data.get("stream", False)
                disabled_val = entity_data.get("disabled", False)
                if settings is not None:
                    if settings.labelSingular is not None:
                        label_singular = settings.labelSingular
                    if settings.labelPlural is not None:
                        label_plural = settings.labelPlural
                    if settings.stream is not None:
                        stream_val = settings.stream
                    if settings.disabled is not None:
                        disabled_val = settings.disabled

                # Parse duplicate checks into typed models
                duplicate_checks = self._parse_duplicate_checks(
                    duplicate_checks_raw
                )

                # Parse saved views into typed models
                saved_views = self._parse_saved_views(saved_views_raw)

                entities.append(EntityDefinition(
                    name=entity_name,
                    fields=fields,
                    action=action,
                    type=entity_data.get("type"),
                    labelSingular=label_singular,
                    labelPlural=label_plural,
                    stream=stream_val,
                    disabled=disabled_val,
                    layouts=layouts,
                    description=entity_data.get("description"),
                    settings=settings,
                    duplicate_checks=duplicate_checks,
                    saved_views=saved_views,
                    settings_raw=settings_raw,
                    duplicate_checks_raw=duplicate_checks_raw,
                    saved_views_raw=saved_views_raw,
                    email_templates_raw=email_templates_raw,
                    workflows_raw=workflows_raw,
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
            deprecation_warnings=deprecation_warnings,
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

        # Validate field-level requiredWhen / visibleWhen conditions
        errors.extend(self._validate_field_conditions(entity))

        # Validate settings

        # Validate duplicate checks
        errors.extend(self._validate_duplicate_checks(entity))

        # Validate saved views
        errors.extend(self._validate_saved_views(entity))

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
        # Parse requiredWhen and visibleWhen condition expressions
        rw_raw = data.get("requiredWhen")
        rw_parsed = None
        if rw_raw is not None:
            try:
                rw_parsed = parse_condition(rw_raw)
            except ValueError:
                pass  # Validation will catch this

        vw_raw = data.get("visibleWhen")
        vw_parsed = None
        if vw_raw is not None:
            try:
                vw_parsed = parse_condition(vw_raw)
            except ValueError:
                pass  # Validation will catch this

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
            required_when_raw=rw_raw,
            visible_when_raw=vw_raw,
            required_when=rw_parsed,
            visible_when=vw_parsed,
            formula_raw=data.get("formula"),
            externally_populated=bool(data.get("externallyPopulated", False)),
        )

    def _parse_layout(
        self,
        layout_type: str,
        data: dict[str, Any],
        entity_name: str = "",
        deprecation_warnings: list[str] | None = None,
    ) -> LayoutSpec:
        """Parse a layout definition from YAML.

        :param layout_type: Layout type (detail, edit, list).
        :param data: Raw layout data.
        :param entity_name: Entity name for deprecation warning context.
        :param deprecation_warnings: Accumulator for deprecation messages.
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
                panels.append(self._parse_panel(
                    panel_data,
                    entity_name=entity_name,
                    deprecation_warnings=deprecation_warnings,
                ))
        return LayoutSpec(layout_type=layout_type, panels=panels)

    def _parse_panel(
        self,
        data: dict[str, Any],
        entity_name: str = "",
        deprecation_warnings: list[str] | None = None,
    ) -> PanelSpec:
        """Parse a panel definition from YAML.

        :param data: Raw panel data.
        :param entity_name: Entity name for deprecation warning context.
        :param deprecation_warnings: Accumulator for deprecation messages.
        :returns: PanelSpec instance.
        """
        tabs: list[TabSpec] | None = None
        raw_tabs = data.get("tabs")
        if isinstance(raw_tabs, list):
            tabs = [self._parse_tab(t) for t in raw_tabs if isinstance(t, dict)]

        # Deprecation warning for dynamicLogicVisible
        dynamic_logic = data.get("dynamicLogicVisible")
        if dynamic_logic is not None:
            panel_label = data.get("label", "(unnamed)")
            msg = (
                f"{entity_name}.panel[{panel_label}]: "
                f"'dynamicLogicVisible' is deprecated in v1.1; "
                f"use 'visibleWhen' instead"
            )
            logger.warning(msg)
            if deprecation_warnings is not None:
                deprecation_warnings.append(msg)

        # Parse panel-level visibleWhen condition expression
        panel_vw_raw = data.get("visibleWhen")
        panel_vw_parsed = None
        if panel_vw_raw is not None:
            try:
                panel_vw_parsed = parse_condition(panel_vw_raw)
            except ValueError:
                pass  # Validation will catch this

        return PanelSpec(
            label=data.get("label", ""),
            tabBreak=data.get("tabBreak", False),
            tabLabel=data.get("tabLabel"),
            style=data.get("style", "default"),
            hidden=data.get("hidden", False),
            dynamicLogicVisible=dynamic_logic,
            visible_when_raw=panel_vw_raw,
            visible_when=panel_vw_parsed,
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

            # Panel-level visibleWhen vs dynamicLogicVisible mutual exclusion
            if (
                panel.visible_when_raw is not None
                and panel.dynamicLogicVisible is not None
            ):
                errors.append(
                    f"{panel_prefix}: cannot set both 'visibleWhen' and "
                    f"'dynamicLogicVisible' on the same panel"
                )

            # Panel-level visibleWhen condition validation
            if panel.visible_when_raw is not None:
                if panel.visible_when is None:
                    try:
                        parse_condition(panel.visible_when_raw)
                    except ValueError as exc:
                        errors.append(
                            f"{panel_prefix}.visibleWhen: {exc}"
                        )
                else:
                    vw_errors = validate_condition(
                        panel.visible_when, field_names
                    )
                    for err in vw_errors:
                        errors.append(
                            f"{panel_prefix}.visibleWhen: {err}"
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

        # Mutual exclusion: required: true + requiredWhen
        if field_def.required is True and field_def.required_when_raw is not None:
            errors.append(
                f"{prefix}: cannot set both 'required: true' and "
                f"'requiredWhen' on the same field"
            )

        # Mutual exclusion: required: true + visibleWhen
        if field_def.required is True and field_def.visible_when_raw is not None:
            errors.append(
                f"{prefix}: cannot set both 'required: true' and "
                f"'visibleWhen' on the same field"
            )

        if field_def.name:
            if field_def.name in seen_names:
                errors.append(
                    f"{prefix}: duplicate field name in entity '{entity_name}'"
                )
            seen_names.add(field_def.name)

        return errors

    @staticmethod
    def _parse_settings(raw: dict | None) -> EntitySettings | None:
        """Parse a raw ``settings:`` dict into an EntitySettings model.

        :param raw: Raw settings dict from YAML (or None).
        :returns: EntitySettings instance, or None if raw is None/empty.
        """
        if not raw or not isinstance(raw, dict):
            return None
        return EntitySettings(
            labelSingular=raw.get("labelSingular"),
            labelPlural=raw.get("labelPlural"),
            stream=raw.get("stream"),
            disabled=raw.get("disabled"),
        )

    @staticmethod
    def _deprecation_merge(
        entity_name: str,
        entity_data: dict,
        settings: EntitySettings | None,
        deprecation_warnings: list[str],
    ) -> EntitySettings | None:
        """Merge deprecated top-level keys into the Settings model.

        When a deprecated top-level key is present and the equivalent
        ``settings.<key>`` is absent, the top-level value populates the
        corresponding Settings field. When both are present,
        ``settings.<key>`` wins and an additional conflict warning is
        emitted.

        :param entity_name: Entity name for warning messages.
        :param entity_data: Raw entity YAML dict.
        :param settings: Parsed EntitySettings (may be None).
        :param deprecation_warnings: Accumulator for deprecation messages.
        :returns: Updated EntitySettings (may create one if needed).
        """
        _DEPRECATED_ENTITY_KEYS = {
            "labelSingular", "labelPlural", "stream", "disabled",
        }
        has_deprecated = any(k in entity_data for k in _DEPRECATED_ENTITY_KEYS)
        if not has_deprecated:
            return settings

        # Ensure a settings object exists for merging
        if settings is None:
            settings = EntitySettings()

        for dep_key in _DEPRECATED_ENTITY_KEYS:
            if dep_key not in entity_data:
                continue
            top_val = entity_data[dep_key]
            settings_val = getattr(settings, dep_key)
            if settings_val is not None:
                # Both present — settings wins, emit conflict warning
                if top_val != settings_val:
                    msg = (
                        f"{entity_name}: both top-level '{dep_key}' and "
                        f"'settings.{dep_key}' are set; "
                        f"using settings.{dep_key}={settings_val!r} "
                        f"(top-level value {top_val!r} ignored)"
                    )
                    logger.warning(msg)
                    deprecation_warnings.append(msg)
            else:
                # Top-level present, settings absent — merge into settings
                setattr(settings, dep_key, top_val)

        return settings

    @staticmethod
    def _parse_duplicate_checks(
        raw: list | None,
    ) -> list[DuplicateCheck]:
        """Parse a raw ``duplicateChecks:`` list into typed models.

        :param raw: Raw list from YAML (or None).
        :returns: List of DuplicateCheck instances.
        """
        if not raw or not isinstance(raw, list):
            return []
        checks: list[DuplicateCheck] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            raw_fields = item.get("fields", [])
            if isinstance(raw_fields, str):
                raw_fields = [raw_fields]
            normalize_raw = item.get("normalize")
            normalize = (
                dict(normalize_raw)
                if isinstance(normalize_raw, dict)
                else None
            )
            checks.append(DuplicateCheck(
                id=str(item.get("id", "")),
                fields=list(raw_fields) if isinstance(raw_fields, list) else [],
                onMatch=str(item.get("onMatch", "")),
                message=item.get("message"),
                normalize=normalize,
                alertTemplate=item.get("alertTemplate"),
                alertTo=item.get("alertTo"),
            ))
        return checks

    def _validate_field_conditions(
        self, entity: EntityDefinition
    ) -> list[str]:
        """Validate field-level requiredWhen/visibleWhen conditions.

        Checks condition-expression validity and field references
        against the entity's field set.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        field_names = {f.name for f in entity.fields}

        for field_def in entity.fields:
            prefix = f"{entity.name}.{field_def.name or '(unnamed)'}"

            # requiredWhen condition validation
            if field_def.required_when_raw is not None:
                if field_def.required_when is None:
                    try:
                        parse_condition(field_def.required_when_raw)
                    except ValueError as exc:
                        errors.append(
                            f"{prefix}.requiredWhen: {exc}"
                        )
                else:
                    rw_errors = validate_condition(
                        field_def.required_when, field_names
                    )
                    for err in rw_errors:
                        errors.append(f"{prefix}.requiredWhen: {err}")

            # visibleWhen condition validation
            if field_def.visible_when_raw is not None:
                if field_def.visible_when is None:
                    try:
                        parse_condition(field_def.visible_when_raw)
                    except ValueError as exc:
                        errors.append(
                            f"{prefix}.visibleWhen: {exc}"
                        )
                else:
                    vw_errors = validate_condition(
                        field_def.visible_when, field_names
                    )
                    for err in vw_errors:
                        errors.append(f"{prefix}.visibleWhen: {err}")

        return errors

    def _parse_saved_views(
        self, raw: list | None,
    ) -> list[SavedView]:
        """Parse a raw ``savedViews:`` list into typed models.

        :param raw: Raw list from YAML (or None).
        :returns: List of SavedView instances.
        """
        if not raw or not isinstance(raw, list):
            return []
        views: list[SavedView] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            # Parse filter via condition_expression
            filter_raw = item.get("filter")
            parsed_filter = None
            if filter_raw is not None:
                try:
                    parsed_filter = parse_condition(filter_raw)
                except ValueError:
                    # Validation will catch this; store None
                    pass

            # Parse orderBy — single object or list of objects
            order_by: list[OrderByClause] = []
            raw_order = item.get("orderBy")
            if isinstance(raw_order, dict):
                order_by.append(OrderByClause(
                    field=str(raw_order.get("field", "")),
                    direction=str(raw_order.get("direction", "asc")),
                ))
            elif isinstance(raw_order, list):
                for ob in raw_order:
                    if isinstance(ob, dict):
                        order_by.append(OrderByClause(
                            field=str(ob.get("field", "")),
                            direction=str(ob.get("direction", "asc")),
                        ))

            # Parse columns
            columns = item.get("columns")
            if isinstance(columns, list):
                columns = [str(c) for c in columns]
            else:
                columns = None

            views.append(SavedView(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                description=item.get("description"),
                columns=columns,
                filter=parsed_filter,
                order_by=order_by,
                filter_raw=filter_raw,
            ))
        return views

    def _validate_saved_views(
        self, entity: EntityDefinition
    ) -> list[str]:
        """Validate the entity's ``savedViews:`` block per spec Section 10.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if not entity.saved_views:
            return errors

        field_names = {f.name for f in entity.fields}
        seen_ids: set[str] = set()

        for view in entity.saved_views:
            prefix = f"{entity.name}.savedViews[{view.id or '(no id)'}]"

            # id is required and must be unique
            if not view.id:
                errors.append(f"{prefix}: missing required property 'id'")
            elif view.id in seen_ids:
                errors.append(
                    f"{prefix}: duplicate id '{view.id}' within entity"
                )
            seen_ids.add(view.id)

            # name is required
            if not view.name:
                errors.append(f"{prefix}: missing required property 'name'")

            # filter is required
            if view.filter_raw is None:
                errors.append(f"{prefix}: missing required property 'filter'")
            elif view.filter is None:
                # parse_condition failed at load time
                try:
                    parse_condition(view.filter_raw)
                except ValueError as exc:
                    errors.append(f"{prefix}.filter: {exc}")
            else:
                # Validate field references in filter
                filter_errors = validate_condition(view.filter, field_names)
                for err in filter_errors:
                    errors.append(f"{prefix}.filter: {err}")

            # columns field-reference checks
            if view.columns:
                for col in view.columns:
                    if col not in field_names:
                        errors.append(
                            f"{prefix}.columns: field '{col}' not found "
                            f"on entity '{entity.name}'"
                        )

            # orderBy validation
            for ob in view.order_by:
                ob_prefix = f"{prefix}.orderBy"
                if not ob.field:
                    errors.append(
                        f"{ob_prefix}: missing required property 'field'"
                    )
                elif ob.field not in field_names:
                    errors.append(
                        f"{ob_prefix}: field '{ob.field}' not found "
                        f"on entity '{entity.name}'"
                    )
                if ob.direction not in ("asc", "desc"):
                    errors.append(
                        f"{ob_prefix}: invalid direction '{ob.direction}' "
                        f"(must be 'asc' or 'desc')"
                    )

        return errors

    def _validate_settings(self, entity: EntityDefinition) -> list[str]:
        """Validate the entity's ``settings:`` block per spec Section 10.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if entity.settings_raw is None:
            return errors
        if not isinstance(entity.settings_raw, dict):
            errors.append(
                f"{entity.name}: 'settings' must be a mapping"
            )
            return errors

        # Reject unknown keys
        for key in entity.settings_raw:
            if key not in VALID_SETTINGS_KEYS:
                errors.append(
                    f"{entity.name}.settings: unknown key '{key}'"
                )

        # Type checks
        stream_val = entity.settings_raw.get("stream")
        if stream_val is not None and not isinstance(stream_val, bool):
            errors.append(
                f"{entity.name}.settings.stream: must be a boolean"
            )
        disabled_val = entity.settings_raw.get("disabled")
        if disabled_val is not None and not isinstance(disabled_val, bool):
            errors.append(
                f"{entity.name}.settings.disabled: must be a boolean"
            )

        # Label requirement for create actions is handled by the existing
        # entity-level check in _validate_entity, which sees labels from
        # either settings: or the deprecated top-level (via deprecation merge).

        return errors

    def _validate_duplicate_checks(
        self, entity: EntityDefinition
    ) -> list[str]:
        """Validate the entity's ``duplicateChecks:`` block per spec Section 10.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if not entity.duplicate_checks:
            return errors

        field_names = {f.name for f in entity.fields}
        seen_ids: set[str] = set()

        for rule in entity.duplicate_checks:
            prefix = f"{entity.name}.duplicateChecks[{rule.id or '(no id)'}]"

            # id is required and must be unique
            if not rule.id:
                errors.append(f"{prefix}: missing required property 'id'")
            elif rule.id in seen_ids:
                errors.append(
                    f"{prefix}: duplicate id '{rule.id}' within entity"
                )
            seen_ids.add(rule.id)

            # fields must have at least one entry
            if not rule.fields:
                errors.append(
                    f"{prefix}: 'fields' must list at least one field name"
                )
            else:
                for fname in rule.fields:
                    if fname not in field_names:
                        errors.append(
                            f"{prefix}: field '{fname}' not found on "
                            f"entity '{entity.name}'"
                        )

            # onMatch validation
            if not rule.onMatch:
                errors.append(
                    f"{prefix}: missing required property 'onMatch'"
                )
            elif rule.onMatch not in VALID_ON_MATCH_VALUES:
                errors.append(
                    f"{prefix}: invalid onMatch value '{rule.onMatch}' "
                    f"(must be 'block' or 'warn')"
                )

            # block requires message
            if rule.onMatch == "block" and not rule.message:
                errors.append(
                    f"{prefix}: 'message' is required when onMatch is 'block'"
                )

            # normalize validation
            if rule.normalize:
                for nfield, nvalue in rule.normalize.items():
                    if nfield not in rule.fields:
                        errors.append(
                            f"{prefix}.normalize: key '{nfield}' is not "
                            f"listed in 'fields'"
                        )
                    if nvalue not in VALID_NORMALIZE_VALUES:
                        errors.append(
                            f"{prefix}.normalize: invalid value "
                            f"'{nvalue}' for field '{nfield}' "
                            f"(must be one of: "
                            f"{', '.join(sorted(VALID_NORMALIZE_VALUES))})"
                        )

            # alertTo shape validation (deferred cross-block check for
            # alertTemplate to Prompt E)
            if rule.alertTo is not None:
                self._validate_alert_to(
                    prefix, rule.alertTo, field_names, errors
                )

        return errors

    @staticmethod
    def _validate_alert_to(
        prefix: str,
        alert_to: str,
        field_names: set[str],
        errors: list[str],
    ) -> None:
        """Validate the shape of an ``alertTo`` value.

        Must be one of: a field name on the entity, a literal email
        address (contains ``@``), or ``role:<role-id>``.

        :param prefix: Error message prefix.
        :param alert_to: The alertTo value to validate.
        :param field_names: Valid field names on the entity.
        :param errors: Accumulator for error messages.
        """
        if not alert_to:
            errors.append(f"{prefix}: 'alertTo' must not be empty")
            return
        # role:<role-id>
        if alert_to.startswith("role:"):
            role_id = alert_to[5:]
            if not role_id:
                errors.append(
                    f"{prefix}: 'alertTo' role format requires an id "
                    f"after 'role:'"
                )
            return
        # literal email
        if "@" in alert_to:
            return
        # field name
        if alert_to in field_names:
            return
        errors.append(
            f"{prefix}: 'alertTo' value '{alert_to}' is not a field name, "
            f"a literal email address, or a 'role:<role-id>' string"
        )

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
