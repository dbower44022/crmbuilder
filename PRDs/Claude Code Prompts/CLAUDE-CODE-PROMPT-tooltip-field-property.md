# Claude Code Prompt — Add tooltip Field Property + Import Tooltips Feature

## Context

CRM Builder has two field properties for human-readable text on each field:

- `description` — developer-facing documentation. PRD references, rationale,
  MANUAL CONFIG notes. Lives in the YAML only. Never deployed to EspoCRM.
- `tooltip` — user-facing help text. Deployed to the EspoCRM field's `tooltip`
  property, which displays as a help icon next to field labels in detail and
  edit views.

These are two separate properties serving different audiences. This prompt
implements:

1. `tooltip` as a new field property in the model, config_loader, and
   field_manager
2. An **Import Tooltips** feature — a separate operation that reads `tooltip`
   from each field in the selected program file and writes it to EspoCRM

The full specification is in `PRDs/crmbuilder-spec-espocrm-impl.md` v1.9,
Sections 3.7 and 5.2. Read it before writing any code.

---

## Task 1 — `espo_impl/core/models.py`

### 1a — Add `tooltip` to `FieldDefinition`

Add after `description`:

```python
tooltip: str | None = None    # User-facing help text deployed to EspoCRM tooltip property
```

### 1b — Add tooltip operation models

Add status enum and result type for tooltip operations:

```python
class TooltipStatus(Enum):
    """Outcome status for a tooltip import operation."""
    UPDATED = "updated"
    SKIPPED = "skipped"        # field has no tooltip property
    NO_CHANGE = "no_change"    # EspoCRM tooltip already matches
    ERROR = "error"


@dataclass
class TooltipResult:
    """Result of processing a single field tooltip."""
    entity: str
    field: str
    status: TooltipStatus
    error: str | None = None
```

Update `RunSummary` to include tooltip counts:
```python
tooltips_updated: int = 0
tooltips_skipped: int = 0
tooltips_failed: int = 0
```

Update `RunReport` to include tooltip results:
```python
tooltip_results: list[TooltipResult] = field(default_factory=list)
```

---

## Task 2 — `espo_impl/core/config_loader.py`

In `_parse_field()`, add parsing for `tooltip` alongside `description`:

```python
tooltip=data.get("tooltip"),
```

No validation changes needed — `tooltip` is fully optional on all field types.

---

## Task 3 — Create `espo_impl/core/tooltip_manager.py`

New module. Handles reading, comparing, and writing field tooltips.

### 3.1 API Endpoint

The tooltip is set via the same field manager PUT endpoint used for field
updates:

```python
PUT_URL = "{api_url}/Admin/fieldManager/{entity}/{field_name}"
```

Use the same c-prefix logic as `field_manager.py` — custom fields use their
c-prefixed internal name (e.g., `cMentorStatus`), native fields do not.

### 3.2 Check

Fetch the current field definition via GET to
`Admin/fieldManager/{entity}/{field_name}`. Extract the current `tooltip`
value (may be `null` or absent). Compare to the YAML `tooltip` value.

Return whether they match.

### 3.3 Apply

PUT the field payload with only the `tooltip` key:

```python
{"tooltip": field_def.tooltip}
```

Do not include other field properties — this is a targeted tooltip-only update.

### 3.4 Process

Main entry point:

```python
def process_tooltips(
    self,
    entity_def: EntityDefinition,
    dry_run: bool = False
) -> list[TooltipResult]:
    """Process tooltips for all fields in an entity that have a tooltip value."""
```

For each field in `entity_def.fields`:
1. If `field_def.tooltip` is None or empty → log SKIPPED, continue
2. Fetch current tooltip from EspoCRM
3. If matches → log NO_CHANGE, continue
4. If differs → apply (unless dry_run), return result

### 3.5 Error Handling

Follow the same pattern as `field_manager.py`:
- HTTP 401 → raise `TooltipManagerError` (aborts operation)
- HTTP 403 → log error, mark ERROR, continue
- HTTP 4xx/5xx → log error and response body, mark ERROR, continue
- Network error → log error, mark ERROR, continue

### 3.6 Output messages

```
[TOOLTIP]  Contact.mentorStatus ... CHECKING
[TOOLTIP]  Contact.mentorStatus ... DIFFERS
[TOOLTIP]  Contact.mentorStatus ... UPDATED OK
[TOOLTIP]  Contact.contactType ... NO CHANGE
[TOOLTIP]  Contact.isMentor ... SKIPPED (no tooltip)
```

---

## Task 4 — Add Import Tooltips button to UI

### 4a — `espo_impl/ui/program_panel.py`

Add a **Import Tooltips** button to the program file panel action buttons,
alongside (or below) the existing Add / Edit / Delete buttons.

The button is:
- Enabled when a program file is selected AND an instance is selected AND
  the program has passed Validate
- Disabled during any active operation

### 4b — `espo_impl/ui/main_window.py` (or wherever Run is wired)

Wire the Import Tooltips button to a new worker slot that:
1. Instantiates `TooltipManager`
2. Calls `process_tooltips()` for each entity in the program
3. Collects results into the `RunReport`
4. Emits output lines to the output panel

Import Tooltips runs as a background operation (same thread pattern as Run).
It does NOT require a prior Run or Validate — it can be run at any time
once a program file and instance are selected.

### 4c — Summary block

After Import Tooltips completes, emit a summary:

```
===========================================
TOOLTIP IMPORT SUMMARY
===========================================
Total fields processed  : 47
  Updated               : 32
  No change             : 8
  Skipped (no tooltip)  : 6
  Failed                : 1
===========================================
```

---

## Task 5 — Update `core/reporter.py`

Include tooltip results in both `.log` and `.json` report outputs.

JSON schema addition:
```json
{
  "tooltip_results": [
    {
      "entity": "Contact",
      "field": "mentorStatus",
      "status": "updated",
      "error": null
    }
  ]
}
```

---

## Task 6 — Add tests

### `tests/test_config_loader.py` additions

- `tooltip` property parsed correctly from YAML
- Field with no `tooltip` property → `tooltip` is `None`
- `description` and `tooltip` can coexist independently

### `tests/test_tooltip_manager.py` (new file)

- Field with no tooltip → SKIPPED
- Current tooltip matches YAML → NO_CHANGE
- Current tooltip differs → UPDATED
- Current tooltip is null, YAML has value → UPDATED
- HTTP 401 raises TooltipManagerError
- HTTP 403 logs error and continues
- Payload contains only `tooltip` key (no other field properties)
- c-prefix applied to custom field names, not native fields

---

## Task 7 — Update spec and guides

### `PRDs/crmbuilder-spec-espocrm-impl.md`

Already updated to v1.9 with full specification. No further changes needed.

### `docs/user-guide.md`

Add a section covering:
- The `tooltip` property — what it is, when to add it
- The distinction between `description` (developer docs) and `tooltip` (user help)
- How to run Import Tooltips
- Example of a well-written tooltip vs a description

---

## Implementation Order

1. Task 1 — models.py
2. Task 2 — config_loader.py
3. Task 6 — config_loader tests (confirm passing)
4. Task 3 — tooltip_manager.py
5. Task 6 — tooltip_manager tests (confirm passing)
6. Task 4 — UI button
7. Task 5 — reporter.py
8. Task 7 — user-guide.md update

Confirm with me after step 3 and after step 5 before proceeding further.
