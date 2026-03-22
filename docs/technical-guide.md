# EspoCRM Implementation Tool — Technical Guide

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
│   └── reporter.py                # .log and .json report generation
├── ui/                            # PySide6 GUI components
│   ├── main_window.py             # Top-level window + state machine
│   ├── instance_panel.py          # Instance list + CRUD
│   ├── instance_dialog.py         # Add/Edit instance modal
│   ├── program_panel.py           # Program file list + CRUD
│   ├── output_panel.py            # Color-coded monospace output
│   └── confirm_delete_dialog.py   # Destructive op confirmation + entity name mapping
└── workers/
    └── run_worker.py              # QThread wrapper for background operations
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

    api_url -> str                   # Property: {url}/api/v1
    slug -> str                      # Property: filename-safe name
```

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

**Button enable rules:**
- **Validate:** instance and program selected, not in progress
- **Run:** validated, not in progress
- **Verify:** run complete, not in progress
- **View Report:** report file exists

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

## Testing

### Running Tests

```bash
uv run pytest tests/ -v
```

### Test Coverage

| Module | Test File | Cases |
|--------|-----------|-------|
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
  "secret_key": "admin_password"
}
```

Filename: `{name.lower().replace(" ", "_").replace("-", "_")}.json`

Gitignored: `data/instances/*.json` (contains credentials).

### Program Files (`data/programs/`)

YAML files. Not gitignored — safe to commit (no credentials).

### Reports (`reports/`)

`.log` and `.json` files. Gitignored.

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
