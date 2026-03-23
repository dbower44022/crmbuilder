# Claude Code Prompt — Relationship Management Implementation

## Context

The EspoCRM Implementation Tool currently handles entity creation, field
management, and layout management. We are now adding Phase 4: relationship
management — the ability to define and deploy entity relationships via YAML
program files.

Key specifications:
- `PRDs/CBM-SPEC-espocrm-impl.md` (v1.5) — main tool spec
- `PRDs/CBM-SPEC-relationship-management.md` — relationship spec (read this first)

Read both documents carefully before writing any code.

---

## Overview of Changes

1. Add `RelationshipDefinition`, `RelationshipStatus`, `RelationshipResult`
   to `core/models.py`
2. Add `relationships` parsing to `config_loader.py`
3. Add validation for relationship definitions
4. Create `core/relationship_manager.py`
5. Update `workers/run_worker.py` to process relationships after layouts
6. Update `core/reporter.py` to include relationship results
7. Update spec and guides
8. Add tests

Implement in the order listed. Confirm with me after each task before
proceeding to the next.

---

## Task 1 — Update `core/models.py`

Add the following dataclasses and enum:

```python
@dataclass
class RelationshipDefinition:
    name: str                        # identifier for this relationship
    description: str | None          # business rationale and PRD reference
    entity: str                      # primary entity (natural name)
    entity_foreign: str              # foreign entity (natural name)
    link_type: str                   # oneToMany, manyToOne, manyToMany
    link: str                        # link name on primary entity
    link_foreign: str                # link name on foreign entity
    label: str                       # panel label on primary entity
    label_foreign: str               # panel label on foreign entity
    relation_name: str | None = None # junction table name (manyToMany only)
    audited: bool = False
    audited_foreign: bool = False
    action: str | None = None        # None=deploy, "skip"=record only


class RelationshipStatus(Enum):
    CREATED = "created"
    SKIPPED = "skipped"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class RelationshipResult:
    name: str
    entity: str
    entity_foreign: str
    link: str
    status: RelationshipStatus
    verified: bool = False
    message: str | None = None
```

Update `RunSummary` to include:
```python
relationships_created: int = 0
relationships_skipped: int = 0
relationships_failed: int = 0
```

Update `RunReport` to include:
```python
relationship_results: list[RelationshipResult] = field(default_factory=list)
```

Update `ProgramFile` to include:
```python
relationships: list[RelationshipDefinition] = field(default_factory=list)
```

---

## Task 2 — Update `core/config_loader.py`

### 2a — Parse `relationships` block

In `load_program()`, after parsing entities, parse the top-level
`relationships` list:

```python
relationships = []
for rel_data in data.get("relationships", []):
    relationships.append(self._parse_relationship(rel_data))
program.relationships = relationships
```

### 2b — Add `_parse_relationship()` method

```python
def _parse_relationship(self, data: dict) -> RelationshipDefinition:
    return RelationshipDefinition(
        name=data["name"],
        description=data.get("description"),
        entity=data["entity"],
        entity_foreign=data["entityForeign"],
        link_type=data["linkType"],
        link=data["link"],
        link_foreign=data["linkForeign"],
        label=data["label"],
        label_foreign=data["labelForeign"],
        relation_name=data.get("relationName"),
        audited=data.get("audited", False),
        audited_foreign=data.get("auditedForeign", False),
        action=data.get("action"),
    )
```

### 2c — Add validation

In `validate_program()`, for each relationship:
- `linkType` must be one of: `oneToMany`, `manyToOne`, `manyToMany`
- `name`, `entity`, `entityForeign`, `link`, `linkForeign`, `label`,
  `labelForeign` must all be non-empty strings
- `relationName` is required if `linkType` is `manyToMany`
- `action` if present must be `"skip"`
- Warn if `description` is missing (not an error)
- Warn if the same `link` name appears twice on the same entity

---

## Task 3 — Create `core/relationship_manager.py`

### 3.1 API Endpoints

```python
# Check — read existing link
CHECK_URL = "{api_url}/Metadata?key=entityDefs.{entity}.links.{link}"

# Create
CREATE_URL = "{api_url}/EntityManager/action/createLink"

# Delete (not used in normal flow — included for reference)
DELETE_URL = "{api_url}/EntityManager/action/removeLink"
```

### 3.2 Entity Name Resolution

Import and use the existing `get_espo_entity_name()` function for all
entity name resolution. Both primary and foreign entity names must be
resolved before building any API URL or payload.

### 3.3 Link Type Mapping

For the check/verify step, map YAML linkType to the Metadata API `type`
value that appears on the primary entity side:

```python
LINK_TYPE_TO_METADATA = {
    "oneToMany": "hasMany",
    "manyToOne": "belongsTo",
    "manyToMany": "hasMany",
}
```

### 3.4 Check

```python
def _check_link_exists(self, espo_entity: str, link: str) -> dict | None:
    """Fetch link metadata. Returns link dict if exists, None if not."""
```

GET `Metadata?key=entityDefs.{espo_entity}.links.{link}`

- HTTP 200 with a non-empty dict → link exists, return dict
- HTTP 200 with null/empty → link does not exist, return None
- HTTP 4xx/5xx → raise error

### 3.5 Compare

```python
def _compare_link(
    self,
    existing: dict,
    rel: RelationshipDefinition,
    espo_entity_foreign: str
) -> bool:
    """Return True if existing link matches spec."""
```

Compare:
- `existing["type"]` == `LINK_TYPE_TO_METADATA[rel.link_type]`
- `existing["entity"]` == `espo_entity_foreign`
- `existing.get("foreign")` == `rel.link_foreign`

If all match → True (skip). If any differ → False (warn, still skip).

### 3.6 Build Payload

```python
def _build_payload(self, rel: RelationshipDefinition) -> dict:
```

```python
{
    "entity": get_espo_entity_name(rel.entity),
    "entityForeign": get_espo_entity_name(rel.entity_foreign),
    "link": rel.link,
    "linkForeign": rel.link_foreign,
    "label": rel.label,
    "labelForeign": rel.label_foreign,
    "linkType": rel.link_type,
    "relationName": rel.relation_name,
    "linkMultipleField": False,
    "linkMultipleFieldForeign": False,
    "audited": rel.audited,
    "auditedForeign": rel.audited_foreign,
    "layout": None,
    "layoutForeign": None,
    "selectFilter": None,
    "selectFilterForeign": None,
}
```

### 3.7 Process

Main entry point:

```python
def process_relationships(
    self,
    relationships: list[RelationshipDefinition],
    dry_run: bool = False
) -> list[RelationshipResult]:
```

For each relationship:

1. If `rel.action == "skip"` → log SKIP with note "already exists (manual)",
   return SKIPPED result, continue
2. Check if link exists:
   - Exists and matches → log EXISTS, return SKIPPED
   - Exists but differs → log WARNING with details, return WARNING, continue
   - Does not exist → proceed to create
3. Create (unless dry_run):
   - POST payload to createLink
   - On success → proceed to verify
   - On failure → log error, return ERROR
4. Verify:
   - Re-fetch via check endpoint
   - Confirm type, entity, foreign match
   - Return CREATED + verified=True if OK
   - Return CREATED + verified=False if mismatch

### 3.8 Error Handling

- HTTP 401 → raise RelationshipManagerError (aborts run)
- HTTP 403 → log error, mark ERROR, continue
- HTTP 4xx/5xx → log error and response body, mark ERROR, continue
- Network error → log error, mark ERROR, continue

---

## Task 4 — Update `workers/run_worker.py`

After layout operations complete, process relationships:

```python
if program.relationships:
    relationship_results = rel_mgr.process_relationships(
        program.relationships,
        dry_run=self.dry_run
    )
    all_relationship_results.extend(relationship_results)
```

### Output messages

```
[RELATIONSHIP]  Session → Contact (mentorAttendees) ... CHECKING
[RELATIONSHIP]  Session → Contact (mentorAttendees) ... MISSING
[RELATIONSHIP]  Session → Contact (mentorAttendees) ... CREATING
[RELATIONSHIP]  Session → Contact (mentorAttendees) ... CREATED OK
[RELATIONSHIP]  Session → Contact (mentorAttendees) ... VERIFIED

[RELATIONSHIP]  Engagement → Account (assignedEngagement) ... SKIP (manual)
```

### Summary block

```
===========================================
RELATIONSHIP SUMMARY
===========================================
Total relationships processed : 11
  Created                     : 5
  Skipped (already exists)    : 6
  Failed                      : 0
===========================================
```

---

## Task 5 — Update `core/reporter.py`

Include relationship results in both `.log` and `.json` outputs.

JSON schema addition:
```json
{
  "relationship_results": [
    {
      "name": "sessionToMentorAttendees",
      "entity": "Session",
      "entity_foreign": "Contact",
      "link": "mentorAttendees",
      "status": "created",
      "verified": true,
      "message": null
    }
  ]
}
```

---

## Task 6 — Update Spec and Guides

### 6a — Update `PRDs/CBM-SPEC-espocrm-impl.md`

- Bump version to 1.6
- Add Section 11: Relationship Management (reference
  CBM-SPEC-relationship-management.md)
- Add `relationships` to the YAML top-level structure description
- Update Future Phases — move relationships from future to current

### 6b — Update `docs/technical-guide.md`

Add a "Relationship Manager" section covering:
- The two confirmed API endpoints (createLink and removeLink)
- The check endpoint (Metadata key pattern)
- The link type mapping table (YAML → Metadata)
- The `action: skip` pattern for pre-existing relationships
- Entity name resolution for both sides of a relationship

### 6c — Update `docs/user-guide.md`

Add a "Relationship Configuration" section to the "Writing YAML Program Files"
chapter covering:
- The `relationships` block structure
- `linkType` values and what they mean
- When to use `action: skip`
- The `relationName` requirement for manyToMany

---

## Task 7 — Add Tests

### `tests/test_relationship_manager.py`

- `_build_payload()` for oneToMany
- `_build_payload()` for manyToMany (with relationName)
- `_compare_link()` — matching link returns True
- `_compare_link()` — type mismatch returns False
- `_compare_link()` — entity mismatch returns False
- `action: skip` → SKIPPED immediately, no API call
- Existing matching link → SKIPPED
- Existing mismatched link → WARNING, no create attempted
- Missing link → create attempted
- HTTP 401 → raises RelationshipManagerError
- HTTP 403 → ERROR, continues
- Successful create → verify → CREATED + verified=True

### `tests/test_config_loader.py` additions

- `relationships` block parsed into `RelationshipDefinition` list
- `action: skip` parsed correctly
- `manyToMany` without `relationName` raises validation error
- Invalid `linkType` raises validation error
- Missing required fields raise validation errors

---

## Implementation Order

1. Task 1 — models.py
2. Task 2 — config_loader.py
3. Task 7 — config_loader tests (confirm passing)
4. Task 3 — relationship_manager.py
5. Task 7 — relationship_manager tests (confirm passing)
6. Task 4 — run_worker.py
7. Task 5 — reporter.py
8. Task 6 — spec and guide updates

Confirm with me after step 3 and after step 5 before proceeding.

---

## Important Notes

### get_espo_entity_name() refactoring
This prompt is a good opportunity to ensure `get_espo_entity_name()` is
defined in `core/entity_manager.py` and imported everywhere it's used
(relationship_manager, layout_manager, confirm_delete_dialog). If this
refactoring hasn't been done yet, do it now as part of this task.

### action: skip relationships
The 6 pre-existing CBM relationships use `action: skip`. This means the
tool logs them as skipped without making any API call — not even the check.
This is deliberate: these relationships were created manually and are known
to be correct. The check step is skipped to avoid unnecessary API calls.
The relationships are defined in YAML purely for documentation and
reproducibility purposes.

### Relationship file location
The CBM relationships are defined in a dedicated file:
`data/programs/cbm_relationships.yaml`

This file contains only a `relationships` block — no `entities` block.
The config_loader must handle YAML files that have `relationships` but
no `entities`, and vice versa.

### Processing order
Relationships must be processed after all entity creation, field
management, and layout management is complete. The run_worker must
ensure this ordering is respected. If an entity referenced in a
relationship does not exist (e.g. because entity creation failed),
log an error for that relationship and skip it rather than crashing.
