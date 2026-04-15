"""YAML program file loading and validation."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from espo_impl.core.condition_expression import parse_condition, validate_condition
from espo_impl.core.formula_parser import extract_field_refs, parse_arithmetic
from espo_impl.core.models import (
    SUPPORTED_ENTITY_TYPES,
    VALID_NORMALIZE_VALUES,
    VALID_ON_MATCH_VALUES,
    VALID_SETTINGS_KEYS,
    AggregateFormula,
    ArithmeticFormula,
    ColumnSpec,
    ConcatFormula,
    DuplicateCheck,
    EmailTemplate,
    EntityAction,
    EntityDefinition,
    EntitySettings,
    FieldDefinition,
    Formula,
    LayoutSpec,
    OrderByClause,
    PanelSpec,
    ProgramFile,
    RelationshipDefinition,
    SavedView,
    TabSpec,
    Workflow,
    WorkflowAction,
    WorkflowTrigger,
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

                # Parse email templates into typed models
                email_templates = self._parse_email_templates(
                    email_templates_raw, path.parent if path else None
                )

                # Parse workflows into typed models
                workflows = self._parse_workflows(workflows_raw)

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
                    email_templates=email_templates,
                    workflows=workflows,
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

        # Cross-block alertTemplate resolution
        errors.extend(self._validate_alert_template_refs(program))

        # Cross-block workflow template resolution
        errors.extend(self._validate_workflow_template_refs(program))

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

        # Validate field-level formula blocks
        errors.extend(self._validate_formula_fields(entity))

        # Validate settings

        # Validate duplicate checks
        errors.extend(self._validate_duplicate_checks(entity))

        # Validate saved views
        errors.extend(self._validate_saved_views(entity))

        # Validate email templates
        errors.extend(self._validate_email_templates(entity))

        # Validate workflows
        errors.extend(self._validate_workflows(entity))

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

        # Parse formula block
        formula_raw = data.get("formula")
        formula_parsed = None
        if formula_raw is not None and isinstance(formula_raw, dict):
            try:
                formula_parsed = self._parse_formula(formula_raw)
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
            formula=formula_parsed,
            formula_raw=formula_raw,
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

    def _validate_formula_fields(
        self, entity: EntityDefinition
    ) -> list[str]:
        """Validate formula blocks on all fields in an entity.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        field_names = {f.name for f in entity.fields}

        for field_def in entity.fields:
            if field_def.formula_raw is not None or field_def.formula is not None:
                errors.extend(
                    self._validate_formula(
                        entity.name, field_def, field_names,
                    )
                )

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

    def _parse_email_templates(
        self, raw: list | None, yaml_dir: Path | None,
    ) -> list[EmailTemplate]:
        """Parse a raw ``emailTemplates:`` list into typed models.

        :param raw: Raw list from YAML (or None).
        :param yaml_dir: Directory containing the program YAML.
        :returns: List of EmailTemplate instances.
        """
        if not raw or not isinstance(raw, list):
            return []
        templates: list[EmailTemplate] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            body_file = str(item.get("bodyFile", ""))
            body_content = None
            body_hash = None
            if body_file and yaml_dir is not None:
                body_path = yaml_dir / body_file
                if body_path.is_file():
                    body_content = body_path.read_text(encoding="utf-8")
                    body_hash = hashlib.sha256(
                        body_content.encode("utf-8")
                    ).hexdigest()

            merge_fields = item.get("mergeFields", [])
            if not isinstance(merge_fields, list):
                merge_fields = []

            templates.append(EmailTemplate(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                entity=str(item.get("entity", "")),
                subject=str(item.get("subject", "")),
                body_file=body_file,
                merge_fields=[str(f) for f in merge_fields],
                description=item.get("description"),
                audience=item.get("audience"),
                body_content=body_content,
                body_hash=body_hash,
            ))
        return templates

    def _validate_email_templates(
        self, entity: EntityDefinition
    ) -> list[str]:
        """Validate the entity's ``emailTemplates:`` block per spec Section 10.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if not entity.email_templates:
            return errors

        field_names = {f.name for f in entity.fields}
        seen_ids: set[str] = set()

        for tmpl in entity.email_templates:
            prefix = f"{entity.name}.emailTemplates[{tmpl.id or '(no id)'}]"

            # id required and unique
            if not tmpl.id:
                errors.append(f"{prefix}: missing required property 'id'")
            elif tmpl.id in seen_ids:
                errors.append(
                    f"{prefix}: duplicate id '{tmpl.id}' within entity"
                )
            seen_ids.add(tmpl.id)

            # Required fields
            if not tmpl.name:
                errors.append(f"{prefix}: missing required property 'name'")
            if not tmpl.entity:
                errors.append(
                    f"{prefix}: missing required property 'entity'"
                )
            elif tmpl.entity != entity.name:
                errors.append(
                    f"{prefix}: 'entity' value '{tmpl.entity}' does not "
                    f"match parent entity '{entity.name}'"
                )
            if not tmpl.subject:
                errors.append(
                    f"{prefix}: missing required property 'subject'"
                )
            if not tmpl.body_file:
                errors.append(
                    f"{prefix}: missing required property 'bodyFile'"
                )
            elif tmpl.body_content is None:
                errors.append(
                    f"{prefix}: bodyFile '{tmpl.body_file}' not found"
                )
            if not tmpl.merge_fields:
                errors.append(
                    f"{prefix}: missing required property 'mergeFields'"
                )

            # mergeFields must reference real fields on entity
            for mf in tmpl.merge_fields:
                if mf not in field_names:
                    errors.append(
                        f"{prefix}.mergeFields: field '{mf}' not found "
                        f"on entity '{entity.name}'"
                    )

            # Placeholder validation
            merge_set = set(tmpl.merge_fields)
            used_placeholders: set[str] = set()

            # Extract {{...}} from subject
            if tmpl.subject:
                for match in re.finditer(r"\{\{(\w+)\}\}", tmpl.subject):
                    ph = match.group(1)
                    used_placeholders.add(ph)
                    if ph not in merge_set:
                        errors.append(
                            f"{prefix}.subject: placeholder "
                            f"'{{{{{ph}}}}}' not in mergeFields"
                        )

            # Extract {{...}} from body
            if tmpl.body_content:
                for match in re.finditer(
                    r"\{\{(\w+)\}\}", tmpl.body_content
                ):
                    ph = match.group(1)
                    used_placeholders.add(ph)
                    if ph not in merge_set:
                        errors.append(
                            f"{prefix}.bodyFile: placeholder "
                            f"'{{{{{ph}}}}}' not in mergeFields"
                        )

            # Every mergeField must be used
            for mf in tmpl.merge_fields:
                if mf not in used_placeholders:
                    errors.append(
                        f"{prefix}.mergeFields: '{mf}' is listed but "
                        f"never used in subject or bodyFile"
                    )

        return errors

    def _validate_alert_template_refs(
        self, program: ProgramFile
    ) -> list[str]:
        """Validate cross-block alertTemplate references.

        Each ``duplicateChecks[].alertTemplate`` must reference an ``id``
        in the same entity's ``emailTemplates[]``.

        :param program: Parsed program file.
        :returns: List of error messages.
        """
        errors: list[str] = []
        for entity in program.entities:
            template_ids = {t.id for t in entity.email_templates}
            for rule in entity.duplicate_checks:
                if rule.alertTemplate is not None:
                    if rule.alertTemplate not in template_ids:
                        prefix = (
                            f"{entity.name}.duplicateChecks"
                            f"[{rule.id}]"
                        )
                        errors.append(
                            f"{prefix}: alertTemplate "
                            f"'{rule.alertTemplate}' does not match "
                            f"any emailTemplates id on entity "
                            f"'{entity.name}'"
                        )
        return errors

    def _validate_workflow_template_refs(
        self, program: ProgramFile
    ) -> list[str]:
        """Validate cross-block workflow sendEmail template references.

        Each ``workflows[].actions[].template`` for ``sendEmail`` actions
        must reference an ``id`` in the same entity's ``emailTemplates[]``.

        :param program: Parsed program file.
        :returns: List of error messages.
        """
        errors: list[str] = []
        for entity in program.entities:
            template_ids = {t.id for t in entity.email_templates}
            for wf in entity.workflows:
                for action in wf.actions:
                    if action.type == "sendEmail" and action.template:
                        if action.template not in template_ids:
                            prefix = (
                                f"{entity.name}.workflows"
                                f"[{wf.id}]"
                            )
                            errors.append(
                                f"{prefix}: sendEmail template "
                                f"'{action.template}' does not match "
                                f"any emailTemplates id on entity "
                                f"'{entity.name}'"
                            )
        return errors

    def _parse_workflows(
        self, raw: list | None,
    ) -> list[Workflow]:
        """Parse a raw ``workflows:`` list into typed models.

        :param raw: Raw list from YAML (or None).
        :returns: List of Workflow instances.
        """
        if not raw or not isinstance(raw, list):
            return []
        workflows: list[Workflow] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            # Parse trigger
            trigger = None
            raw_trigger = item.get("trigger")
            if isinstance(raw_trigger, dict):
                from_val = raw_trigger.get("from")
                to_val = raw_trigger.get("to")
                trigger = WorkflowTrigger(
                    event=str(raw_trigger.get("event", "")),
                    field=raw_trigger.get("field"),
                    from_values=from_val,
                    to_values=to_val,
                )

            # Parse where clause via condition_expression
            where_raw = item.get("where")
            where_parsed = None
            if where_raw is not None:
                try:
                    where_parsed = parse_condition(where_raw)
                except ValueError:
                    pass  # Validation will catch this

            # Parse actions
            actions: list[WorkflowAction] = []
            raw_actions = item.get("actions", [])
            if isinstance(raw_actions, list):
                for act_data in raw_actions:
                    if isinstance(act_data, dict):
                        actions.append(WorkflowAction(
                            type=str(act_data.get("type", "")),
                            field=act_data.get("field"),
                            value=act_data.get("value"),
                            template=act_data.get("template"),
                            to=act_data.get("to"),
                        ))

            workflows.append(Workflow(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                trigger=trigger,
                where=where_parsed,
                where_raw=where_raw,
                actions=actions,
                description=item.get("description"),
            ))
        return workflows

    _VALID_TRIGGER_EVENTS: set[str] = {
        "onCreate", "onUpdate", "onFieldChange",
        "onFieldTransition", "onDelete",
    }

    _VALID_ACTION_TYPES: set[str] = {
        "setField", "clearField", "sendEmail", "sendInternalNotification",
    }

    def _validate_workflows(
        self, entity: EntityDefinition
    ) -> list[str]:
        """Validate the entity's ``workflows:`` block.

        :param entity: Entity definition to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if not entity.workflows:
            return errors

        field_names = {f.name for f in entity.fields}
        seen_ids: set[str] = set()

        for wf in entity.workflows:
            prefix = f"{entity.name}.workflows[{wf.id or '(no id)'}]"

            # id is required and must be unique
            if not wf.id:
                errors.append(f"{prefix}: missing required property 'id'")
            elif wf.id in seen_ids:
                errors.append(
                    f"{prefix}: duplicate id '{wf.id}' within entity"
                )
            seen_ids.add(wf.id)

            # name is required
            if not wf.name:
                errors.append(f"{prefix}: missing required property 'name'")

            # trigger is required
            if wf.trigger is None:
                errors.append(
                    f"{prefix}: missing required property 'trigger'"
                )
            else:
                errors.extend(
                    self._validate_workflow_trigger(
                        prefix, wf.trigger, field_names
                    )
                )

            # actions must be non-empty
            if not wf.actions:
                errors.append(
                    f"{prefix}: 'actions' must be a non-empty list"
                )
            else:
                for i, action in enumerate(wf.actions):
                    errors.extend(
                        self._validate_workflow_action(
                            f"{prefix}.actions[{i}]",
                            action,
                            field_names,
                        )
                    )

            # where clause validation
            if wf.where_raw is not None:
                if wf.where is None:
                    try:
                        parse_condition(wf.where_raw)
                    except ValueError as exc:
                        errors.append(f"{prefix}.where: {exc}")
                else:
                    wh_errors = validate_condition(wf.where, field_names)
                    for err in wh_errors:
                        errors.append(f"{prefix}.where: {err}")

        return errors

    def _validate_workflow_trigger(
        self,
        prefix: str,
        trigger: WorkflowTrigger,
        field_names: set[str],
    ) -> list[str]:
        """Validate a workflow trigger specification.

        :param prefix: Error message prefix.
        :param trigger: Trigger to validate.
        :param field_names: Set of valid field names on the entity.
        :returns: List of error messages.
        """
        errors: list[str] = []
        t_prefix = f"{prefix}.trigger"

        if not trigger.event:
            errors.append(f"{t_prefix}: missing required property 'event'")
            return errors

        if trigger.event not in self._VALID_TRIGGER_EVENTS:
            errors.append(
                f"{t_prefix}: invalid event '{trigger.event}' "
                f"(must be one of {sorted(self._VALID_TRIGGER_EVENTS)})"
            )
            return errors

        if trigger.event == "onFieldChange":
            if not trigger.field:
                errors.append(
                    f"{t_prefix}: 'field' is required for "
                    f"onFieldChange trigger"
                )
            elif trigger.field not in field_names:
                errors.append(
                    f"{t_prefix}: field '{trigger.field}' not found "
                    f"on entity"
                )
        elif trigger.event == "onFieldTransition":
            if not trigger.field:
                errors.append(
                    f"{t_prefix}: 'field' is required for "
                    f"onFieldTransition trigger"
                )
            elif trigger.field not in field_names:
                errors.append(
                    f"{t_prefix}: field '{trigger.field}' not found "
                    f"on entity"
                )
            if trigger.from_values is None and trigger.to_values is None:
                errors.append(
                    f"{t_prefix}: onFieldTransition requires "
                    f"'from' and/or 'to'"
                )

        return errors

    def _validate_workflow_action(
        self,
        prefix: str,
        action: WorkflowAction,
        field_names: set[str],
    ) -> list[str]:
        """Validate a single workflow action.

        :param prefix: Error message prefix.
        :param action: Action to validate.
        :param field_names: Set of valid field names on the entity.
        :returns: List of error messages.
        """
        errors: list[str] = []

        if not action.type:
            errors.append(f"{prefix}: missing required property 'type'")
            return errors

        if action.type not in self._VALID_ACTION_TYPES:
            errors.append(
                f"{prefix}: invalid action type '{action.type}' "
                f"(must be one of {sorted(self._VALID_ACTION_TYPES)})"
            )
            return errors

        if action.type == "setField":
            if not action.field:
                errors.append(
                    f"{prefix}: 'field' is required for setField"
                )
            elif action.field not in field_names:
                errors.append(
                    f"{prefix}: field '{action.field}' not found on entity"
                )
            if action.value is None:
                errors.append(
                    f"{prefix}: 'value' is required for setField"
                )
            elif isinstance(action.value, str) and action.value != "now":
                # Try to parse as arithmetic expression
                try:
                    parse_arithmetic(action.value)
                except ValueError:
                    pass  # Literal string -- valid

        elif action.type == "clearField":
            if not action.field:
                errors.append(
                    f"{prefix}: 'field' is required for clearField"
                )
            elif action.field not in field_names:
                errors.append(
                    f"{prefix}: field '{action.field}' not found on entity"
                )

        elif action.type == "sendEmail":
            if not action.template:
                errors.append(
                    f"{prefix}: 'template' is required for sendEmail"
                )
            if not action.to:
                errors.append(
                    f"{prefix}: 'to' is required for sendEmail"
                )
            elif "@" not in str(action.to):
                # Must be a field name on the entity
                if action.to not in field_names:
                    errors.append(
                        f"{prefix}: 'to' value '{action.to}' is neither "
                        f"an email address nor a field on the entity"
                    )

        elif action.type == "sendInternalNotification":
            if not action.template:
                errors.append(
                    f"{prefix}: 'template' is required for "
                    f"sendInternalNotification"
                )
            if not action.to:
                errors.append(
                    f"{prefix}: 'to' is required for "
                    f"sendInternalNotification"
                )
            elif not (
                "@" in str(action.to)
                or str(action.to).startswith("role:")
                or str(action.to).startswith("user:")
            ):
                errors.append(
                    f"{prefix}: 'to' value '{action.to}' must be an "
                    f"email, 'role:<id>', or 'user:<id>'"
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

    # ------------------------------------------------------------------
    # Formula parsing
    # ------------------------------------------------------------------

    VALID_AGGREGATE_FUNCTIONS: set[str] = {
        "count", "sum", "avg", "min", "max", "first", "last",
    }

    def _parse_formula(self, raw: dict) -> Formula:
        """Parse a raw ``formula:`` dict into a Formula model.

        :param raw: Raw formula dict from YAML.
        :returns: Formula instance.
        :raises ValueError: On malformed input.
        """
        formula_type = raw.get("type")
        if not formula_type:
            raise ValueError("formula: missing required property 'type'")

        if formula_type == "aggregate":
            return self._parse_aggregate_formula(raw)
        if formula_type == "arithmetic":
            return self._parse_arithmetic_formula(raw)
        if formula_type == "concat":
            return self._parse_concat_formula(raw)

        raise ValueError(
            f"formula: unknown type '{formula_type}' "
            f"(must be 'aggregate', 'arithmetic', or 'concat')"
        )

    def _parse_aggregate_formula(self, raw: dict) -> Formula:
        """Parse an aggregate formula block."""
        # Parse where clause
        where_raw = raw.get("where")
        where_parsed = None
        if where_raw is not None:
            try:
                where_parsed = parse_condition(where_raw)
            except ValueError:
                pass  # Validation will catch

        # Parse orderBy
        order_by = None
        raw_order = raw.get("orderBy")
        if isinstance(raw_order, dict):
            order_by = OrderByClause(
                field=str(raw_order.get("field", "")),
                direction=str(raw_order.get("direction", "asc")),
            )

        aggregate = AggregateFormula(
            function=str(raw.get("function", "")),
            related_entity=str(raw.get("relatedEntity", "")),
            via=str(raw.get("via", "")),
            field=raw.get("field"),
            pick_field=raw.get("pickField"),
            order_by=order_by,
            join=raw.get("join"),
            where=where_parsed,
            where_raw=where_raw,
        )
        return Formula(type="aggregate", aggregate=aggregate)

    def _parse_arithmetic_formula(self, raw: dict) -> Formula:
        """Parse an arithmetic formula block."""
        expression = str(raw.get("expression", ""))
        parsed_ast = None
        if expression:
            try:
                parsed_ast = parse_arithmetic(expression)
            except ValueError:
                pass  # Validation will catch

        arithmetic = ArithmeticFormula(
            expression=expression,
            parsed=parsed_ast,
        )
        return Formula(type="arithmetic", arithmetic=arithmetic)

    def _parse_concat_formula(self, raw: dict) -> Formula:
        """Parse a concat formula block."""
        parts = raw.get("parts", [])
        if not isinstance(parts, list):
            parts = []

        concat = ConcatFormula(parts=parts)
        return Formula(type="concat", concat=concat)

    # ------------------------------------------------------------------
    # Formula validation
    # ------------------------------------------------------------------

    def _validate_formula(
        self,
        entity_name: str,
        field_def: FieldDefinition,
        field_names: set[str],
    ) -> list[str]:
        """Validate a field's formula block.

        :param entity_name: Name of the containing entity.
        :param field_def: Field definition with formula.
        :param field_names: All field names on this entity.
        :returns: List of error messages.
        """
        errors: list[str] = []
        prefix = f"{entity_name}.{field_def.name}.formula"
        formula = field_def.formula

        if formula is None:
            # formula_raw is present but didn't parse
            raw = field_def.formula_raw
            if raw is not None and isinstance(raw, dict):
                try:
                    self._parse_formula(raw)
                except ValueError as exc:
                    errors.append(f"{prefix}: {exc}")
            elif raw is not None:
                errors.append(
                    f"{prefix}: must be a mapping, got "
                    f"{type(raw).__name__}"
                )
            return errors

        # formula: requires readOnly: true
        if field_def.readOnly is not True:
            errors.append(
                f"{prefix}: formula fields must have 'readOnly: true'"
            )

        # Validate by type
        if formula.type == "aggregate":
            errors.extend(
                self._validate_aggregate_formula(prefix, formula.aggregate)
            )
        elif formula.type == "arithmetic":
            errors.extend(
                self._validate_arithmetic_formula(
                    prefix, formula.arithmetic, field_names
                )
            )
        elif formula.type == "concat":
            errors.extend(
                self._validate_concat_formula(
                    prefix, formula.concat, field_names
                )
            )
        else:
            errors.append(
                f"{prefix}: unknown type '{formula.type}' "
                f"(must be 'aggregate', 'arithmetic', or 'concat')"
            )

        return errors

    def _validate_aggregate_formula(
        self, prefix: str, agg: AggregateFormula | None,
    ) -> list[str]:
        """Validate an aggregate formula.

        :param prefix: Error message prefix.
        :param agg: Aggregate formula to validate.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if agg is None:
            errors.append(f"{prefix}: missing aggregate data")
            return errors

        # function is required and must be valid
        if not agg.function:
            errors.append(
                f"{prefix}: missing required property 'function'"
            )
        elif agg.function not in self.VALID_AGGREGATE_FUNCTIONS:
            errors.append(
                f"{prefix}: invalid function '{agg.function}' "
                f"(must be one of: "
                f"{', '.join(sorted(self.VALID_AGGREGATE_FUNCTIONS))})"
            )

        # relatedEntity and via are required
        if not agg.related_entity:
            errors.append(
                f"{prefix}: missing required property 'relatedEntity'"
            )
        if not agg.via:
            errors.append(
                f"{prefix}: missing required property 'via'"
            )

        # Function-specific validations
        if agg.function == "count":
            if agg.field is not None:
                errors.append(
                    f"{prefix}: 'field' must not be set for "
                    f"function 'count'"
                )
        elif agg.function in ("sum", "avg", "min", "max"):
            if not agg.field:
                errors.append(
                    f"{prefix}: 'field' is required for "
                    f"function '{agg.function}'"
                )
        elif agg.function in ("first", "last"):
            if not agg.pick_field:
                errors.append(
                    f"{prefix}: 'pickField' is required for "
                    f"function '{agg.function}'"
                )
            if agg.order_by is None:
                errors.append(
                    f"{prefix}: 'orderBy' is required for "
                    f"function '{agg.function}'"
                )
            elif agg.order_by is not None:
                if not agg.order_by.field:
                    errors.append(
                        f"{prefix}.orderBy: missing required "
                        f"property 'field'"
                    )
                if agg.order_by.direction not in ("asc", "desc"):
                    errors.append(
                        f"{prefix}.orderBy: invalid direction "
                        f"'{agg.order_by.direction}' "
                        f"(must be 'asc' or 'desc')"
                    )

        # where clause — parse validation only (cross-entity field refs
        # are deferred since the related entity fields aren't available here)
        if agg.where_raw is not None and agg.where is None:
            try:
                parse_condition(agg.where_raw)
            except ValueError as exc:
                errors.append(f"{prefix}.where: {exc}")

        return errors

    def _validate_arithmetic_formula(
        self,
        prefix: str,
        arith: ArithmeticFormula | None,
        field_names: set[str],
    ) -> list[str]:
        """Validate an arithmetic formula.

        :param prefix: Error message prefix.
        :param arith: Arithmetic formula to validate.
        :param field_names: Valid field names on the entity.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if arith is None:
            errors.append(f"{prefix}: missing arithmetic data")
            return errors

        if not arith.expression:
            errors.append(
                f"{prefix}: missing required property 'expression'"
            )
            return errors

        if arith.parsed is None:
            # parse failed — try again for the error message
            try:
                parse_arithmetic(arith.expression)
            except ValueError as exc:
                errors.append(f"{prefix}.expression: {exc}")
            return errors

        # Validate field references
        refs = extract_field_refs(arith.parsed)
        for ref in sorted(refs):
            if ref not in field_names:
                errors.append(
                    f"{prefix}.expression: field '{ref}' not found "
                    f"on entity"
                )

        return errors

    def _validate_concat_formula(
        self,
        prefix: str,
        concat: ConcatFormula | None,
        field_names: set[str],
    ) -> list[str]:
        """Validate a concat formula.

        :param prefix: Error message prefix.
        :param concat: Concat formula to validate.
        :param field_names: Valid field names on the entity.
        :returns: List of error messages.
        """
        errors: list[str] = []
        if concat is None:
            errors.append(f"{prefix}: missing concat data")
            return errors

        if not concat.parts:
            errors.append(
                f"{prefix}: 'parts' must be a non-empty list"
            )
            return errors

        for i, part in enumerate(concat.parts):
            if not isinstance(part, dict):
                errors.append(
                    f"{prefix}.parts[{i}]: each part must be a mapping"
                )
                continue
            keys = set(part.keys())
            if keys == {"literal"}:
                pass  # literals are always valid
            elif keys == {"field"}:
                field_name = part["field"]
                if field_name not in field_names:
                    errors.append(
                        f"{prefix}.parts[{i}]: field '{field_name}' "
                        f"not found on entity"
                    )
            elif keys == {"lookup"}:
                lookup = part["lookup"]
                if not isinstance(lookup, dict):
                    errors.append(
                        f"{prefix}.parts[{i}]: 'lookup' must be a mapping"
                    )
                else:
                    if "via" not in lookup:
                        errors.append(
                            f"{prefix}.parts[{i}].lookup: missing "
                            f"required property 'via'"
                        )
                    if "field" not in lookup:
                        errors.append(
                            f"{prefix}.parts[{i}].lookup: missing "
                            f"required property 'field'"
                        )
            else:
                errors.append(
                    f"{prefix}.parts[{i}]: part must have exactly one "
                    f"key: 'literal', 'field', or 'lookup'"
                )

        return errors

