# CRM Builder — Technical Guide

**Version:** 1.3
**Last Updated:** March 2026  
**Changelog:** See end of document.

## Architecture Overview

```
espo_impl/
├── main.py                        # Entry point, directory init, QApplication
├── core/                          # Business logic (no GUI dependencies)
│   ├── models.py                  # Data models (dataclasses + enums)
│   ├── api_client.py              # EspoCRM REST API wrapper
│   ├── config_loader.py           # YAML parsing + validation
│   ├── field_manager.py           # Field CHECK→ACT orchestration
│   ├── entity_manager.py          # Entity create/delete orchestration
│   ├── comparator.py              # Field spec vs API state comparison
│   ├── reporter.py                # .log and .json report generation
│   └── import_manager.py          # Data import CHECK→ACT orchestration
├── ui/                            # PySide6 GUI components
│   ├── main_window.py             # Top-level window + state machine
│   ├── instance_panel.py          # Instance list + CRUD
│   ├── instance_dialog.py         # Add/Edit instance modal
│   ├── program_panel.py           # Program file list + CRUD
│   ├── output_panel.py            # Color-coded monospace output
│   ├── confirm_delete_dialog.py   # Destructive op confirmation + entity name mapping
│   └── import_dialog.py           # Four-step data import wizard
└── workers/
    ├── run_worker.py              # QThread wrapper for background operations
    └── import_worker.py           # QThread wrapper for import operations
```

The `core/` layer has no GUI dependencies and can be tested independently. The `ui/` layer handles all PySide6 interaction. The `workers/` layer bridges the two using Qt signals for thread-safe communication.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pyside6 | >= 6.10.2 | Qt6 GUI framework |
| requests | >= 2.32.5 | HTTP client |
| pyyaml | >= 6.0.2 | YAML parsing |
| pytest | >= 9.0.2 | Test framework (dev) |
| pytest-cov | >= 7.0.0 | Coverage reporting (dev) |
| ruff | >= 0.15.7 | Linter + formatter (dev) |

Build system: Hatchling. Package manager: uv.

---

## Data Models (`core/models.py`)

### InstanceProfile

```python
@dataclass
class InstanceProfile:
    name: str                        # Display name
    url: str                         # EspoCRM base URL
    api_key: str                     # API key or username
    auth_method: str = "api_key"     # "api_key", "hmac", or "basic"
    secret_key: str | None = None    # HMAC secret or password
    project_folder: str | None = None  # Path to client project directory

    api_url -> str                   # Property: {url}/api/v1
    slug -> str                      # Property: filename-safe name
    programs_dir -> Path | None      # Property: {project_folder}/programs
    reports_dir -> Path | None       # Property: {project_folder}/reports
    docs_dir -> Path | None          # Property: {project_folder}/Implementation Docs
```

The three directory properties return `None` when `project_folder` is not set. This drives the fallback behavior throughout the UI — when an instance has no project folder, the tool falls back to its own `data/programs/` and `reports/` directories.

### EntityAction (Enum)

```python
class EntityAction(Enum):
    NONE = "none"                    # Fields only (default)
    CREATE = "create"                # Create entity if not exists
    DELETE = "delete"                # Delete entity if exists
    DELETE_AND_CREATE = "delete_and_create"  # Delete then recreate
```

### EntityDefinition

```python
@dataclass
class EntityDefinition:
    name: str                        # YAML name (e.g., "Engagement")
    fields: list[FieldDefinition]
    action: EntityAction = EntityAction.NONE
    type: str | None = None          # "Base", "Person", "Company", "Event"
    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool = False
    disabled: bool = False
```

### FieldDefinition

```python
@dataclass
class FieldDefinition:
    name: str                        # lowerCamelCase field name
    type: str                        # Field type (varchar, enum, etc.)
    label: str                       # Display label
    required: bool | None = None     # None = not specified (won't compare)
    default: str | None = None
    readOnly: bool | None = None
    audited: bool | None = None
    options: list[str] | None = None
    translatedOptions: dict[str, str] | None = None
    style: dict[str, str | None] | None = None
    isSorted: bool | None = None
    displayAsLabel: bool | None = None
    min: int | None = None           # Minimum value (int/float fields)
    max: int | None = None           # Maximum value (int/float fields)
    maxLength: int | None = None     # Maximum character length (varchar fields)
    category: str | None = None      # UI grouping for layout tab assignment
    description: str | None = None   # Business rationale (for doc generator)
```

Optional fields default to `None` so the comparator can distinguish "not specified in YAML" from "explicitly set to a value." Only specified properties are compared against the API state.

### ProgramFile

```python
@dataclass
class ProgramFile:
    version: str
    description: str
    entities: list[EntityDefinition]
    source_path: Path | None = None

    has_delete_operations -> bool    # Property: any entity has DELETE/DELETE_AND_CREATE
```

### Result Types

```python
class FieldStatus(Enum):
    CREATED, UPDATED, SKIPPED, VERIFIED,
    VERIFICATION_FAILED, SKIPPED_TYPE_CONFLICT, ERROR

@dataclass
class FieldResult:
    entity: str
    field: str
    status: FieldStatus
    verified: bool = False
    changes: list[str] | None = None
    error: str | None = None

@dataclass
class RunSummary:
    total, created, updated, skipped, verification_failed, errors: int

@dataclass
class RunReport:
    timestamp, instance_name, espocrm_url, program_file, operation: str
    summary: RunSummary
    results: list[FieldResult]
```

---

## API Client (`core/api_client.py`)

### Authentication

All requests go through `_request()`, which handles auth header injection.

**API Key:** Sets `X-Api-Key` header on the session (applied to all requests).

**HMAC:** Computes a per-request signature:
```python
uri = path_after_api_v1  # e.g., "Admin/fieldManager/Contact/cContactType"
string_to_sign = f"{METHOD} /{uri}"
hmac_hash = HMAC-SHA256(secret_key, string_to_sign).hexdigest()
header_value = base64(f"{api_key}:{hmac_hash}")
# Header: X-Hmac-Authorization: {header_value}
```

**Basic:** Sets both `Authorization: Basic {base64(user:pass)}` and `Espo-Authorization: {base64(user:pass)}` headers on the session.

### Endpoints

All methods return `tuple[int, dict | None]` (status_code, response_body).

| Method | HTTP | Endpoint | Notes |
|--------|------|----------|-------|
| `get_field(entity, name)` | GET | `/Metadata?key=entityDefs.{entity}.fields.{name}` | Falls back to `/Admin/fieldManager/{entity}/{name}` |
| `create_field(entity, payload)` | POST | `/Admin/fieldManager/{entity}` | Auto-injects `isCustom: true` |
| `update_field(entity, name, payload)` | PUT | `/Admin/fieldManager/{entity}/{name}` | |
| `create_entity(payload)` | POST | `/EntityManager/action/createEntity` | EspoCRM adds C prefix |
| `remove_entity(name)` | POST | `/EntityManager/action/removeEntity` | Uses C-prefixed name |
| `check_entity_exists(name)` | GET | `/Metadata?key=scopes.{name}` | Returns `(status, bool)` |
| `rebuild()` | POST | `/Admin/rebuild` | Cache rebuild |
| `test_connection()` | GET | `/Metadata?key=app.adminPanel` | Returns `(bool, message)` |
| `get_entity_field_list(entity)` | GET | `/Metadata?key=entityDefs.{entity}.fields` | All field definitions for an entity |
| `search_by_email(entity, email)` | GET | `/{entity}?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}&maxSize=2` | Returns list of matches |
| `get_record(entity, id)` | GET | `/{entity}/{id}` | Single record by ID |
| `create_record(entity, payload)` | POST | `/{entity}` | Create a new record |
| `patch_record(entity, id, payload)` | PATCH | `/{entity}/{id}` | Partial update on existing record |

### Error Handling

Network errors and timeouts return `(-1, None)`. All other errors return the actual HTTP status code. The caller is responsible for interpreting status codes — the client does not raise exceptions for HTTP errors.

---

## EspoCRM Naming Conventions

### Entity Names

Custom entities get a `C` prefix: `Engagement` → `CEngagement`.

Mapping is currently in `confirm_delete_dialog.py` (known placement issue — `ENTITY_NAME_MAP` and `get_espo_entity_name()` are core business logic and should be refactored to `core/entity_manager.py` in a future cleanup):

```python
ENTITY_NAME_MAP = {
    "Engagement": "CEngagement",
    "Session": "CSessions",
    "Workshop": "CWorkshops",
    "WorkshopAttendance": "CWorkshopAttendee",
    "NpsSurveyResponse": "CNpsSurveyResponse",
}

NATIVE_ENTITIES = {"Contact", "Account", "Lead", ...}

def get_espo_entity_name(yaml_name: str) -> str:
    if yaml_name in NATIVE_ENTITIES: return yaml_name
    if yaml_name in ENTITY_NAME_MAP: return ENTITY_NAME_MAP[yaml_name]
    return f"C{yaml_name}"  # default
```

Note: EspoCRM's auto-generated C-prefixed names don't always follow a consistent rule (e.g., `Session` → `CSessions` with an extra `s`). The mapping table handles these irregularities.

### Field Names

Custom fields get a `c` prefix with capitalized first letter: `contactType` → `cContactType`.

```python
def _custom_field_name(name: str) -> str:
    return f"c{name[0].upper()}{name[1:]}"
```

### When Each Name Form Is Used

| Operation | Entity Name | Field Name |
|-----------|-------------|------------|
| Entity CREATE (POST) | Natural (`Engagement`) | N/A |
| Entity DELETE (POST) | C-prefixed (`CEngagement`) | N/A |
| Entity CHECK (GET) | C-prefixed (`CEngagement`) | N/A |
| Field CREATE (POST) | C-prefixed (`CEngagement`) | Natural (`contactType`) |
| Field UPDATE (PUT) | C-prefixed (`CEngagement`) | c-prefixed (`cContactType`) |
| Field CHECK (GET) | C-prefixed (`CEngagement`) | c-prefixed first, then natural |

---

## YAML Processing (`core/config_loader.py`)

### Supported Field Types

```python
SUPPORTED_FIELD_TYPES = {
    "varchar", "text", "wysiwyg", "enum", "multiEnum",
    "bool", "int", "float", "date", "datetime",
    "currency", "url", "email", "phone",
}
```

### Supported Entity Types

```python
SUPPORTED_ENTITY_TYPES = {"Base", "Person", "Company", "Event"}
```

### Validation Rules

**Top-level:** `version`, `description`, and `entities` are required.

**Entity-level:**
- `create` / `delete_and_create` require `type`, `labelSingular`, `labelPlural`
- `type` must be in `SUPPORTED_ENTITY_TYPES`
- `delete` must not contain `fields`

**Field-level:**
- `name`, `type`, `label` are required
- `type` must be in `SUPPORTED_FIELD_TYPES`
- `enum` / `multiEnum` must have non-empty `options`
- No duplicate `name` within the same entity

---

## Field Comparison (`core/comparator.py`)

### Properties Compared

**All field types:** `label`, `required`, `default`, `readOnly`, `audited`, `min`, `max`, `maxLength`

**Enum/multiEnum additionally:** `options` (order-sensitive), `translatedOptions`, `style`

### Comparison Rules

1. **Type mismatch** → `type_conflict = True`, no further comparison
2. **Only specified properties are compared** — if the YAML spec doesn't set `required`, it won't be checked against the API value (because it's `None` in the model)
3. **Options order matters** — `["A", "B"]` ≠ `["B", "A"]`
4. Returns `ComparisonResult(matches: bool, differences: list[str], type_conflict: bool)`

---

## Field Manager (`core/field_manager.py`)

### Field Resolution

`_get_field_resolved(entity, field_name)` tries two lookups:
1. c-prefixed name first (e.g., `cContactType`) — handles custom fields
2. Raw name fallback (e.g., `contactType`) — handles system fields

Returns `(status_code, body, resolved_name)`.

### Run Workflow

For each entity (skipping `action: delete` and entities with no fields):

1. Map entity name → EspoCRM name via `get_espo_entity_name()`
2. For each field in the entity:
   - **CHECK:** `_get_field_resolved()` to find existing field
   - **COMPARE:** If found, compare spec vs current state
   - **ACT:** Create (POST), Update (PUT), or Skip
   - **409 handling:** If CREATE returns 409, extract actual field name from error response and fall back to UPDATE

### 409 Conflict Recovery

```python
def _extract_field_name_from_409(body: dict) -> str | None:
    return body["messageTranslation"]["data"]["field"]
    # e.g., "cContactType"
```

When a CREATE fails with 409 (field already exists under c-prefixed name), the tool extracts the actual name and issues an UPDATE instead.

### Inline Verification

Inline verification (re-reading the field after create/update) is **disabled**. EspoCRM's cache may return stale data or HTTP 500 immediately after a write. The standalone Verify button should be used after the cache settles.

---

## Entity Manager (`core/entity_manager.py`)

### API Endpoints (Discovered)

```
Create: POST /api/v1/EntityManager/action/createEntity
        Payload: {"name":"Engagement","type":"Base","labelSingular":"Engagement",
                  "labelPlural":"Engagements","stream":false,"disabled":false}
        EspoCRM adds C prefix automatically.

Delete: POST /api/v1/EntityManager/action/removeEntity
        Payload: {"name":"CEngagement"}
        Uses the C-prefixed internal name.

Rebuild: POST /api/v1/Admin/rebuild
```

Note: Both create and delete use POST (not PUT/DELETE methods).

### Operations

- **`_create_entity()`** — Checks existence via Metadata API, skips if exists, creates with natural name
- **`_delete_entity()`** — Checks existence, skips if not found, deletes with C-prefixed name
- **`process_entity()`** — Dispatches to create/delete/delete_and_create
- **`rebuild_cache()`** — POST to `/Admin/rebuild`

### Error Handling

- HTTP 401 → raises `EntityManagerError` (aborts entire run)
- All other errors → logged, returns `False` (continue-and-log pattern)
- For `delete_and_create`: if delete fails, create is not attempted

---

## Layout Manager (`core/layout_manager.py`)

### API Endpoints

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Read | GET | `/Layout/action/getOriginal?scope={entity}&name={type}` |
| Save | PUT | `/{entity}/layout/{type}` |

Both use the EspoCRM internal entity name (C-prefixed for custom entities).

### Tab Expansion Algorithm

When a panel has `tabs` instead of `rows`, each tab expands into a separate API panel object:

1. **First tab** inherits the parent panel's `tabBreak`, `tabLabel`, and `dynamicLogicVisible`
2. **Subsequent tabs** get `tabBreak: false`, `tabLabel: null`, but still inherit `dynamicLogicVisible`
3. Each tab's rows are auto-generated from fields matching its `category`

### Auto-Row Generation

When a tab specifies a `category` instead of explicit `rows`:

1. Collect fields where `field.category == tab.category`, in definition order
2. Group into rows of 2 fields each
3. `wysiwyg`, `text`, and `address` type fields get their own full-width row (single cell)
4. If last row has one normal field, pad with `false` (empty cell)

### Field Name C-Prefix in Layouts

Field names in layout row cells must use the c-prefixed internal name for custom fields:

```python
def _resolve_field_name(name, custom_field_names):
    if name in custom_field_names:
        return f"c{name[0].upper()}{name[1:]}"
    return name  # native fields pass through
```

A field is considered custom if it appears in the entity's `fields` list in the YAML. Native fields referenced in explicit `rows` (e.g., `name`, `emailAddress`) pass through without prefix.

### Dynamic Logic Translation

```python
# YAML shorthand:
{"attribute": "contactType", "value": "Mentor"}

# API format (with c-prefix applied):
{"conditionGroup": [{"type": "equals", "attribute": "cContactType", "value": "Mentor"}]}
```

### The `category` Property

Added to `FieldDefinition` — a string tag that groups fields for layout tab assignment. Has no effect on the EspoCRM field itself; only used by the layout manager for auto-row generation.

---

## Run Orchestration (`workers/run_worker.py`)

The `RunWorker` (QThread) orchestrates the full execution:

```
1. Entity Deletions
   └── For each DELETE / DELETE_AND_CREATE entity:
       └── _delete_entity()
   └── rebuild_cache()

2. Entity Creations
   └── For each CREATE / DELETE_AND_CREATE entity:
       └── _create_entity()
   └── rebuild_cache()

3. Field Operations
   └── field_mgr.run(program)
       └── For each entity with fields (skipping DELETE-only):
           └── For each field:
               └── CHECK → COMPARE → ACT

4. Layout Operations
   └── For each entity with layouts (skipping DELETE-only):
       └── layout_mgr.process_layouts(entity_def, fields)
           └── For each layout type:
               └── CHECK → APPLY (if differs) → summary
```

### Signals

```python
output_line = Signal(str, str)    # (message, color) → output panel
finished_ok = Signal(object)      # RunReport → main window
finished_error = Signal(str)      # error message → main window
```

Qt signals are automatically queued when crossing thread boundaries, making the `output_line.emit` callback thread-safe.

---

## UI Components

### Main Window State Machine

```python
@dataclass
class UIState:
    instance: InstanceProfile | None    # Selected instance
    program_path: Path | None           # Selected program file path
    program: ProgramFile | None         # Parsed program (after validate)
    validated: bool                     # Validate passed
    run_complete: bool                  # Run finished
    operation_in_progress: bool         # Worker thread active
    last_report_path: Path | None       # Most recent report
```

**Button behavior:** Buttons are never disabled. Each click handler checks
preconditions and shows an explanatory message in the output panel if they
are not met (e.g., "Select an instance first", "Validate a program file
first", "An operation is already in progress").

- **Import Data:** Opens the import wizard dialog. Requires an instance.

### Instance-Aware Directory Switching

When an instance is selected, `_on_instance_selected` updates the program panel's directory:

- If the instance has a `project_folder` → `programs_dir` (project folder's `programs/`)
- Otherwise → falls back to `base_dir / "data" / "programs"`

The `Reporter` is created lazily in `_start_worker` using the instance's `reports_dir` (or `base_dir / "reports"` as fallback). This ensures reports land in the correct project folder.

After add/edit, `instance_panel` explicitly emits `instance_selected` to guarantee the main window picks up the updated profile, even when the list selection index hasn't changed (e.g., single-instance case).

### Confirmation Dialog

Triggered before any run that contains `DELETE` or `DELETE_AND_CREATE` actions. The dialog:
1. Lists affected entities with their EspoCRM internal names
2. Requires exact `DELETE` text input to enable the Proceed button
3. Fires before ANY API calls — including non-destructive ones in the same program

### Output Panel

Color-coded monospace QTextEdit with dark theme background (`#1e1e1e`).

| Color Key | Hex | Usage |
|-----------|-----|-------|
| `"green"` | `#4CAF50` | Success |
| `"red"` | `#F44336` | Error |
| `"yellow"` | `#FFC107` | Warning |
| `"gray"` | `#9E9E9E` | No change |
| `"white"` | `#D4D4D4` | Informational |

---

## Report Generation (`core/reporter.py`)

### Filename Format

```
{instance_slug}_{operation}_{YYYYMMDD_HHMMSS}.{ext}
```

Example: `cbm_production_run_20260321_143022.log`

### JSON Report Schema

```json
{
  "run_metadata": {
    "timestamp": "ISO 8601",
    "instance": "Instance Name",
    "espocrm_url": "https://...",
    "program_file": "filename.yaml",
    "operation": "run|verify|preview"
  },
  "summary": {
    "total": 5,
    "created": 2,
    "updated": 1,
    "skipped": 1,
    "verification_failed": 0,
    "errors": 1
  },
  "results": [
    {
      "entity": "Contact",
      "field": "contactType",
      "status": "created|updated|skipped|verified|verification_failed|skipped_type_conflict|error",
      "verified": true,
      "changes": ["label", "options"],
      "error": null
    }
  ]
}
```

---

## Relationship Manager (`core/relationship_manager.py`)

### API Endpoints

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Check | GET | `/Metadata?key=entityDefs.{entity}.links.{link}` |
| Create | POST | `/EntityManager/action/createLink` |
| Delete | POST | `/EntityManager/action/removeLink` (not used in normal flow) |

### Link Type Mapping

| YAML `linkType` | Metadata `type` (primary side) |
|-----------------|-------------------------------|
| `oneToMany` | `hasMany` |
| `manyToOne` | `belongsTo` |
| `manyToMany` | `hasMany` |

### `action: skip` Pattern

Relationships with `action: skip` are logged as SKIPPED without any API calls — not even the check step. This is for pre-existing relationships that were created manually and are known to be correct. They're defined in YAML for documentation and full reproducibility.

### Entity Name Resolution

Both `entity` and `entityForeign` are resolved via `get_espo_entity_name()` before any API call. The `link` and `linkForeign` names are used as-is (they are already in EspoCRM's internal format).

### Processing Order

Relationships are processed after all entity creation, field management, and layout management is complete. This ensures all referenced entities exist.

---

## Import Manager (`core/import_manager.py`)

### Data Structures

```python
class ImportAction(Enum):
    CREATE, UPDATE, SKIP, ERROR

@dataclass
class RecordPlan:
    source_name: str             # display name from JSON
    email: str | None            # email used for matching
    action: ImportAction
    espo_id: str | None          # set if existing record found
    fields_to_set: dict          # payload for CREATE/UPDATE
    fields_skipped: list         # fields with existing values
    error_message: str | None

@dataclass
class ImportResult:
    source_name, email, action, success, fields_set,
    fields_skipped, error_message

@dataclass
class ImportReport:
    timestamp, instance_name, entity, source_file,
    total, created, updated, skipped, errors, results
```

### CHECK Phase (`check()`)

For each source record:

1. Build candidate payload from field mapping + fixed values
2. Clean phone numbers to E.164 format (`+1` prefix for US 10-digit)
3. Derive `firstName`/`lastName` from record display name or email if missing
4. Find email address from mapped fields or fixed values
5. Search EspoCRM by email (`search_by_email`, `maxSize=2`)
6. If no match → `CREATE` with full payload
7. If match found → fetch full record, compare each field:
   - Existing value is `None` or `""` → include in `fields_to_set`
   - Existing value is non-empty → add to `fields_skipped`
   - All fields skipped → `SKIP`; otherwise → `UPDATE`
8. If 2 matches → use first, log WARNING about duplicate email

### ACT Phase (`execute()`)

Iterates pre-computed `RecordPlan` objects from CHECK:

- `CREATE` → `POST /api/v1/{entity}` with payload
- `UPDATE` → `PATCH /api/v1/{entity}/{id}` with partial payload
- `SKIP` / `ERROR` → logged, no API call

Errors on individual records do not abort the import. Each record's
outcome is logged with full field=value detail.

### Payload Transformations

- **Phone cleaning**: Strips non-digit characters, prepends `+1` for
  10-digit US numbers, `+` for 11-digit numbers starting with `1`
- **Name derivation**: Parses record `name` field (strips Mr./Mrs./Ms./Dr.)
  then falls back to email local part (`first.last@domain`)
- **Boolean conversion**: Fixed-value strings `"true"`/`"false"` →
  Python `True`/`False`
- **Empty filtering**: Empty string values are excluded from payload
- **Non-writable fields**: Fields with types `personName`, `address`,
  `map`, `foreign`, `linkParent`, `autoincrement` and fields marked
  `readOnly` or `notStorable` are excluded from mapping dropdowns

### Report Writing

`write_report()` produces `.log` and `.json` files in the instance's
`reports/` directory with filename pattern `import_{timestamp}.{ext}`.

---

### Import Dialog (`ui/import_dialog.py`)

Four-step wizard (`QDialog` with `QStackedWidget`):

| Step | Widget | Background Worker |
|------|--------|-------------------|
| 1 — Setup | File picker, entity combo, fixed-value table | None (sync field fetch) |
| 2 — Mapping | Mapping table with searchable combos, unmapped list | None |
| 3 — Preview | Scroll area with per-record plans, summary counts | `CheckWorker` (QThread) |
| 4 — Execute | Output panel, progress bar, summary, View Report | `ImportWorker` (QThread) |

The dialog is fully self-contained — it does not interact with the main
window's `UIState`. The `EspoAdminClient` is passed in from the main window.

Field combos use `setEditable(True)` with `MatchContains` completer for
type-to-filter search. Auto-mapping uses a known alias table plus
case-insensitive label and normalized matching.

---

## Documentation Generator (`tools/generate_docs.py`)

Reads all YAML program files and produces a structured reference manual in both `.md` and `.docx` formats. The YAML files are the single source of truth.

### Running

Use the **Generate Docs** button in the application UI. The button is enabled when the selected instance has a project folder with at least one `.yaml` file in its `programs/` directory.

The tool reads from `{project_folder}/programs/` and writes to `{project_folder}/Implementation Docs/`. Output files are named after the instance: `{instance_name}-CRM-Reference.md` and `{instance_name}-CRM-Reference.docx`.

Generate Docs requires a project folder — instances without one see an error message prompting them to configure a project folder.

CLI usage (standalone):

```bash
uv run python tools/generate_docs.py --programs ~/Projects/CBM/programs/ --output ~/Projects/CBM/Implementation\ Docs/
```

### Architecture

```
tools/docgen/
├── models.py          # DocDocument, DocSection, DocTable, DocParagraph
├── yaml_loader.py     # Load YAML files, build entity index, canonical ordering
├── builders/          # One builder per document section
│   ├── entity_builder.py      # Section 2 — entity header tables
│   ├── field_builder.py       # Section 3 — field tables with c-prefix, type mapping
│   ├── layout_builder.py      # Section 4 — panel/tab/column descriptions
│   ├── view_builder.py        # Section 5 — list view columns
│   ├── placeholder_builder.py # Sections 6-8 — future capability placeholders
│   └── appendix_builder.py    # Appendix A (enum values) and B (deployment status)
└── renderers/
    ├── md_renderer.py         # GitHub Markdown output
    └── docx_renderer.py       # Word document output (python-docx)
```

### Key Behaviors

- **`description` property**: Read from entities, fields, and panels. Entities without description show "No description provided." Field descriptions truncated to 200 chars in tables.
- **Type mapping**: YAML types mapped to display names (e.g., `wysiwyg` → "Rich Text")
- **c-prefix**: Internal field names use the c-prefix (e.g., `cContactType`)
- **Entity ordering**: Follows canonical order: Account, Contact, Engagement, Session, NpsSurveyResponse, Workshop, WorkshopAttendance, Dues
- **Entity display names**: Account → "Company", NpsSurveyResponse → "NPS Survey Response"

### When to Regenerate

Regenerate whenever YAML program files are updated. Commit both the YAML changes and the regenerated documents together.

---

## Testing

### Running Tests

```bash
uv run pytest tests/ -v
```

### Test Coverage

| Module | Test File | Cases |
|--------|-----------|-------|
| `models.py` | `test_models.py` | Project folder directory properties, None handling |
| `config_loader.py` | `test_config_loader.py` | YAML parsing, validation rules, entity actions, field types |
| `api_client.py` | `test_api_client.py` | Auth headers, URL construction, HMAC signing, error handling |
| `comparator.py` | `test_comparator.py` | Match/diff detection, type conflicts, enum order, optional fields |
| `field_manager.py` | `test_field_manager.py` | Create/update/skip flows, 409 recovery, c-prefix resolution, error propagation |
| `entity_manager.py` | `test_entity_manager.py` | Create/delete/delete_and_create, name mapping, cache rebuild, 401 abort |
| `reporter.py` | `test_reporter.py` | File generation, filename format, JSON schema, directory creation |

### Mocking Pattern

All tests mock `requests.Session.request` at the session level:

```python
client = make_client()
client.session.request = MagicMock(return_value=mock_response(status_code=200))
```

For `FieldManager` and `EntityManager` tests, the `EspoAdminClient` is mocked entirely:

```python
client = MagicMock()
client.get_field.side_effect = [(404, None), (404, None)]
client.create_field.return_value = (200, {})
```

### Linting

```bash
uv run ruff check espo_impl/ tests/
```

Configuration in `pyproject.toml`: line length 88, Python 3.12 target, rules E/F/I/B/C4/UP.

---

## File Storage

### Instance Profiles (`data/instances/`)

```json
{
  "name": "CBM Production",
  "url": "https://cbm.espocloud.com",
  "api_key": "admin_username",
  "auth_method": "basic",
  "secret_key": "admin_password",
  "project_folder": "/home/user/Projects/ClevelandBusinessMentors"
}
```

Filename: `{name.lower().replace(" ", "_").replace("-", "_")}.json`

Gitignored: `data/instances/*.json` (contains credentials).

The `project_folder` key is optional. Existing JSON files without it load normally — `data.get("project_folder")` returns `None`.

### Project Folder Structure

When an instance has a `project_folder`, the tool uses its subdirectories for all file operations:

```
{project_folder}/
├── programs/            ← YAML program files (loaded in Program File panel)
├── Implementation Docs/ ← generated reference manual
└── reports/             ← run/verify reports
```

These directories are created automatically when an instance is saved with a project folder (via `_ensure_project_structure`).

### Fallback Directories

When `project_folder` is `None` (legacy instances or no folder configured):

| Purpose | Fallback Path |
|---------|--------------|
| Programs | `{base_dir}/data/programs/` |
| Reports | `{base_dir}/reports/` |
| Generate Docs | Disabled (shows error message) |

### Program Files

YAML files live in the project folder's `programs/` directory. Not gitignored — safe to commit (no credentials).

### Reports

`.log` and `.json` files in the project folder's `reports/` directory. Typically gitignored in the client repo.

---

## Extending the Tool

### Adding a New Field Type

1. Add the type string to `SUPPORTED_FIELD_TYPES` in `config_loader.py`
2. If it has special properties (like `options` for enums), add them to `FieldDefinition` in `models.py`
3. Update `_build_payload()` in `field_manager.py` to include the new properties
4. Update comparison logic in `comparator.py` if the new properties need comparing
5. Add tests

### Adding a New Entity Name Mapping

Add the mapping to `ENTITY_NAME_MAP` (currently in `confirm_delete_dialog.py`):

```python
ENTITY_NAME_MAP["NewEntity"] = "CNewEntity"
```

### Adding a New API Endpoint

1. Add the method to `EspoAdminClient` in `api_client.py`
2. Use `self._request()` to handle auth and error wrapping
3. Return `tuple[int, dict | None]`
4. Add tests mocking `session.request`

### Adding a New Operation Phase

The run sequence is in `RunWorker._run_full()`. Insert new phases between entity ops and field ops as needed. Use `EntityManager` or `FieldManager` patterns for orchestration.
---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.3 | March 2026 | Added data import: import_manager.py, import_dialog.py, import_worker.py, 5 new API endpoints, never-disable button pattern |
| 1.2 | March 2026 | Added project folder architecture, renamed to CRM Builder |
| 1.1 | March 2026 | Added layout manager, relationship manager, documentation generator, and content_version support |
| 1.0 | Early 2026 | Initial release covering entity and field management |
