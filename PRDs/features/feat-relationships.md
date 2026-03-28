# CRM Builder — Relationship Management

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md, feat-entities.md

---

## 1. Purpose

This document defines the requirements for relationship management in
CRM Builder — the creation and verification of links between CRM
entities.

Relationships connect entities together, allowing CRM users to navigate
between related records, view related data within a record, and run
reports that span multiple entities. Defining relationships correctly
is essential for a well-functioning CRM data model.

---

## 2. What Is a Relationship

A relationship defines a navigable link between two entities. Each
relationship has:

- A **primary entity** — the entity the relationship is defined from
- A **foreign entity** — the entity the relationship connects to
- A **link type** — the cardinality of the relationship (one-to-many,
  many-to-one, many-to-many)
- **Link names** — the internal names of the link on each side
- **Labels** — the display names shown in the CRM UI on each side

When a relationship is created, the CRM adds a related records panel
to the detail view of both entities, allowing users to view and
navigate to related records from either side.

---

## 3. Link Types

CRM Builder supports three relationship types:

| Type | Meaning | Example |
|---|---|---|
| `oneToMany` | One record of the primary entity relates to many records of the foreign entity | One Engagement has many Sessions |
| `manyToOne` | Many records of the primary entity relate to one record of the foreign entity | Many Sessions belong to one Engagement |
| `manyToMany` | Many records on both sides relate to each other | Many Contacts can attend many Workshops |

`oneToMany` and `manyToOne` describe the same relationship from
opposite sides. A YAML file defines each relationship once, from
the perspective of the primary entity.

`manyToMany` relationships require a `relationName` property that
names the junction table used to store the association.

---

## 4. Relationship Definitions in YAML

Relationships are defined in a top-level `relationships` list,
separate from the `entities` block. This allows relationships that
span multiple entities to be defined once rather than on each side.

Each relationship requires:

| Property | Required | Description |
|---|---|---|
| `name` | yes | Identifier for this relationship. Used in reports and output |
| `description` | yes | Business rationale and PRD reference |
| `entity` | yes | Primary entity natural name |
| `entityForeign` | yes | Foreign entity natural name |
| `linkType` | yes | `oneToMany`, `manyToOne`, or `manyToMany` |
| `link` | yes | Link name on the primary entity |
| `linkForeign` | yes | Link name on the foreign entity |
| `label` | yes | Panel label shown on the primary entity's detail view |
| `labelForeign` | yes | Panel label shown on the foreign entity's detail view |
| `relationName` | manyToMany only | Junction table name |
| `audited` | no | Track changes in audit log on primary side. Default: false |
| `auditedForeign` | no | Track changes in audit log on foreign side. Default: false |
| `action` | no | `skip` to document without deploying. Default: deploy |

Entity names use natural names without any platform-specific prefix.
The tool applies prefix transformations at deployment time.

---

## 5. Relationship Operations

### 5.1 The Check → Act Cycle

Each relationship defined in the YAML is processed through a two-step
cycle during a Run:

**Check** — the current state of the link is read from the CRM
instance. If the link does not exist, processing moves to Create.
If it exists, the existing link is compared to the spec.

**Act** — if the link does not exist, it is created. If it exists
and matches the spec, it is skipped. If it exists but differs from
the spec, it is logged as a warning and skipped — relationships
cannot be updated via the CRM API (see Section 5.3).

### 5.2 Create

When a relationship does not exist on the CRM instance, it is created
with all properties specified in the YAML definition.

After creating any relationship, a cache rebuild is recommended before
subsequent operations that depend on the new link.

### 5.3 No Update Support

Relationships cannot be updated via the CRM API. If an existing
relationship differs from the spec, CRM Builder logs a warning and
skips it. The warning message advises the user to manually correct
the relationship or delete and recreate it.

This is a known platform constraint, not a CRM Builder limitation.

### 5.4 The `action: skip` Pattern

A relationship with `action: skip` is documented in the YAML but no
API calls are made — not even the check step. This is used for
relationships that were created manually on the CRM instance before
the YAML file was written.

Including skipped relationships ensures full reproducibility: if the
instance were rebuilt from scratch, all relationships (including
previously manual ones) would be created by the tool.

---

## 6. Relationship Description Requirement

Every relationship definition must include a `description` property.
The description must explain:

- The business purpose of the relationship
- Why the two entities are connected
- A reference to the PRD section that defines it

This is a validation requirement. Program files with relationship
definitions missing a description will fail validation and cannot
be run.

---

## 7. Processing Order

Relationships are processed after all entity, field, and layout
operations have completed. This ensures all referenced entities
exist before any relationship between them is attempted.

Within the relationships list, relationships are processed in
definition order. If a relationship fails because a referenced
entity does not exist, the error is logged and processing
continues with the next relationship.

---

## 8. Output and Reporting

### 8.1 Output Panel Messages

Relationship operations emit messages to the output panel following
the conventions in `app-ui-patterns.md`:

```
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... CHECKING
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... EXISTS
[RELATIONSHIP]  Session → Engagement (sessionEngagement) ... SKIPPED (no changes needed)

[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CHECKING
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... NOT FOUND
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CREATING
[RELATIONSHIP]  NpsSurveyResponse → Engagement (engagement) ... CREATED OK

[RELATIONSHIP]  Dues → Contact (mentor) ... CHECKING
[RELATIONSHIP]  Dues → Contact (mentor) ... EXISTS BUT DIFFERS
[RELATIONSHIP]  Dues → Contact (mentor) ... WARNING (cannot update — manual correction required)

[RELATIONSHIP]  WorkshopAttendance → Contact (contact) ... SKIP (action: skip)
```

### 8.2 Summary Block

```
===========================================
RELATIONSHIP SUMMARY
===========================================
Total relationships processed :  11
  Created                     :   5
  Skipped (exists, matches)   :   4
  Skipped (action: skip)      :   1
  Warnings (exists, differs)  :   1
  Errors                      :   0
===========================================
```

### 8.3 Report Status Values

Relationship results use the following status values in the JSON
report:

| Status | Meaning |
|---|---|
| `created` | Relationship did not exist and was successfully created |
| `skipped` | Relationship exists and matches spec — no change needed |
| `skipped_action` | Relationship has `action: skip` — no API calls made |
| `warning` | Relationship exists but differs from spec — manual correction required |
| `error` | Operation failed due to an API or network error |

---

## 9. Error Handling

Relationship-level errors follow the continue-and-log pattern defined
in `app-logging-reporting.md`. An error on one relationship does not
stop processing of subsequent relationships.

The one exception is an authentication failure (HTTP 401), which
aborts the entire run immediately.

---

## 10. Validation Rules

The following rules are checked during Validate before any API calls
are made:

- Every relationship must have all required properties (Section 4)
- `manyToMany` relationships must include `relationName`
- `linkType` must be one of: `oneToMany`, `manyToOne`, `manyToMany`
- `description` is required on every relationship definition
- `action`, if specified, must be `skip`

Validation failures are reported individually and prevent the Run
action from proceeding.

---

## 11. Future Considerations

- **Relationship deletion** — removing a relationship that exists on
  the CRM instance is not currently part of the standard run workflow.
  A future phase may add a `delete` action for relationships, with
  the same destructive confirmation requirements as entity deletion.
- **Relationship update** — if a future CRM platform version supports
  updating existing relationships via API, CRM Builder will add update
  support following the same check/compare/act pattern used for fields.
- **Additional link properties** — properties such as `linkMultipleField`
  and select filters are not currently exposed in the YAML schema.
  These may be added as needed for specific platform requirements.
