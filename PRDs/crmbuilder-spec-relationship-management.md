# CBM EspoCRM Relationship Management — Technical Specification

**Version:** 1.0  
**Status:** Draft  
**Scope:** Phase 4 — Relationship Management  
**Parent spec:** crmbuilder-spec-espocrm-impl.md (v1.5)

---

## 1. Overview

Relationships define the links between EspoCRM entities. The implementation
tool manages relationships declaratively via the `relationships` block in YAML
program files, using the same check/act/verify pattern as fields and layouts.

---

## 2. Confirmed API Endpoints

All endpoints confirmed via network traffic observation on EspoCRM v9.3.3.

### 2.1 Check (Read)

```
GET /api/v1/Metadata?key=entityDefs.{EspoEntityName}.links.{linkName}
```

Returns the link object if it exists, null/empty if not. Uses the EspoCRM
internal entity name (C-prefixed for custom entities).

Example:
```
GET /api/v1/Metadata?key=entityDefs.CEngagement.links.assignedMentor
```

Returns:
```json
{
  "type": "belongsTo",
  "entity": "Contact",
  "foreign": "cEngagements",
  "audited": false,
  "isCustom": true
}
```

### 2.2 Create

```
POST /api/v1/EntityManager/action/createLink
```

Confirmed payload structure:
```json
{
  "entity": "CEngagement",
  "entityForeign": "Call",
  "link": "calls1",
  "linkForeign": "engagement",
  "label": "Calls1",
  "labelForeign": "Engagement",
  "linkType": "oneToMany",
  "relationName": null,
  "linkMultipleField": false,
  "linkMultipleFieldForeign": false,
  "audited": false,
  "auditedForeign": false,
  "layout": null,
  "layoutForeign": null,
  "selectFilter": null,
  "selectFilterForeign": null
}
```

### 2.3 Delete

```
POST /api/v1/EntityManager/action/removeLink
```

Payload:
```json
{
  "entity": "Account",
  "link": "linkName"
}
```

---

## 3. Link Type Mapping

The `createLink` API uses a different type vocabulary than the Metadata API.

| YAML linkType | API linkType | Primary side (Metadata) | Foreign side (Metadata) |
|---|---|---|---|
| `oneToMany` | `oneToMany` | `hasMany` | `belongsTo` |
| `manyToOne` | `manyToOne` | `belongsTo` | `hasMany` |
| `manyToMany` | `manyToMany` | `hasMany` | `hasMany` |

**Note:** `manyToOne` and `oneToMany` describe the same relationship from
opposite sides. The YAML always defines a relationship from the perspective
of the primary entity. `manyToOne` means: many records of the primary entity
belong to one record of the foreign entity.

---

## 4. YAML Schema

Relationships are defined in a top-level `relationships` list, separate from
the `entities` block. This allows relationships that span multiple entities to
be defined once rather than on each side.

### 4.1 Top-Level Structure

```yaml
version: "1.0"
description: "CBM EspoCRM Configuration — Relationships"

relationships:
  - name: sessionEngagement
    description: "..."
    entity: Session
    entityForeign: Engagement
    linkType: manyToOne
    link: sessionEngagement
    linkForeign: engagementSessionses
    label: "Engagement"
    labelForeign: "Sessions"
    audited: false
```

### 4.2 Relationship Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Identifier for this relationship (used in reports) |
| `description` | string | yes | Business rationale and PRD reference |
| `entity` | string | yes | Primary entity (natural name, e.g. `Session`) |
| `entityForeign` | string | yes | Foreign entity (natural name, e.g. `Engagement`) |
| `linkType` | string | yes | `oneToMany`, `manyToOne`, or `manyToMany` |
| `link` | string | yes | Link name on the primary entity |
| `linkForeign` | string | yes | Link name on the foreign entity |
| `label` | string | yes | Panel label on the primary entity's detail view |
| `labelForeign` | string | yes | Panel label on the foreign entity's detail view |
| `relationName` | string | no | Junction table name (manyToMany only) |
| `audited` | boolean | no | Default: false |
| `auditedForeign` | boolean | no | Default: false |
| `action` | string | no | `skip` to record but not deploy. Default: deploy |

### 4.3 Entity Name Resolution

As with fields and layouts, relationship API calls use the EspoCRM internal
entity name. Apply the same `get_espo_entity_name()` mapping:

| Natural name | EspoCRM name |
|---|---|
| `Engagement` | `CEngagement` |
| `Session` | `CSessions` |
| `NpsSurveyResponse` | `CNpsSurveyResponse` |
| `Workshop` | `CWorkshops` |
| `WorkshopAttendance` | `CWorkshopAttendee` |
| `Dues` | `CDues` |
| `Contact` | `Contact` |
| `Account` | `Account` |

---

## 5. Check / Act / Verify Logic

### 5.1 Check

For each relationship defined in the YAML:

1. Fetch `GET /api/v1/Metadata?key=entityDefs.{EspoEntity}.links.{link}`
2. If the response is null or empty → relationship does not exist → ACT
3. If the response contains a link object:
   - Compare `type` (mapped from linkType)
   - Compare `entity` (foreign entity name)
   - Compare `foreign` (linkForeign name)
   - If all match → SKIP (already correct)
   - If any differ → log WARNING and SKIP (do not attempt to update)

**Note:** Relationships cannot be updated via API — only created or deleted.
If a relationship exists but differs from the spec, log a WARNING advising
manual correction and skip. Do not delete and recreate automatically.

### 5.2 Act

POST to `/api/v1/EntityManager/action/createLink` with the full payload
built from the YAML relationship definition.

**Payload construction:**

```python
{
    "entity": get_espo_entity_name(rel.entity),
    "entityForeign": get_espo_entity_name(rel.entity_foreign),
    "link": rel.link,
    "linkForeign": rel.link_foreign,
    "label": rel.label,
    "labelForeign": rel.label_foreign,
    "linkType": rel.link_type,          # "oneToMany", "manyToOne", "manyToMany"
    "relationName": rel.relation_name,  # None unless manyToMany
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

### 5.3 Verify

After creation, re-fetch the link via the check endpoint and confirm:
- `type` matches (using the type mapping table)
- `entity` matches (foreign entity name)
- `foreign` matches (linkForeign name)

### 5.4 Already-Existing Relationships

The 6 relationships already manually created on CBM's EspoCRM instance are
included in the YAML with their exact existing link names. The check step
will find them and skip creation. This ensures full reproducibility — if
the instance were rebuilt from scratch, all relationships would be created.

---

## 6. Processing Order

Process relationships after all entity and field operations are complete,
and after layouts have been applied. This ensures all entities exist before
any relationship between them is attempted.

Within the relationships list, process in definition order. If a
relationship fails (e.g. entity does not exist), log the error and continue.

---

## 7. Output Messages

```
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... CHECKING
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... EXISTS
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... NO CHANGES NEEDED

[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CHECKING
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... MISSING
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CREATING
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CREATED OK
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... VERIFIED
```

---

## 8. Summary Block

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

## 9. Error Handling

Follow the same pattern as field_manager.py:
- HTTP 401 → raise RelationshipManagerError (aborts run)
- HTTP 403 → log error, mark as ERROR, continue
- HTTP 4xx/5xx → log error and response body, mark as ERROR, continue
- Relationship exists but differs → WARNING, skip (do not attempt update)
- Entity referenced in relationship not found → ERROR, skip this relationship

---

## 10. Data Models

```python
@dataclass
class RelationshipDefinition:
    name: str
    description: str | None
    entity: str                  # natural name
    entity_foreign: str          # natural name
    link_type: str               # oneToMany, manyToOne, manyToMany
    link: str                    # link name on primary entity
    link_foreign: str            # link name on foreign entity
    label: str
    label_foreign: str
    relation_name: str | None = None   # manyToMany junction table
    audited: bool = False
    audited_foreign: bool = False
    action: str | None = None    # None = deploy, "skip" = record only


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

---

## 11. CBM Relationship Inventory

Complete list of all 11 CBM relationships. The first 6 already exist;
the final 5 are to be created by the tool.

| # | Primary Entity | Foreign Entity | Type | Link | Link Foreign | Status |
|---|---|---|---|---|---|---|
| 1 | Engagement | Account | manyToOne | assignedEngagement | cCompanyRequestionHelp | Exists |
| 2 | Engagement | Contact | manyToOne | assignedMentor | cEngagements | Exists |
| 3 | Engagement | Contact | manyToMany | contacts | cEngagementContacts | Exists |
| 4 | Engagement | Contact | manyToMany | cBMContacts | cCoMentorEngagements | Exists |
| 5 | Engagement | Session | oneToMany | engagementSessionses | sessionEngagement | Exists |
| 6 | Workshop | WorkshopAttendance | oneToMany | workshopAttendees | workshopAttended | Exists |
| 7 | NpsSurveyResponse | Engagement | manyToOne | engagement | npsSurveyResponses | To create |
| 8 | WorkshopAttendance | Contact | manyToOne | contact | workshopAttendances | To create |
| 9 | WorkshopAttendance | Engagement | manyToOne | engagement | workshopAttendances | To create |
| 10 | Dues | Contact | manyToOne | mentor | duesRecords | To create |
| 11 | Session | Contact | manyToMany | mentorAttendees | attendedSessions | To create |

**Note on #8 and #9:** Both use `workshopAttendances` as the foreign link name,
but on different entities (Contact and Engagement respectively). No collision.
