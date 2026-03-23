"""Data models for the EspoCRM Implementation Tool."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass
class InstanceProfile:
    """An EspoCRM instance connection profile.

    :param name: Human-readable instance name.
    :param url: Base URL of the EspoCRM instance.
    :param api_key: API key for authentication.
    :param auth_method: Authentication method ("api_key" or "hmac").
    :param secret_key: Secret key for HMAC authentication.
    """

    name: str
    url: str
    api_key: str
    auth_method: str = "api_key"
    secret_key: str | None = None

    @property
    def api_url(self) -> str:
        """Full API base URL."""
        return f"{self.url.rstrip('/')}/api/v1"

    @property
    def slug(self) -> str:
        """Filename-safe slug derived from name."""
        return self.name.lower().replace(" ", "_").replace("-", "_")


@dataclass
class FieldDefinition:
    """A single field specification from a YAML program file.

    :param name: Internal field name (lowerCamelCase).
    :param type: EspoCRM field type.
    :param label: Display label.
    """

    name: str
    type: str
    label: str
    required: bool | None = None
    default: str | None = None
    readOnly: bool | None = None
    audited: bool | None = None
    options: list[str] | None = None
    translatedOptions: dict[str, str] | None = None
    style: dict[str, str | None] | None = None
    isSorted: bool | None = None
    displayAsLabel: bool | None = None
    min: int | None = None
    max: int | None = None
    maxLength: int | None = None
    category: str | None = None
    description: str | None = None


@dataclass
class TabSpec:
    """A sub-tab within a panel, populated by field category."""

    label: str
    category: str
    rows: list | None = None


@dataclass
class ColumnSpec:
    """A column in a list view layout."""

    field: str
    width: int | None = None


@dataclass
class PanelSpec:
    """A panel in a detail/edit layout."""

    label: str
    tabBreak: bool = False
    tabLabel: str | None = None
    style: str = "default"
    hidden: bool = False
    dynamicLogicVisible: dict | None = None
    rows: list | None = None
    tabs: list[TabSpec] | None = None
    description: str | None = None


@dataclass
class LayoutSpec:
    """Layout definition for one layout type (detail, edit, or list)."""

    layout_type: str
    panels: list[PanelSpec] | None = None
    columns: list[ColumnSpec] | None = None


class EntityAction(Enum):
    """Action to perform on an entity."""

    NONE = "none"
    CREATE = "create"
    DELETE = "delete"
    DELETE_AND_CREATE = "delete_and_create"


SUPPORTED_ENTITY_TYPES: set[str] = {"Base", "Person", "Company", "Event"}


@dataclass
class EntityDefinition:
    """Entity definition from a YAML program file.

    :param name: Entity name (e.g., "Contact", "Engagement").
    :param fields: List of field definitions for this entity.
    :param action: Entity-level action (create, delete, delete_and_create, or none).
    :param type: Entity type for creation (Base, Person, Company, Event).
    :param labelSingular: Singular display name.
    :param labelPlural: Plural display name.
    :param stream: Whether to enable the Stream panel.
    :param disabled: Whether the entity is disabled.
    """

    name: str
    fields: list[FieldDefinition]
    action: EntityAction = EntityAction.NONE
    type: str | None = None
    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool = False
    disabled: bool = False
    layouts: dict[str, LayoutSpec] = field(default_factory=dict)
    description: str | None = None


@dataclass
class ProgramFile:
    """Parsed YAML program file.

    :param version: Program file format version.
    :param description: Human-readable description.
    :param entities: List of entity definitions.
    :param source_path: Path to the source YAML file.
    """

    version: str
    description: str
    entities: list[EntityDefinition]
    source_path: Path | None = None

    @property
    def has_delete_operations(self) -> bool:
        """Whether any entity in this program has a delete action."""
        return any(
            e.action in (EntityAction.DELETE, EntityAction.DELETE_AND_CREATE)
            for e in self.entities
        )


class EntityLayoutStatus(Enum):
    """Outcome status for a layout operation."""

    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFICATION_FAILED = "verification_failed"
    ERROR = "error"


@dataclass
class LayoutResult:
    """Result of processing a single layout."""

    entity: str
    layout_type: str
    status: EntityLayoutStatus
    verified: bool = False
    error: str | None = None


class FieldStatus(Enum):
    """Outcome status for a single field operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"
    SKIPPED_TYPE_CONFLICT = "skipped_type_conflict"
    ERROR = "error"


@dataclass
class FieldResult:
    """Result of processing a single field.

    :param entity: Entity name.
    :param field: Field name.
    :param status: Outcome status.
    :param verified: Whether post-action verification passed.
    :param changes: List of changed property names (for updates).
    :param error: Error message if status is ERROR.
    """

    entity: str
    field: str
    status: FieldStatus
    verified: bool = False
    changes: list[str] | None = None
    error: str | None = None


@dataclass
class RunSummary:
    """Aggregate summary of a run or verify operation."""

    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    verification_failed: int = 0
    errors: int = 0
    layouts_updated: int = 0
    layouts_skipped: int = 0
    layouts_failed: int = 0


@dataclass
class RunReport:
    """Complete report for a run or verify operation.

    :param timestamp: ISO 8601 timestamp of the operation.
    :param instance_name: Name of the target instance.
    :param espocrm_url: URL of the target instance.
    :param program_file: Name of the program file used.
    :param operation: Either "run" or "verify".
    :param summary: Aggregate result counts.
    :param results: Per-field results.
    """

    timestamp: str
    instance_name: str
    espocrm_url: str
    program_file: str
    operation: str
    summary: RunSummary = field(default_factory=RunSummary)
    results: list[FieldResult] = field(default_factory=list)
    layout_results: list[LayoutResult] = field(default_factory=list)
