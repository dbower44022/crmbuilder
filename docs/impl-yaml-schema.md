# CRM Builder — YAML Schema Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/application/app-yaml-schema.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of YAML program file
parsing, validation, and the data models that represent program file
contents in memory. It covers `core/config_loader.py` and the
relevant portions of `core/models.py`.

---

## 2. File Locations

```
espo_impl/core/config_loader.py    # YAML parsing and validation
espo_impl/core/models.py           # Data models for program file contents
```

---

## 3. Data Models (`core/models.py`)

### 3.1 InstanceProfile

```python
@dataclass
class InstanceProfile:
    name: str
    url: str
    api_key: str
    auth_method: str = "api_key"    # "api_key", "hmac", or "basic"
    secret_key: str | None = None   # HMAC secret or Basic password
    project_folder: str | None = None

    @property
    def api_url(self) -> str:
        return f"{self.url.rstrip('/')}/api/v1"

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "_").replace("-", "_")

    @property
    def programs_dir(self) -> Path | None:
        return Path(self.project_folder) / "programs" \
            if self.project_folder else None

    @property
    def reports_dir(self) -> Path | None:
        return Path(self.project_folder) / "reports" \
            if self.project_folder else None

    @property
    def docs_dir(self) -> Path | None:
        return Path(self.project_folder) / "Implementation Docs" \
            if self.project_folder else None
```

The three directory properties return `None` when `project_folder`
is not set. This drives fallback behavior throughout the UI.

### 3.2 EntityAction

```python
class EntityAction(Enum):
    NONE = "none"
    CREATE = "create"
    DELETE = "delete"
    DELETE_AND_CREATE = "delete_and_create"
```

### 3.3 FieldDefinition

```python
@dataclass
class FieldDefinition:
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
```

Optional fields default to `None` so the comparator can distinguish
"not specified in YAML" from "explicitly set to a value." Only
specified properties are compared against the API state.

### 3.4 EntityDefinition

```python
@dataclass
class EntityDefinition:
    name: str
    fields: list[FieldDefinition]
    action: EntityAction = EntityAction.NONE
    type: str | None = None
    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool = False
    disabled: bool = False
    description: str | None = None
    layout: dict | None = None      # raw layout dict, processed by layout_manager
```

### 3.5 RelationshipDefinition

```python
@dataclass
class RelationshipDefinition:
    name: str
    entity: str
    entity_foreign: str
    link_type: str
    link: str
    link_foreign: str
    label: str
    label_foreign: str
    description: str | None = None
    relation_name: str | None = None
    audited: bool = False
    audited_foreign: bool = False
    action: str | None = None       # None = deploy, "skip" = record only
```

### 3.6 ProgramFile

```python
@dataclass
class ProgramFile:
    version: str
    description: str
    entities: list[EntityDefinition]
    relationships: list[RelationshipDefinition] = field(default_factory=list)
    content_version: str | None = None
    source_path: Path | None = None

    @property
    def has_delete_operations(self) -> bool:
        return any(
            e.action in (EntityAction.DELETE, EntityAction.DELETE_AND_CREATE)
            for e in self.entities
        )
```

---

## 4. Config Loader (`core/config_loader.py`)

### 4.1 Supported Field Types

```python
SUPPORTED_FIELD_TYPES = {
    "varchar", "text", "wysiwyg", "enum", "multiEnum",
    "bool", "int", "float", "date", "datetime",
    "currency", "url", "email", "phone",
}
```

### 4.2 Supported Entity Types

```python
SUPPORTED_ENTITY_TYPES = {"Base", "Person", "Company", "Event"}
```

### 4.3 Load and Validate

```python
def load_program_file(path: Path) -> tuple[ProgramFile | None, list[str]]:
    """
    Returns (program, errors). If errors is non-empty, program is None.
    """
```

Parsing is done with `yaml.safe_load()`. The function returns a
`(ProgramFile, [])` on success or `(None, [error_strings])` on
failure. All validation errors are collected before returning — the
function never raises on a validation error.

### 4.4 Validation Rules

**Top-level:**
- `version`, `description` are required
- `entities` key must be a dict if present
- `relationships` key must be a list if present

**Entity-level:**
- `description` is required on all entity blocks
- `action: create` and `action: delete_and_create` require `type`,
  `labelSingular`, `labelPlural`
- `type` must be in `SUPPORTED_ENTITY_TYPES`
- `action: delete` must not contain `fields` or `layout`
- No duplicate entity names within the file

**Field-level:**
- `name`, `type`, `label` are required
- `type` must be in `SUPPORTED_FIELD_TYPES`
- `enum` and `multiEnum` require non-empty `options`
- No duplicate field `name` within the same entity

**Layout-level:**
- Each panel must have `rows` or `tabs`, not both
- `tabBreak: true` requires `tabLabel`
- Tab `category` references must match at least one field's `category`
  in the entity's field list
- Field names in explicit `rows` must exist in the entity's field list

**Relationship-level:**
- `name`, `entity`, `entityForeign`, `linkType`, `link`, `linkForeign`,
  `label`, `labelForeign` are required
- `linkType` must be one of: `oneToMany`, `manyToOne`, `manyToMany`
- `manyToMany` requires `relationName`
- `description` is required
- `action`, if present, must be `"skip"`

### 4.5 Error Format

Validation errors are returned as human-readable strings:

```
"Entity 'Engagement': missing required field 'description'"
"Entity 'Contact', field 'contactType': type 'enum' requires non-empty 'options'"
"Entity 'Contact', layout panel 'Mentor Details': 'tabs' category 'Mentor Admin' not found in field list"
"Relationship 'duesToMentor': missing required field 'description'"
```

---

## 5. EspoCRM Naming Conventions

### 5.1 Entity Name Mapping

Custom entities get a `C` prefix when stored in EspoCRM. The mapping
is maintained in `confirm_delete_dialog.py` (known placement issue —
should be refactored to `core/entity_manager.py`):

```python
ENTITY_NAME_MAP = {
    "Engagement":        "CEngagement",
    "Session":           "CSessions",
    "Workshop":          "CWorkshops",
    "WorkshopAttendance": "CWorkshopAttendee",
    "NpsSurveyResponse": "CNpsSurveyResponse",
    "Dues":              "CDues",
}

NATIVE_ENTITIES = {
    "Contact", "Account", "Lead", "Opportunity",
    "Case", "Task", "Meeting", "Call", "Email", "Document",
}

def get_espo_entity_name(yaml_name: str) -> str:
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    if yaml_name in ENTITY_NAME_MAP:
        return ENTITY_NAME_MAP[yaml_name]
    return f"C{yaml_name}"    # default fallback
```

Note: EspoCRM's auto-generated C-prefixed names do not always follow
a consistent rule (e.g., `Session` → `CSessions` with an extra `s`).
The mapping table handles these irregularities. New custom entities
should be added to the map explicitly rather than relying on the
default fallback.

### 5.2 Field Name Mapping

Custom fields get a `c` prefix with capitalized first letter:

```python
def _custom_field_name(name: str) -> str:
    return f"c{name[0].upper()}{name[1:]}"
# "contactType" → "cContactType"
# "isMentor"    → "cIsMentor"
```

### 5.3 When Each Name Form Is Used

| Operation | Entity Name | Field Name |
|---|---|---|
| Entity CREATE (POST) | Natural (`Engagement`) | N/A |
| Entity DELETE (POST) | C-prefixed (`CEngagement`) | N/A |
| Entity CHECK (GET) | C-prefixed (`CEngagement`) | N/A |
| Field CREATE (POST) | C-prefixed (`CEngagement`) | Natural (`contactType`) |
| Field UPDATE (PUT) | C-prefixed (`CEngagement`) | c-prefixed (`cContactType`) |
| Field CHECK (GET) | c-prefixed first, then natural fallback | |
| Layout READ (GET) | C-prefixed (`CEngagement`) | N/A |
| Layout SAVE (PUT) | C-prefixed (`CEngagement`) | c-prefixed in row cells |
| Relationship CHECK (GET) | C-prefixed (`CEngagement`) | N/A |
| Relationship CREATE (POST) | C-prefixed (`CEngagement`) | N/A |

---

## 6. Testing

`config_loader.py` is covered by `tests/test_config_loader.py`:

| Test Area | Cases |
|---|---|
| Valid YAML parsing | Basic file, all field types, entity actions |
| Required field validation | Missing version, description, entity fields |
| Entity action validation | create requires type/labels, delete forbids fields |
| Field type validation | Unsupported types rejected, enum without options rejected |
| Duplicate detection | Duplicate entity names, duplicate field names |
| Layout validation | Panel has both rows and tabs, missing tabLabel, bad category ref |
| Relationship validation | Missing required fields, bad linkType, manyToMany without relationName |

Mocking pattern — tests use `tmp_path` fixture with inline YAML:

```python
def test_missing_description(tmp_path):
    yaml_content = """
version: "1.0"
description: "test"
entities:
  Contact:
    fields:
      - name: foo
        type: varchar
        label: Foo
"""
    path = tmp_path / "test.yaml"
    path.write_text(yaml_content)
    program, errors = load_program_file(path)
    assert program is None
    assert any("description" in e for e in errors)
```
